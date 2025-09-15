"""
Pytest configuration and fixtures.
"""

import pytest
import boto3
from moto import mock_dynamodb, mock_s3, mock_iam, mock_sts
from unittest.mock import patch

from src.iam_temprole_creator.models import RoleRequest, PermissionTier
from src.iam_temprole_creator.config import settings


@pytest.fixture
def mock_aws_services():
    """Mock AWS services for testing."""
    with mock_dynamodb(), mock_s3(), mock_iam(), mock_sts():
        yield


@pytest.fixture
def sample_role_request():
    """Create a sample role request for testing."""
    return RoleRequest(
        project_id="test-project",
        user_id="test-user",
        permission_tier=PermissionTier.READ_ONLY,
        duration_hours=4,
        reason="Testing the system",
        mfa_used=True
    )


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('src.iam_temprole_creator.config.settings') as mock_settings:
        mock_settings.aws_region = "us-east-1"
        mock_settings.aws_account_id = "123456789012"
        mock_settings.mfa_required = True
        mock_settings.allowed_ip_ranges = ["10.0.0.0/8", "172.16.0.0/12"]
        mock_settings.allowed_departments = ["Engineering", "DevOps"]
        mock_settings.dynamodb_table_name = "test-sessions"
        mock_settings.policy_templates_bucket = "test-templates"
        yield mock_settings
