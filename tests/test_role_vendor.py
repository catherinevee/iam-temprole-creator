"""
Tests for role vendor service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.iam_temprole_creator.models import (
    RoleRequest, PermissionTier, SessionStatus, RoleSession
)
from src.iam_temprole_creator.role_vendor import RoleVendor


class TestRoleVendor:
    """Test RoleVendor class."""
    
    @pytest.fixture
    def role_vendor(self):
        """Create RoleVendor instance for testing."""
        return RoleVendor()
    
    @pytest.fixture
    def sample_request(self):
        """Create sample role request."""
        return RoleRequest(
            project_id="test-project",
            user_id="test-user",
            permission_tier=PermissionTier.READ_ONLY,
            duration_hours=4,
            reason="Testing the system",
            mfa_used=True
        )
    
    @pytest.fixture
    def sample_session(self):
        """Create sample role session."""
        return RoleSession(
            project_id="test-project",
            user_id="test-user",
            role_arn="arn:aws:iam::123456789012:role/temp-role-test",
            permission_tier=PermissionTier.READ_ONLY,
            expires_at=datetime.utcnow() + timedelta(hours=4)
        )
    
    @patch('src.iam_temprole_creator.role_vendor.db_manager')
    @patch('src.iam_temprole_creator.role_vendor.policy_manager')
    def test_request_role_success(self, mock_policy_manager, mock_db_manager, 
                                 role_vendor, sample_request):
        """Test successful role request."""
        # Mock database operations
        mock_db_manager.create_session.return_value = True
        mock_db_manager.update_session_status.return_value = True
        
        # Mock policy manager
        mock_template = Mock()
        mock_template.template_content = '{"Version": "2012-10-17", "Statement": []}'
        mock_policy_manager.get_policy_template.return_value = mock_template
        mock_policy_manager.generate_policy.return_value = '{"Version": "2012-10-17", "Statement": []}'
        mock_policy_manager.create_trust_policy.return_value = '{"Version": "2012-10-17", "Statement": []}'
        mock_policy_manager.create_permission_boundary.return_value = '{"Version": "2012-10-17", "Statement": []}'
        
        # Mock IAM operations
        with patch.object(role_vendor.iam, 'create_role') as mock_create_role, \
             patch.object(role_vendor.iam, 'put_role_policy') as mock_put_policy:
            
            mock_create_role.return_value = {}
            mock_put_policy.return_value = {}
            
            # Test role request
            session = role_vendor.request_role(sample_request)
            
            # Assertions
            assert session is not None
            assert session.project_id == sample_request.project_id
            assert session.user_id == sample_request.user_id
            assert session.permission_tier == sample_request.permission_tier
            assert session.status == SessionStatus.ACTIVE
            
            # Verify database calls
            mock_db_manager.create_session.assert_called_once()
            mock_db_manager.update_session_status.assert_called()
    
    def test_validate_request_invalid_ip(self, role_vendor, sample_request):
        """Test request validation with invalid IP."""
        sample_request.ip_address = "192.168.1.1"  # Not in allowed ranges
        
        # Mock the IP validation
        with patch.object(role_vendor, '_is_ip_allowed', return_value=False):
            result = role_vendor._validate_request(sample_request)
            assert result is False
    
    def test_validate_request_mfa_required(self, role_vendor, sample_request):
        """Test request validation with MFA requirement."""
        sample_request.mfa_used = False
        
        with patch('src.iam_temprole_creator.role_vendor.settings') as mock_settings:
            mock_settings.mfa_required = True
            result = role_vendor._validate_request(sample_request)
            assert result is False
    
    @patch('src.iam_temprole_creator.role_vendor.db_manager')
    def test_get_session_status_success(self, mock_db_manager, role_vendor, sample_session):
        """Test successful session status retrieval."""
        mock_db_manager.get_session.return_value = sample_session
        
        status = role_vendor.get_session_status("test-project", "test-session-id")
        
        assert status is not None
        assert status["session_id"] == sample_session.session_id
        assert status["project_id"] == sample_session.project_id
        assert status["user_id"] == sample_session.user_id
        assert status["permission_tier"] == sample_session.permission_tier.value
        assert status["status"] == sample_session.status.value
    
    @patch('src.iam_temprole_creator.role_vendor.db_manager')
    def test_get_session_status_not_found(self, mock_db_manager, role_vendor):
        """Test session status retrieval when session not found."""
        mock_db_manager.get_session.return_value = None
        
        status = role_vendor.get_session_status("test-project", "nonexistent-session")
        
        assert status is None
    
    @patch('src.iam_temprole_creator.role_vendor.db_manager')
    def test_revoke_session_success(self, mock_db_manager, role_vendor, sample_session):
        """Test successful session revocation."""
        mock_db_manager.get_session.return_value = sample_session
        mock_db_manager.update_session_status.return_value = True
        
        result = role_vendor.revoke_session("test-project", "test-session-id")
        
        assert result is True
        mock_db_manager.update_session_status.assert_called_with(
            "test-project", "test-session-id", SessionStatus.REVOKED
        )
    
    @patch('src.iam_temprole_creator.role_vendor.db_manager')
    def test_revoke_session_not_found(self, mock_db_manager, role_vendor):
        """Test session revocation when session not found."""
        mock_db_manager.get_session.return_value = None
        
        result = role_vendor.revoke_session("test-project", "nonexistent-session")
        
        assert result is False
    
    @patch('src.iam_temprole_creator.role_vendor.db_manager')
    def test_list_user_sessions(self, mock_db_manager, role_vendor, sample_session):
        """Test listing user sessions."""
        mock_db_manager.get_user_sessions.return_value = [sample_session]
        
        sessions = role_vendor.list_user_sessions("test-user")
        
        assert len(sessions) == 1
        assert sessions[0]["user_id"] == "test-user"
        assert sessions[0]["session_id"] == sample_session.session_id
    
    @patch('src.iam_temprole_creator.role_vendor.db_manager')
    def test_cleanup_expired_sessions(self, mock_db_manager, role_vendor, sample_session):
        """Test cleanup of expired sessions."""
        # Make session expired
        sample_session.expires_at = datetime.utcnow() - timedelta(hours=1)
        mock_db_manager.get_expired_sessions.return_value = [sample_session]
        mock_db_manager.update_session_status.return_value = True
        
        cleaned_count = role_vendor.cleanup_expired_sessions()
        
        assert cleaned_count == 1
        mock_db_manager.update_session_status.assert_called_with(
            sample_session.project_id, sample_session.session_id, SessionStatus.EXPIRED
        )
    
    def test_is_ip_allowed_valid(self, role_vendor):
        """Test IP validation with valid IP."""
        with patch('src.iam_temprole_creator.role_vendor.settings') as mock_settings:
            mock_settings.allowed_ip_ranges = ["10.0.0.0/8", "172.16.0.0/12"]
            
            result = role_vendor._is_ip_allowed("10.1.1.1")
            assert result is True
    
    def test_is_ip_allowed_invalid(self, role_vendor):
        """Test IP validation with invalid IP."""
        with patch('src.iam_temprole_creator.role_vendor.settings') as mock_settings:
            mock_settings.allowed_ip_ranges = ["10.0.0.0/8", "172.16.0.0/12"]
            
            result = role_vendor._is_ip_allowed("192.168.1.1")
            assert result is False
    
    def test_is_ip_allowed_invalid_format(self, role_vendor):
        """Test IP validation with invalid IP format."""
        result = role_vendor._is_ip_allowed("invalid-ip")
        assert result is False
