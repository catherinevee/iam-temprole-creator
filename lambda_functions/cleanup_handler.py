"""
Lambda function for cleaning up expired sessions.
"""

import json
from datetime import datetime
from typing import Dict, Any

from src.iam_temprole_creator.role_vendor import role_vendor


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for session cleanup.
    
    This function is triggered by EventBridge on a schedule
    to clean up expired sessions.
    """
    
    try:
        print(f"Starting cleanup at {datetime.utcnow().isoformat()}")
        
        # Clean up expired sessions
        cleaned_count = role_vendor.cleanup_expired_sessions()
        
        print(f"Cleaned up {cleaned_count} expired sessions")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Cleaned up {cleaned_count} expired sessions',
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error in cleanup handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'timestamp': datetime.utcnow().isoformat()
            })
        }
