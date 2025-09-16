#!/usr/bin/env python3
"""
Create AWS Budget Alert for IAM Role Vending Machine
"""

import boto3
import json
from datetime import datetime

def create_budget_with_alert():
    """Create a budget with email alert for the IAM Role Vending Machine"""
    
    # Initialize AWS clients
    budgets_client = boto3.client('budgets')
    sts_client = boto3.client('sts')
    
    # Get account ID
    account_id = sts_client.get_caller_identity()['Account']
    
    print(f"Creating budget for AWS Account: {account_id}")
    
    # Define the budget
    budget = {
        'BudgetName': 'IAM-Role-Vendor-Monitoring',
        'BudgetLimit': {
            'Amount': '50',
            'Unit': 'USD'
        },
        'TimeUnit': 'MONTHLY',
        'BudgetType': 'COST',
        'CostFilters': {
            'Service': [
                'Amazon DynamoDB',
                'AWS Lambda',
                'Amazon API Gateway',
                'Amazon S3',
                'Amazon CloudWatch',
                'AWS KMS',
                'Amazon EventBridge (CloudWatch Events)'
            ]
        },
        'TimePeriod': {
            'Start': datetime(2025, 1, 1),
            'End': datetime(2087, 6, 15)
        }
    }
    
    try:
        # Create the budget
        print("Creating budget...")
        budgets_client.create_budget(
            AccountId=account_id,
            Budget=budget
        )
        print("✓ Budget created successfully!")
        
        # Define notification
        notification = {
            'NotificationType': 'ACTUAL',
            'ComparisonOperator': 'GREATER_THAN',
            'Threshold': 40.0,  # Alert at 40% of budget
            'ThresholdType': 'PERCENTAGE'
        }
        
        # Define subscribers
        subscribers = [
            {
                'SubscriptionType': 'EMAIL',
                'Address': 'catherine.vee@outlook.com'
            }
        ]
        
        # Create notification
        print("Creating email notification...")
        budgets_client.create_notification(
            AccountId=account_id,
            BudgetName='IAM-Role-Vendor-Monitoring',
            Notification=notification,
            Subscribers=subscribers
        )
        print("✓ Email notification created successfully!")
        
        # Create additional notification for 80% threshold
        notification_80 = {
            'NotificationType': 'ACTUAL',
            'ComparisonOperator': 'GREATER_THAN',
            'Threshold': 80.0,  # Alert at 80% of budget
            'ThresholdType': 'PERCENTAGE'
        }
        
        print("Creating 80% threshold notification...")
        budgets_client.create_notification(
            AccountId=account_id,
            BudgetName='IAM-Role-Vendor-Monitoring',
            Notification=notification_80,
            Subscribers=subscribers
        )
        print("✓ 80% threshold notification created successfully!")
        
        # Create forecasted spending alert
        notification_forecast = {
            'NotificationType': 'FORECASTED',
            'ComparisonOperator': 'GREATER_THAN',
            'Threshold': 100.0,  # Alert when forecasted to exceed 100% of budget
            'ThresholdType': 'PERCENTAGE'
        }
        
        print("Creating forecasted spending notification...")
        budgets_client.create_notification(
            AccountId=account_id,
            BudgetName='IAM-Role-Vendor-Monitoring',
            Notification=notification_forecast,
            Subscribers=subscribers
        )
        print("✓ Forecasted spending notification created successfully!")
        
        print("\n" + "="*60)
        print("BUDGET ALERT SETUP COMPLETE")
        print("="*60)
        print(f"Budget Name: IAM-Role-Vendor-Monitoring")
        print(f"Budget Limit: $50/month")
        print(f"Email Alerts: catherine.vee@outlook.com")
        print(f"Alert Thresholds:")
        print(f"  - 40% of budget ($20)")
        print(f"  - 80% of budget ($40)")
        print(f"  - Forecasted to exceed 100% ($50)")
        print(f"Services Monitored:")
        for service in budget['CostFilters']['Service']:
            print(f"  - {service}")
        print("="*60)
        
    except budgets_client.exceptions.DuplicateRecordException:
        print("⚠️  Budget already exists. Adding notifications to existing budget...")
        
        # Try to add notifications to existing budget
        notification = {
            'NotificationType': 'ACTUAL',
            'ComparisonOperator': 'GREATER_THAN',
            'Threshold': 40.0,
            'ThresholdType': 'PERCENTAGE'
        }
        
        subscribers = [
            {
                'SubscriptionType': 'EMAIL',
                'Address': 'catherine.vee@outlook.com'
            }
        ]
        
        try:
            budgets_client.create_notification(
                AccountId=account_id,
                BudgetName='IAM-Role-Vendor-Monitoring',
                Notification=notification,
                Subscribers=subscribers
            )
            print("✓ Email notification added to existing budget!")
        except Exception as e:
            print(f"Note: Could not add notification (may already exist): {e}")
            
    except Exception as e:
        print(f"❌ Error creating budget: {e}")
        return False
        
    return True

if __name__ == "__main__":
    create_budget_with_alert()
