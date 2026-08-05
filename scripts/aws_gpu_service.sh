#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"
AWS_PROFILE_NAME="${AWS_PROFILE:-ml-prep-deploy}"
AWS_REGION_NAME="${AWS_REGION:-us-east-1}"
STACK_NAME="${AWS_GPU_STACK_NAME:-docsmind-gpu-dev}"
CLUSTER_NAME="docsmind-gpu-dev"
EMBEDDING_SERVICE_NAME="docsmind-app-embedding-gpu"
GENERATION_SERVICE_NAME="docsmind-vllm-gpu"
EMBEDDING_ASG_NAME="docsmind-embedding-gpu-dev"
GENERATION_ASG_NAME="docsmind-vllm-gpu-dev"

aws_cli() {
  aws --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION_NAME" "$@"
}

stack_output() {
  local output_key="$1"
  aws_cli cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey==\`$output_key\`].OutputValue | [0]" \
    --output text
}

deploy_stack() {
  local vpc_id subnet_text subnet_pairs subnet_one subnet_two
  local load_balancer_subnets
  local embedding_instance_type generation_instance_type generation_fallback_type
  local generation_second_fallback_type embedding_gpu_subnets generation_gpu_subnets
  local availability_zone subnet_id offering_count
  local collection_name collection_json collection_arn collection_endpoint
  local app_image_tag allowed_cidr secret_arn

  vpc_id="${VPC_ID:-$(aws_cli ec2 describe-vpcs \
    --filters Name=is-default,Values=true \
    --query 'Vpcs[0].VpcId' --output text)}"
  subnet_text="$(aws_cli ec2 describe-subnets \
    --filters Name=vpc-id,Values="$vpc_id" Name=default-for-az,Values=true \
    --query 'sort_by(Subnets,&AvailabilityZone)[].SubnetId' --output text)"
  subnet_pairs="$(aws_cli ec2 describe-subnets \
    --filters Name=vpc-id,Values="$vpc_id" Name=default-for-az,Values=true \
    --query 'sort_by(Subnets,&AvailabilityZone)[].[AvailabilityZone,SubnetId]' --output text)"
  IFS=$'\t' read -r subnet_one subnet_two _ <<<"$subnet_text"
  if [[ -z "$subnet_one" || -z "$subnet_two" ]]; then
    echo "At least two default public subnets are required for the ALBs." >&2
    exit 1
  fi
  load_balancer_subnets="$(tr '\t' ',' <<<"$subnet_text" | tr -d '\n')"
  embedding_instance_type="${EMBEDDING_GPU_INSTANCE_TYPE:-g4dn.xlarge}"
  generation_instance_type="${GENERATION_GPU_INSTANCE_TYPE:-g6.xlarge}"
  generation_fallback_type="${GENERATION_GPU_FALLBACK_INSTANCE_TYPE:-g6e.xlarge}"
  generation_second_fallback_type="${GENERATION_GPU_SECOND_FALLBACK_INSTANCE_TYPE:-g5.xlarge}"
  embedding_gpu_subnets=""
  generation_gpu_subnets=""
  while IFS=$'\t' read -r availability_zone subnet_id; do
    offering_count="$(aws_cli ec2 describe-instance-type-offerings \
      --location-type availability-zone \
      --filters Name=location,Values="$availability_zone" \
        Name=instance-type,Values="$embedding_instance_type" \
      --query 'length(InstanceTypeOfferings)' --output text)"
    if [[ "$offering_count" == "1" ]]; then
      embedding_gpu_subnets="${embedding_gpu_subnets:+$embedding_gpu_subnets,}$subnet_id"
    fi
    offering_count="$(aws_cli ec2 describe-instance-type-offerings \
      --location-type availability-zone \
      --filters Name=location,Values="$availability_zone" \
        Name=instance-type,Values="$generation_instance_type","$generation_fallback_type","$generation_second_fallback_type" \
      --query 'length(InstanceTypeOfferings)' --output text)"
    if [[ "$offering_count" == "3" ]]; then
      generation_gpu_subnets="${generation_gpu_subnets:+$generation_gpu_subnets,}$subnet_id"
    fi
  done <<<"$subnet_pairs"
  if [[ -z "$embedding_gpu_subnets" || -z "$generation_gpu_subnets" ]]; then
    echo "No compatible default subnets were found for the configured GPU instance types." >&2
    exit 1
  fi

  collection_name="${OPENSEARCH_COLLECTION_NAME:-docsmind-dev}"
  collection_json="$(aws_cli opensearchserverless batch-get-collection \
    --names "$collection_name" --output json)"
  collection_arn="$(jq -r '.collectionDetails[0].arn // empty' <<<"$collection_json")"
  collection_endpoint="$(jq -r '.collectionDetails[0].collectionEndpoint // empty' <<<"$collection_json")"
  if [[ -z "$collection_arn" || -z "$collection_endpoint" ]]; then
    echo "OpenSearch collection $collection_name was not found." >&2
    exit 1
  fi

  app_image_tag="${APP_IMAGE_TAG:-a9aa044cb5e2}"
  aws_cli ecr describe-images --repository-name "${APP_REPOSITORY_NAME:-docsmind-app}" \
    --image-ids imageTag="$app_image_tag" >/dev/null
  allowed_cidr="${APP_ALLOWED_CIDR:-$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')/32}"
  secret_arn="$(aws_cli secretsmanager describe-secret \
    --secret-id docsmind/vllm-api-key --query ARN --output text)"

  aws_cli cloudformation deploy \
    --stack-name "$STACK_NAME" \
    --template-file infra/aws/gpu-ecs.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
      VpcId="$vpc_id" \
      EmbeddingSubnetIds="$embedding_gpu_subnets" \
      GenerationSubnetIds="$generation_gpu_subnets" \
      LoadBalancerSubnetIds="$load_balancer_subnets" \
      AllowedCidr="$allowed_cidr" \
      EmbeddingDesiredCapacity="${GPU_EMBEDDING_DESIRED_CAPACITY:-0}" \
      GenerationDesiredCapacity="${GPU_GENERATION_DESIRED_CAPACITY:-0}" \
      EmbeddingInstanceType="$embedding_instance_type" \
      GenerationInstanceType="$generation_instance_type" \
      GenerationFallbackInstanceType="$generation_fallback_type" \
      GenerationSecondFallbackInstanceType="$generation_second_fallback_type" \
      AppImageRepository="${APP_REPOSITORY_NAME:-docsmind-app}" \
      AppImageTag="$app_image_tag" \
      VllmApiKeySecretArn="$secret_arn" \
      OpenSearchCollectionArn="$collection_arn" \
      OpenSearchCollectionName="$collection_name" \
      OpenSearchEndpoint="$collection_endpoint" \
      OpenSearchIndexName="${OPENSEARCH_INDEX_NAME:-docsmind-volkswagen-wikipedia-bge-m3-v1}" \
    --tags Project=DocsMind Environment=development

  aws_cli cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`AppUrl` || OutputKey==`InternalVllmBaseUrl` || OutputKey==`EmbeddingModel` || OutputKey==`GenerationModel`].[OutputKey,OutputValue]' \
    --output table
}

case "$ACTION" in
  deploy)
    deploy_stack
    ;;
  quota)
    aws_cli service-quotas get-service-quota \
      --service-code ec2 --quota-code L-DB2E81BA \
      --query 'Quota.{Name:QuotaName,Value:Value,Adjustable:Adjustable}' --output json
    aws_cli service-quotas list-requested-service-quota-change-history-by-quota \
      --service-code ec2 --quota-code L-DB2E81BA \
      --query 'RequestedQuotas[0:5].{Id:Id,Desired:DesiredValue,Status:Status,Created:Created}' \
      --output json
    ;;
  start)
    aws_cli autoscaling update-auto-scaling-group \
      --auto-scaling-group-name "$GENERATION_ASG_NAME" \
      --min-size 0 --max-size 1 --desired-capacity 1
    aws_cli ecs update-service \
      --cluster "$CLUSTER_NAME" --service "$GENERATION_SERVICE_NAME" \
      --desired-count 1 --force-new-deployment \
      --query 'service.{service:serviceName,desired:desiredCount,status:status}' --output json
    aws_cli autoscaling update-auto-scaling-group \
      --auto-scaling-group-name "$EMBEDDING_ASG_NAME" \
      --min-size 0 --max-size 1 --desired-capacity 1
    aws_cli ecs update-service \
      --cluster "$CLUSTER_NAME" --service "$EMBEDDING_SERVICE_NAME" \
      --desired-count 1 --force-new-deployment \
      --query 'service.{service:serviceName,desired:desiredCount,status:status}' --output json
    ;;
  start-generation)
    aws_cli autoscaling update-auto-scaling-group \
      --auto-scaling-group-name "$GENERATION_ASG_NAME" \
      --min-size 0 --max-size 1 --desired-capacity 1
    aws_cli ecs update-service \
      --cluster "$CLUSTER_NAME" --service "$GENERATION_SERVICE_NAME" \
      --desired-count 1 --force-new-deployment \
      --query 'service.{service:serviceName,desired:desiredCount,status:status}' --output json
    ;;
  start-embedding)
    aws_cli autoscaling update-auto-scaling-group \
      --auto-scaling-group-name "$EMBEDDING_ASG_NAME" \
      --min-size 0 --max-size 1 --desired-capacity 1
    aws_cli ecs update-service \
      --cluster "$CLUSTER_NAME" --service "$EMBEDDING_SERVICE_NAME" \
      --desired-count 1 --force-new-deployment \
      --query 'service.{service:serviceName,desired:desiredCount,status:status}' --output json
    ;;
  stop)
    aws_cli ecs update-service \
      --cluster "$CLUSTER_NAME" --service "$EMBEDDING_SERVICE_NAME" \
      --desired-count 0 --query 'service.{service:serviceName,desired:desiredCount}' --output json
    aws_cli ecs update-service \
      --cluster "$CLUSTER_NAME" --service "$GENERATION_SERVICE_NAME" \
      --desired-count 0 --query 'service.{service:serviceName,desired:desiredCount}' --output json
    aws_cli ecs wait services-stable --cluster "$CLUSTER_NAME" \
      --services "$EMBEDDING_SERVICE_NAME" "$GENERATION_SERVICE_NAME"
    aws_cli autoscaling update-auto-scaling-group \
      --auto-scaling-group-name "$EMBEDDING_ASG_NAME" \
      --min-size 0 --max-size 1 --desired-capacity 0
    aws_cli autoscaling update-auto-scaling-group \
      --auto-scaling-group-name "$GENERATION_ASG_NAME" \
      --min-size 0 --max-size 1 --desired-capacity 0
    ;;
  status)
    aws_cli cloudformation describe-stacks --stack-name "$STACK_NAME" \
      --query 'Stacks[0].{status:StackStatus,outputs:Outputs}' --output json
    aws_cli ecs describe-services \
      --cluster "$CLUSTER_NAME" \
      --services "$EMBEDDING_SERVICE_NAME" "$GENERATION_SERVICE_NAME" \
      --query 'services[].{service:serviceName,status:status,desired:desiredCount,running:runningCount,pending:pendingCount,taskDefinition:taskDefinition,events:events[0:3].[createdAt,message]}' \
      --output json
    aws_cli autoscaling describe-auto-scaling-groups \
      --auto-scaling-group-names "$EMBEDDING_ASG_NAME" "$GENERATION_ASG_NAME" \
      --query 'AutoScalingGroups[].{name:AutoScalingGroupName,min:MinSize,max:MaxSize,desired:DesiredCapacity,instances:Instances[].{id:InstanceId,type:InstanceType,state:LifecycleState,health:HealthStatus}}' \
      --output json
    for target_group_key in PublicTargetGroupArn InternalTargetGroupArn; do
      target_group_arn="$(stack_output "$target_group_key")"
      aws_cli elbv2 describe-target-health --target-group-arn "$target_group_arn" \
        --query 'TargetHealthDescriptions[].{target:Target.Id,port:Target.Port,state:TargetHealth.State,reason:TargetHealth.Reason}' \
        --output json
    done
    ;;
  logs)
    echo "Embedding GPU logs"
    aws_cli logs tail /ecs/docsmind-embedding-gpu-dev --since 30m
    echo "Generation GPU logs"
    aws_cli logs tail /ecs/docsmind-vllm-gpu-dev --since 30m
    echo "Application logs"
    aws_cli logs tail /ecs/docsmind-app-gpu-dev --since 30m
    ;;
  *)
    echo "Usage: $0 {deploy|quota|start|start-generation|start-embedding|stop|status|logs}" >&2
    exit 2
    ;;
esac
