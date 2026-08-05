# AWS OpenSearch Serverless setup runbook

- Date performed: 2026-07-16
- Region: `us-east-1`
- Purpose: replace the local vector-index storage layer with a managed AWS vector store.

## Where this fits in DocsMind

The pipeline is:

```text
Ingest -> Chunk -> Embed -> Index -> Query -> Embed -> Search -> Rerank -> Generate -> Cite -> Eval
                            ^
                            |
                  OpenSearch goes here
```

FAISS, Qdrant, and OpenSearch occupy the same **Index/Search** stage. The
`OpenSearchVectorStore` sits behind the existing `VectorStore` interface, so
the ingestion and retrieval pipelines do not need to know which backend stores
the vectors.

The infrastructure setup initially stopped before creating an index. The
subsequent implementation created `docsmind-chunks` and ingested the corpus.
See [implementation.md](implementation.md) for the code path, failures found by
the real AWS test, and measured results.

## Final state

| Item | Value |
|---|---|
| Collection | `docsmind-dev` |
| Collection type | Vector search |
| Serverless generation | NextGen |
| Collection group | `nextgen-docsmind-dev` |
| Region | `us-east-1` |
| Indexing capacity | Minimum `0` OCU, maximum `2` OCU |
| Search capacity | Minimum `0` OCU, maximum `2` OCU |
| Encryption | AWS-owned key |
| Network access | Public endpoint, IAM authenticated |
| Deletion protection | Disabled |
| IAM workload user | `docsmind-digitalocean` |
| IAM inline policy | `docsmind-opensearch-api` |
| Data access policy | `docsmind-dev-access` |
| Network policy | `auto-docsmind-dev` |
| AWS profile on DigitalOcean | `docsmind` |
| OpenSearch index | `docsmind-chunks` |
| Indexed vectors/chunks | `3,207` |

The endpoint is visible in the AWS collection details page. Account IDs, the
collection ARN, the access-key ID, and the secret key are deliberately not
stored in this repository.

## Why this configuration was chosen

At the **Index/Search** stage, the local alternatives are FAISS and Qdrant.
OpenSearch Serverless was chosen to learn the production pattern of a managed,
authenticated, remotely accessible vector store.

NextGen Serverless was selected because it can reduce capacity to zero when the
collection is inactive. That makes it more suitable for a learning workload
than keeping a provisioned OpenSearch domain running continuously. The maximum
capacity was limited to two indexing OCUs and two search OCUs to prevent
unbounded scaling.

The public endpoint was selected for the development setup because the
DigitalOcean Droplet is outside AWS. It is **not anonymous**: every request
still requires AWS SigV4 authentication, the IAM policy, and the OpenSearch
data access policy. A production deployment would prefer private connectivity
when the network design supports it and should use short-lived credentials.

## Step-by-step record

### 1. Selected the AWS region

The AWS Console was set to `us-east-1`. The collection, endpoint, signer region,
and future application configuration must all use this same region.

### 2. Created the IAM workload user

In IAM:

1. Opened **IAM -> Users -> Create user**.
2. Entered the user name `docsmind-digitalocean`.
3. Left AWS Management Console access disabled.
4. Created the user without attaching broad managed policies.

The user represents the DocsMind process running on DigitalOcean. It is not a
human console user.

### 3. Created the OpenSearch Serverless collection

In **Amazon OpenSearch Service -> Serverless collections**:

1. Started a new NextGen collection.
2. Set the name to `docsmind-dev`.
3. Set the description to `DocsMind development vector and hybrid search collection`.
4. Selected **Vector search** as the collection type.
5. Created/selected the collection group `nextgen-docsmind-dev`.
6. Set minimum indexing capacity to `0` OCU and maximum to `2` OCU.
7. Set minimum search capacity to `0` OCU and maximum to `2` OCU.
8. Selected an AWS-owned encryption key.
9. Allowed public network access for the development endpoint.
10. Left deletion protection disabled while the project is experimental.
11. Created the collection.
12. Waited until its status became **Active**.

AWS also created an OpenSearch UI application/workspace for the collection.
The application is not required by the Python client, but it can be used to
inspect indexes and documents manually.

### 4. Created the OpenSearch data access policy

The data access policy was named `docsmind-dev-access`. Its rule was named
`docsmind-index-access`, and its principal was the IAM user
`docsmind-digitalocean`.

The rule grants these index-level operations for indexes inside the collection:

- Create index
- Describe index
- Update index
- Delete index
- Read documents
- Write/update documents

A redacted equivalent policy is:

```json
[
  {
    "Description": "DocsMind index access",
    "Rules": [
      {
        "ResourceType": "index",
        "Resource": ["index/docsmind-dev/*"],
        "Permission": [
          "aoss:CreateIndex",
          "aoss:DescribeIndex",
          "aoss:UpdateIndex",
          "aoss:DeleteIndex",
          "aoss:ReadDocument",
          "aoss:WriteDocument"
        ]
      }
    ],
    "Principal": [
      "arn:aws:iam::<ACCOUNT_ID>:user/docsmind-digitalocean"
    ]
  }
]
```

OpenSearch Serverless has two permission layers:

1. **IAM permission** allows the principal to call the collection API.
2. **Data access policy** allows operations on the collection's indexes and
   documents.

Having only one layer results in authorization failures.

### 5. Attached the least-privilege IAM policy

The IAM Console's visual policy editor remained stuck while loading its service
list. The policy was therefore attached from the signed-in AWS CloudShell.

The policy allows only `aoss:APIAccessAll` against the one collection ARN:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DocsMindOpenSearchApi",
      "Effect": "Allow",
      "Action": "aoss:APIAccessAll",
      "Resource": "<DOCSMIND_COLLECTION_ARN>"
    }
  ]
}
```

The equivalent CloudShell command was:

```bash
aws iam put-user-policy \
  --user-name docsmind-digitalocean \
  --policy-name docsmind-opensearch-api \
  --policy-document '<POLICY_JSON>'
```

The attachment was verified with:

```bash
aws iam list-user-policies \
  --user-name docsmind-digitalocean \
  --output text
```

The result contained `docsmind-opensearch-api`.

### 6. Created the programmatic access key

In **IAM -> Users -> docsmind-digitalocean -> Security credentials**:

1. Selected **Create access key**.
2. Selected **Application running outside AWS** because the DigitalOcean
   Droplet is not an AWS compute instance.
3. Added the description:
   `DocsMind on DigitalOcean - OpenSearch Serverless`.
4. Created one access key.
5. Captured the access-key ID and secret once.
6. Closed the one-time secret screen after installation and verification.

The key values were never written to the repository or shown in chat.

Long-lived IAM keys are acceptable for this learning setup but are not the
preferred production design. IAM Roles Anywhere, workload identity, or an AWS
compute role would provide short-lived credentials.

### 7. Installed the AWS profile on DigitalOcean

The target machine is configured outside the repository:

```text
<DIGITALOCEAN_USER>@<DROPLET_IP>
```

Before installation, check whether the Droplet already has
`~/.aws/credentials` or `~/.aws/config` and merge profiles rather than
overwriting existing credentials.

The key was transferred over SSH and stored as the `docsmind` profile:

```ini
# ~/.aws/credentials
[docsmind]
aws_access_key_id = <REDACTED>
aws_secret_access_key = <REDACTED>
```

```ini
# ~/.aws/config
[profile docsmind]
region = us-east-1
output = json
```

Permissions were set to:

```text
700 /home/docsmind/.aws
600 /home/docsmind/.aws/credentials
600 /home/docsmind/.aws/config
```

The temporary credential files used for the SSH transfer were deleted from the
Mac immediately after installation.

### 8. Installed the Python AWS clients in the DigitalOcean venv

The Droplet needs `boto3` and `opensearch-py` in the project virtual
environment at `/home/docsmind/app/.venv`.

The required SDKs were installed with:

```bash
/home/docsmind/app/.venv/bin/pip install boto3 opensearch-py
```

Installed versions at setup time included:

- `boto3==1.43.49`
- `botocore==1.43.49`
- `opensearch-py==3.2.0`

These packages must also be declared in the repository dependencies so a new
Droplet can be rebuilt without manual package installation.

### 9. Verified AWS authentication

The profile was loaded explicitly rather than relying on the default AWS
profile:

```python
import boto3

session = boto3.Session(
    profile_name="docsmind",
    region_name="us-east-1",
)

identity = session.client("sts").get_caller_identity()
assert identity["Arn"].endswith("/docsmind-digitalocean")
```

The check should authenticate as `docsmind-digitalocean`.

### 10. Verified signed OpenSearch data access

OpenSearch Serverless uses SigV4 service name `aoss`, not the `es` service name
used by provisioned OpenSearch domains.

The read-only verification was:

```python
import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

session = boto3.Session(
    profile_name="docsmind",
    region_name="us-east-1",
)

auth = AWSV4SignerAuth(
    session.get_credentials(),
    "us-east-1",
    "aoss",
)

client = OpenSearch(
    hosts=[
        {
            "host": "<COLLECTION_ID>.aoss.us-east-1.on.aws",
            "port": 443,
        }
    ],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)

indexes = client.cat.indices(format="json")
print(f"index_count={len(indexes)}")
```

The result was:

```text
opensearch_authenticated=yes
index_count=0
```

An earlier `client.info()` call returned HTTP `404` because the Serverless root
route did not provide that provisioned-domain API response. This was not an IAM
failure: an authorization failure would return `403`. The supported
`cat.indices` request then proved that signing, IAM access, the network policy,
and the data access policy all worked together.

## What was deliberately not done during infrastructure setup

- No secret was added to `.env`, Git, the notebook, or this document.
- No broad AWS-managed administrator policy was attached.
- No AWS budget alert was created because a notification email was not supplied.
- No VPC/private endpoint was configured for this development collection.

## Implementation status

At the **Index/Search** stage, the next work is:

1. **Done:** add `boto3` and `opensearch-py` to `pyproject.toml`.
2. **Done:** add endpoint, index, region, AWS profile, timeout, retry, and batch settings.
3. **Done:** implement `OpenSearchVectorStore` behind `VectorStore`.
4. **Done:** create a 384-dimensional cosine `knn_vector` mapping.
5. **Done:** store chunk ID, text, source, metadata, insertion order, and vector.
6. **Done:** ingest 3,207 chunks and verify production hybrid retrieval.
7. **Next:** run the full labeled dense/hybrid/rerank evaluation against OpenSearch.
8. **Next:** measure cold/warm latency, ingestion time, storage, and AWS cost.

## Interview depth signal

The useful interview answer is not simply, “I used OpenSearch.” The stronger
answer is:

> At the Index/Search stage, I kept FAISS, Qdrant, and AWS OpenSearch behind one
> vector-store interface. I chose Serverless NextGen for a low-duty-cycle
> learning workload, capped its OCUs, used two-layer authorization, signed
> requests with SigV4, and verified the data plane separately from AWS identity.

The follow-up questions to be ready for are:

- Why use OpenSearch instead of pgvector, Qdrant Cloud, or a provisioned domain?
- How much does scale-to-zero actually save for this workload?
- What happens to latency on the first request after the collection is idle?
- Why are both IAM and a data access policy required?
- Why is the SigV4 service name `aoss`?
- How will retrieval quality and latency be compared with FAISS and Qdrant?
- When should the public endpoint be replaced with VPC-only access?
- How will the long-lived key be rotated or replaced with short-lived credentials?

Those measurements and trade-offs are the evidence that turns a cloud service
choice into a production engineering story.
