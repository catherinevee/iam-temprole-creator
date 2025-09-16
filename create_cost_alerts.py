#!/usr/bin/env python3
"""
Create AWS Cost Control Alerts based on August 2025 billing analysis
"""

import boto3
import json
from datetime import datetime

def create_cost_alerts():
    budgets_client = boto3.client('budgets')
    sts_client = boto3.client('sts')
    account_id = sts_client.get_caller_identity()['Account']
    
    # Create a new budget specifically for cost control based on August 2025 data
    budget = {
        'BudgetName': 'Cost-Control-Budget-Aug2025',
        'BudgetLimit': {
            'Amount': '1800',  # Set 10% below actual August spend
            'Unit': 'USD'
        },
        'TimeUnit': 'MONTHLY',
        'BudgetType': 'COST',
        'CostFilters': {
            'Service': [
                'Amazon Relational Database Service',  # 78.3% of costs
                'Amazon Elastic Container Service for Kubernetes',  # 8.7% of costs
                'Amazon Elastic Compute Cloud - Compute',  # 1.6% of costs
                'EC2 - Other',  # 2.6% of costs
                'Amazon Virtual Private Cloud',  # 0.4% of costs
                'AmazonCloudWatch'  # 0.1% of costs
            ]
        },
        'TimePeriod': {
            'Start': datetime(2025, 1, 1),
            'End': datetime(2026, 12, 31)
        }
    }
    
    try:
        # Create the budget
        print('Creating cost control budget...')
        budgets_client.create_budget(AccountId=account_id, Budget=budget)
        print('✓ Cost control budget created!')
        
        # Create multiple alert thresholds
        thresholds = [
            {'percentage': 50, 'description': '50% of budget ($900)'},
            {'percentage': 75, 'description': '75% of budget ($1,350)'},
            {'percentage': 90, 'description': '90% of budget ($1,620)'},
            {'percentage': 100, 'description': '100% of budget ($1,800)'},
            {'percentage': 110, 'description': '110% of budget ($1,980) - CRITICAL'}
        ]
        
        subscribers = [
            {'SubscriptionType': 'EMAIL', 'Address': 'catherine.vee@outlook.com'}
        ]
        
        for threshold in thresholds:
            notification = {
                'NotificationType': 'ACTUAL',
                'ComparisonOperator': 'GREATER_THAN',
                'Threshold': threshold['percentage'],
                'ThresholdType': 'PERCENTAGE'
            }
            
            try:
                budgets_client.create_notification(
                    AccountId=account_id,
                    BudgetName='Cost-Control-Budget-Aug2025',
                    Notification=notification,
                    Subscribers=subscribers
                )
                print('✓ Alert created for ' + threshold['description'])
            except Exception as e:
                print('Note: Alert for ' + threshold['description'] + ' - ' + str(e))
        
        # Create forecasted spending alert
        forecast_notification = {
            'NotificationType': 'FORECASTED',
            'ComparisonOperator': 'GREATER_THAN',
            'Threshold': 100.0,
            'ThresholdType': 'PERCENTAGE'
        }
        
        try:
            budgets_client.create_notification(
                AccountId=account_id,
                BudgetName='Cost-Control-Budget-Aug2025',
                Notification=forecast_notification,
                Subscribers=subscribers
            )
            print('✓ Forecasted spending alert created!')
        except Exception as e:
            print('Note: Forecasted alert - ' + str(e))
            
        print('\n' + '='*60)
        print('COST CONTROL ALERTS SETUP COMPLETE')
        print('='*60)
        print('Budget: $1,800/month (10% below August 2025 actual)')
        print('Email: catherine.vee@outlook.com')
        print('Alert Thresholds:')
        for threshold in thresholds:
            print('  - ' + threshold['description'])
        print('  - Forecasted to exceed 100% ($1,800)')
        print('='*60)
        
    except Exception as e:
        print('Error: ' + str(e))

if __name__ == '__main__':
    create_cost_alerts()
