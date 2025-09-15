# IAM Role Vending Machine - Complete Cleanup Script (PowerShell)
# This script completely removes all AWS resources created by the IAM Role Vending Machine

param(
    [string]$Region = "us-east-1",
    [switch]$DryRun = $false,
    [switch]$Force = $false
)

Write-Host "IAM Role Vending Machine Cleanup Script" -ForegroundColor Green
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "Dry Run: $DryRun" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green

# Function to log messages
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARNING" { "Yellow" }
        "SUCCESS" { "Green" }
        default { "White" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

# Function to execute AWS command
function Invoke-AWSCommand {
    param([string]$Command, [string]$Description)
    
    if ($DryRun) {
        Write-Log "DRY RUN: $Command" "WARNING"
        return
    }
    
    Write-Log "Executing: $Description"
    try {
        Invoke-Expression $Command
        Write-Log "Success: $Description" "SUCCESS"
    }
    catch {
        Write-Log "Error: $Description - $($_.Exception.Message)" "ERROR"
    }
}

# Function to handle confirmation
function Confirm-Action {
    param([string]$Message)
    
    if ($Force) {
        return $true
    }
    
    $response = Read-Host "$Message (y/N)"
    return $response -match "^[yY]"
}

Write-Log "Starting cleanup process..."

if (-not $DryRun -and -not $Force) {
    if (-not (Confirm-Action "This will delete ALL IAM Role Vending Machine resources. Continue?")) {
        Write-Log "Cleanup cancelled by user" "WARNING"
        exit 0
    }
}

# 1. Delete Lambda Functions
Write-Log "Deleting Lambda functions..."
Invoke-AWSCommand "aws lambda delete-function --function-name iam-role-vendor-role-vendor --region $Region" "Delete Lambda function: iam-role-vendor-role-vendor"
Invoke-AWSCommand "aws lambda delete-function --function-name iam-role-vendor-cleanup --region $Region" "Delete Lambda function: iam-role-vendor-cleanup"

# 2. Delete EventBridge Rules
Write-Log "Deleting EventBridge rules..."
Invoke-AWSCommand "aws events remove-targets --rule iam-role-vendor-cleanup-schedule --ids CleanupTarget --region $Region" "Remove EventBridge targets"
Invoke-AWSCommand "aws events delete-rule --name iam-role-vendor-cleanup-schedule --region $Region" "Delete EventBridge rule"

# 3. Delete API Gateway
Write-Log "Deleting API Gateway..."
try {
    $apiId = aws apigateway get-rest-apis --region $Region --query 'items[?contains(name, `iam-role-vendor`)].id' --output text 2>$null
    if ($apiId -and $apiId -ne "None") {
        Invoke-AWSCommand "aws apigateway delete-rest-api --rest-api-id $apiId --region $Region" "Delete API Gateway: $apiId"
    } else {
        Write-Log "API Gateway not found or already deleted"
    }
}
catch {
    Write-Log "Error checking API Gateway: $($_.Exception.Message)" "ERROR"
}

# 4. Delete DynamoDB Tables
Write-Log "Deleting DynamoDB tables..."
Invoke-AWSCommand "aws dynamodb delete-table --table-name iam-role-vendor-sessions --region $Region" "Delete DynamoDB table: iam-role-vendor-sessions"
Invoke-AWSCommand "aws dynamodb delete-table --table-name iam-role-vendor-audit-logs --region $Region" "Delete DynamoDB table: iam-role-vendor-audit-logs"

# 5. Delete CloudWatch Log Groups
Write-Log "Deleting CloudWatch log groups..."
Invoke-AWSCommand "aws logs delete-log-group --log-group-name /aws/lambda/iam-role-vendor-role-vendor --region $Region" "Delete CloudWatch log group: /aws/lambda/iam-role-vendor-role-vendor"
Invoke-AWSCommand "aws logs delete-log-group --log-group-name /aws/lambda/iam-role-vendor-cleanup --region $Region" "Delete CloudWatch log group: /aws/lambda/iam-role-vendor-cleanup"

# 6. Delete SNS Topics
Write-Log "Deleting SNS topics..."
try {
    $snsTopic = aws sns list-topics --region $Region --query 'Topics[?contains(TopicArn, `iam-role-vendor`)].TopicArn' --output text 2>$null
    if ($snsTopic -and $snsTopic -ne "None") {
        Invoke-AWSCommand "aws sns delete-topic --topic-arn $snsTopic --region $Region" "Delete SNS topic: $snsTopic"
    } else {
        Write-Log "SNS topic not found or already deleted"
    }
}
catch {
    Write-Log "Error checking SNS topics: $($_.Exception.Message)" "ERROR"
}

# 7. Delete S3 Buckets
Write-Log "Deleting S3 buckets..."
Invoke-AWSCommand "aws s3 rm s3://iam-role-vendor-policy-templates-025066254478 --recursive" "Delete S3 bucket contents"
Invoke-AWSCommand "aws s3api delete-bucket --bucket iam-role-vendor-policy-templates-025066254478 --region $Region" "Delete S3 bucket: iam-role-vendor-policy-templates-025066254478"

# 8. Delete IAM Roles and Policies
Write-Log "Deleting IAM roles and policies..."

# Detach policies from roles
Invoke-AWSCommand "aws iam detach-role-policy --role-name iam-role-vendor-lambda-role --policy-arn arn:aws:iam::025066254478:policy/iam-role-vendor-lambda-policy" "Detach policy from role"

# Delete roles
Invoke-AWSCommand "aws iam delete-role --role-name iam-role-vendor-lambda-role" "Delete IAM role: iam-role-vendor-lambda-role"
Invoke-AWSCommand "aws iam delete-role --role-name temp-role-test-project-742447d4" "Delete IAM role: temp-role-test-project-742447d4"
Invoke-AWSCommand "aws iam delete-role --role-name temp-role-test-project-87962a1e" "Delete IAM role: temp-role-test-project-87962a1e"

# Delete policies
Invoke-AWSCommand "aws iam delete-policy --policy-arn arn:aws:iam::025066254478:policy/iam-role-vendor-lambda-policy" "Delete IAM policy"

# 9. Schedule KMS Keys for Deletion
Write-Log "Scheduling KMS keys for deletion..."
try {
    $kmsKeys = aws kms list-keys --region $Region --query 'Keys[].KeyId' --output text 2>$null
    if ($kmsKeys) {
        foreach ($keyId in $kmsKeys.Split(" ")) {
            try {
                $keyDesc = aws kms describe-key --key-id $keyId --region $Region --query 'KeyMetadata.Description' --output text 2>$null
                if ($keyDesc -match "iam-role-vendor" -or $keyDesc -match "IAM Role Vending Machine") {
                    Invoke-AWSCommand "aws kms schedule-key-deletion --key-id $keyId --pending-window-in-days 7 --region $Region" "Schedule KMS key for deletion: $keyId"
                }
            }
            catch {
                Write-Log "Error processing KMS key $keyId: $($_.Exception.Message)" "ERROR"
            }
        }
    }
}
catch {
    Write-Log "Error listing KMS keys: $($_.Exception.Message)" "ERROR"
}

Write-Log "Cleanup process completed!" "SUCCESS"
Write-Log "Note: KMS keys are scheduled for deletion in 7 days" "WARNING"
Write-Log "Note: Some resources may take a few minutes to fully delete" "WARNING"

if ($DryRun) {
    Write-Log "This was a dry run - no resources were actually deleted" "WARNING"
}
