# IAM Temporary Role Creator

A secure AWS IAM Role creator that creates temporary IAM roles with automatic expiration for contractor access and time-bound permissions.

[![Terraform](https://img.shields.io/badge/terraform-1.6.0+-%235835CC.svg?style=for-the-badge&logo=terraform&logoColor=white)](https://terraform.io)
[![AWS Provider](https://img.shields.io/badge/aws--provider-5.31.0+-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)](https://registry.terraform.io/providers/hashicorp/aws/latest)
[![Python](https://img.shields.io/badge/python-3.11+-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

## Purpose

This system addresses the need for secure, temporary AWS access by:

- Eliminating manual role creation processes (reducing from 2 hours to under 5 minutes)
- Providing time-bound access with automatic expiration
- Enforcing security controls including MFA, IP restrictions, and permission boundaries
- Maintaining comprehensive audit trails for compliance
- Supporting multiple permission tiers based on predefined templates

## Key Features

### Access Management
- **Temporary IAM Roles**: Configurable time limits (1 hour to 36 hours)
- **Permission Tiers**: Predefined access levels (read-only, developer, admin, break-glass)
- **Automatic Expiration**: TTL-based cleanup with EventBridge scheduling
- **Unique Session IDs**: UUID-based session tracking

### Security Controls
- **MFA Enforcement**: Required for all role assumptions
- **IP Restrictions**: Configurable CIDR range limitations
- **External ID Validation**: Unique external IDs for cross-account access
- **Permission Boundaries**: Prevent privilege escalation
- **Rate Limiting**: 100 requests per minute per user

### Monitoring & Compliance
- **CloudTrail Integration**: All role assumptions logged
- **Structured JSON Logging**: Complete audit trail
- **Real-time Metrics**: CloudWatch integration
- **Break-glass Alerts**: SNS notifications for emergency access

## Architecture

The system uses a serverless-first design:

- **API Gateway**: REST API with request throttling
- **Lambda Functions**: Core role vending logic (Python 3.11+)
- **DynamoDB**: Session tracking and audit logs
- **S3**: Policy template storage with versioning
- **KMS**: Encryption for all data at rest
- **EventBridge**: Automated cleanup scheduling

## Quick Start

### Prerequisites
- Python 3.11+
- AWS CLI configured with appropriate permissions
- Terraform (for infrastructure deployment)

### Installation

1. **Clone and Setup**:
   ```bash
   git clone <repository-url>
   cd iam-temprole-creator
   pip install -r requirements.txt
   ```

2. **Deploy Infrastructure**:
   ```bash
   cd infrastructure
   terraform init
   terraform apply
   ```

3. **Configure Environment**:
   ```bash
   export IAM_ROLE_AWS_ACCOUNT_ID="your-account-id"
   export IAM_ROLE_DYNAMODB_TABLE_NAME="iam-role-vendor-sessions"
   export IAM_ROLE_POLICY_TEMPLATES_BUCKET="your-bucket-name"
   export IAM_ROLE_AWS_REGION="us-east-1"
   ```

4. **Install CLI Tool**:
   ```bash
   pip install -e .
   ```

## Usage

### Request a Temporary Role
```bash
python -m iam_temprole_creator.cli request-role \
  --project-id "security-audit" \
  --user-id "john.doe" \
  --permission-tier "read-only" \
  --duration-hours 4 \
  --reason "Reviewing S3 buckets for security audit" \
  --mfa-used
```

### Manage Sessions
```bash
# List all your sessions
python -m iam_temprole_creator.cli list-sessions --user-id "john.doe"

# Check session status
python -m iam_temprole_creator.cli check-status \
  --project-id "security-audit" \
  --session-id "abc12345-def6-7890-ghij-klmnopqrstuv"

# Revoke a session early
python -m iam_temprole_creator.cli revoke-session \
  --project-id "security-audit" \
  --session-id "abc12345-def6-7890-ghij-klmnopqrstuv"
```

## Permission Tiers

| Tier | Description | Max Duration | MFA Required | Use Case |
|------|-------------|--------------|--------------|----------|
| **read-only** | View-only access to S3, EC2, IAM | 36 hours | Yes | Security audits, compliance reviews |
| **developer** | Full access to S3, EC2, Lambda (no IAM changes) | 8 hours | Yes | Application development, deployments |
| **admin** | Full AWS access with restrictions | 8 hours | Yes | Infrastructure management |
| **break-glass** | Emergency access (triggers alerts) | 1 hour | Yes | Incident response, emergencies |

## Configuration

### Environment Variables
```bash
# AWS Configuration
export IAM_ROLE_AWS_REGION="us-east-1"
export IAM_ROLE_AWS_ACCOUNT_ID="123456789012"
export IAM_ROLE_DYNAMODB_TABLE_NAME="iam-role-vendor-sessions"
export IAM_ROLE_POLICY_TEMPLATES_BUCKET="iam-role-vendor-policy-templates-123456789012"

# Security Configuration
export IAM_ROLE_MFA_REQUIRED="true"
export IAM_ROLE_MAX_SESSION_DURATION="129600"  # 36 hours in seconds
export IAM_ROLE_ALLOWED_IP_RANGES='["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]'
export IAM_ROLE_ALLOWED_DEPARTMENTS='["Engineering", "DevOps", "Security"]'
```

## Cleanup

The project includes comprehensive cleanup scripts to remove all AWS resources:

### Python Script (Recommended)
```bash
# Preview what will be deleted
python cleanup.py --dry-run

# Complete cleanup with confirmation
python cleanup.py

# Force cleanup without prompts
python cleanup.py --force
```

### What Gets Cleaned Up
- Lambda Functions
- DynamoDB Tables
- API Gateway
- IAM Roles & Policies
- EventBridge Rules
- CloudWatch Log Groups
- SNS Topics
- S3 Buckets
- KMS Keys

## Development

### Running Tests
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=iam_temprole_creator --cov-report=html
```

## Security & Compliance

### Compliance Frameworks
- **SOC2**: Complete audit trail and access controls
- **HIPAA**: Data encryption and access logging
- **PCI-DSS**: Secure credential handling
- **GDPR**: Data residency and access controls

### Security Features
- **Encryption**: All data encrypted with AWS KMS
- **Access Controls**: MFA, IP restrictions, permission boundaries
- **Audit Trail**: Complete logging for 7+ years
- **Monitoring**: Real-time security alerts

## Project Structure

```
iam-temprole-creator/
├── src/iam_temprole_creator/          # Main Python package
│   ├── cli.py                         # Command-line interface
│   ├── config.py                      # Configuration management
│   ├── database.py                    # DynamoDB operations
│   ├── models.py                      # Pydantic data models
│   ├── policy_manager.py              # IAM policy management
│   └── role_vendor.py                 # Core role vending logic
├── infrastructure/                    # Terraform infrastructure
│   └── main.tf                        # Main Terraform configuration
├── lambda_functions/                  # AWS Lambda functions
├── policy_templates/                  # IAM policy templates
├── tests/                             # Test suite
├── cleanup.py                         # Python cleanup script
├── requirements.txt                   # Python dependencies
└── README.md                          # This file
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support and questions:
- Create an issue in the repository
- Contact the IAM team at iam-team@company.com

## Security Notice

This tool creates temporary AWS credentials. Always follow your organization's security policies and never share credentials with unauthorized parties. All access is logged and monitored for security compliance.