#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"
AWS_PROFILE_NAME="${AWS_PROFILE:-ml-prep-deploy}"
AWS_REGION_NAME="${AWS_REGION:-us-east-1}"
APP_REGISTRY_STACK="${APP_REGISTRY_STACK:-docsmind-app-registry-dev}"
EMBEDDING_STACK="${AWS_STACK_NAME:-docsmind-embedding-dev}"
REPOSITORY_NAME="${APP_REPOSITORY_NAME:-docsmind-app}"
CLUSTER_NAME="docsmind-embedding-dev"
SERVICE_NAME="docsmind-embedding-cpu"
ASG_NAME="docsmind-embedding-dev"

aws_cli() {
  aws --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION_NAME" "$@"
}

registry_uri() {
  aws_cli cloudformation describe-stacks \
    --stack-name "$APP_REGISTRY_STACK" \
    --query 'Stacks[0].Outputs[?OutputKey==`RepositoryUri`].OutputValue | [0]' \
    --output text
}

case "$ACTION" in
  registry)
    aws_cli cloudformation deploy \
      --stack-name "$APP_REGISTRY_STACK" \
      --template-file infra/aws/app-ecr.yaml \
      --capabilities CAPABILITY_NAMED_IAM \
      --parameter-overrides RepositoryName="$REPOSITORY_NAME" \
      --tags Project=DocsMind Environment=development
    registry_uri
    ;;
  build)
    REPOSITORY_URI="$(registry_uri)"
    IMAGE_TAG="${APP_IMAGE_TAG:-$(git rev-parse --short=12 HEAD)}"
    GIT_REF="${APP_GIT_REF:-$(git rev-parse HEAD)}"
    if command -v docker >/dev/null; then
      aws_cli ecr get-login-password | docker login \
        --username AWS --password-stdin "${REPOSITORY_URI%/*}"
      docker buildx build \
        --platform linux/amd64 \
        --provenance=false \
        --tag "$REPOSITORY_URI:$IMAGE_TAG" \
        --tag "$REPOSITORY_URI:latest" \
        --push .
    else
      BUILD_PROJECT="$(aws_cli cloudformation describe-stacks \
        --stack-name "$APP_REGISTRY_STACK" \
        --query 'Stacks[0].Outputs[?OutputKey==`BuildProjectName`].OutputValue | [0]' \
        --output text)"
      BUILD_ID="$(aws_cli codebuild start-build \
        --project-name "$BUILD_PROJECT" \
        --environment-variables-override \
          name=GIT_REF,value="$GIT_REF",type=PLAINTEXT \
          name=IMAGE_TAG,value="$IMAGE_TAG",type=PLAINTEXT \
        --query 'build.id' --output text)"
      while true; do
        BUILD_STATUS="$(aws_cli codebuild batch-get-builds --ids "$BUILD_ID" \
          --query 'builds[0].buildStatus' --output text)"
        case "$BUILD_STATUS" in
          SUCCEEDED)
            break
            ;;
          FAILED|FAULT|STOPPED|TIMED_OUT)
            aws_cli codebuild batch-get-builds --ids "$BUILD_ID" \
              --query 'builds[0].{status:buildStatus,phases:phases[*].{phase:phaseType,status:phaseStatus,contexts:contexts}}' \
              --output json >&2
            exit 1
            ;;
        esac
        echo "CodeBuild $BUILD_STATUS"
        sleep 5
      done
    fi
    echo "$REPOSITORY_URI:$IMAGE_TAG"
    ;;
  deploy)
    VPC_ID="${VPC_ID:-$(aws_cli ec2 describe-vpcs \
      --filters Name=is-default,Values=true \
      --query 'Vpcs[0].VpcId' --output text)}"
    SUBNET_TEXT="$(aws_cli ec2 describe-subnets \
      --filters Name=vpc-id,Values="$VPC_ID" Name=default-for-az,Values=true \
      --query 'sort_by(Subnets,&AvailabilityZone)[].SubnetId' --output text)"
    IFS=$'\t' read -r SUBNET_ONE SUBNET_TWO _ <<<"$SUBNET_TEXT"
    if [[ -z "$SUBNET_ONE" || -z "$SUBNET_TWO" ]]; then
      echo "At least two default public subnets are required for the ALB." >&2
      exit 1
    fi
    ALB_SUBNETS="$SUBNET_ONE,$SUBNET_TWO"
    COLLECTION_NAME="${OPENSEARCH_COLLECTION_NAME:-docsmind-dev}"
    COLLECTION_JSON="$(aws_cli opensearchserverless batch-get-collection \
      --names "$COLLECTION_NAME" --output json)"
    COLLECTION_ARN="$(jq -r '.collectionDetails[0].arn // empty' <<<"$COLLECTION_JSON")"
    COLLECTION_ENDPOINT="$(jq -r '.collectionDetails[0].collectionEndpoint // empty' <<<"$COLLECTION_JSON")"
    if [[ -z "$COLLECTION_ARN" || -z "$COLLECTION_ENDPOINT" ]]; then
      echo "OpenSearch collection $COLLECTION_NAME was not found." >&2
      exit 1
    fi
    IMAGE_TAG="${APP_IMAGE_TAG:-$(git rev-parse --short=12 HEAD)}"
    if [[ -n "${VLLM_BASE_URL:-}" ]]; then
      VLLM_BASE_URL_VALUE="$VLLM_BASE_URL"
    else
      VLLM_PUBLIC_IP="$(aws_cli ec2 describe-instances \
        --filters Name=tag:Name,Values=g6-xlarge Name=instance-state-name,Values=running \
        --query 'Reservations[].Instances[].PublicIpAddress | [0]' --output text)"
      if [[ -z "$VLLM_PUBLIC_IP" || "$VLLM_PUBLIC_IP" == "None" ]]; then
        echo "No running g6-xlarge vLLM host was found. Set VLLM_BASE_URL explicitly." >&2
        exit 1
      fi
      VLLM_BASE_URL_VALUE="https://${VLLM_PUBLIC_IP//./-}.sslip.io/v1"
    fi
    aws_cli ecr describe-images --repository-name "$REPOSITORY_NAME" \
      --image-ids imageTag="$IMAGE_TAG" >/dev/null
    ALLOWED_CIDR="${APP_ALLOWED_CIDR:-$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')/32}"
    aws_cli cloudformation deploy \
      --stack-name "$EMBEDDING_STACK" \
      --template-file infra/aws/embedding-ecs.yaml \
      --capabilities CAPABILITY_NAMED_IAM \
      --parameter-overrides \
        VpcId="$VPC_ID" \
        SubnetId="$SUBNET_ONE" \
        PublicSubnetIds="$ALB_SUBNETS" \
        AllowedCidr="$ALLOWED_CIDR" \
        OpenSearchCollectionArn="$COLLECTION_ARN" \
        OpenSearchCollectionName="$COLLECTION_NAME" \
        OpenSearchEndpoint="$COLLECTION_ENDPOINT" \
        OpenSearchIndexName="${OPENSEARCH_INDEX_NAME:-docsmind-volkswagen-wikipedia-bge-m3-v1}" \
        AppImageRepository="$REPOSITORY_NAME" \
        AppImageTag="$IMAGE_TAG" \
        VllmBaseUrl="$VLLM_BASE_URL_VALUE" \
        VllmModel="${VLLM_MODEL:-openclaw}" \
        InstanceType="${EMBEDDING_INSTANCE_TYPE:-m7i.large}" \
        DesiredCapacity="${APP_DEPLOY_DESIRED_CAPACITY:-0}" \
      --tags Project=DocsMind Environment=development
    aws_cli cloudformation describe-stacks --stack-name "$EMBEDDING_STACK" \
      --query 'Stacks[0].Outputs[?OutputKey==`AppUrl` || OutputKey==`VllmApiKeySecretArn`].[OutputKey,OutputValue]' \
      --output table
    ;;
  secret)
    if [[ -t 0 ]]; then
      echo "Pipe the vLLM API key to this command; it is not accepted as an argument." >&2
      exit 2
    fi
    # SSH and command-line producers commonly append one newline. Header values
    # cannot contain CR/LF, so normalize transport line endings before storage
    # without ever holding or printing the key in a shell variable.
    tr -d '\r\n' | aws_cli secretsmanager put-secret-value \
        --secret-id docsmind/vllm-api-key \
        --secret-string file:///dev/stdin \
        --query 'ARN' --output text
    ;;
  start)
    aws_cli autoscaling update-auto-scaling-group \
      --auto-scaling-group-name "$ASG_NAME" --min-size 0 --max-size 1 --desired-capacity 1
    aws_cli ecs update-service \
      --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" --desired-count 1 \
      --force-new-deployment \
      --query 'service.{desired:desiredCount,status:status}' --output json
    ;;
  stop)
    aws_cli ecs update-service \
      --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" --desired-count 0 \
      --query 'service.{desired:desiredCount,status:status}' --output json
    aws_cli ecs wait services-stable --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME"
    aws_cli autoscaling update-auto-scaling-group \
      --auto-scaling-group-name "$ASG_NAME" --min-size 0 --max-size 1 --desired-capacity 0
    ;;
  status)
    aws_cli ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
      --query 'services[0].{status:status,desired:desiredCount,running:runningCount,pending:pendingCount,taskDefinition:taskDefinition,events:events[0:5].[createdAt,message]}' \
      --output json
    TARGET_GROUP_ARN="$(aws_cli cloudformation describe-stacks --stack-name "$EMBEDDING_STACK" \
      --query 'Stacks[0].Outputs[?OutputKey==`AppTargetGroupArn`].OutputValue | [0]' --output text)"
    aws_cli elbv2 describe-target-health --target-group-arn "$TARGET_GROUP_ARN" \
      --query 'TargetHealthDescriptions[].{target:Target.Id,state:TargetHealth.State,reason:TargetHealth.Reason}' \
      --output json
    aws_cli cloudformation describe-stacks --stack-name "$EMBEDDING_STACK" \
      --query 'Stacks[0].Outputs[?OutputKey==`AppUrl`].OutputValue | [0]' --output text
    ;;
  logs)
    aws_cli logs tail /ecs/docsmind-app-dev --follow --since 15m
    ;;
  *)
    echo "Usage: $0 {registry|build|deploy|secret|start|stop|status|logs}" >&2
    exit 2
    ;;
esac
