# AWS BGE-M3 build log: decisions, failures, and fixes

This is the engineering record from the 2026-08-05 DocsMind embedding-service
session. It intentionally includes failed approaches and incomplete work. The
goal is to preserve the reasoning and evidence needed to explain the system in
an interview, not merely the final configuration.

## Pipeline position

The work changed only the **Embed** stage:

```text
Ingestion
Corpus -> Documents -> 512-token chunks -> Embed documents -> Vector index
                                      ^
                                      |
                              BGE-M3 service

Retrieval
Question -> Embed query -> dense search -> BM25 -> RRF -> rerank -> generate
               ^
               |
       the same BGE-M3 service
```

The embedding service does two different workloads:

- Bulk ingestion embeds every new or changed chunk.
- Online retrieval embeds one user question at a time.

They use the same model and vector space, but they have different traffic
patterns. Bulk ingestion values throughput. Online queries value low tail
latency and continuous availability.

## Starting decisions

### Why BGE-M3

The existing `BAAI/bge-small-en-v1.5` model is a useful free baseline, but its
384-dimensional English-focused embeddings were not the desired production
candidate. BGE-M3 was selected as the next candidate because it provides
1,024-dimensional multilingual dense embeddings and leaves room for a corpus
containing English, German, and other European-language automotive material.

This is still a **candidate**, not a proven quality improvement. A model becomes
the production choice only after retrieval evaluation on the same corpus and
labeled questions.

### Why CPU first

The development goal was to prove packaging, deployment, health checks,
networking, batching, application integration, and failure behavior without
paying for an idle GPU. The intended progression is:

```text
CPU development -> functional system -> measured CPU baseline
                -> GPU deployment -> same benchmark -> cost/quality decision
```

CPU is acceptable for occasional development ingestion and individual query
embeddings. It is not assumed to be the final answer for frequent large corpus
updates.

### Why ECS on EC2 instead of Kubernetes

One service on one machine did not justify a Kubernetes control plane. ECS on
EC2 still exercises production patterns: task definitions, immutable revisions,
health checks, logs, capacity providers, rolling deployments, IAM, and
scale-to-zero. Kubernetes becomes justified when service count, team count,
portability, or scheduling complexity outweighs its operating cost.

### Why not plain EC2

A plain VM would run the container, but ECS provides a service contract around
it. ECS detects failed tasks, restarts them, records stopped reasons, performs
deployments, and separates the EC2 host lifecycle from the container lifecycle.
Those behaviors produced the most useful evidence during the OOM incident.

## Attempted managed embedding paths

Before self-hosting BGE-M3, two Bedrock providers were implemented behind the
same `EmbeddingProvider` interface.

### Cohere Embed v4 hurdle

Bedrock Marketplace activation failed with `INVALID_PAYMENT_INSTRUMENT`. AWS
promotional credit did not satisfy the third-party Marketplace account
requirement.

**Decision:** keep the Cohere client implementation as an optional provider,
but do not describe it as deployed. No Cohere index was created.

### Titan Text Embeddings v2 hurdle

Titan v2 calls were throttled across the tested regions despite visible quota
information. The request failed before the vector-store construction step.

**Decision:** keep Titan as an optional managed-provider implementation, but do
not make successful deployment claims. No Titan index was created.

**General lesson:** a quota shown in a console is not deployment evidence. The
real evidence is a successful sustained request path using the same account,
region, model ID, and workload that production will use.

## Packaging and infrastructure hurdles

### No local Docker runtime

The Mac did not have Docker available, so building a custom image and pushing it
to ECR would have added a separate workstation setup dependency.

**Fix:** use the official Hugging Face Text Embeddings Inference image directly:

```text
ghcr.io/huggingface/text-embeddings-inference:cpu-1.9.3
```

The tag is pinned instead of using `latest`. The BGE-M3 Hugging Face revision is
also pinned:

```text
5617a9f61b028005a4858fdac845db406aefb181
```

This makes a later CPU/GPU comparison reproducible. A new image or model
revision is an explicit change, not an invisible redeployment.

### CloudFormation health-check validation failure

The first stack used an ECS container health-check `StartPeriod` of 600 seconds.
CloudFormation rejected it because ECS permits at most 300 seconds.

**Fix:** change `StartPeriod` to 300 seconds and validate the template before
redeployment.

The initial stack reached `ROLLBACK_COMPLETE`. The deployment helper was updated
to detect that terminal state, delete the failed stack, wait for deletion, and
then deploy again.

**General lesson:** infrastructure validation errors should become automation.
The useful fix was not only changing one number; it was making the next failed
deployment recover predictably.

### Slow failed-stack cleanup

Deleting the failed stack waited for the Auto Scaling group and EC2 instance to
finish termination. CloudFormation temporarily remained in
`DELETE_IN_PROGRESS` even after the instance was shutting down.

**Fix:** inspect CloudFormation events, Auto Scaling activities, and EC2 state
instead of starting a second overlapping deployment. Once deletion completed,
the same deployment command created a clean stack.

## The CPU OOM incident

### Initial configuration

The first `m7i.large` task used:

- 2 vCPU and 8 GiB host memory
- 7,000 MiB container hard limit
- BGE-M3 float32 ONNX weights
- `max-batch-tokens=8192`
- `max-concurrent-requests=32`
- `max-client-batch-size=64`

The model weights downloaded successfully. Failure happened during model
warm-up, before the HTTP server became ready.

### Observed failure

ECS started four replacement tasks. Every stopped task showed:

```text
stopCode: EssentialContainerExited
exitCode: 137
reason: OutOfMemoryError: Container killed due to memory usage
```

The logs consistently ended at `Warming up model`. This separated the root
cause from networking, IAM, image download, and health-check problems.

### Why it happened

`max-batch-tokens` is the maximum total token envelope TEI may place into one
inference batch. It affects temporary activation memory during warm-up and
inference, not only request validation. An 8,192-token warm-up exceeded the
available memory even though the model's idle resident memory was much lower.

This distinction matters:

```text
Model fits at idle != configured inference envelope fits at peak
```

After the working deployment warmed up, the TEI container used about 1.91 GiB
at idle. The earlier OOM was still real because peak warm-up memory, not idle
memory, crossed the 7 GB limit.

### Fix

The CPU development envelope was reduced to:

```text
max-batch-tokens=2048
max-concurrent-requests=8
max-client-batch-size=8
```

With `max-batch-tokens=2048`, TEI warns that BGE-M3's native 8,192-token input
length is truncated to 2,048. This is intentional for the development profile.
DocsMind currently creates 512-token chunks, so an individual chunk remains
well below that limit.

The corrected task downloaded the model, completed warm-up, started the HTTP
server, passed the container health check, and reached ECS steady state with no
failed tasks.

### Alternative considered

Moving immediately to `m7i.xlarge` would provide 4 vCPU and 16 GiB memory and
would probably accommodate a larger envelope. It was not the first fix because
the current 512-token chunking did not require 8,192-token requests. Tightening
the workload envelope preserved the cheap development target and made the
constraint explicit.

If future chunking or long-document embedding genuinely needs more than 2,048
tokens, the correct response is more memory or a GPU profile—not silent
truncation without evaluation.

## Chunking and batching: two limits at the same stage

DocsMind's Wikipedia pipeline produced:

- 1,147 heading-aware section documents
- 1,776 chunks
- `chunk_size=512`
- `chunk_overlap=64`

Chunk size and TEI batch size are different controls:

| Control | Applies to | Current value | Failure when too large |
|---|---|---:|---|
| Chunk size | One stored passage | 512 tokens | Poor retrieval focus, truncation, more compute per chunk |
| TEI input limit | One input | 2,048 tokens | Input is truncated by the dev service |
| TEI batch-token limit | Total tokens in an inference batch | 2,048 tokens | Peak memory grows; initial setting caused OOM |
| Client batch size | Texts in one HTTP call | 8 | Request is rejected or backpressured |

Eight 512-token chunks can contain roughly 4,096 tokens before tokenizer
variation. Sending eight inputs in one HTTP request therefore does not mean TEI
runs all eight in one 2,048-token inference batch. TEI schedules work within its
token ceiling. The request contract and the hardware batch are related but not
identical.

In an interview, the depth question is not “what chunk size did you use?” It is:
“how did chunk length affect retrieval quality, embedding latency, batch
packing, memory, and cost—and what evidence changed your configuration?”

## Backpressure hurdle

After the first working deployment, the service allowed 16 texts in a client
request while the CPU backend forced `max_batch_requests=8`. A benchmark request
with 16 inputs returned HTTP 429 and TEI logged `no permits available`.

**Fix:** align `max-client-batch-size` with the backend limit of eight. The
application also sends at most eight documents per TEI call.

This is preferable to an unbounded queue. Under overload, a production service
should reject excess work clearly so callers can retry with jitter, slow the
ingestion producer, or send work to a durable job queue.

## Application integration hurdle

The first `TEIEmbedder` implementation could send the entire document list in a
single `/embed` request. That does not match a service whose maximum client
batch is eight. A 1,776-chunk ingestion would eventually violate the service
contract.

**Fix:** add `DOCSMIND_TEI_EMBED_BATCH_SIZE`, default it to eight, split document
inputs into bounded calls, validate the vector count and dimension for every
response, concatenate results in original order, and keep query embedding as a
one-input call.

Order preservation is critical. If vector 500 is accidentally attached to
chunk 501, the index remains structurally valid but retrieval returns the wrong
text. This is harder to detect than a crash, so the batching behavior has an
explicit test.

## Vector-space safety

BGE-small produces 384-dimensional vectors. BGE-M3 produces 1,024-dimensional
vectors. Dimension checking catches that obvious mismatch, but equal dimensions
would not prove compatibility: two models can produce vectors of the same size
in entirely different coordinate spaces.

**Fix:** write an embedding manifest beside the local vector-store marker and
validate provider, model name, and dimension at query startup. Use a separate
OpenSearch index name for every embedding-space migration.

The intended new index name is:

```text
docsmind-volkswagen-wikipedia-bge-m3-v1
```

The existing 384-dimensional Wikipedia index and `docsmind-chunks` index are not
replacement targets.

## Private network access

The EC2 security group has no inbound rules. TEI maps container port 80 to host
port 8080, but the host port is not exposed publicly.

Development access uses an AWS Systems Manager port-forwarding session:

```text
Mac localhost:8080 -> SSM session -> EC2 localhost:8080 -> TEI container:80
```

This removed the need for SSH ingress, a bastion host, or a public unauthenticated
embedding endpoint. The verified path returned HTTP 200 from `/health`, reported
the pinned model and runtime from `/info`, and returned a normalized
1,024-dimensional vector from `/embed`.

A production application running inside AWS should use private service
discovery or an internal load balancer. An operator's SSM tunnel is a secure
development path, not an application-to-service production topology.

## AWS credential dependency hurdle

The AWS CLI profile uses the newer AWS login-session credential provider. AWS
CLI commands worked, but boto3 raised a missing dependency error because the
Python environment did not contain `awscrt`.

**Fix:** add `awscrt` to project dependencies. This must be installed before a
Python ingestion process reaches OpenSearch authentication:

```bash
make install
```

This failure was found before the user-run ingestion. Without the dependency,
embedding could finish successfully and then OpenSearch connection setup would
fail—a particularly wasteful ordering for a long CPU job.

## Measurements and what they mean

The short synthetic benchmark over the SSM tunnel measured:

| Client batch | p50 | p95 | Throughput |
|---:|---:|---:|---:|
| 1 | 420.26 ms | 424.42 ms | 2.38 texts/s |
| 4 | 813.57 ms | 999.27 ms | 4.82 texts/s |
| 8 | 1,341.58 ms | 1,432.38 ms | 5.91 texts/s |

Batching improved throughput by about 2.5 times from batch one to batch eight,
while increasing the completion latency of the batch. That is expected: the CPU
does more useful work per scheduling cycle, but a batch takes longer to finish.

An interrupted real-corpus run exposed a second lesson. Near-512-token chunks
were much slower than the short benchmark sentences, initially progressing at
roughly 1.0–1.3 chunks/s. Sequence length changes transformer compute
substantially, so a benchmark made only of short sentences overstates bulk
corpus throughput.

The corpus ingestion was stopped at the user's request during embedding. The
code creates the vector store only after the embedding array is complete, so:

- No BGE-M3 OpenSearch index was created.
- No local BGE-M3 index marker was written.
- Existing OpenSearch indexes were untouched.

The benchmark is useful capacity evidence, but it is not a retrieval-quality
evaluation. BGE-M3 still needs Hit@1, Hit@3, MRR, and relevant-source analysis on
the same Volkswagen snapshot before it can replace the baseline on quality
grounds.

## Cost and lifecycle hurdle

The measured on-demand `m7i.large` compute price in `us-east-1` was
$0.1008/hour. Public IPv4 and prorated gp3 storage make the running development
total roughly $0.11/hour before small logging and monitoring charges.

The service can scale to zero. The root EBS volume uses
`DeleteOnTermination=true`, so scale-to-zero removes the VM and its model cache.
The next cold start downloads the pinned model again.

The cache therefore has two different behaviors:

- Task restart on the same EC2 VM: model files are reused.
- EC2 scale-to-zero and later restart: model files are downloaded again.

EFS or a baked image could preserve faster cold starts, but each adds storage,
build, or operating cost. For intermittent development, redownloading is an
acceptable trade-off.

## Final working system

The provisioned development system now has:

- CloudFormation-managed ECS, EC2 capacity, IAM, logs, and networking
- One healthy CPU TEI task on `m7i.large`
- Pinned TEI image and pinned BGE-M3 revision
- No inbound security-group rules
- SSM port forwarding for development access
- Container health checks and CloudWatch logs
- Bounded token, concurrency, and client-batch limits
- A DocsMind `tei` embedding-provider option
- Ordered application-side batching
- Embedding-space manifest validation
- Start, stop, status, logs, tunnel, and benchmark commands

## Work deliberately left for later

The following are not claimed as complete:

1. User-run ingestion into the isolated BGE-M3 OpenSearch index
2. Volkswagen retrieval-quality evaluation against the bge-small baseline
3. GPU deployment using the same model revision and workload
4. CPU-versus-GPU latency, throughput, utilization, and cost comparison
5. Durable ingestion queue, retry policy, and resumable/checkpointed embedding
6. Private service discovery or an internal load balancer for an AWS-hosted app
7. Production autoscaling and alert thresholds

## Interview version

A defensible summary is:

> I deployed BGE-M3 with Hugging Face TEI on ECS backed by a CPU EC2 capacity
> provider. The first 8,192-token configuration repeatedly failed during
> warm-up with exit 137, so I used ECS stopped-task evidence to identify peak
> memory as the failure boundary. I reduced the development token and
> concurrency envelope to match 512-token RAG chunks, aligned client batching
> with backend backpressure, kept the endpoint private through SSM, and pinned
> both the container and model revision. Short-input batching reached about
> 5.9 texts/s, while a real corpus showed why sequence-length-aware benchmarks
> are necessary. I kept the old and new embedding spaces in separate indexes
> and did not claim a quality improvement before retrieval evaluation.

The real depth signal is the chain from observation to decision:

```text
Failure evidence -> root cause -> smallest safe fix -> measured behavior
                 -> explicit trade-off -> next validation gate
```
