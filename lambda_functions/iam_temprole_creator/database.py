"""
DynamoDB operations for the IAM Role Vending Machine.
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from .models import RoleSession, SessionStatus, AuditLog
from .config import settings


class DynamoDBManager:
    """Manages DynamoDB operations for role sessions."""
    
    def __init__(self):
        """Initialize DynamoDB client."""
        self.dynamodb = boto3.resource('dynamodb', region_name=settings.dynamodb_region)
        self.table = self.dynamodb.Table(settings.dynamodb_table_name)
    
    def create_session(self, session: RoleSession) -> bool:
        """Create a new role session record."""
        try:
            # Convert datetime objects to ISO strings for DynamoDB
            item = session.dict()
            item['requested_at'] = session.requested_at.isoformat()
            item['expires_at'] = session.expires_at.isoformat()
            
            # Convert any Decimal values
            item = self._convert_decimals(item)
            
            self.table.put_item(Item=item)
            return True
        except ClientError as e:
            print(f"Error creating session: {e}")
            return False
    
    def get_session(self, project_id: str, session_id: str) -> Optional[RoleSession]:
        """Get a role session by project ID and session ID."""
        try:
            response = self.table.get_item(
                Key={
                    'ProjectId': project_id,
                    'SessionId': session_id
                }
            )
            
            if 'Item' in response:
                item = response['Item']
                return self._item_to_session(item)
            return None
        except ClientError as e:
            print(f"Error getting session: {e}")
            return None
    
    def update_session_status(self, project_id: str, session_id: str, 
                            status: SessionStatus, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update session status."""
        try:
            update_expression = "SET #status = :status"
            expression_attribute_names = {"#status": "Status"}
            expression_attribute_values = {":status": status.value}
            
            if metadata:
                update_expression += ", RequestMetadata = :metadata"
                expression_attribute_values[":metadata"] = metadata
            
            self.table.update_item(
                Key={
                    'ProjectId': project_id,
                    'SessionId': session_id
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
            return True
        except ClientError as e:
            print(f"Error updating session status: {e}")
            return False
    
    def get_user_sessions(self, user_id: str, status: Optional[SessionStatus] = None) -> List[RoleSession]:
        """Get all sessions for a user."""
        try:
            query_params = {
                'IndexName': 'UserIdIndex',
                'KeyConditionExpression': Key('UserId').eq(user_id)
            }
            
            if status:
                query_params['FilterExpression'] = Attr('Status').eq(status.value)
            
            response = self.table.query(**query_params)
            
            sessions = []
            for item in response.get('Items', []):
                session = self._item_to_session(item)
                if session:
                    sessions.append(session)
            
            return sessions
        except ClientError as e:
            print(f"Error getting user sessions: {e}")
            return []
    
    def get_expired_sessions(self) -> List[RoleSession]:
        """Get all expired sessions for cleanup."""
        try:
            current_time = datetime.utcnow().isoformat()
            
            response = self.table.query(
                IndexName='ExpiresAtIndex',
                KeyConditionExpression=Key('ExpiresAt').lt(current_time),
                FilterExpression=Attr('Status').ne(SessionStatus.EXPIRED.value)
            )
            
            sessions = []
            for item in response.get('Items', []):
                session = self._item_to_session(item)
                if session:
                    sessions.append(session)
            
            return sessions
        except ClientError as e:
            print(f"Error getting expired sessions: {e}")
            return []
    
    def delete_session(self, project_id: str, session_id: str) -> bool:
        """Delete a session record."""
        try:
            self.table.delete_item(
                Key={
                    'ProjectId': project_id,
                    'SessionId': session_id
                }
            )
            return True
        except ClientError as e:
            print(f"Error deleting session: {e}")
            return False
    
    def log_audit_event(self, audit_log: AuditLog) -> bool:
        """Log an audit event."""
        try:
            # Use a separate table for audit logs
            audit_table = self.dynamodb.Table(f"{settings.dynamodb_table_name}-audit")
            
            item = audit_log.dict()
            item['timestamp'] = audit_log.timestamp.isoformat()
            item = self._convert_decimals(item)
            
            audit_table.put_item(Item=item)
            return True
        except ClientError as e:
            print(f"Error logging audit event: {e}")
            return False
    
    def _item_to_session(self, item: Dict[str, Any]) -> Optional[RoleSession]:
        """Convert DynamoDB item to RoleSession object."""
        try:
            # Convert ISO strings back to datetime objects
            item['requested_at'] = datetime.fromisoformat(item['requested_at'].replace('Z', '+00:00'))
            item['expires_at'] = datetime.fromisoformat(item['expires_at'].replace('Z', '+00:00'))
            
            # Convert field names to match model
            field_mapping = {
                'ProjectId': 'project_id',
                'SessionId': 'session_id',
                'UserId': 'user_id',
                'RoleArn': 'role_arn',
                'PermissionTier': 'permission_tier',
                'RequestedAt': 'requested_at',
                'ExpiresAt': 'expires_at',
                'Status': 'status',
                'RequestMetadata': 'request_metadata'
            }
            
            mapped_item = {}
            for db_field, model_field in field_mapping.items():
                if db_field in item:
                    mapped_item[model_field] = item[db_field]
            
            return RoleSession(**mapped_item)
        except Exception as e:
            print(f"Error converting item to session: {e}")
            return None
    
    def _convert_decimals(self, obj):
        """Convert Decimal objects to int/float for JSON serialization."""
        if isinstance(obj, list):
            return [self._convert_decimals(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: self._convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, Decimal):
            return float(obj) if obj % 1 else int(obj)
        else:
            return obj


# Global database manager instance
db_manager = DynamoDBManager()
