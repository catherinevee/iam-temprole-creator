#!/usr/bin/env python3
"""
IAM Role Vending Machine - Complete Cleanup Script

This script completely removes all AWS resources created by the IAM Role Vending Machine.
It handles dependencies and ensures proper cleanup order.

Usage:
    python cleanup.py [--region REGION] [--dry-run] [--force]

Options:
    --region REGION    AWS region (default: us-east-1)
    --dry-run         Show what would be deleted without actually deleting
    --force           Skip confirmation prompts
"""

import argparse
import boto3
import json
import sys
import time
from typing import List, Dict, Any
from botocore.exceptions import ClientError, BotoCoreError


class IAMRoleVendorCleanup:
    """Complete cleanup for IAM Role Vending Machine resources."""
    
    def __init__(self, region: str = "us-east-1", dry_run: bool = False, force: bool = False):
        self.region = region
        self.dry_run = dry_run
        self.force = force
        self.session = boto3.Session(region_name=region)
        
        # Initialize AWS clients
        self.lambda_client = self.session.client('lambda')
        self.dynamodb = self.session.resource('dynamodb')
        self.apigateway = self.session.client('apigateway')
        self.iam = self.session.client('iam')
        self.events = self.session.client('events')
        self.logs = self.session.client('logs')
        self.sns = self.session.client('sns')
        self.s3 = self.session.client('s3')
        self.kms = self.session.client('kms')
        
        # Resource tracking
        self.deleted_resources = []
        self.failed_resources = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    def confirm(self, message: str) -> bool:
        """Ask for user confirmation unless force is enabled."""
        if self.force:
            return True
        response = input(f"{message} (y/N): ").lower().strip()
        return response in ['y', 'yes']
        
    def delete_lambda_functions(self):
        """Delete Lambda functions."""
        self.log("Deleting Lambda functions...")
        
        functions = [
            "iam-role-vendor-role-vendor",
            "iam-role-vendor-cleanup"
        ]
        
        for func_name in functions:
            try:
                if self.dry_run:
                    self.log(f"DRY RUN: Would delete Lambda function: {func_name}")
                    continue
                    
                self.lambda_client.delete_function(FunctionName=func_name)
                self.log(f"Deleted Lambda function: {func_name}")
                self.deleted_resources.append(f"Lambda:{func_name}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    self.log(f"Lambda function {func_name} not found (already deleted)")
                else:
                    self.log(f"Failed to delete Lambda function {func_name}: {e}", "ERROR")
                    self.failed_resources.append(f"Lambda:{func_name}")
                    
    def delete_dynamodb_tables(self):
        """Delete DynamoDB tables."""
        self.log("Deleting DynamoDB tables...")
        
        tables = [
            "iam-role-vendor-sessions",
            "iam-role-vendor-audit-logs"
        ]
        
        for table_name in tables:
            try:
                if self.dry_run:
                    self.log(f"DRY RUN: Would delete DynamoDB table: {table_name}")
                    continue
                    
                table = self.dynamodb.Table(table_name)
                table.delete()
                self.log(f"Deleted DynamoDB table: {table_name}")
                self.deleted_resources.append(f"DynamoDB:{table_name}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    self.log(f"DynamoDB table {table_name} not found (already deleted)")
                else:
                    self.log(f"Failed to delete DynamoDB table {table_name}: {e}", "ERROR")
                    self.failed_resources.append(f"DynamoDB:{table_name}")
                    
    def delete_api_gateway(self):
        """Delete API Gateway."""
        self.log("Deleting API Gateway...")
        
        try:
            # Find the API Gateway
            apis = self.apigateway.get_rest_apis()
            api_id = None
            
            for api in apis['items']:
                if 'iam-role-vendor' in api['name'].lower():
                    api_id = api['id']
                    break
                    
            if not api_id:
                self.log("API Gateway not found (already deleted)")
                return
                
            if self.dry_run:
                self.log(f"DRY RUN: Would delete API Gateway: {api_id}")
                return
                
            self.apigateway.delete_rest_api(restApiId=api_id)
            self.log(f"Deleted API Gateway: {api_id}")
            self.deleted_resources.append(f"APIGateway:{api_id}")
            
        except ClientError as e:
            self.log(f"Failed to delete API Gateway: {e}", "ERROR")
            self.failed_resources.append("APIGateway:unknown")
            
    def delete_iam_roles_and_policies(self):
        """Delete IAM roles and policies."""
        self.log("Deleting IAM roles and policies...")
        
        # Roles to delete
        roles = [
            "iam-role-vendor-lambda-role",
            "temp-role-test-project-742447d4",
            "temp-role-test-project-87962a1e"
        ]
        
        # Policies to delete
        policies = [
            "arn:aws:iam::025066254478:policy/iam-role-vendor-lambda-policy"
        ]
        
        # Delete roles
        for role_name in roles:
            try:
                if self.dry_run:
                    self.log(f"DRY RUN: Would delete IAM role: {role_name}")
                    continue
                    
                # Detach policies first
                attached_policies = self.iam.list_attached_role_policies(RoleName=role_name)
                for policy in attached_policies['AttachedPolicies']:
                    self.iam.detach_role_policy(
                        RoleName=role_name,
                        PolicyArn=policy['PolicyArn']
                    )
                    self.log(f"Detached policy {policy['PolicyName']} from role {role_name}")
                
                # Delete inline policies
                inline_policies = self.iam.list_role_policies(RoleName=role_name)
                for policy_name in inline_policies['PolicyNames']:
                    self.iam.delete_role_policy(
                        RoleName=role_name,
                        PolicyName=policy_name
                    )
                    self.log(f"Deleted inline policy {policy_name} from role {role_name}")
                
                # Delete the role
                self.iam.delete_role(RoleName=role_name)
                self.log(f"Deleted IAM role: {role_name}")
                self.deleted_resources.append(f"IAMRole:{role_name}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    self.log(f"IAM role {role_name} not found (already deleted)")
                else:
                    self.log(f"Failed to delete IAM role {role_name}: {e}", "ERROR")
                    self.failed_resources.append(f"IAMRole:{role_name}")
        
        # Delete policies
        for policy_arn in policies:
            try:
                if self.dry_run:
                    self.log(f"DRY RUN: Would delete IAM policy: {policy_arn}")
                    continue
                    
                self.iam.delete_policy(PolicyArn=policy_arn)
                self.log(f"Deleted IAM policy: {policy_arn}")
                self.deleted_resources.append(f"IAMPolicy:{policy_arn}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    self.log(f"IAM policy {policy_arn} not found (already deleted)")
                else:
                    self.log(f"Failed to delete IAM policy {policy_arn}: {e}", "ERROR")
                    self.failed_resources.append(f"IAMPolicy:{policy_arn}")
                    
    def delete_eventbridge_rules(self):
        """Delete EventBridge rules."""
        self.log("Deleting EventBridge rules...")
        
        rules = [
            "iam-role-vendor-cleanup-schedule"
        ]
        
        for rule_name in rules:
            try:
                if self.dry_run:
                    self.log(f"DRY RUN: Would delete EventBridge rule: {rule_name}")
                    continue
                    
                # Remove targets first
                targets = self.events.list_targets_by_rule(Rule=rule_name)
                if targets['Targets']:
                    target_ids = [target['Id'] for target in targets['Targets']]
                    self.events.remove_targets(Rule=rule_name, Ids=target_ids)
                    self.log(f"Removed targets from EventBridge rule: {rule_name}")
                
                # Delete the rule
                self.events.delete_rule(Name=rule_name)
                self.log(f"Deleted EventBridge rule: {rule_name}")
                self.deleted_resources.append(f"EventBridge:{rule_name}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    self.log(f"EventBridge rule {rule_name} not found (already deleted)")
                else:
                    self.log(f"Failed to delete EventBridge rule {rule_name}: {e}", "ERROR")
                    self.failed_resources.append(f"EventBridge:{rule_name}")
                    
    def delete_cloudwatch_logs(self):
        """Delete CloudWatch log groups."""
        self.log("Deleting CloudWatch log groups...")
        
        log_groups = [
            "/aws/lambda/iam-role-vendor-role-vendor",
            "/aws/lambda/iam-role-vendor-cleanup"
        ]
        
        for log_group_name in log_groups:
            try:
                if self.dry_run:
                    self.log(f"DRY RUN: Would delete CloudWatch log group: {log_group_name}")
                    continue
                    
                self.logs.delete_log_group(logGroupName=log_group_name)
                self.log(f"Deleted CloudWatch log group: {log_group_name}")
                self.deleted_resources.append(f"CloudWatchLogs:{log_group_name}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    self.log(f"CloudWatch log group {log_group_name} not found (already deleted)")
                else:
                    self.log(f"Failed to delete CloudWatch log group {log_group_name}: {e}", "ERROR")
                    self.failed_resources.append(f"CloudWatchLogs:{log_group_name}")
                    
    def delete_sns_topics(self):
        """Delete SNS topics."""
        self.log("Deleting SNS topics...")
        
        try:
            topics = self.sns.list_topics()
            for topic in topics['Topics']:
                topic_arn = topic['TopicArn']
                if 'iam-role-vendor' in topic_arn:
                    if self.dry_run:
                        self.log(f"DRY RUN: Would delete SNS topic: {topic_arn}")
                        continue
                        
                    self.sns.delete_topic(TopicArn=topic_arn)
                    self.log(f"Deleted SNS topic: {topic_arn}")
                    self.deleted_resources.append(f"SNS:{topic_arn}")
                    
        except ClientError as e:
            self.log(f"Failed to delete SNS topics: {e}", "ERROR")
            self.failed_resources.append("SNS:unknown")
            
    def delete_s3_buckets(self):
        """Delete S3 buckets."""
        self.log("Deleting S3 buckets...")
        
        buckets = [
            "iam-role-vendor-policy-templates-025066254478",
            "driftmgr-test-bucket-1755579790"
        ]
        
        for bucket_name in buckets:
            try:
                if self.dry_run:
                    self.log(f"DRY RUN: Would delete S3 bucket: {bucket_name}")
                    continue
                    
                # Delete all objects and versions
                self.s3.delete_objects(
                    Bucket=bucket_name,
                    Delete={
                        'Objects': [
                            {'Key': obj['Key'], 'VersionId': obj['VersionId']}
                            for obj in self.s3.list_object_versions(Bucket=bucket_name).get('Versions', [])
                        ]
                    }
                )
                
                # Delete delete markers
                delete_markers = self.s3.list_object_versions(Bucket=bucket_name).get('DeleteMarkers', [])
                if delete_markers:
                    self.s3.delete_objects(
                        Bucket=bucket_name,
                        Delete={
                            'Objects': [
                                {'Key': obj['Key'], 'VersionId': obj['VersionId']}
                                for obj in delete_markers
                            ]
                        }
                    )
                
                # Delete the bucket
                self.s3.delete_bucket(Bucket=bucket_name)
                self.log(f"Deleted S3 bucket: {bucket_name}")
                self.deleted_resources.append(f"S3:{bucket_name}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchBucket':
                    self.log(f"S3 bucket {bucket_name} not found (already deleted)")
                else:
                    self.log(f"Failed to delete S3 bucket {bucket_name}: {e}", "ERROR")
                    self.failed_resources.append(f"S3:{bucket_name}")
                    
    def delete_kms_keys(self):
        """Delete KMS keys (schedule for deletion)."""
        self.log("Scheduling KMS keys for deletion...")
        
        try:
            keys = self.kms.list_keys()
            for key in keys['Keys']:
                key_id = key['KeyId']
                
                # Get key details
                try:
                    key_details = self.kms.describe_key(KeyId=key_id)
                    key_description = key_details['KeyMetadata'].get('Description', '')
                    
                    # Only delete keys related to our project
                    if 'iam-role-vendor' in key_description.lower() or 'iam role vendor' in key_description.lower():
                        if self.dry_run:
                            self.log(f"DRY RUN: Would schedule KMS key for deletion: {key_id}")
                            continue
                            
                        self.kms.schedule_key_deletion(
                            KeyId=key_id,
                            PendingWindowInDays=7
                        )
                        self.log(f"Scheduled KMS key for deletion: {key_id}")
                        self.deleted_resources.append(f"KMS:{key_id}")
                        
                except ClientError as e:
                    if e.response['Error']['Code'] == 'AccessDenied':
                        self.log(f"Access denied for KMS key {key_id} (may be AWS-managed)")
                    else:
                        self.log(f"Failed to process KMS key {key_id}: {e}", "ERROR")
                        
        except ClientError as e:
            self.log(f"Failed to list KMS keys: {e}", "ERROR")
            
    def cleanup_all(self):
        """Perform complete cleanup."""
        self.log("Starting IAM Role Vending Machine cleanup...")
        
        if not self.dry_run and not self.force:
            if not self.confirm("This will delete ALL IAM Role Vending Machine resources. Continue?"):
                self.log("Cleanup cancelled by user")
                return
                
        # Cleanup order matters due to dependencies
        cleanup_steps = [
            ("Lambda Functions", self.delete_lambda_functions),
            ("EventBridge Rules", self.delete_eventbridge_rules),
            ("API Gateway", self.delete_api_gateway),
            ("DynamoDB Tables", self.delete_dynamodb_tables),
            ("CloudWatch Logs", self.delete_cloudwatch_logs),
            ("SNS Topics", self.delete_sns_topics),
            ("S3 Buckets", self.delete_s3_buckets),
            ("IAM Roles & Policies", self.delete_iam_roles_and_policies),
            ("KMS Keys", self.delete_kms_keys),
        ]
        
        for step_name, cleanup_func in cleanup_steps:
            self.log(f"Step: {step_name}")
            try:
                cleanup_func()
            except Exception as e:
                self.log(f"Error in {step_name}: {e}", "ERROR")
                self.failed_resources.append(f"{step_name}:{str(e)}")
                
        # Summary
        self.log("Cleanup Summary:")
        self.log(f"Successfully deleted: {len(self.deleted_resources)} resources")
        self.log(f"Failed to delete: {len(self.failed_resources)} resources")
        
        if self.deleted_resources:
            self.log("Deleted resources:")
            for resource in self.deleted_resources:
                self.log(f"  - {resource}")
                
        if self.failed_resources:
            self.log("Failed resources:")
            for resource in self.failed_resources:
                self.log(f"  - {resource}")
                
        if self.failed_resources:
            self.log("Some resources failed to delete. Check the logs above.", "WARNING")
            return 1
        else:
            self.log("All resources successfully deleted!")
            return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Cleanup IAM Role Vending Machine resources")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")
    
    args = parser.parse_args()
    
    cleanup = IAMRoleVendorCleanup(
        region=args.region,
        dry_run=args.dry_run,
        force=args.force
    )
    
    exit_code = cleanup.cleanup_all()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
