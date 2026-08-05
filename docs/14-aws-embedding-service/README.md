# BGE-M3 embedding service on AWS

For the chronological engineering record—including the Bedrock hurdles,
CloudFormation rollback, CPU OOM, batch-limit 429, application batching fix,
credential dependency, and incomplete ingestion—see
[the build log](build-log.md).

For the exact first full-corpus execution topology, command, batching behavior,
live CPU/memory evidence, authorization path, progress, failure semantics, and
post-ingestion verification checklist, see the
[2026-08-05 ingestion run record](ingestion-run-2026-08-05.md).

The completed 20-query bge-small versus BGE-M3 dense/hybrid comparison is in
[the Volkswagen embedding evaluation](wikipedia-embedding-eval.md), with raw
per-query evidence in `wikipedia-embedding-eval.json`.

## Where this fits

This service owns one stage of the RAG pipeline:

```text
Ingest -> Chunk -> [TEI + BGE-M3 on ECS/EC2] -> OpenSearch
Query --------------^                         -> dense search -> BM25 -> RRF
```

It creates vectors for new chunks during ingestion and one vector for each user
question during retrieval. It does not run the generator LLM. Keeping embedding
and generation separate lets each workload use different hardware and scaling.

The application insertion point is `TEIEmbedder` in
`docsmind/index/embeddings.py`. `build_embedder()` in `docsmind/factory.py`
selects it when `DOCSMIND_EMBEDDING_PROVIDER=tei`.

## Deployed development architecture

CloudFormation in `infra/aws/embedding-ecs.yaml` creates:

- One ECS cluster and EC2 capacity provider in `us-east-1`
- An Auto Scaling group with zero-or-one `m7i.large` instance
- A pinned TEI CPU image: `cpu-1.9.3`
- A pinned BGE-M3 model revision:
  `5617a9f61b028005a4858fdac845db406aefb181`
- A 40 GB encrypted gp3 root volume and host model cache
- Seven-day CloudWatch log retention and ECS Container Insights
- An EC2 role for ECS registration and Systems Manager access
- A security group with no inbound rules

TEI listens on container port 80, mapped to host port 8080. That port is not
open to the internet. For development, AWS Systems Manager forwards local
`localhost:8080` to the EC2 host. A production application inside AWS should use
private service discovery or an internal load balancer instead of an operator
tunnel.

ECS on EC2 is the right development step because it teaches task definitions,
health checks, capacity providers, rolling deployments, logs, and scale-to-zero
without adding a Kubernetes control plane. Kubernetes becomes useful when
multiple teams, many services, or cross-cloud scheduling justify its extra
operational surface.

## CPU sizing decision

The first `m7i.large` attempt used an 8,192-token batch ceiling. TEI was killed
four times during warm-up with exit code 137 and an ECS
`OutOfMemoryError`. The model did not fail because CPU inference is unsupported;
the warm-up envelope temporarily exceeded the 7 GB container limit.

The working development profile is:

| Setting | Value | Why |
|---|---:|---|
| Instance | `m7i.large` | 2 vCPU, 8 GiB; low-cost CPU development |
| TEI dtype | `float32` | CPU ONNX path supported by the pinned image |
| Maximum input/batch tokens | 2,048 | Fits memory and covers 512-token chunks |
| Concurrent requests | 8 | Bounded admission and explicit backpressure |
| Client batch size | 8 | Matches the CPU backend's measured limit |
| Container memory | 7,000 MiB | Leaves room for ECS and the operating system |

BGE-M3 natively supports 8,192 tokens. This service intentionally truncates
above 2,048 in the development profile. If the corpus later needs long-document
embeddings, increase memory or move to the GPU profile and rerun the benchmark.

After warm-up, the observed TEI container used about 1.91 GiB of its 6.84 GiB
limit at idle. That does not contradict the warm-up OOM: transient peak memory,
not idle resident memory, was the failure boundary.

## Operations

Deploy and inspect the service:

```bash
AWS_PROFILE=ml-prep-deploy AWS_REGION=us-east-1 make aws-embedding-deploy
AWS_PROFILE=ml-prep-deploy AWS_REGION=us-east-1 make aws-embedding-status
```

Start it and open a tunnel in a separate terminal:

```bash
AWS_PROFILE=ml-prep-deploy AWS_REGION=us-east-1 make aws-embedding-start
AWS_PROFILE=ml-prep-deploy AWS_REGION=us-east-1 make aws-embedding-tunnel
```

Then select the remote provider:

```bash
DOCSMIND_EMBEDDING_PROVIDER=tei
DOCSMIND_TEI_BASE_URL=http://localhost:8080
DOCSMIND_TEI_EMBED_MODEL=BAAI/bge-m3
DOCSMIND_TEI_EMBED_DIMENSIONS=1024
DOCSMIND_TEI_EMBED_BATCH_SIZE=8
```

When work is finished, scale both the task and EC2 capacity to zero:

```bash
AWS_PROFILE=ml-prep-deploy AWS_REGION=us-east-1 make aws-embedding-stop
```

Scale-to-zero terminates the EC2 root volume, so the next cold start downloads
the pinned model again. The host cache speeds task restarts on the same VM; it
does not persist across VM termination. EFS or a baked model image would trade
ongoing storage/build cost for faster cold starts.

## Measured CPU baseline

Run while the SSM tunnel is open:

```bash
make aws-embedding-benchmark \
  ARGS='--batch-sizes 1 4 8 --repeats 10 \
  --output docs/14-aws-embedding-service/cpu-baseline.json'
```

Measured on 2026-08-05 with synthetic automotive sentences over the SSM tunnel:

| Batch | p50 latency | p95 latency | Throughput |
|---:|---:|---:|---:|
| 1 | 420.26 ms | 424.42 ms | 2.38 texts/s |
| 4 | 813.57 ms | 999.27 ms | 4.82 texts/s |
| 8 | 1,341.58 ms | 1,432.38 ms | 5.91 texts/s |

All responses contained 1,024-dimensional normalized vectors. Batching eight
texts delivered about 2.5 times the batch-1 throughput, while increasing the
time to finish that batch. The raw result is in `cpu-baseline.json`.

This is a serving benchmark, not a retrieval-quality evaluation. Hit@k and MRR
must still compare `bge-small` and BGE-M3 on the same Volkswagen questions and
corpus snapshot before BGE-M3 can be called a quality improvement.

## Cost boundary

At the measured `us-east-1` on-demand price, `m7i.large` compute is
$0.1008/hour. Public IPv4 and prorated gp3 storage bring the running total to
roughly $0.11/hour before small CloudWatch charges. An always-on instance would
be about $80/month, so the development service should normally be at zero.
There is no additional ECS control-plane charge for the EC2 launch type.

## GPU comparison gate

The later GPU deployment should keep the same model revision, test sentences,
batch sizes, and output validation. Compare:

- p50 and p95 latency for a user question
- texts per second as batch size rises
- cold-start and warm-start time
- CPU/GPU memory and utilization
- cost per 1,000 embedded chunks
- Hit@k and MRR after re-indexing the same corpus

In an interview, the important claim is not “I ran BGE-M3 on ECS.” It is: “I
found an OOM boundary, tuned batching to fit the development hardware, measured
latency and throughput, kept the endpoint private, and defined the evidence
required before moving to GPU.”
