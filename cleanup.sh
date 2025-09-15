#!/bin/bash
# IAM Role Vending Machine - Complete Cleanup Script
# This script completely removes all AWS resources created by the IAM Role Vending Machine

set -e

REGION=${1:-us-east-1}
DRY_RUN=${2:-false}

echo "IAM Role Vending Machine Cleanup Script"
echo "Region: $REGION"
echo "Dry Run: $DRY_RUN"
echo "========================================"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to execute command if not dry run
execute() {
    if [ "$DRY_RUN" = "true" ]; then
        log "DRY RUN: $1"
    else
        log "Executing: $1"
        eval "$1"
    fi
}

# Function to handle errors
handle_error() {
    log "ERROR: $1"
    if [ "$DRY_RUN" != "true" ]; then
        exit 1
    fi
}

log "Starting cleanup process..."

# 1. Delete Lambda Functions
log "Deleting Lambda functions..."
execute "aws lambda delete-function --function-name iam-role-vendor-role-vendor --region $REGION" || log "Lambda function iam-role-vendor-role-vendor not found or already deleted"
execute "aws lambda delete-function --function-name iam-role-vendor-cleanup --region $REGION" || log "Lambda function iam-role-vendor-cleanup not found or already deleted"

# 2. Delete EventBridge Rules
log "Deleting EventBridge rules..."
execute "aws events remove-targets --rule iam-role-vendor-cleanup-schedule --ids CleanupTarget --region $REGION" || log "No targets to remove from EventBridge rule"
execute "aws events delete-rule --name iam-role-vendor-cleanup-schedule --region $REGION" || log "EventBridge rule not found or already deleted"

# 3. Delete API Gateway
log "Deleting API Gateway..."
API_ID=$(aws apigateway get-rest-apis --region $REGION --query 'items[?contains(name, `iam-role-vendor`)].id' --output text)
if [ ! -z "$API_ID" ] && [ "$API_ID" != "None" ]; then
    execute "aws apigateway delete-rest-api --rest-api-id $API_ID --region $REGION"
else
    log "API Gateway not found or already deleted"
fi

# 4. Delete DynamoDB Tables
log "Deleting DynamoDB tables..."
execute "aws dynamodb delete-table --table-name iam-role-vendor-sessions --region $REGION" || log "DynamoDB table iam-role-vendor-sessions not found or already deleted"
execute "aws dynamodb delete-table --table-name iam-role-vendor-audit-logs --region $REGION" || log "DynamoDB table iam-role-vendor-audit-logs not found or already deleted"

# 5. Delete CloudWatch Log Groups
log "Deleting CloudWatch log groups..."
execute "aws logs delete-log-group --log-group-name /aws/lambda/iam-role-vendor-role-vendor --region $REGION" || log "CloudWatch log group not found or already deleted"
execute "aws logs delete-log-group --log-group-name /aws/lambda/iam-role-vendor-cleanup --region $REGION" || log "CloudWatch log group not found or already deleted"

# 6. Delete SNS Topics
log "Deleting SNS topics..."
SNS_TOPIC=$(aws sns list-topics --region $REGION --query 'Topics[?contains(TopicArn, `iam-role-vendor`)].TopicArn' --output text)
if [ ! -z "$SNS_TOPIC" ] && [ "$SNS_TOPIC" != "None" ]; then
    execute "aws sns delete-topic --topic-arn $SNS_TOPIC --region $REGION"
else
    log "SNS topic not found or already deleted"
fi

# 7. Delete S3 Buckets
log "Deleting S3 buckets..."
execute "aws s3 rm s3://iam-role-vendor-policy-templates-025066254478 --recursive" || log "S3 bucket contents not found or already deleted"
execute "aws s3api delete-bucket --bucket iam-role-vendor-policy-templates-025066254478 --region $REGION" || log "S3 bucket not found or already deleted"

# 8. Delete IAM Roles and Policies
log "Deleting IAM roles and policies..."

# Detach policies from roles
execute "aws iam detach-role-policy --role-name iam-role-vendor-lambda-role --policy-arn arn:aws:iam::025066254478:policy/iam-role-vendor-lambda-policy" || log "Policy not attached or role not found"

# Delete roles
execute "aws iam delete-role --role-name iam-role-vendor-lambda-role" || log "IAM role iam-role-vendor-lambda-role not found or already deleted"
execute "aws iam delete-role --role-name temp-role-test-project-742447d4" || log "IAM role temp-role-test-project-742447d4 not found or already deleted"
execute "aws iam delete-role --role-name temp-role-test-project-87962a1e" || log "IAM role temp-role-test-project-87962a1e not found or already deleted"

# Delete policies
execute "aws iam delete-policy --policy-arn arn:aws:iam::025066254478:policy/iam-role-vendor-lambda-policy" || log "IAM policy not found or already deleted"

# 9. Schedule KMS Keys for Deletion
log "Scheduling KMS keys for deletion..."
KMS_KEYS=$(aws kms list-keys --region $REGION --query 'Keys[].KeyId' --output text)
for key_id in $KMS_KEYS; do
    KEY_DESC=$(aws kms describe-key --key-id $key_id --region $REGION --query 'KeyMetadata.Description' --output text 2>/dev/null || echo "")
    if [[ "$KEY_DESC" == *"iam-role-vendor"* ]] || [[ "$KEY_DESC" == *"IAM Role Vending Machine"* ]]; then
        execute "aws kms schedule-key-deletion --key-id $key_id --pending-window-in-days 7 --region $REGION" || log "KMS key $key_id not found or already scheduled for deletion"
    fi
done

log "Cleanup process completed!"
log "Note: KMS keys are scheduled for deletion in 7 days"
log "Note: Some resources may take a few minutes to fully delete"

if [ "$DRY_RUN" = "true" ]; then
    log "This was a dry run - no resources were actually deleted"
fi
