# IAM Role Vending Machine Infrastructure - Simplified Version
# This Terraform configuration creates the AWS infrastructure for the IAM Role Vending Machine

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.31.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "iam-role-vendor"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "iam-role-vendor"
}

# Local values
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# KMS Key for encryption
resource "aws_kms_key" "main" {
  description             = "KMS key for IAM Role Vending Machine"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-kms-key"
  })
}

resource "aws_kms_alias" "main" {
  name          = "alias/${var.project_name}-key"
  target_key_id = aws_kms_key.main.key_id
}

# S3 Bucket for policy templates
resource "aws_s3_bucket" "policy_templates" {
  bucket = "${var.project_name}-policy-templates-${local.account_id}"
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-policy-templates"
  })
}

resource "aws_s3_bucket_versioning" "policy_templates" {
  bucket = aws_s3_bucket.policy_templates.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "policy_templates" {
  bucket = aws_s3_bucket.policy_templates.id
  
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.main.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "policy_templates" {
  bucket = aws_s3_bucket.policy_templates.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# DynamoDB Table for session tracking
resource "aws_dynamodb_table" "sessions" {
  name           = "${var.project_name}-sessions"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "ProjectId"
  range_key      = "SessionId"
  
  attribute {
    name = "ProjectId"
    type = "S"
  }
  
  attribute {
    name = "SessionId"
    type = "S"
  }
  
  attribute {
    name = "UserId"
    type = "S"
  }
  
  attribute {
    name = "ExpiresAt"
    type = "S"
  }
  
  # Global Secondary Index for user queries
  global_secondary_index {
    name     = "UserIdIndex"
    hash_key = "UserId"
    projection_type = "ALL"
  }
  
  # Global Secondary Index for cleanup operations
  global_secondary_index {
    name     = "ExpiresAtIndex"
    hash_key = "ExpiresAt"
    projection_type = "ALL"
  }
  
  # TTL for automatic cleanup
  ttl {
    attribute_name = "ExpiresAt"
    enabled        = true
  }
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-sessions"
  })
}

# DynamoDB Table for audit logs
resource "aws_dynamodb_table" "audit_logs" {
  name           = "${var.project_name}-audit-logs"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "timestamp"
  range_key      = "request_id"
  
  attribute {
    name = "timestamp"
    type = "S"
  }
  
  attribute {
    name = "request_id"
    type = "S"
  }
  
  # TTL for log retention (7 years)
  ttl {
    attribute_name = "timestamp"
    enabled        = true
  }
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-audit-logs"
  })
}

# IAM Role for Lambda functions
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# IAM Policy for Lambda functions
resource "aws_iam_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.sessions.arn,
          "${aws_dynamodb_table.sessions.arn}/index/*",
          aws_dynamodb_table.audit_logs.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.policy_templates.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:TagRole",
          "iam:UntagRole"
        ]
        Resource = "arn:aws:iam::${local.account_id}:role/temp-role-*"
      },
      {
        Effect = "Allow"
        Action = [
          "sts:AssumeRole"
        ]
        Resource = "arn:aws:iam::${local.account_id}:role/temp-role-*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.main.arn
      }
    ]
  })
  
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# SNS Topic for break-glass notifications
resource "aws_sns_topic" "break_glass" {
  name = "${var.project_name}-break-glass-alerts"
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-break-glass-alerts"
  })
}

# Lambda function for role vending
resource "aws_lambda_function" "role_vendor" {
  filename         = "../lambda_functions/role_vendor.zip"
  function_name    = "${var.project_name}-role-vendor"
  role            = aws_iam_role.lambda_role.arn
  handler         = "role_vendor_handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 30
  
  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.sessions.name
      POLICY_TEMPLATES_BUCKET = aws_s3_bucket.policy_templates.bucket
      AWS_ACCOUNT_ID = local.account_id
      REGION = local.region
    }
  }
  
  tags = local.common_tags
}

# Lambda function for cleanup
resource "aws_lambda_function" "cleanup" {
  filename         = "../lambda_functions/cleanup.zip"
  function_name    = "${var.project_name}-cleanup"
  role            = aws_iam_role.lambda_role.arn
  handler         = "cleanup_handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 60
  
  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.sessions.name
      AWS_ACCOUNT_ID = local.account_id
      REGION = local.region
    }
  }
  
  tags = local.common_tags
}

# EventBridge rule for cleanup schedule
resource "aws_cloudwatch_event_rule" "cleanup_schedule" {
  name                = "${var.project_name}-cleanup-schedule"
  description         = "Trigger cleanup function every hour"
  schedule_expression = "rate(1 hour)"
  
  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "cleanup_target" {
  rule      = aws_cloudwatch_event_rule.cleanup_schedule.name
  target_id = "CleanupTarget"
  arn       = aws_lambda_function.cleanup.arn
}

resource "aws_lambda_permission" "allow_eventbridge_cleanup" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cleanup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.cleanup_schedule.arn
}

# API Gateway
resource "aws_api_gateway_rest_api" "main" {
  name        = "${var.project_name}-api"
  description = "IAM Role Vending Machine API"
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }
  
  tags = local.common_tags
}

# API Gateway Lambda integration
resource "aws_api_gateway_resource" "sessions" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "sessions"
}

resource "aws_api_gateway_resource" "session_id" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.sessions.id
  path_part   = "{session_id}"
}

# API Gateway methods
resource "aws_api_gateway_method" "request_role" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_rest_api.main.root_resource_id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "get_session" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.session_id.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "revoke_session" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.session_id.id
  http_method   = "DELETE"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "list_sessions" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.sessions.id
  http_method   = "GET"
  authorization = "NONE"
}

# Lambda integrations
resource "aws_api_gateway_integration" "request_role" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_method.request_role.resource_id
  http_method = aws_api_gateway_method.request_role.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.role_vendor.invoke_arn
}

resource "aws_api_gateway_integration" "get_session" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_method.get_session.resource_id
  http_method = aws_api_gateway_method.get_session.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.role_vendor.invoke_arn
}

resource "aws_api_gateway_integration" "revoke_session" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_method.revoke_session.resource_id
  http_method = aws_api_gateway_method.revoke_session.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.role_vendor.invoke_arn
}

resource "aws_api_gateway_integration" "list_sessions" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_method.list_sessions.resource_id
  http_method = aws_api_gateway_method.list_sessions.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.role_vendor.invoke_arn
}

# Lambda permissions for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.role_vendor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# API Gateway deployment
resource "aws_api_gateway_deployment" "main" {
  depends_on = [
    aws_api_gateway_integration.request_role,
    aws_api_gateway_integration.get_session,
    aws_api_gateway_integration.revoke_session,
    aws_api_gateway_integration.list_sessions
  ]
  
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = var.environment
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "role_vendor" {
  name              = "/aws/lambda/${aws_lambda_function.role_vendor.function_name}"
  retention_in_days = 30
  
  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "cleanup" {
  name              = "/aws/lambda/${aws_lambda_function.cleanup.function_name}"
  retention_in_days = 30
  
  tags = local.common_tags
}

# Outputs
output "api_gateway_url" {
  description = "API Gateway URL"
  value       = aws_api_gateway_deployment.main.invoke_url
}

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.sessions.name
}

output "policy_templates_bucket" {
  description = "S3 bucket for policy templates"
  value       = aws_s3_bucket.policy_templates.bucket
}

output "kms_key_id" {
  description = "KMS key ID"
  value       = aws_kms_key.main.key_id
}

output "break_glass_topic_arn" {
  description = "SNS topic ARN for break-glass notifications"
  value       = aws_sns_topic.break_glass.arn
}
