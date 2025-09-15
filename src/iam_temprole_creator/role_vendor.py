"""
Core role vending service for the IAM Role Vending Machine.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import boto3
from botocore.exceptions import ClientError

from .models import (
    RoleRequest, RoleSession, Credentials, SessionStatus, 
    PermissionTier, AuditLog
)
from .config import settings, get_external_id, get_role_arn
from .database import db_manager
from .policy_manager import policy_manager


class RoleVendor:
    """Core service for vending temporary IAM roles."""
    
    def __init__(self):
        """Initialize role vendor."""
        self.sts = boto3.client('sts', region_name=settings.aws_region)
        self.iam = boto3.client('iam', region_name=settings.aws_region)
        self.sns = boto3.client('sns', region_name=settings.aws_region)
    
    def request_role(self, request: RoleRequest) -> Optional[RoleSession]:
        """Request a temporary IAM role."""
        try:
            # Validate request
            if not self._validate_request(request):
                return None
            
            # Generate external ID
            external_id = get_external_id(request.project_id, request.user_id)
            request.external_id = external_id
            
            # Create role session record
            session = self._create_session_record(request)
            if not session:
                return None
            
            # Create temporary IAM role
            role_arn = self._create_temporary_role(request, session.session_id)
            if not role_arn:
                db_manager.update_session_status(
                    session.project_id, session.session_id, SessionStatus.FAILED
                )
                return None
            
            # Update session with role ARN
            session.role_arn = role_arn
            session.status = SessionStatus.ACTIVE
            
            # Update database
            db_manager.update_session_status(
                session.project_id, session.session_id, SessionStatus.ACTIVE,
                {"role_arn": role_arn}
            )
            
            # Log audit event
            self._log_audit_event(
                user_id=request.user_id,
                action="ROLE_REQUESTED",
                permission_tier=request.permission_tier,
                result="SUCCESS",
                session_duration=request.duration_hours * 3600
            )
            
            return session
            
        except Exception as e:
            print(f"Error requesting role: {e}")
            self._log_audit_event(
                user_id=request.user_id,
                action="ROLE_REQUESTED",
                permission_tier=request.permission_tier,
                result="FAILURE",
                error_details={"error": str(e)}
            )
            return None
    
    def assume_role(self, session: RoleSession, session_name: Optional[str] = None) -> Optional[Credentials]:
        """Assume the temporary role and return credentials."""
        try:
            if session.status != SessionStatus.ACTIVE:
                raise ValueError("Session is not active")
            
            if datetime.utcnow() > session.expires_at:
                self._expire_session(session)
                raise ValueError("Session has expired")
            
            # Generate session name if not provided
            if not session_name:
                session_name = f"temp-role-{session.session_id[:8]}"
            
            # Assume role
            response = self.sts.assume_role(
                RoleArn=session.role_arn,
                RoleSessionName=session_name,
                DurationSeconds=min(3600, (session.expires_at - datetime.utcnow()).total_seconds()),
                ExternalId=session.request_metadata.get('external_id')
            )
            
            credentials = Credentials(
                access_key_id=response['Credentials']['AccessKeyId'],
                secret_access_key=response['Credentials']['SecretAccessKey'],
                session_token=response['Credentials']['SessionToken'],
                expiration=response['Credentials']['Expiration'],
                role_arn=session.role_arn,
                session_name=session_name
            )
            
            # Log successful assumption
            self._log_audit_event(
                user_id=session.user_id,
                action="ROLE_ASSUMED",
                permission_tier=session.permission_tier,
                result="SUCCESS"
            )
            
            return credentials
            
        except ClientError as e:
            print(f"Error assuming role: {e}")
            self._log_audit_event(
                user_id=session.user_id,
                action="ROLE_ASSUMED",
                permission_tier=session.permission_tier,
                result="FAILURE",
                error_details={"error": str(e)}
            )
            return None
        except Exception as e:
            print(f"Unexpected error assuming role: {e}")
            return None
    
    def revoke_session(self, project_id: str, session_id: str) -> bool:
        """Revoke a temporary role session."""
        try:
            session = db_manager.get_session(project_id, session_id)
            if not session:
                return False
            
            # Update session status
            success = db_manager.update_session_status(
                project_id, session_id, SessionStatus.REVOKED
            )
            
            if success:
                # Log revocation
                self._log_audit_event(
                    user_id=session.user_id,
                    action="ROLE_REVOKED",
                    permission_tier=session.permission_tier,
                    result="SUCCESS"
                )
                
                # Send notification if break-glass
                if session.permission_tier == PermissionTier.BREAK_GLASS:
                    self._send_break_glass_notification(session)
            
            return success
            
        except Exception as e:
            print(f"Error revoking session: {e}")
            return False
    
    def get_session_status(self, project_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a role session."""
        try:
            session = db_manager.get_session(project_id, session_id)
            if not session:
                return None
            
            return {
                "session_id": session.session_id,
                "project_id": session.project_id,
                "user_id": session.user_id,
                "permission_tier": session.permission_tier.value,
                "status": session.status.value,
                "requested_at": session.requested_at.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "time_remaining": max(0, (session.expires_at - datetime.utcnow()).total_seconds())
            }
            
        except Exception as e:
            print(f"Error getting session status: {e}")
            return None
    
    def list_user_sessions(self, user_id: str, status: Optional[SessionStatus] = None) -> List[Dict[str, Any]]:
        """List all sessions for a user."""
        try:
            sessions = db_manager.get_user_sessions(user_id, status)
            
            return [
                {
                    "session_id": session.session_id,
                    "project_id": session.project_id,
                    "permission_tier": session.permission_tier.value,
                    "status": session.status.value,
                    "requested_at": session.requested_at.isoformat(),
                    "expires_at": session.expires_at.isoformat(),
                    "time_remaining": max(0, (session.expires_at - datetime.utcnow()).total_seconds())
                }
                for session in sessions
            ]
            
        except Exception as e:
            print(f"Error listing user sessions: {e}")
            return []
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        try:
            expired_sessions = db_manager.get_expired_sessions()
            cleaned_count = 0
            
            for session in expired_sessions:
                # Update status to expired
                if db_manager.update_session_status(
                    session.project_id, session.session_id, SessionStatus.EXPIRED
                ):
                    cleaned_count += 1
                    
                    # Log expiration
                    self._log_audit_event(
                        user_id=session.user_id,
                        action="ROLE_EXPIRED",
                        permission_tier=session.permission_tier,
                        result="SUCCESS"
                    )
            
            return cleaned_count
            
        except Exception as e:
            print(f"Error cleaning up expired sessions: {e}")
            return 0
    
    def _validate_request(self, request: RoleRequest) -> bool:
        """Validate role request."""
        # Check IP restrictions
        if request.ip_address and not self._is_ip_allowed(request.ip_address):
            print(f"IP address {request.ip_address} not allowed")
            return False
        
        # Check MFA requirement
        if settings.mfa_required and not request.mfa_used:
            print("MFA required but not used")
            return False
        
        # Check duration limits
        if request.duration_hours > settings.max_session_duration // 3600:
            print(f"Duration {request.duration_hours} hours exceeds maximum")
            return False
        
        return True
    
    def _is_ip_allowed(self, ip_address: str) -> bool:
        """Check if IP address is in allowed ranges."""
        import ipaddress
        
        try:
            ip = ipaddress.ip_address(ip_address)
            for cidr in settings.allowed_ip_ranges:
                if ip in ipaddress.ip_network(cidr):
                    return True
            return False
        except ValueError:
            return False
    
    def _create_session_record(self, request: RoleRequest) -> Optional[RoleSession]:
        """Create session record in database."""
        try:
            expires_at = datetime.utcnow() + timedelta(hours=request.duration_hours)
            
            session = RoleSession(
                project_id=request.project_id,
                user_id=request.user_id,
                role_arn="",  # Will be updated after role creation
                permission_tier=request.permission_tier,
                expires_at=expires_at,
                request_metadata={
                    "external_id": request.external_id,
                    "ip_address": request.ip_address,
                    "mfa_used": request.mfa_used,
                    "reason": request.reason
                }
            )
            
            if db_manager.create_session(session):
                return session
            return None
            
        except Exception as e:
            print(f"Error creating session record: {e}")
            return None
    
    def _create_temporary_role(self, request: RoleRequest, session_id: str) -> Optional[str]:
        """Create temporary IAM role."""
        try:
            role_name = f"temp-role-{request.project_id}-{session_id[:8]}"
            
            # Get policy template
            template = policy_manager.get_policy_template(request.permission_tier)
            if not template:
                # Use default template
                template = policy_manager.DEFAULT_TEMPLATES.get(request.permission_tier)
                if not template:
                    raise ValueError(f"No template found for {request.permission_tier}")
            
            # Generate policy
            policy_variables = {
                "projectId": request.project_id,
                "userId": request.user_id,
                "sessionId": session_id
            }
            
            policy_document = policy_manager.generate_policy(template, policy_variables)
            
            # Create trust policy
            trust_policy = policy_manager.create_trust_policy(
                external_id=request.external_id,
                allowed_departments=settings.allowed_departments,
                ip_ranges=settings.allowed_ip_ranges,
                mfa_required=settings.mfa_required
            )
            
            # Create role
            self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=trust_policy,
                Description=f"Temporary role for {request.user_id} on project {request.project_id}",
                MaxSessionDuration=min(3600, request.duration_hours * 3600),
                Tags=[
                    {"Key": "Project", "Value": request.project_id},
                    {"Key": "User", "Value": request.user_id},
                    {"Key": "SessionId", "Value": session_id},
                    {"Key": "PermissionTier", "Value": request.permission_tier.value},
                    {"Key": "CreatedBy", "Value": "iam-role-vendor"},
                    {"Key": "ExpiresAt", "Value": (datetime.utcnow() + timedelta(hours=request.duration_hours)).isoformat()}
                ]
            )
            
            # Attach policy
            self.iam.put_role_policy(
                RoleName=role_name,
                PolicyName="TemporaryAccessPolicy",
                PolicyDocument=policy_document
            )
            
            return get_role_arn(settings.aws_account_id, role_name)
            
        except ClientError as e:
            print(f"Error creating temporary role: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error creating role: {e}")
            return None
    
    def _expire_session(self, session: RoleSession) -> None:
        """Mark session as expired."""
        db_manager.update_session_status(
            session.project_id, session.session_id, SessionStatus.EXPIRED
        )
    
    def _log_audit_event(self, user_id: str, action: str, permission_tier: PermissionTier,
                        result: str, session_duration: Optional[int] = None,
                        error_details: Optional[Dict[str, Any]] = None) -> None:
        """Log audit event."""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            permission_tier=permission_tier,
            session_duration=session_duration,
            result=result,
            error_details=error_details
        )
        
        db_manager.log_audit_event(audit_log)
    
    def _send_break_glass_notification(self, session: RoleSession) -> None:
        """Send notification for break-glass access."""
        if not settings.break_glass_notification_topic:
            return
        
        try:
            message = {
                "alert_type": "BREAK_GLASS_ACCESS",
                "user_id": session.user_id,
                "project_id": session.project_id,
                "session_id": session.session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "expires_at": session.expires_at.isoformat()
            }
            
            self.sns.publish(
                TopicArn=settings.break_glass_notification_topic,
                Message=json.dumps(message),
                Subject="Break-Glass Access Alert"
            )
        except Exception as e:
            print(f"Error sending break-glass notification: {e}")


# Global role vendor instance
role_vendor = RoleVendor()
