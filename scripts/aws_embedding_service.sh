#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"
AWS_PROFILE_NAME="${AWS_PROFILE:-ml-prep-deploy}"
AWS_REGION_NAME="${AWS_REGION:-us-east-1}"
STACK_NAME="${AWS_STACK_NAME:-docsmind-embedding-dev}"
CLUSTER_NAME="docsmind-embedding-dev"
SERVICE_NAME="docsmind-embedding-cpu"
ASG_NAME="docsmind-embedding-dev"

aws_cli() {
  aws --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION_NAME" "$@"
}

instance_id() {
  aws_cli autoscaling describe-auto-scaling-groups \
    --auto-scaling-group-names "$ASG_NAME" \
    --query 'AutoScalingGroups[0].Instances[?LifecycleState==`InService`].InstanceId | [0]' \
    --output text
}

case "$ACTION" in
  deploy)
    CURRENT_STATUS="$(aws_cli cloudformation describe-stacks \
      --stack-name "$STACK_NAME" --query 'Stacks[0].StackStatus' --output text \
      2>/dev/null || true)"
    if [[ "$CURRENT_STATUS" == "ROLLBACK_COMPLETE" ]]; then
      aws_cli cloudformation delete-stack --stack-name "$STACK_NAME"
      aws_cli cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"
    fi
    VPC_ID="${VPC_ID:-$(aws_cli ec2 describe-vpcs \
      --filters Name=is-default,Values=true \
      --query 'Vpcs[0].VpcId' --output text)}"
    SUBNET_ID="${SUBNET_ID:-$(aws_cli ec2 describe-subnets \
      --filters Name=vpc-id,Values="$VPC_ID" Name=default-for-az,Values=true \
      --query 'sort_by(Subnets,&AvailabilityZone)[0].SubnetId' --output text)}"
    if [[ "$VPC_ID" == "None" || "$SUBNET_ID" == "None" ]]; then
      echo "A VPC and public subnet are required. Set VPC_ID and SUBNET_ID." >&2
      exit 1
    fi
    aws_cli cloudformation deploy \
      --stack-name "$STACK_NAME" \
      --template-file infra/aws/embedding-ecs.yaml \
      --capabilities CAPABILITY_NAMED_IAM \
      --parameter-overrides \
        VpcId="$VPC_ID" \
        SubnetId="$SUBNET_ID" \
        InstanceType="${EMBEDDING_INSTANCE_TYPE:-m7i.large}" \
        DesiredCapacity=1 \
      --tags Project=DocsMind Environment=development
    ;;
  status)
    aws_cli cloudformation describe-stacks \
      --stack-name "$STACK_NAME" \
      --query 'Stacks[0].{status:StackStatus,outputs:Outputs}' \
      --output json
    aws_cli ecs describe-services \
      --cluster "$CLUSTER_NAME" \
      --services "$SERVICE_NAME" \
      --query 'services[0].{status:status,desired:desiredCount,running:runningCount,pending:pendingCount,events:events[0:5].[createdAt,message]}' \
      --output json
    ;;
  start)
    aws_cli autoscaling update-auto-scaling-group \
      --auto-scaling-group-name "$ASG_NAME" --min-size 0 --max-size 1 --desired-capacity 1
    aws_cli ecs update-service \
      --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" --desired-count 1 \
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
  tunnel)
    TARGET_ID="$(instance_id)"
    if [[ -z "$TARGET_ID" || "$TARGET_ID" == "None" ]]; then
      echo "No running embedding EC2 instance was found." >&2
      exit 1
    fi
    aws_cli ssm start-session \
      --target "$TARGET_ID" \
      --document-name AWS-StartPortForwardingSession \
      --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
    ;;
  logs)
    aws_cli logs tail /ecs/docsmind-embedding-dev --follow --since 15m
    ;;
  *)
    echo "Usage: $0 {deploy|status|start|stop|tunnel|logs}" >&2
    exit 2
    ;;
esac
