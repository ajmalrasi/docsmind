# Hosted DocsMind application on AWS

## Where this fits

This deployment starts at the **Query** stage. Ingestion is already complete:

```text
Browser
  -> ALB
  -> FastAPI /query
  -> BGE-M3 query embedding
  -> OpenSearch dense + BM25 -> RRF
  -> vLLM generation
  -> cited answer
```

The application does not re-fetch Wikipedia, recreate chunks, or re-index the
1,776 stored vectors.

## ECR versus ECS

ECR is the image warehouse. ECS is the runtime.

```text
Dockerfile -> ECR image -> ECS task -> running FastAPI process
```

`infra/aws/app-ecr.yaml` creates the `docsmind-app` registry with scan-on-push,
AES-256 encryption, and a lifecycle rule retaining the ten newest images.

`infra/aws/embedding-ecs.yaml` runs that image as an `app` container beside the
existing `tei` container. Both share one ECS task and one `m7i.large` development
host. A Docker link named `embedding` keeps TEI private; FastAPI calls
`http://embedding:80` without opening the embedding port to the internet.

## Why the app shares the TEI task

The deployed TEI task uses ECS bridge networking because its CPU host downloads
the model through the host's public route. A separate Fargate application could
not address that private bridge container directly. It would require another
internal load balancer, Cloud Map/SRV resolver, Service Connect proxy, or a
network-mode redesign.

For this one-host development system, a second container in the same task is the
smallest reliable topology:

- No Kubernetes control plane.
- No second internal load balancer charge.
- TEI remains unreachable from the public internet.
- API and embedder start and scale to zero together.
- The app starts only after TEI passes its health check.

The trade-off is coupled scaling. Production traffic may require FastAPI and
TEI to scale independently. At that point, use `awsvpc` plus private service
discovery or an internal load balancer and run the API on Fargate.

## Runtime components

| Component | Responsibility |
|---|---|
| Public ALB | IP-restricted development entry point |
| `app` ECS container | Static chat page, `/live`, `/ready`, `/health`, `/query` |
| `tei` ECS container | One 1,024-dimensional BGE-M3 vector per question |
| OpenSearch Serverless | Reads `docsmind-volkswagen-wikipedia-bge-m3-v1` |
| vLLM HTTPS endpoint | Generates an answer from retrieved passages |
| Secrets Manager | Injects the vLLM bearer key into the task |
| CloudWatch Logs | Seven-day application and TEI logs |

The app task role has `aoss:APIAccessAll` on the one collection because AWS
requires that IAM gate for data-plane calls. A separate OpenSearch data access
policy grants only collection describe plus index describe/read permissions for
the BGE-M3 index. The app cannot create, update, or delete indexes.

## Web and API behavior

`docsmind/serving/app.py` serves a dependency-free HTML/CSS/JavaScript interface
from `docsmind/serving/static/index.html`. Keeping it in the FastAPI image avoids
a separate frontend deployment during development.

Health endpoints have different meanings:

| Endpoint | Meaning |
|---|---|
| `/live` | The Python process is alive |
| `/ready` | OpenSearch and the full pipeline loaded successfully |
| `/health` | Index size, backend, retrieval mode, and model summary |
| `/query` | Executes the complete RAG request |

The ECS container and ALB check `/ready`, not merely `/live`. A process that
cannot load OpenSearch must not receive user traffic. Startup errors are logged
with their exception type, while the public response avoids leaking internal
endpoints or credential details.

## Deployment workflow

The development workstation needs an authenticated AWS CLI profile. When local
Docker is available, the script builds and pushes `linux/amd64` directly. When
Docker is absent, the ECR stack's short-lived CodeBuild project checks out the
exact public Git commit, builds on x86_64, and pushes the same immutable commit
tag plus `latest`.

```bash
AWS_PROFILE=ml-prep-deploy make aws-app-registry
AWS_PROFILE=ml-prep-deploy make aws-app-build
AWS_PROFILE=ml-prep-deploy make aws-app-deploy
```

The API key is read from standard input so it is not placed in shell history or
passed as a command-line argument:

```bash
printf '%s' "$VLLM_API_KEY" | \
  AWS_PROFILE=ml-prep-deploy bash scripts/aws_app_service.sh secret
```

Then start and inspect the coupled application/embedding task:

```bash
AWS_PROFILE=ml-prep-deploy make aws-app-start
AWS_PROFILE=ml-prep-deploy make aws-app-status
AWS_PROFILE=ml-prep-deploy make aws-app-logs
```

The deploy script discovers the current public IP of the running `g6-xlarge`
vLLM host and derives its `sslip.io` URL. This avoids silently retaining a dead
URL after EC2 assigns a different public IP. A stable production endpoint should
use an Elastic IP or Route 53 name; discovery is the cost-saving development
choice.

Stop EC2 compute when the development session ends:

```bash
AWS_PROFILE=ml-prep-deploy make aws-app-stop
```

The ALB remains provisioned while compute is stopped and therefore still has a
small hourly charge. Delete the development stack when the endpoint is no
longer needed; the ECR repository and vLLM secret have retention policies to
prevent accidental data loss.

CodeBuild is a build worker, not an application runtime. It stops billing when
the image build finishes. ECS remains responsible for running the image.

### First build hurdle: Docker Hub throttling

The first CodeBuild run authenticated to ECR, checked out the exact Git commit,
and reached `docker build`, but Docker Hub returned HTTP 429 while resolving
`python:3.12-slim`. This was a base-image registry throttle, not an application
or ECR failure.

The Dockerfile now pulls the official Python image through AWS Public ECR:

```text
public.ecr.aws/docker/library/python:3.12-slim
```

The buildspec also aborts immediately when pre-build or build fails, so it does
not attempt to push a nonexistent image. In an interview, this is the useful
debug signal: identify whether failure happened while fetching the base image,
building application layers, authenticating to the private registry, or pushing
the result; “Docker build failed” is not a root cause.

## Security boundary

This is a development deployment, not an unrestricted public product:

- The ALB security group accepts HTTP only from `APP_ALLOWED_CIDR`, defaulting
  to the deployer's current public `/32` address.
- The EC2 host accepts port 8000 only from the ALB security group.
- TEI port 8080 has no inbound security-group rule.
- The vLLM key comes from Secrets Manager and never enters the ECR image.
- The OpenSearch task role is read-only at the data-policy layer.
- The image runs as UID/GID `10001`, not root.

Before broad public access, add a real domain, ACM certificate, HTTPS listener,
WAF/rate limits, authentication, request quotas, and application autoscaling.
HTTP plus a workstation `/32` is deliberately a temporary development boundary.

## Failure modes and debugging

| Symptom | Likely stage | Evidence |
|---|---|---|
| ALB target unhealthy during cold start | Embed | TEI model-download and health logs |
| `/ready` returns 503 | Search/startup | App CloudWatch startup exception type |
| Query returns embedding-service 503 | Query embed | TEI task health and HTTP status |
| Query returns index-service 503 | Search | OpenSearch access policy and task-role ARN |
| Query returns generation 502/503 | Generate | vLLM URL, secret version, and provider logs |
| UI opens but questions fail after secret update | Generate | ECS injects secrets only at container start; force a new deployment |

### First query hurdle: newline in the injected bearer token

The first hosted `/query` reached a healthy application with 1,776 OpenSearch
chunks but returned 503 at the model boundary. The ECS host could reach vLLM
over HTTPS, so security groups and DNS were not the cause. The secret had been
piped from an SSH command that printed a trailing newline. Secrets Manager
preserved it, and the resulting Authorization header was invalid.

The `secret` action now removes only CR/LF transport characters while streaming
stdin directly to Secrets Manager. It never stores or prints the key in a shell
variable. After secret rotation, ECS needs a new task deployment because secret
values are injected only when a container starts.

### First successful answer: citation-format drift

After the secret fix, the hosted pipeline answered the Golf Mk7 question
correctly in about 5.3 seconds:

```text
The Volkswagen Golf Mk7 uses the MQB platform [1, 2, 4].
```

The prompt requested `[1][2][4]`. The open model instead produced the common
grouped form `[1, 2, 4]`. Retrieval and generation succeeded, but the original
regex extracted no citations, so the UI received an empty source list.

`RAGPipeline._extract_citations()` now accepts both formats, still discards
numbers outside the supplied passage range, and has an offline regression test.
The prompt remains strict because format instructions reduce variation; the
parser is tolerant because production systems must not assume perfect model
format compliance.

In an interview, this is a concrete structured-output regression: the natural
language answer was correct, yet the machine-consumed citation contract failed.
The fix belongs at both layers—clearer prompting and defensive parsing—and the
evidence is the before/after API response, not a subjective visual judgment.

## Deployed evidence — 2026-08-06

The final AWS development deployment produced:

| Evidence | Result |
|---|---|
| ECR repository | `docsmind-app` |
| Deployed image tag | `a9aa044cb5e2` |
| ECS task definition | `docsmind-embedding-cpu:5` |
| ECS containers | `tei` healthy, `app` healthy |
| ALB target | Healthy |
| `/ready` | HTTP 200, `ready` |
| `/health` index size | 1,776 |
| Vector backend | OpenSearch |
| Retrieval mode | Hybrid dense + BM25/RRF |
| Generator | vLLM model alias `openclaw` |

The final browser-level question was:

```text
What platform does the Golf Mk7 use?
```

The live UI returned:

```text
The Golf Mk7 uses the MQB platform [1][2][3].
```

Observed end-to-end API latency was approximately 1.9–2.35 seconds across the
final browser and curl requests. The response included three populated citation
objects linking to the Volkswagen Golf Mk7 and Volkswagen Golf Wikipedia pages.

No corpus fetch, chunking, embedding ingestion, or index rebuild ran during this
deployment. BGE-M3 embedded only the user questions. OpenSearch continued to
serve the already-persisted 1,776-vector index.

In an interview, the real question is not “did you push a Docker image to ECR?”
It is: “how did the image receive identity and secrets, how did readiness prevent
bad tasks from receiving traffic, why was the topology coupled, and what would
make you separate the services?” This deployment makes each answer visible in
code and CloudFormation.
