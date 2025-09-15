# IAM Role Vending Machine - Cleanup Scripts

This directory contains comprehensive cleanup scripts to completely remove all AWS resources created by the IAM Role Vending Machine.

## 🧹 Available Cleanup Scripts

### 1. Python Script (`cleanup.py`)
**Most comprehensive and recommended**

```bash
# Basic cleanup
python cleanup.py

# Dry run (show what would be deleted)
python cleanup.py --dry-run

# Force cleanup without confirmation
python cleanup.py --force

# Specify region
python cleanup.py --region us-west-2

# Help
python cleanup.py --help
```

**Features:**
- ✅ Handles dependencies and proper cleanup order
- ✅ Comprehensive error handling
- ✅ Dry run mode
- ✅ Force mode (skip confirmations)
- ✅ Detailed logging
- ✅ Resource tracking and reporting
- ✅ Handles versioned S3 objects
- ✅ Manages KMS key scheduling

### 2. Bash Script (`cleanup.sh`)
**For Linux/macOS systems**

```bash
# Make executable
chmod +x cleanup.sh

# Basic cleanup
./cleanup.sh

# Dry run
./cleanup.sh us-east-1 true

# Different region
./cleanup.sh us-west-2 false
```

### 3. PowerShell Script (`cleanup.ps1`)
**For Windows systems**

```powershell
# Basic cleanup
.\cleanup.ps1

# Dry run
.\cleanup.ps1 -DryRun

# Force cleanup
.\cleanup.ps1 -Force

# Different region
.\cleanup.ps1 -Region us-west-2

# Help
Get-Help .\cleanup.ps1 -Full
```

## 🎯 What Gets Cleaned Up

### **AWS Resources Deleted:**
1. **Lambda Functions**
   - `iam-role-vendor-role-vendor`
   - `iam-role-vendor-cleanup`

2. **DynamoDB Tables**
   - `iam-role-vendor-sessions`
   - `iam-role-vendor-audit-logs`

3. **API Gateway**
   - `iam-role-vendor-api` (and all associated resources)

4. **IAM Resources**
   - `iam-role-vendor-lambda-role`
   - `iam-role-vendor-lambda-policy`
   - All temporary roles (`temp-role-*`)

5. **EventBridge Rules**
   - `iam-role-vendor-cleanup-schedule`

6. **CloudWatch Log Groups**
   - `/aws/lambda/iam-role-vendor-role-vendor`
   - `/aws/lambda/iam-role-vendor-cleanup`

7. **SNS Topics**
   - `iam-role-vendor-break-glass-alerts`

8. **S3 Buckets**
   - `iam-role-vendor-policy-templates-*`
   - All objects and versions

9. **KMS Keys**
   - Project-specific keys (scheduled for deletion in 7 days)

## ⚠️ Important Notes

### **Before Running Cleanup:**
1. **Backup Important Data**: Ensure you have backups of any important data
2. **Check Dependencies**: Verify no other services depend on these resources
3. **Review Costs**: Some resources may have incurred costs that will be eliminated
4. **AWS Permissions**: Ensure your AWS credentials have sufficient permissions

### **Cleanup Order:**
The scripts follow a specific order to handle dependencies:
1. Lambda Functions (first)
2. EventBridge Rules (remove targets first)
3. API Gateway
4. DynamoDB Tables
5. CloudWatch Logs
6. SNS Topics
7. S3 Buckets (with version handling)
8. IAM Roles & Policies (detach policies first)
9. KMS Keys (schedule for deletion)

### **KMS Key Deletion:**
- KMS keys are **scheduled for deletion** in 7 days
- This is a safety measure to prevent accidental data loss
- Keys can be cancelled from deletion within the 7-day window
- AWS-managed default service keys are **not deleted** (requires root access)

## 🚀 Usage Examples

### **Development Environment Cleanup:**
```bash
# Quick cleanup for development
python cleanup.py --force --region us-east-1
```

### **Production Environment Cleanup:**
```bash
# Safe cleanup with confirmation
python cleanup.py --region us-east-1
# Review the dry run first
python cleanup.py --dry-run --region us-east-1
```

### **Multi-Region Cleanup:**
```bash
# Clean up multiple regions
python cleanup.py --region us-east-1 --force
python cleanup.py --region us-west-2 --force
python cleanup.py --region eu-west-1 --force
```

## 🔍 Troubleshooting

### **Common Issues:**

1. **"Access Denied" Errors**
   - Ensure your AWS credentials have sufficient permissions
   - Some resources may require specific IAM permissions

2. **"Resource Not Found" Errors**
   - These are usually safe to ignore (resource already deleted)
   - The scripts handle these gracefully

3. **"Bucket Not Empty" Errors**
   - The Python script handles versioned objects automatically
   - For other scripts, manually delete objects first

4. **"Cannot Delete Entity" Errors**
   - Usually means dependencies need to be removed first
   - The Python script handles this automatically

### **Manual Cleanup Steps:**
If scripts fail, you can manually clean up:

```bash
# 1. Delete Lambda functions
aws lambda delete-function --function-name iam-role-vendor-role-vendor
aws lambda delete-function --function-name iam-role-vendor-cleanup

# 2. Delete DynamoDB tables
aws dynamodb delete-table --table-name iam-role-vendor-sessions
aws dynamodb delete-table --table-name iam-role-vendor-audit-logs

# 3. Delete API Gateway
aws apigateway delete-rest-api --rest-api-id <API_ID>

# 4. Continue with other resources...
```

## 📊 Cost Impact

**Resources that incur costs:**
- Lambda functions (execution time)
- DynamoDB tables (read/write capacity)
- API Gateway (requests)
- CloudWatch logs (storage)
- S3 buckets (storage)
- KMS keys (usage)

**Estimated monthly cost elimination:**
- Small deployment: $5-20/month
- Medium deployment: $20-100/month
- Large deployment: $100+/month

## 🛡️ Security Considerations

1. **Data Deletion**: All data is permanently deleted
2. **Audit Trails**: CloudTrail logs may still contain historical records
3. **KMS Keys**: 7-day deletion window allows for recovery
4. **IAM Policies**: Ensure no other services depend on deleted policies

## 📝 Logs and Monitoring

The cleanup scripts provide detailed logging:
- Timestamped operations
- Success/failure status
- Resource tracking
- Error details

**Log levels:**
- `INFO`: Normal operations
- `WARNING`: Non-critical issues
- `ERROR`: Failed operations
- `SUCCESS`: Successful operations

## 🔄 Recovery

**If you need to recover:**
1. **KMS Keys**: Cancel deletion within 7 days
2. **Other Resources**: Redeploy using `terraform apply`
3. **Data**: Restore from backups (if available)

**Note**: Most resources cannot be recovered once deleted.

---

## 📞 Support

If you encounter issues with the cleanup scripts:
1. Check the troubleshooting section above
2. Review AWS CloudTrail logs for detailed error information
3. Ensure your AWS credentials have sufficient permissions
4. Consider running in dry-run mode first to identify issues

**Remember**: Always test cleanup scripts in a non-production environment first!
