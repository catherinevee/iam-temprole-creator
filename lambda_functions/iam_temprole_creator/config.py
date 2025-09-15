"""
Configuration management for the IAM Role Vending Machine.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings."""
    
    # AWS Configuration
    aws_region: str = Field(default="us-east-1", description="AWS region")
    aws_account_id: Optional[str] = Field(default=None, description="AWS account ID")
    
    # DynamoDB Configuration
    dynamodb_table_name: str = Field(default="iam-role-sessions", description="DynamoDB table name")
    dynamodb_region: str = Field(default="us-east-1", description="DynamoDB region")
    
    # S3 Configuration
    policy_templates_bucket: str = Field(default="iam-role-templates", description="S3 bucket for policy templates")
    
    # Security Configuration
    mfa_required: bool = Field(default=True, description="Require MFA for all role assumptions")
    max_session_duration: int = Field(default=3600, description="Maximum session duration in seconds")
    allowed_ip_ranges: List[str] = Field(
        default=["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
        description="Allowed IP ranges for role assumption"
    )
    allowed_departments: List[str] = Field(
        default=["Engineering", "DevOps", "Security"],
        description="Allowed departments for role assumption"
    )
    
    # API Configuration
    api_gateway_stage: str = Field(default="prod", description="API Gateway stage")
    rate_limit_per_minute: int = Field(default=100, description="Rate limit per user per minute")
    
    # Monitoring Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    enable_cloudtrail: bool = Field(default=True, description="Enable CloudTrail logging")
    
    # Break-glass Configuration
    break_glass_role_arn: Optional[str] = Field(default=None, description="Break-glass role ARN")
    break_glass_notification_topic: Optional[str] = Field(default=None, description="SNS topic for break-glass notifications")
    
    # Cleanup Configuration
    cleanup_interval_hours: int = Field(default=1, description="Cleanup interval in hours")
    session_cleanup_delay_hours: int = Field(default=24, description="Delay before cleaning up expired sessions")
    
    class Config:
        env_prefix = "IAM_ROLE_"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_trust_policy_arn(account_id: str) -> str:
    """Get the trust policy ARN for a given account."""
    return f"arn:aws:iam::{account_id}:root"


def get_role_arn(account_id: str, role_name: str) -> str:
    """Get the role ARN for a given account and role name."""
    return f"arn:aws:iam::{account_id}:role/{role_name}"


def get_external_id(project_id: str, user_id: str) -> str:
    """Generate a unique external ID for cross-account access."""
    import hashlib
    import time
    
    # Create a deterministic but unique external ID
    data = f"{project_id}:{user_id}:{int(time.time() // 3600)}"  # Changes every hour
    return hashlib.sha256(data.encode()).hexdigest()[:16]
