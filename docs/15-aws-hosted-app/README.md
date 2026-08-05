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

In an interview, the real question is not “did you push a Docker image to ECR?”
It is: “how did the image receive identity and secrets, how did readiness prevent
bad tasks from receiving traffic, why was the topology coupled, and what would
make you separate the services?” This deployment makes each answer visible in
code and CloudFormation.
