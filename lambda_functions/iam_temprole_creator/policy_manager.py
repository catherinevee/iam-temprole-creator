"""
Policy template management and generation for the IAM Role Vending Machine.
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from .models import PolicyTemplate, PermissionTier, TrustPolicy
from .config import settings


class PolicyManager:
    """Manages IAM policy templates and generation."""
    
    def __init__(self):
        """Initialize policy manager."""
        self.s3 = boto3.client('s3', region_name=settings.aws_region)
        self.iam = boto3.client('iam', region_name=settings.aws_region)
    
    def get_policy_template(self, permission_tier: PermissionTier) -> Optional[PolicyTemplate]:
        """Get policy template for a permission tier."""
        try:
            key = f"templates/{permission_tier.value}.json"
            response = self.s3.get_object(
                Bucket=settings.policy_templates_bucket,
                Key=key
            )
            
            template_data = json.loads(response['Body'].read().decode('utf-8'))
            return PolicyTemplate(**template_data)
        except ClientError as e:
            print(f"Error getting policy template: {e}")
            return None
    
    def generate_policy(self, template: PolicyTemplate, variables: Dict[str, Any]) -> str:
        """Generate IAM policy from template with variable substitution."""
        policy_content = template.template_content
        
        # Replace variables in the template
        for var_name, var_value in variables.items():
            placeholder = f"${{{var_name}}}"
            policy_content = policy_content.replace(placeholder, str(var_value))
        
        # Validate that all required variables are provided
        missing_vars = self._find_missing_variables(policy_content, variables)
        if missing_vars:
            raise ValueError(f"Missing required variables: {missing_vars}")
        
        return policy_content
    
    def create_trust_policy(self, external_id: str, allowed_departments: List[str], 
                           ip_ranges: List[str], mfa_required: bool = True) -> str:
        """Create trust policy for temporary role."""
        trust_policy = TrustPolicy.create_for_external_id(
            external_id=external_id,
            allowed_departments=allowed_departments,
            ip_ranges=ip_ranges,
            mfa_required=mfa_required
        )
        
        return json.dumps(trust_policy.dict(), indent=2)
    
    def create_permission_boundary(self, permission_tier: PermissionTier) -> str:
        """Create permission boundary policy based on tier."""
        boundary_policies = {
            PermissionTier.READ_ONLY: {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:ListBucket",
                            "ec2:Describe*",
                            "iam:Get*",
                            "iam:List*"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Deny",
                        "Action": [
                            "iam:*",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "ec2:Modify*",
                            "ec2:Create*",
                            "ec2:Delete*"
                        ],
                        "Resource": "*"
                    }
                ]
            },
            PermissionTier.DEVELOPER: {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:*",
                            "ec2:*",
                            "lambda:*",
                            "iam:Get*",
                            "iam:List*",
                            "iam:PassRole"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Deny",
                        "Action": [
                            "iam:CreateRole",
                            "iam:DeleteRole",
                            "iam:AttachRolePolicy",
                            "iam:DetachRolePolicy",
                            "iam:PutRolePolicy",
                            "iam:DeleteRolePolicy",
                            "kms:DeleteKey",
                            "kms:ScheduleKeyDeletion"
                        ],
                        "Resource": "*"
                    }
                ]
            },
            PermissionTier.ADMIN: {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "*",
                        "Resource": "*"
                    },
                    {
                        "Effect": "Deny",
                        "Action": [
                            "iam:DeleteAccountPasswordPolicy",
                            "iam:DeleteAccountAlias",
                            "iam:DeleteAccount",
                            "organizations:LeaveOrganization",
                            "organizations:DeleteOrganization"
                        ],
                        "Resource": "*"
                    }
                ]
            },
            PermissionTier.BREAK_GLASS: {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "*",
                        "Resource": "*"
                    }
                ]
            }
        }
        
        return json.dumps(boundary_policies[permission_tier], indent=2)
    
    def validate_policy(self, policy_json: str) -> bool:
        """Validate IAM policy JSON."""
        try:
            policy = json.loads(policy_json)
            
            # Basic validation
            if not isinstance(policy, dict):
                return False
            
            if 'Version' not in policy:
                return False
            
            if 'Statement' not in policy:
                return False
            
            if not isinstance(policy['Statement'], list):
                return False
            
            # Validate each statement
            for statement in policy['Statement']:
                if not isinstance(statement, dict):
                    return False
                
                required_fields = ['Effect', 'Action']
                if not all(field in statement for field in required_fields):
                    return False
                
                if statement['Effect'] not in ['Allow', 'Deny']:
                    return False
            
            return True
        except (json.JSONDecodeError, KeyError, TypeError):
            return False
    
    def _find_missing_variables(self, content: str, variables: Dict[str, Any]) -> List[str]:
        """Find missing variables in template content."""
        pattern = r'\$\{([^}]+)\}'
        matches = re.findall(pattern, content)
        return [var for var in matches if var not in variables]
    
    def upload_template(self, template: PolicyTemplate) -> bool:
        """Upload policy template to S3."""
        try:
            key = f"templates/{template.permission_tier.value}.json"
            
            self.s3.put_object(
                Bucket=settings.policy_templates_bucket,
                Key=key,
                Body=json.dumps(template.dict(), indent=2),
                ContentType='application/json'
            )
            return True
        except ClientError as e:
            print(f"Error uploading template: {e}")
            return False


# Default policy templates
DEFAULT_TEMPLATES = {
    PermissionTier.READ_ONLY: PolicyTemplate(
        name="read-only-template",
        permission_tier=PermissionTier.READ_ONLY,
        template_content="""{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::${projectId}-*",
                "arn:aws:s3:::${projectId}-*/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:Describe*",
                "iam:Get*",
                "iam:List*"
            ],
            "Resource": "*"
        }
    ]
}""",
        variables=["projectId"],
        version="1.0"
    ),
    PermissionTier.DEVELOPER: PolicyTemplate(
        name="developer-template",
        permission_tier=PermissionTier.DEVELOPER,
        template_content="""{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:*"
            ],
            "Resource": [
                "arn:aws:s3:::${projectId}-*",
                "arn:aws:s3:::${projectId}-*/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:*",
                "lambda:*",
                "iam:Get*",
                "iam:List*",
                "iam:PassRole"
            ],
            "Resource": "*"
        }
    ]
}""",
        variables=["projectId"],
        version="1.0"
    ),
    PermissionTier.ADMIN: PolicyTemplate(
        name="admin-template",
        permission_tier=PermissionTier.ADMIN,
        template_content="""{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "*",
            "Resource": "*"
        }
    ]
}""",
        variables=[],
        version="1.0"
    )
}


# Global policy manager instance
policy_manager = PolicyManager()
