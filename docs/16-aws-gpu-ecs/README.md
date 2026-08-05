# GPU embedding and generation on ECS

This page explains the final architecture and operating model. The complete
chronological record—including every failed deployment, its evidence, the fix,
the security incident, and the exact current AWS inventory—is in
[migration-log.md](migration-log.md).

## Pipeline position

This deployment changes the two model-execution stages. It does not fetch the
corpus, recreate chunks, or rebuild the OpenSearch index.

```text
Question
  -> [Embed: BGE-M3 / TEI / T4]
  -> [Search: OpenSearch dense + BM25 -> RRF]
  -> [Generate: Gemma / vLLM / L4]
  -> cited answer
```

The application still uses `TEIEmbedder` in `docsmind/index/embeddings.py` and
`VLLMClient` in `docsmind/llm/vllm_client.py`. Moving the model servers changes
their endpoints and hardware, not the application interfaces.

## Why there are two GPU services

The original standalone `g6.xlarge` ran Gemma through vLLM with
`--gpu-memory-utilization 0.95`. Live `nvidia-smi` evidence showed approximately
21.7 GiB used out of the L4's 23 GiB, leaving about 850 MiB free. BGE-M3 could
not safely fit in that remainder.

ECS schedules physical GPUs as integer resources. Two containers cannot each
reserve a fraction of the same single L4. Combining two unrelated servers into
one custom container would hide their health, deployment, and scaling
boundaries. The production-shaped design therefore keeps them separate:

| ECS service | Pipeline stage | Capacity provider | GPU |
|---|---|---|---|
| `docsmind-app-embedding-gpu` | Query embedding plus FastAPI/UI | `docsmind-embedding-gpu-dev` | `g4dn.xlarge`, one T4 |
| `docsmind-vllm-gpu` | Answer generation | `docsmind-vllm-gpu-dev` | `g6.xlarge` preferred; `g6e.xlarge`/`g5.xlarge` fallback |

The T4 is the cheaper GPU that comfortably fits BGE-M3. A separate generation
GPU remains dedicated to the 12B quantized model and its KV cache; the preferred
host is an L4, while the current capacity fallback is an A10G. This lets
ingestion/query embedding and generation scale independently in a later
production profile.

The generation Auto Scaling Group prefers `g6.xlarge` and can fall back to
`g6e.xlarge` or `g5.xlarge` when L4 capacity is unavailable. The L40S is also
Ada; the A10G is an Ampere fallback with approximately the same VRAM as the L4.
All three provide one compatible physical GPU and stay within the same
four-vCPU GPU quota unit. The fallbacks cost more per hour, so they are
availability options rather than the steady-state development choice. Every
benchmark must record the instance and GPU actually placed by ECS.

In an interview, the real question is not “did you put both models on GPU?” It
is: “what did GPU memory measurements and scheduler constraints force you to
separate, and how did that affect cost and failure isolation?”

## Infrastructure

`infra/aws/gpu-ecs.yaml` creates one ECS cluster with two Auto Scaling Group
capacity providers:

```text
Internet (restricted workstation /32)
  -> public ALB
  -> g4dn ECS task (provisioned, currently scaled to zero)
       ├── FastAPI/UI
       └── TEI + BGE-M3 on T4
            -> OpenSearch Serverless
            -> internal ALB
                 -> generation ECS task (currently g5.xlarge)
                      └── vLLM + Gemma on A10G
```

Security groups permit only these paths:

- Workstation CIDR -> public ALB port 80
- Public ALB -> application host port 8000
- Application host -> internal vLLM ALB port 80
- Internal vLLM ALB -> generation host port 8000

Both ALBs enable every compatible default subnet. The GPU Auto Scaling Groups
can therefore select an Availability Zone with live accelerator capacity
without producing a healthy container that the load balancer cannot route to.
Target deregistration uses a 30-second drain window. The five-minute ALB default
needlessly held the only physical GPU during single-instance task replacement.

TEI's host port 8080 is not open. vLLM has no public endpoint. Both the app and
vLLM receive the existing bearer token from Secrets Manager at task start. The
application task role retains read-only OpenSearch data-policy permissions.

Both launch templates use the current ECS GPU-optimized AMI resolved from AWS
Systems Manager. User data enables ECS GPU support. The task definitions reserve
one physical GPU explicitly, so ECS will not place them on a non-GPU host.

## Reproducible model contracts

The model artifacts are immutable deployment inputs:

- BGE-M3 revision:
  `5617a9f61b028005a4858fdac845db406aefb181`
- TEI Turing image index digest:
  `sha256:dee4a1493f54fbfd444c6e02bc95bfecaa22b9430c3655fb1d018a22ea991473`
- vLLM Gemma image digest:
  `sha256:0ea4b07a909f78a5cc8a6a82e9d3dd3efa51b59a0f5421fcf2207e80a3aae53b`

The bearer token is injected only as `VLLM_API_KEY`. It is not passed through
`--api-key`, because vLLM includes non-default CLI arguments in startup logs.
Environment-only configuration keeps the secret out of the command line and
CloudWatch output.

The mixed-instance generation profile uses BF16 KV cache because the A10G
fallback is compute capability 8.6 and cannot run vLLM's native FP8 Triton KV
cache. An L4-only benchmark profile can explicitly select FP8 after capacity is
pinned to SM89 hardware.

The vLLM container health check uses `curl`, which is present in the image. The
first ECS revision incorrectly used the nonexistent `python` alias even though
the image provides `python3`; vLLM served traffic, but Docker health remained
unhealthy until the executable mismatch was corrected.

The GPU TEI profile uses FP16, CLS pooling, an 8,192-token batch envelope, 32
concurrent requests, and a maximum client batch of 32. These are serving limits,
not chunk settings. The stored Wikipedia chunks remain 512 tokens with a
64-token overlap, and the vector dimension remains 1,024.

Changing CPU FP32 query embedding to GPU FP16 does not change the model or vector
dimension, so the existing BGE-M3 index remains compatible. Retrieval evaluation
should still measure whether small numerical differences alter ranking before a
production sign-off.

## Scale to zero

Each service has its own zero-to-one Auto Scaling Group. The operational order
is important:

```text
Start: GPU host -> ECS task -> model health -> load-balancer target
Stop: ECS desired count 0 -> task stops -> ASG desired capacity 0
```

Use:

```bash
AWS_PROFILE=ml-prep-deploy make aws-gpu-quota
AWS_PROFILE=ml-prep-deploy make aws-gpu-deploy
AWS_PROFILE=ml-prep-deploy make aws-gpu-start
AWS_PROFILE=ml-prep-deploy make aws-gpu-status
AWS_PROFILE=ml-prep-deploy make aws-gpu-logs
AWS_PROFILE=ml-prep-deploy make aws-gpu-stop
```

Scale-to-zero removes EC2 GPU compute charges. The two ALBs, ECR images,
CloudWatch logs, and other retained control-plane/storage resources still have
small costs. A zero-capacity service also cannot wake directly from an ALB
request; an operator, schedule, or separate wake-up control plane must set the
service desired counts to one.

Cold starts include launching the instances, pulling approximately 17 GB of
vLLM image data, downloading BGE-M3 after a fresh embedding host, warming both
models, and passing load-balancer health thresholds. Root volumes are encrypted
and deleted with the instances, so caches do not survive a full scale-to-zero
cycle.

## Verified deployment state — 2026-08-06

The migration is intentionally partial because the account cannot run two
four-vCPU GPU instances simultaneously:

| Resource | Verified state |
|---|---|
| CloudFormation stack `docsmind-gpu-dev` | `UPDATE_COMPLETE` |
| ECS generation service `docsmind-vllm-gpu` | desired `1`, running `1`, task definition revision `5` |
| Generation host | `g5.xlarge` / A10G in `us-east-1f` |
| Internal vLLM target | Healthy |
| ECS GPU embedding service | Created, desired `0`, running `0` |
| Existing CPU BGE-M3 service | Still active on `m7i.large` |
| Original standalone generator | `g6.xlarge`, stopped and preserved |
| Hosted query path | CPU BGE-M3 -> OpenSearch -> ECS GPU vLLM; verified end to end |

The live query “What platform does the Golf Mk7 use?” returned “The Golf Mk7
uses the MQB platform” with three citations. `/health` reported the existing
1,776-chunk hybrid index. This verifies the generation cutover; it does **not**
verify the GPU embedding service.

The account's `Running On-Demand G and VT instances` quota remains four vCPUs.
The running `g5.xlarge` consumes all four. Generation plus a `g4dn.xlarge`
embedding host requires eight. Twelve was requested to permit temporary
cutover headroom; the request remains `CASE_OPENED`.

No re-ingestion is needed merely to move BGE-M3 from CPU FP32 to GPU FP16. The
model revision, CLS pooling, 1,024-dimensional vector contract, chunk IDs, and
OpenSearch index remain the same. After quota approval, the remaining gate is:

1. Start only the GPU embedding host and service.
2. Verify TEI identity, health, and a normalized 1,024-dimensional vector.
3. Run the same labeled retrieval evaluation to detect FP16 ranking changes.
4. Cut the hosted application from CPU TEI to GPU TEI.
5. Verify `/health` and a cited `/query` response.
6. Scale the old CPU embedding stack to zero only after the checks pass.

The quota hurdle is an account-level placement constraint, not a model or
container failure. Approval alone is not evidence: simultaneous healthy task
placement is the acceptance test.
