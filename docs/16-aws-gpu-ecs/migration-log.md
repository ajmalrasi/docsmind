# AWS GPU ECS migration: complete engineering log

## Purpose and scope

This is the detailed record of the 2026-08-06 migration from a standalone GPU
EC2 model server toward independently scalable ECS services for generation and
embedding. It records what was changed, where it runs, why each choice was
made, what failed, how the failure was diagnosed, what fixed it, what was
actually verified, and what remains incomplete.

This work did **not** fetch or parse corpus data, recreate chunks, run ingestion,
or replace the OpenSearch index. The existing Volkswagen Wikipedia index stayed
online throughout. The work changed model-serving infrastructure and the
application's generation endpoint.

Secrets are deliberately excluded. Resource names, instance IDs, task revisions,
and non-secret internal endpoints are retained as an auditable development
record.

## Pipeline position

The full path is:

```text
Ingest -> Chunk -> Embed documents -> Index
                                  OpenSearch Serverless

Question -> Embed query -> Dense + BM25 -> RRF -> Generate -> Cite
               |                                |
         BGE-M3 / TEI                    Gemma / vLLM
         CPU today                       ECS GPU today
         GPU prepared
```

Two stages execute neural models:

1. **Embed** converts each stored chunk and each new question into a
   1,024-dimensional BGE-M3 vector.
2. **Generate** gives retrieved chunks to Gemma through vLLM and produces the
   cited answer.

The migration separated those stages so each can use appropriate hardware,
health checks, deployments, and scaling. It did not change the interfaces used
by `TEIEmbedder` or `VLLMClient`.

## Starting state

Before this work, AWS had two separate runtime paths:

| Function | Runtime | State before migration |
|---|---|---|
| BGE-M3 embeddings | ECS on `m7i.large`, CPU TEI 1.9.3 | Running |
| DocsMind FastAPI/UI | Sidecar beside CPU TEI | Running |
| Gemma generation | Standalone `g6.xlarge` EC2 | Running |
| Vector search | OpenSearch Serverless | 1,776 indexed chunks |

The standalone generator was instance `i-0d7385b600fd36704`, a `g6.xlarge` in
`us-east-1c` with one NVIDIA L4. It served the OpenAI-compatible model alias
`openclaw` from a custom vLLM/Gemma container.

The embedding/application host was `i-01bc35981c55f2ac3`, an `m7i.large` in
`us-east-1a`. It ran BGE-M3 on CPU and the hosted application. That service was
kept because GPU embedding could not yet be placed under the account quota.

## Requested outcome

The requested architecture was:

- move the standalone vLLM server into ECS;
- move BGE-M3 from CPU to GPU;
- allow each expensive GPU service to scale to zero;
- retain the existing OpenSearch corpus and application behavior;
- use CPU during development where sensible, then make the GPU profile ready
  for later tests and benchmarks;
- avoid Kubernetes unless the workload justified its extra control plane.

The operational boundary was infrastructure and application integration. A new
bulk ingestion and benchmark run was not part of this migration.

## Measurements and constraints before implementation

### One L4 could not safely host both models

The existing vLLM process used approximately 21.7 GiB of the L4's 23 GiB of
usable memory, leaving about 850 MiB. Its configured GPU memory utilization was
0.95. BGE-M3 plus TEI could not safely fit into the remainder.

That measurement ruled out “put both containers on the existing GPU.” A model
loading once is not sufficient capacity evidence; peak inference allocations,
vLLM's KV cache, CUDA context memory, and safe headroom also matter.

### ECS does not provide fractional GPU reservations here

ECS GPU task definitions reserve physical GPUs with an integer
`ResourceRequirements` value. With one GPU on the host, one task can reserve
`GPU: 1`; two independent tasks cannot each reserve half.

Putting both servers into one hand-managed container was rejected because it
would combine their deployment lifecycle, health, logs, failure domain, and
scaling. Two services make those boundaries explicit.

### Why ECS on EC2, not ECS Fargate or Kubernetes

The GPU workloads require ECS on EC2 capacity. The EC2 hosts supply NVIDIA GPUs
and use the ECS GPU-optimized AMI. ECS manages task placement, revisions,
health, recovery, logs, and service desired count; Auto Scaling Groups manage
the host lifecycle.

Kubernetes would add a cluster control plane, node/device plugin operation, and
more scheduling machinery without solving a problem that two ECS services could
not solve. Kubernetes becomes useful with more teams, more model services,
multi-node scheduling, portability requirements, or complex autoscaling. It was
not the smallest production-shaped solution for this development system.

### GPU quota was the hard account constraint

AWS service quota `L-DB2E81BA`, **Running On-Demand G and VT instances**, was
4 vCPUs. Each relevant xlarge GPU instance consumes 4 vCPUs:

```text
one generation GPU                    = 4 vCPUs
one embedding GPU                     = 4 vCPUs
both final GPU services               = 8 vCPUs
old generator + both new GPU services = 12 vCPUs during no-downtime cutover
```

A quota increase to 12 was requested. Request ID:
`aece8076239841baa590b087eb64b713biGhUepe`. At the 2026-08-06 snapshot it was
`CASE_OPENED`; the effective quota was still 4. AWS Premium Support escalation
was unavailable because the account did not have the required support
subscription. GPU Spot quota was also unusable: quota `L-3819A6DF` was zero.

The important distinction is that an open quota case does not provide capacity.
Only the effective quota returned by Service Quotas controls placement.

## Final infrastructure design

### Resource topology

`infra/aws/gpu-ecs.yaml` defines:

- CloudFormation stack `docsmind-gpu-dev`;
- ECS cluster `docsmind-gpu-dev`;
- one embedding Auto Scaling Group and ECS capacity provider;
- one generation Auto Scaling Group and ECS capacity provider;
- one public, IP-restricted ALB for the application;
- one internal ALB for vLLM;
- task execution, application task, and container-instance IAM roles;
- separate log groups for TEI, the application, and vLLM;
- security groups that permit only the intended service-to-service paths.

The network path is:

```text
workstation /32
  -> public ALB:80
  -> application host:8000
       -> local TEI:80 inside the embedding task
       -> OpenSearch Serverless over AWS APIs
       -> internal vLLM ALB:80
            -> generation host:8000
```

TEI host port 8080 has no inbound rule. The vLLM host accepts port 8000 only
from the internal ALB security group. The internal ALB accepts port 80 only
from the application-host security group.

### Embedding service contract

The prepared service is `docsmind-app-embedding-gpu`, backed by ASG and capacity
provider `docsmind-embedding-gpu-dev`.

| Setting | Value |
|---|---|
| Instance | `g4dn.xlarge`, one NVIDIA T4 |
| Host root volume | 80 GiB encrypted gp3, deleted on termination |
| TEI image | digest `sha256:dee4a1493f54fbfd444c6e02bc95bfecaa22b9430c3655fb1d018a22ea991473` |
| Model | `BAAI/bge-m3` |
| Model revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| Dtype and pooling | FP16, CLS |
| Vector dimension | 1,024 |
| TEI max batch tokens | 8,192 |
| Concurrent requests | 32 |
| Client batch size | 32 |
| GPU reservation | one physical GPU |
| Current desired/running | 0/0 |

The task contains two containers. TEI owns the GPU. The DocsMind application
starts only after TEI becomes healthy, talks to it through the task-local link,
queries OpenSearch, and calls the internal vLLM load balancer. The application
image tag is resolved from ECR during deployment; the helper currently defaults
to the already-built `a9aa044cb5e2` tag.

The embedding ASG has minimum 0, maximum 1, and desired capacity 0. Its model
cache is a host directory on the ephemeral EC2 root volume. Therefore a full
scale-to-zero deletes the cache and the next start downloads the model again.

### Generation service contract

The running service is `docsmind-vllm-gpu`, backed by ASG and capacity provider
`docsmind-vllm-gpu-dev`.

| Setting | Value |
|---|---|
| Preferred instance | `g6.xlarge`, one NVIDIA L4 |
| Fallbacks | `g6e.xlarge`, then `g5.xlarge` |
| Actual placed instance | `g5.xlarge`, one NVIDIA A10G |
| Host root volume | 250 GiB encrypted gp3, deleted on termination |
| Image | digest `sha256:0ea4b07a909f78a5cc8a6a82e9d3dd3efa51b59a0f5421fcf2207e80a3aae53b` |
| Model path | `/models/gemma-4-12b-w4a16` |
| Served alias | `openclaw` |
| Quantization | `compressed-tensors`, W4A16 model |
| Model dtype | automatic |
| KV-cache dtype | BF16 |
| Maximum model length | 16,384 tokens |
| GPU memory utilization | 0.95 |
| Maximum sequences | 4 |
| Execution mode | eager |
| GPU reservation | one physical GPU |
| Current desired/running | 1/1 |

The mixed-instance ASG uses prioritized On-Demand allocation. `g6.xlarge` is
preferred for cost/performance, while the fallbacks prevent one unavailable
instance family from blocking the development deployment. Every benchmark must
record the GPU actually placed; an A10G result must not be labeled an L4 result.

### Immutable inputs

Both model revisions and container images are pinned. Tags such as `latest`
could silently change CUDA libraries, server behavior, kernels, or model
weights between deployments. Digests and a Hugging Face commit make a later
benchmark reproducible.

### Host configuration

Both launch templates use the current Amazon Linux 2 ECS GPU-optimized AMI from
the SSM public parameter. User data sets:

```text
ECS_ENABLE_GPU_SUPPORT=true
ECS_ENABLE_TASK_IAM_ROLE=true
```

Instance Metadata Service v2 is required. EBS volumes are encrypted. ECS
managed draining is enabled so capacity-provider scale-in stops tasks through
the scheduler rather than abruptly killing a live container.

### Scale-to-zero semantics

Stopping a service is a two-step operation:

1. set ECS desired count to zero and wait for tasks to stop;
2. set the backing ASG desired capacity to zero.

Doing this in the opposite order can terminate a host underneath a running
task. Starting reverses the dependency: create the host first, then request the
task.

Scale-to-zero removes GPU EC2 compute charges. It does not remove ALB hourly and
LCU charges, ECR storage, CloudWatch logs, or other retained resources. An ALB
request cannot wake a zero-host ECS service by itself; an operator, schedule, or
wake-up controller must change desired capacity.

## Chronological implementation and troubleshooting record

### 1. Audited the standalone generator

The first action was read-only inspection of the existing `g6.xlarge` and its
container. `nvidia-smi` showed vLLM using approximately 21.7 GiB of the L4's
23 GiB. The service was already near its configured 0.95 memory fraction.

**Why:** this determined whether the cheapest change—adding TEI to the same
host—was technically safe. It was not.

### 2. Chose two independently scalable ECS services

Generation and embedding were assigned separate ASGs and ECS capacity
providers. The planned embedding host was `g4dn.xlarge`; the planned generator
was `g6.xlarge`.

**Why:** embedding has small latency-sensitive online calls plus occasional
bulk throughput work. Generation has a large resident model and KV cache. They
need different scaling and benchmarking, and one failure should not directly
kill the other process.

### 3. Built scale-to-zero infrastructure before consuming GPU capacity

The CloudFormation template, deployment helper, and Make targets were created.
The stack was initially deployed with both service desired counts and both ASG
desired capacities at zero.

**Why:** IAM, networking, load balancers, task definitions, and capacity
providers can be provisioned without paying for two idle GPUs. It also exposes
template errors separately from runtime/model errors.

### 4. Checked quota and requested twelve vCPUs

Service Quotas returned an effective limit of four. Twelve was requested to
allow old generation, new generation, and new embedding to overlap during a
safe cutover.

The quota prevented the final two-GPU state. A staged generator-only migration
was still possible if the old GPU released its four vCPUs first.

### 5. Stopped, but did not delete, the old generator

The original `g6.xlarge` was stopped to free the only four GPU vCPUs. It stayed
in `stopping` longer than the graceful wait. After confirming the exact target,
the stop was completed with the EC2 force/skip-OS-shutdown options.

**Why preserve it:** termination would delete the easiest rollback target. The
old root volume and instance configuration were retained. No corpus or vector
data lived on this host; it was only a model server.

### 6. Encountered zonal accelerator-capacity failures

Initial Auto Scaling attempts for `g6.xlarge` could not obtain capacity in the
available zone. Expanding the ASG to more compatible default subnets helped the
scheduler search more zones. A `g6e.xlarge` fallback was also attempted and hit
capacity constraints.

The generation ASG was changed to a prioritized mixed-instance policy:

```text
g6.xlarge -> g6e.xlarge -> g5.xlarge
```

AWS successfully launched `g5.xlarge` instance `i-0ea5b546a22c79b72` in
`us-east-1f`.

**Root cause:** regional product availability does not guarantee immediate
On-Demand capacity in every Availability Zone. The ECS task and model were not
the cause.

### 7. Fixed an ALB Availability Zone mismatch

The new task ran in `us-east-1f`, but the internal ALB initially enabled only
subnets in other zones. Target health reported `unused` with reason
`Target.NotInUse` even though the container itself was running.

Both ALBs were changed to use all compatible default VPC subnets. The GPU ASGs
still use only subnets where their configured instance types are offered.

**Why this worked:** an ALB can route to a registered instance target only when
the target's Availability Zone is enabled on that load balancer. Security-group
and application debugging would not fix `Target.NotInUse`.

### 8. Fixed unsupported FP8 KV cache on the A10G fallback

The original L4 profile requested FP8 KV cache. vLLM rejected it on the A10G:

```text
compute capability 8.6; native FP8 KV cache requires SM89 or newer
```

The mixed-hardware default was changed to `bfloat16`.

**Why:** the A10G is Ampere/SM86, while the L4 is Ada/SM89. A fallback is not
valid merely because it has similar VRAM; the configured kernels and data types
must also be supported. An L4-only benchmark can explicitly restore FP8 after
pinning placement to compatible hardware.

### 9. Found and contained an API-key exposure in startup logs

An early task passed the bearer token using vLLM's `--api-key` CLI argument.
vLLM prints non-default startup arguments, so the token appeared in its
CloudWatch startup stream.

Immediate containment actions were:

1. rotate Secrets Manager secret `docsmind/vllm-api-key`;
2. delete the affected CloudWatch log stream;
3. remove the CLI argument from the task definition;
4. inject the secret only as environment variable `VLLM_API_KEY`;
5. restart the application task so it received the rotated value;
6. verify new startup logs did not contain the token.

The old standalone token became invalid after rotation. No secret value is
recorded in this repository.

**General lesson:** a secret reference in an ECS task definition is not enough
if the application later copies that secret into its process arguments. Startup
logs and process listings are part of the threat model.

### 10. Fixed a false-unhealthy container

The first vLLM Docker health check invoked `python`. The image contained
`python3`, not a `python` alias. vLLM itself served traffic, but ECS saw the
container as unhealthy because the health-check executable failed.

The check was replaced with:

```text
curl -fsS http://localhost:8000/health || exit 1
```

**Evidence:** server logs and direct health behavior showed the application was
up while Docker health failed. This separated a health-probe bug from a model
startup failure.

### 11. Reduced the target drain delay

The target group initially used the ALB default 300-second deregistration delay.
During task replacement, that held the only quota-constrained GPU for five
minutes after the task was superseded.

Both target groups now use a 30-second deregistration delay.

**Trade-off:** shorter draining speeds development replacement but gives
long-running requests less time to finish. Production should choose this value
from measured request duration and graceful-shutdown behavior.

### 12. Recovered a stuck CloudFormation/ECS update without losing the cache

CloudFormation continued tracking a superseded failed ECS deployment. Repeated
updates would not make useful progress. The recovery sequence was:

1. set the generation ECS service desired count to zero;
2. place the ASG instance in standby while decrementing desired capacity;
3. cancel the CloudFormation update;
4. wait for `UPDATE_ROLLBACK_COMPLETE`;
5. exit standby so the same instance returned to service;
6. deploy the corrected template with generation desired count one.

**Why standby mattered:** it preserved the `g5.xlarge` and its already-pulled
approximately 17 GB image/model cache. Terminating it would consume more time
and bandwidth and might lose scarce zonal capacity.

The corrected stack reached `UPDATE_COMPLETE`. Generation task definition
revision `docsmind-vllm-gpu:5` became healthy.

### 13. Verified the generator runtime

The placed host reported an NVIDIA A10G. vLLM loaded the quantized 12B Gemma
model. Runtime logs reported approximately:

- 12.22 GiB available for KV cache;
- 150,682-token KV-cache capacity;
- about 9.2x theoretical concurrency at a 16,384-token maximum request length.

The service reached desired 1/running 1, the container became healthy, and the
internal ALB target became healthy. These figures describe the actual A10G/BF16
deployment, not the preferred L4/FP8 profile.

### 14. Cut the existing application over to ECS vLLM

The existing CPU embedding/application stack was updated to application task
definition revision `docsmind-embedding-cpu:6`. It received the rotated bearer
token and the internal ECS vLLM base URL. BGE-M3 remained on CPU.

The effective live path became:

```text
browser -> existing public ALB -> FastAPI
        -> CPU BGE-M3 TEI
        -> OpenSearch hybrid retrieval
        -> internal ALB -> ECS vLLM on A10G
        -> cited response
```

A final smoke question asked, “What platform does the Golf Mk7 use?” The answer
stated that it uses the MQB platform and included three citations. `/health`
reported hybrid retrieval and 1,776 indexed chunks. One observed request took
about 29 seconds; that single cold/JIT-affected observation is not a benchmark.

### 15. Left GPU embedding at zero

The GPU embedding task definition and ASG exist, but starting `g4dn.xlarge`
while `g5.xlarge` is running would exceed the effective four-vCPU GPU quota.
Therefore:

- GPU BGE-M3 has **not** been runtime-verified;
- BGE-M3 is **still running on CPU**;
- the application remains available through the existing CPU stack;
- no ingestion or retrieval benchmark was run against GPU FP16;
- no claim is made that GPU embedding migration is complete.

This was the correct stopping boundary. Continued quota polling could not change
the external AWS decision.

## Failure matrix

| Symptom | Evidence | Root cause | Fix | Verified? |
|---|---|---|---|---|
| Could not run both new GPU services | Service quota value `4` | Account GPU On-Demand vCPU limit | Requested `12`; keep embedding at zero | Block remains |
| `g6` host did not launch | ASG capacity activity | Zonal On-Demand scarcity | More subnets and prioritized `g6e`/`g5` fallbacks | Yes, `g5` launched |
| ALB target `unused` | `Target.NotInUse` | Target AZ absent from ALB | Enable all compatible default subnets | Yes |
| vLLM exited on A10G | SM86/FP8 error | FP8 KV cache requires newer GPU | BF16 mixed-profile default | Yes |
| Secret appeared in logs | Startup CLI dump | Token passed in `--api-key` | Rotate, delete stream, environment-only injection | Yes |
| Healthy server marked unhealthy | Probe command failure | Image lacked `python` alias | Use `curl` health check | Yes |
| Replacement appeared stuck | Target draining for 300 seconds | ALB default deregistration delay | Set 30 seconds | Yes |
| CloudFormation update stuck | Stack/ECS deployment state | Superseded failed deployment | Standby, cancel/rollback, corrected update | Yes |
| Old EC2 slow to stop | EC2 remained `stopping` | Guest shutdown did not finish promptly | Exact-target forced stop; preserve instance | Yes |

## Exact AWS state captured on 2026-08-06

| Resource | Captured state |
|---|---|
| Stack `docsmind-gpu-dev` | `UPDATE_COMPLETE` |
| ECS service `docsmind-vllm-gpu` | desired 1, running 1 |
| Generation task definition | `docsmind-vllm-gpu:5` |
| Generation ASG | desired 1 |
| Generation instance | `i-0ea5b546a22c79b72`, `g5.xlarge`, running, `us-east-1f` |
| ECS service `docsmind-app-embedding-gpu` | desired 0, running 0 |
| GPU embedding task definition | `docsmind-app-embedding-gpu:1` |
| Embedding GPU ASG | desired 0, no instances |
| Existing CPU host | `i-01bc35981c55f2ac3`, `m7i.large`, running, `us-east-1a` |
| Original standalone generator | `i-0d7385b600fd36704`, `g6.xlarge`, stopped, `us-east-1c` |
| Effective G/VT quota | 4 vCPUs |
| Requested quota | 12 vCPUs, `CASE_OPENED` |
| OpenSearch index | `docsmind-volkswagen-wikipedia-bge-m3-v1`, 1,776 chunks |

The live public UI remains the existing hosted application at:

```text
http://docsmind-app-dev-2127405200.us-east-1.elb.amazonaws.com
```

Its ALB ingress is restricted to the configured development CIDR. The new vLLM
base is private:

```text
http://internal-docsmind-vllm-gpu-dev-496431696.us-east-1.elb.amazonaws.com/v1
```

These are snapshot values, not discovery configuration. Scripts resolve stack
outputs and AWS state rather than depending on copied endpoints.

## What changed in the repository

### `infra/aws/gpu-ecs.yaml`

Defines the cluster, two capacity providers, ASGs, launch templates, task
definitions, IAM, security groups, ALBs, target groups, listeners, services,
logs, immutable model inputs, and stack outputs.

### `scripts/aws_gpu_service.sh`

Provides these actions:

| Action | Purpose |
|---|---|
| `deploy` | Discover VPC/subnets/OpenSearch/ECR/secret and deploy CloudFormation |
| `quota` | Show effective quota and recent requests |
| `start-generation` | Start only generation host and service |
| `start-embedding` | Start only embedding host and service |
| `start` | Start both; valid only when quota permits eight GPU vCPUs |
| `stop` | Stop both tasks, then reduce both ASGs to zero |
| `status` | Show stack, services, ASGs, instances, and target health |
| `logs` | Read recent TEI, application, and vLLM logs |

During `deploy`, the helper:

1. resolves the default VPC and default subnets;
2. checks GPU instance-type offerings by Availability Zone;
3. gives the ASGs only compatible subnets;
4. gives the ALBs all default subnets so fallback placement remains routable;
5. resolves the existing OpenSearch collection ARN and endpoint;
6. verifies the selected application image tag exists in ECR;
7. resolves the current workstation public address as a `/32` unless overridden;
8. resolves the existing Secrets Manager ARN without reading or printing the
   secret value;
9. deploys the stack with generation and embedding desired counts independently
   configurable.

### `Makefile`

Adds thin targets for the helper actions:

```text
aws-gpu-deploy
aws-gpu-quota
aws-gpu-start
aws-gpu-start-generation
aws-gpu-start-embedding
aws-gpu-stop
aws-gpu-status
aws-gpu-logs
```

### `README.md` and this documentation folder

The root README links the operational commands and architecture guide.
`docs/16-aws-gpu-ecs/README.md` explains the stable design and current state.
This file preserves the chronological engineering record.

## Operating commands

All commands run from the canonical repository on the Mac:

```bash
AWS_PROFILE=ml-prep-deploy make aws-gpu-quota
AWS_PROFILE=ml-prep-deploy make aws-gpu-deploy
AWS_PROFILE=ml-prep-deploy make aws-gpu-start-generation
AWS_PROFILE=ml-prep-deploy make aws-gpu-start-embedding
AWS_PROFILE=ml-prep-deploy make aws-gpu-status
AWS_PROFILE=ml-prep-deploy make aws-gpu-logs
AWS_PROFILE=ml-prep-deploy make aws-gpu-stop
```

Do not run `aws-gpu-start` while the effective quota is below eight; the second
host cannot be placed. Do not stop the current CPU embedding stack until the GPU
TEI service and the end-to-end application path pass acceptance checks.

## Remaining work after quota approval

The remaining work is deliberately small and ordered:

1. Confirm effective quota is at least eight. Do not rely only on case status.
2. Run `make aws-gpu-start-embedding`.
3. Confirm the `g4dn.xlarge` joins ECS and the TEI task reaches healthy.
4. Verify `/info` reports the pinned BGE-M3 revision, FP16, CLS, and dimension
   1,024.
5. Embed a known text and verify vector length and normalization.
6. Run the existing labeled retrieval evaluation against the same 1,776-chunk
   OpenSearch index. Compare ranks, not just HTTP success.
7. Point the hosted application at GPU TEI and redeploy it.
8. Verify `/health` and multiple cited Volkswagen questions.
9. Benchmark latency, throughput, GPU utilization, and cost on the actual T4.
10. Only then scale the CPU embedding service/host to zero.

No corpus re-ingestion is required for the endpoint cutover because CPU and GPU
use the same pinned BGE-M3 model, pooling, and 1,024-dimensional vector space.
FP32 versus FP16 can introduce small numerical differences, so retrieval eval
is still required. Re-ingestion becomes necessary if the model, revision,
pooling, vector dimension, text normalization, or chunk contract changes.

## Rollback plan

### Application/generation rollback

The old standalone `g6.xlarge` is stopped, not deleted. A rollback is not merely
“start the instance,” because its previous token was invalidated. The safe order
is:

1. configure the old service with the current Secrets Manager value without
   exposing it in arguments or logs;
2. start the old instance and verify authenticated `/health` and chat;
3. change the application generation base URL back;
4. deploy and run an end-to-end cited query;
5. only then scale ECS generation to zero.

### Embedding rollback

Until GPU embedding is actually cut over, no rollback is needed: CPU TEI remains
the active service. After a future cutover, preserve the CPU service at zero for
one acceptance window so it can be restarted if GPU TEI fails.

## What was inefficient and the corrected stopping rule

Several troubleshooting steps were necessary to make generation work: capacity
fallbacks, ALB zone coverage, BF16 compatibility, secret containment, the
health-check correction, drain tuning, and stack recovery. Repeatedly checking
unchanged AWS deployment and quota state was not useful after the external quota
became the only blocker for GPU embedding.

The corrected operating rule is:

```text
Poll only while a bounded AWS transition is expected.
If effective quota is unchanged and the request is CASE_OPENED, stop.
Report the partial state once and wait for an external notification or an
explicit user request before checking again.
```

This separates active debugging—where new evidence can change the system—from
waiting on an external decision that local commands cannot accelerate.

## Interview depth signal

The useful story is not simply “I deployed vLLM on ECS.” The evidence-backed
story is:

- GPU memory measurement forced embedding and generation into separate failure
  and scaling domains.
- ECS integer GPU scheduling ruled out fractional co-location.
- AWS quota forced a staged migration rather than the intended two-GPU cutover.
- zonal scarcity required mixed-instance fallback and broader subnet coverage;
- the A10G fallback changed the valid KV-cache dtype from FP8 to BF16;
- ALB target state distinguished an AZ-routing problem from an application
  health problem;
- runtime logs distinguished a broken health probe from a broken server;
- command-line secret exposure was contained and removed from the design;
- the final claim is carefully bounded: generation is verified on ECS/A10G,
  while GPU embedding is provisioned but not yet run.

In an interview, the real question is not “did you use ECS?” It is “what failed,
what evidence identified the layer responsible, what trade-off did the fix
introduce, and which parts did you actually verify?” This log is the evidence
for that answer.
