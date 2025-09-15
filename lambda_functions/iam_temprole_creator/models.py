"""
Data models for the IAM Role Vending Machine.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class PermissionTier(str, Enum):
    """Available permission tiers for temporary roles."""
    READ_ONLY = "read-only"
    DEVELOPER = "developer"
    ADMIN = "admin"
    BREAK_GLASS = "break-glass"


class SessionStatus(str, Enum):
    """Status of a temporary role session."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    FAILED = "FAILED"


class RoleRequest(BaseModel):
    """Request for a temporary IAM role."""
    project_id: str = Field(..., description="Project identifier")
    user_id: str = Field(..., description="User requesting the role")
    permission_tier: PermissionTier = Field(..., description="Requested permission tier")
    duration_hours: int = Field(..., ge=1, le=36, description="Session duration in hours")
    reason: str = Field(..., min_length=10, description="Business justification for access")
    ip_address: Optional[str] = Field(None, description="Source IP address")
    mfa_used: bool = Field(False, description="Whether MFA was used for authentication")
    external_id: Optional[str] = Field(None, description="External ID for cross-account access")
    
    @validator('duration_hours')
    def validate_duration(cls, v, values):
        """Validate duration based on permission tier."""
        permission_tier = values.get('permission_tier')
        if permission_tier == PermissionTier.BREAK_GLASS and v > 1:
            raise ValueError("Break-glass access limited to 1 hour maximum")
        if permission_tier == PermissionTier.ADMIN and v > 8:
            raise ValueError("Admin access limited to 8 hours maximum")
        return v


class RoleSession(BaseModel):
    """Temporary role session record."""
    project_id: str = Field(..., description="Project identifier")
    session_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique session ID")
    user_id: str = Field(..., description="User who requested the role")
    role_arn: str = Field(..., description="ARN of the temporary role")
    permission_tier: PermissionTier = Field(..., description="Permission tier granted")
    requested_at: datetime = Field(default_factory=datetime.utcnow, description="When role was requested")
    expires_at: datetime = Field(..., description="When role expires")
    status: SessionStatus = Field(default=SessionStatus.PENDING, description="Current session status")
    request_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional request metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Credentials(BaseModel):
    """Temporary AWS credentials."""
    access_key_id: str = Field(..., description="AWS Access Key ID")
    secret_access_key: str = Field(..., description="AWS Secret Access Key")
    session_token: str = Field(..., description="AWS Session Token")
    expiration: datetime = Field(..., description="When credentials expire")
    role_arn: str = Field(..., description="ARN of the assumed role")
    session_name: str = Field(..., description="Name of the session")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PolicyTemplate(BaseModel):
    """IAM policy template."""
    name: str = Field(..., description="Template name")
    permission_tier: PermissionTier = Field(..., description="Associated permission tier")
    template_content: str = Field(..., description="Policy template content")
    variables: List[str] = Field(default_factory=list, description="Required template variables")
    version: str = Field(default="1.0", description="Template version")


class TrustPolicy(BaseModel):
    """Trust policy for temporary roles."""
    version: str = Field(default="2012-10-17", description="Policy version")
    statement: List[Dict[str, Any]] = Field(..., description="Trust policy statements")
    
    @classmethod
    def create_for_external_id(cls, external_id: str, allowed_departments: List[str], 
                             ip_ranges: List[str], mfa_required: bool = True) -> "TrustPolicy":
        """Create a trust policy with external ID and conditions."""
        conditions = {
            "StringEquals": {
                "sts:ExternalId": external_id,
                "aws:PrincipalTag/Department": allowed_departments
            },
            "IpAddress": {
                "aws:SourceIp": ip_ranges
            }
        }
        
        if mfa_required:
            conditions["NumericLessThan"] = {
                "aws:MultiFactorAuthAge": "3600"
            }
        
        return cls(
            statement=[{
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::ACCOUNT:root"},
                "Action": "sts:AssumeRole",
                "Condition": conditions
            }]
        )


class AuditLog(BaseModel):
    """Audit log entry."""
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Log timestamp")
    request_id: str = Field(default_factory=lambda: str(uuid4()), description="Request ID")
    user_id: str = Field(..., description="User ID")
    action: str = Field(..., description="Action performed")
    permission_tier: Optional[PermissionTier] = Field(None, description="Permission tier")
    session_duration: Optional[int] = Field(None, description="Session duration in seconds")
    source_ip: Optional[str] = Field(None, description="Source IP address")
    mfa_used: bool = Field(False, description="Whether MFA was used")
    result: str = Field(..., description="Result of the action")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if failed")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
