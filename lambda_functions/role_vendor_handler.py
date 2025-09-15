"""
Lambda function for handling role vending requests via API Gateway.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any

from src.iam_temprole_creator.models import RoleRequest, PermissionTier
from src.iam_temprole_creator.role_vendor import role_vendor
from src.iam_temprole_creator.config import settings


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for role vending API.
    
    Expected event structure:
    {
        "httpMethod": "POST",
        "path": "/request-role",
        "body": {
            "project_id": "string",
            "user_id": "string",
            "permission_tier": "string",
            "duration_hours": int,
            "reason": "string",
            "mfa_used": bool
        }
    }
    """
    
    try:
        # Parse request
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        body = json.loads(event.get('body', '{}'))
        
        # Route request
        if http_method == 'POST' and path == '/request-role':
            return handle_request_role(body, event)
        elif http_method == 'GET' and path.startswith('/sessions/'):
            return handle_get_session(path, event)
        elif http_method == 'DELETE' and path.startswith('/sessions/'):
            return handle_revoke_session(path, event)
        elif http_method == 'GET' and path == '/sessions':
            return handle_list_sessions(body, event)
        else:
            return create_response(404, {"error": "Not found"})
            
    except Exception as e:
        print(f"Error in lambda_handler: {e}")
        return create_response(500, {"error": "Internal server error"})


def handle_request_role(body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle role request."""
    try:
        # Validate required fields
        required_fields = ['project_id', 'user_id', 'permission_tier', 'reason']
        for field in required_fields:
            if field not in body:
                return create_response(400, {"error": f"Missing required field: {field}"})
        
        # Create role request
        request = RoleRequest(
            project_id=body['project_id'],
            user_id=body['user_id'],
            permission_tier=PermissionTier(body['permission_tier']),
            duration_hours=body.get('duration_hours', 4),
            reason=body['reason'],
            ip_address=event.get('requestContext', {}).get('identity', {}).get('sourceIp'),
            mfa_used=body.get('mfa_used', False)
        )
        
        # Request role
        session = role_vendor.request_role(request)
        
        if not session:
            return create_response(500, {"error": "Failed to create role session"})
        
        # Assume role to get credentials
        credentials = role_vendor.assume_role(session)
        
        if not credentials:
            return create_response(500, {"error": "Failed to assume role"})
        
        # Return response
        response_data = {
            "session_id": session.session_id,
            "project_id": session.project_id,
            "permission_tier": session.permission_tier.value,
            "expires_at": session.expires_at.isoformat(),
            "credentials": {
                "access_key_id": credentials.access_key_id,
                "secret_access_key": credentials.secret_access_key,
                "session_token": credentials.session_token,
                "expiration": credentials.expiration.isoformat()
            }
        }
        
        return create_response(200, response_data)
        
    except ValueError as e:
        return create_response(400, {"error": str(e)})
    except Exception as e:
        print(f"Error in handle_request_role: {e}")
        return create_response(500, {"error": "Internal server error"})


def handle_get_session(path: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get session status."""
    try:
        # Extract session ID from path
        path_parts = path.split('/')
        if len(path_parts) < 3:
            return create_response(400, {"error": "Invalid session path"})
        
        session_id = path_parts[2]
        project_id = event.get('queryStringParameters', {}).get('project_id')
        
        if not project_id:
            return create_response(400, {"error": "project_id query parameter required"})
        
        # Get session status
        status = role_vendor.get_session_status(project_id, session_id)
        
        if not status:
            return create_response(404, {"error": "Session not found"})
        
        return create_response(200, status)
        
    except Exception as e:
        print(f"Error in handle_get_session: {e}")
        return create_response(500, {"error": "Internal server error"})


def handle_revoke_session(path: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle revoke session."""
    try:
        # Extract session ID from path
        path_parts = path.split('/')
        if len(path_parts) < 3:
            return create_response(400, {"error": "Invalid session path"})
        
        session_id = path_parts[2]
        project_id = event.get('queryStringParameters', {}).get('project_id')
        
        if not project_id:
            return create_response(400, {"error": "project_id query parameter required"})
        
        # Revoke session
        success = role_vendor.revoke_session(project_id, session_id)
        
        if not success:
            return create_response(500, {"error": "Failed to revoke session"})
        
        return create_response(200, {"message": "Session revoked successfully"})
        
    except Exception as e:
        print(f"Error in handle_revoke_session: {e}")
        return create_response(500, {"error": "Internal server error"})


def handle_list_sessions(body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle list user sessions."""
    try:
        user_id = event.get('queryStringParameters', {}).get('user_id')
        status = event.get('queryStringParameters', {}).get('status')
        
        if not user_id:
            return create_response(400, {"error": "user_id query parameter required"})
        
        # List sessions
        sessions = role_vendor.list_user_sessions(user_id, status)
        
        return create_response(200, {"sessions": sessions})
        
    except Exception as e:
        print(f"Error in handle_list_sessions: {e}")
        return create_response(500, {"error": "Internal server error"})


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create API Gateway response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        },
        'body': json.dumps(body)
    }
