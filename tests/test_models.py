"""
Tests for data models.
"""

import pytest
from datetime import datetime, timedelta
from src.iam_temprole_creator.models import (
    RoleRequest, RoleSession, PermissionTier, SessionStatus,
    Credentials, TrustPolicy, AuditLog
)


class TestRoleRequest:
    """Test RoleRequest model."""
    
    def test_valid_request(self):
        """Test valid role request creation."""
        request = RoleRequest(
            project_id="test-project",
            user_id="test-user",
            permission_tier=PermissionTier.READ_ONLY,
            duration_hours=4,
            reason="Testing the system"
        )
        
        assert request.project_id == "test-project"
        assert request.user_id == "test-user"
        assert request.permission_tier == PermissionTier.READ_ONLY
        assert request.duration_hours == 4
        assert request.reason == "Testing the system"
        assert request.mfa_used is False
    
    def test_invalid_duration(self):
        """Test invalid duration validation."""
        with pytest.raises(ValueError):
            RoleRequest(
                project_id="test-project",
                user_id="test-user",
                permission_tier=PermissionTier.READ_ONLY,
                duration_hours=0,
                reason="Testing the system"
            )
    
    def test_break_glass_duration_limit(self):
        """Test break-glass duration limit."""
        with pytest.raises(ValueError):
            RoleRequest(
                project_id="test-project",
                user_id="test-user",
                permission_tier=PermissionTier.BREAK_GLASS,
                duration_hours=2,
                reason="Testing the system"
            )
    
    def test_admin_duration_limit(self):
        """Test admin duration limit."""
        with pytest.raises(ValueError):
            RoleRequest(
                project_id="test-project",
                user_id="test-user",
                permission_tier=PermissionTier.ADMIN,
                duration_hours=10,
                reason="Testing the system"
            )
    
    def test_short_reason(self):
        """Test short reason validation."""
        with pytest.raises(ValueError):
            RoleRequest(
                project_id="test-project",
                user_id="test-user",
                permission_tier=PermissionTier.READ_ONLY,
                duration_hours=4,
                reason="Short"
            )


class TestRoleSession:
    """Test RoleSession model."""
    
    def test_session_creation(self):
        """Test session creation."""
        expires_at = datetime.utcnow() + timedelta(hours=4)
        session = RoleSession(
            project_id="test-project",
            user_id="test-user",
            role_arn="arn:aws:iam::123456789012:role/test-role",
            permission_tier=PermissionTier.READ_ONLY,
            expires_at=expires_at
        )
        
        assert session.project_id == "test-project"
        assert session.user_id == "test-user"
        assert session.permission_tier == PermissionTier.READ_ONLY
        assert session.status == SessionStatus.PENDING
        assert session.session_id is not None
        assert len(session.session_id) > 0


class TestCredentials:
    """Test Credentials model."""
    
    def test_credentials_creation(self):
        """Test credentials creation."""
        expiration = datetime.utcnow() + timedelta(hours=1)
        credentials = Credentials(
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            session_token="test-session-token",
            expiration=expiration,
            role_arn="arn:aws:iam::123456789012:role/test-role",
            session_name="test-session"
        )
        
        assert credentials.access_key_id == "AKIAIOSFODNN7EXAMPLE"
        assert credentials.secret_access_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert credentials.session_token == "test-session-token"
        assert credentials.role_arn == "arn:aws:iam::123456789012:role/test-role"
        assert credentials.session_name == "test-session"


class TestTrustPolicy:
    """Test TrustPolicy model."""
    
    def test_trust_policy_creation(self):
        """Test trust policy creation."""
        trust_policy = TrustPolicy.create_for_external_id(
            external_id="test-external-id",
            allowed_departments=["Engineering", "DevOps"],
            ip_ranges=["10.0.0.0/8", "172.16.0.0/12"],
            mfa_required=True
        )
        
        assert trust_policy.version == "2012-10-17"
        assert len(trust_policy.statement) == 1
        
        statement = trust_policy.statement[0]
        assert statement["Effect"] == "Allow"
        assert statement["Action"] == "sts:AssumeRole"
        assert "Condition" in statement
        
        conditions = statement["Condition"]
        assert conditions["StringEquals"]["sts:ExternalId"] == "test-external-id"
        assert "aws:PrincipalTag/Department" in conditions["StringEquals"]
        assert "aws:SourceIp" in conditions["IpAddress"]
        assert "aws:MultiFactorAuthAge" in conditions["NumericLessThan"]


class TestAuditLog:
    """Test AuditLog model."""
    
    def test_audit_log_creation(self):
        """Test audit log creation."""
        audit_log = AuditLog(
            user_id="test-user",
            action="ROLE_REQUESTED",
            permission_tier=PermissionTier.READ_ONLY,
            result="SUCCESS"
        )
        
        assert audit_log.user_id == "test-user"
        assert audit_log.action == "ROLE_REQUESTED"
        assert audit_log.permission_tier == PermissionTier.READ_ONLY
        assert audit_log.result == "SUCCESS"
        assert audit_log.timestamp is not None
        assert audit_log.request_id is not None
