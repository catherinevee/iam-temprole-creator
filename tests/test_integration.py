"""
Integration tests for the IAM Role Vending Machine.
"""

import pytest
import json
from datetime import datetime, timedelta
from moto import mock_dynamodb, mock_s3, mock_iam, mock_sts

from src.iam_temprole_creator.role_vendor import RoleVendor
from src.iam_temprole_creator.database import DynamoDBManager
from src.iam_temprole_creator.models import RoleRequest, PermissionTier, SessionStatus


class TestIntegration:
    """Integration tests."""
    
    @pytest.fixture
    def setup_aws_resources(self):
        """Set up AWS resources for testing."""
        with mock_dynamodb(), mock_s3(), mock_iam(), mock_sts():
            # Create DynamoDB table
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = dynamodb.create_table(
                TableName='test-sessions',
                KeySchema=[
                    {'AttributeName': 'ProjectId', 'KeyType': 'HASH'},
                    {'AttributeName': 'SessionId', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'ProjectId', 'AttributeType': 'S'},
                    {'AttributeName': 'SessionId', 'AttributeType': 'S'},
                    {'AttributeName': 'UserId', 'AttributeType': 'S'},
                    {'AttributeName': 'ExpiresAt', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'UserIdIndex',
                        'KeySchema': [
                            {'AttributeName': 'UserId', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    },
                    {
                        'IndexName': 'ExpiresAtIndex',
                        'KeySchema': [
                            {'AttributeName': 'ExpiresAt', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            # Create S3 bucket
            s3 = boto3.client('s3', region_name='us-east-1')
            s3.create_bucket(Bucket='test-templates')
            
            # Upload policy template
            template = {
                "name": "read-only-template",
                "permission_tier": "read-only",
                "template_content": '{"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::${projectId}-*"}]}',
                "variables": ["projectId"],
                "version": "1.0"
            }
            s3.put_object(
                Bucket='test-templates',
                Key='templates/read-only.json',
                Body=json.dumps(template)
            )
            
            yield table, s3
    
    def test_end_to_end_role_request(self, setup_aws_resources):
        """Test complete role request flow."""
        table, s3 = setup_aws_resources
        
        # Create role vendor
        vendor = RoleVendor()
        
        # Create role request
        request = RoleRequest(
            project_id="test-project",
            user_id="test-user",
            permission_tier=PermissionTier.READ_ONLY,
            duration_hours=4,
            reason="Integration testing",
            mfa_used=True
        )
        
        # Request role
        session = vendor.request_role(request)
        
        # Verify session was created
        assert session is not None
        assert session.project_id == "test-project"
        assert session.user_id == "test-user"
        assert session.permission_tier == PermissionTier.READ_ONLY
        assert session.status == SessionStatus.ACTIVE
        
        # Verify session is in database
        db_manager = DynamoDBManager()
        stored_session = db_manager.get_session(session.project_id, session.session_id)
        assert stored_session is not None
        assert stored_session.user_id == "test-user"
    
    def test_session_cleanup(self, setup_aws_resources):
        """Test session cleanup functionality."""
        table, s3 = setup_aws_resources
        
        # Create expired session
        db_manager = DynamoDBManager()
        from src.iam_temprole_creator.models import RoleSession
        
        expired_session = RoleSession(
            project_id="test-project",
            user_id="test-user",
            role_arn="arn:aws:iam::123456789012:role/test-role",
            permission_tier=PermissionTier.READ_ONLY,
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        
        # Create session in database
        db_manager.create_session(expired_session)
        
        # Run cleanup
        vendor = RoleVendor()
        cleaned_count = vendor.cleanup_expired_sessions()
        
        # Verify cleanup
        assert cleaned_count == 1
        
        # Verify session status updated
        updated_session = db_manager.get_session(expired_session.project_id, expired_session.session_id)
        assert updated_session.status == SessionStatus.EXPIRED
