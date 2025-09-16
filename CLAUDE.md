# IAM Role Vending Machine - Implementation Requirements

Build an AWS IAM Role Vending Machine that creates temporary IAM roles with automatic expiration for contractor access and time-bound permissions. The solution must be accessed via CLI tool and support different permission tiers based on predefined rules.

## Core Functional Requirements

### Access Management
- Create temporary IAM roles using AWS STS AssumeRole with configurable time limits (15 minutes to 36 hours)
- Support multiple permission tiers (read-only, developer, admin) with predefined policy templates
- Implement automatic credential expiration and cleanup
- Generate unique session identifiers for each temporary role assumption
- Support role chaining with maximum 1-hour duration limit

### CLI Tool Interface
- Command-line interface for requesting temporary credentials
- Support for multiple authentication methods (AWS SSO, IAM users with MFA)
- Output credentials in multiple formats (environment variables, AWS CLI config, JSON)
- Include commands for: request-role, list-available-roles, check-session-status, revoke-session
- Provide clear error messages and troubleshooting guidance

## Architecture Requirements

### Service Architecture (Serverless-First)
- **API Layer**: API Gateway with request throttling (100 requests/minute per user)
- **Compute**: Lambda functions for core vending logic (Python 3.11+ or Node.js 18+)
- **State Management**: DynamoDB for role mappings and session tracking
- **Orchestration**: Step Functions for complex approval workflows
- **Queue**: SQS for asynchronous request processing with DLQ for failed requests
- **Configuration**: Parameter Store or Secrets Manager for sensitive configurations

### Data Model (DynamoDB)
Primary table schema:
```
- ProjectId (Partition Key)
- SessionId (Sort Key)  
- UserId
- RoleArn
- PermissionTier
- RequestedAt
- ExpiresAt (TTL)
- Status (PENDING, ACTIVE, EXPIRED, REVOKED)
- RequestMetadata (IP, MFA status, etc.)
```

Secondary indexes:
- GSI1: UserId as partition key for user session queries
- GSI2: ExpiresAt for cleanup operations

### Policy Management
- Template-based policy generation using Mustache or similar
- Policy templates stored in S3 with versioning enabled
- Dynamic variable substitution: ${userId}, ${projectId}, ${sessionId}, ${resourcePrefix}
- Maximum policy size optimization (stay under 10,240 character limit)
- Permission boundary enforcement on all vended roles

## Security Requirements

### Authentication & Authorization
- **MFA Enforcement**: Require MFA for all privileged role assumptions
- **IP Restrictions**: Limit role assumption to specified CIDR ranges
- **External ID**: Generate unique external IDs for cross-account access
- **Session Policies**: Apply additional restrictions at assumption time
- **Identity Federation**: Support SAML 2.0 or OIDC for SSO integration

### Trust Policy Configuration
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::ACCOUNT:root"},
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {
        "sts:ExternalId": "${externalId}",
        "aws:PrincipalTag/Department": "${allowedDepartments}"
      },
      "IpAddress": {
        "aws:SourceIp": ["10.0.0.0/8", "172.16.0.0/12"]
      },
      "NumericLessThan": {
        "aws:MultiFactorAuthAge": "3600"
      }
    }
  }]
}
```

### Security Controls
- Implement permission boundaries to prevent privilege escalation
- Block dangerous actions: IAM policy modifications, security group changes, KMS key deletion
- Enforce tagging standards on all created resources
- Implement rate limiting per user and per IP
- Add honeypot detection for suspicious activity patterns

### Encryption & Secrets
- Encrypt all data at rest using AWS KMS CMKs
- Rotate KMS keys annually
- Use Secrets Manager for API keys and external service credentials
- Implement envelope encryption for sensitive request metadata
- Enable CloudTrail log file validation

## Monitoring & Observability

### Metrics (CloudWatch)
Critical metrics to track:
- Request volume by permission tier
- Average provisioning time (target: <5 seconds)
- Failed assumption attempts
- Session duration distribution
- Policy validation failures
- Break-glass access frequency

### Logging Structure
Structured JSON logs for all operations:
```json
{
  "timestamp": "ISO-8601",
  "requestId": "uuid",
  "userId": "string",
  "action": "ROLE_REQUESTED|ROLE_VENDED|ROLE_EXPIRED",
  "permissionTier": "string",
  "sessionDuration": "seconds",
  "sourceIp": "string",
  "mfaUsed": "boolean",
  "result": "SUCCESS|FAILURE",
  "errorDetails": {}
}
```

### Alerting Rules
- **Critical**: Service unavailable for >5 minutes, authentication failures >10/minute
- **Warning**: Provisioning time >10 seconds, validation failures >10%
- **Info**: Break-glass usage, new permission tier requested

## Compliance & Audit

### Audit Requirements
- Log all role assumptions to CloudTrail
- Generate daily reports of active sessions
- Weekly permission usage analysis
- Monthly compliance reports for SOC2/PCI-DSS
- Implement automatic session recording for privileged access

### Compliance Controls
- Data residency: Ensure all data remains in specified AWS regions
- Implement automatic PII detection and masking in logs
- Support for compliance frameworks: SOC2, HIPAA, PCI-DSS, GDPR
- Maintain audit trail for minimum 7 years (CloudTrail → S3 → Glacier)

## Implementation Patterns

### Role Vending Patterns
1. **Push Pattern** (Recommended):
   - Pre-provision roles based on approved requests
   - Support approval workflows via SNS/Email
   - Batch processing for efficiency

2. **Pull Pattern** (On-Demand):
   - Provision roles when first requested
   - Implement caching for frequently used roles
   - Add circuit breakers for downstream services

### Error Handling
- Implement exponential backoff with jitter for API retries
- Dead letter queues for failed requests
- Graceful degradation when non-critical services fail
- Comprehensive error codes and user-friendly messages

### Break-Glass Access
- Separate break-glass role with maximum permissions
- Time-limited console URLs (15-minute expiration)
- Automatic incident creation in ticketing system
- Real-time alerts to security team
- Post-incident automatic credential rotation

## Performance Requirements

### Scalability Targets
- Support 1000+ concurrent sessions
- Handle 10,000 requests per hour
- Sub-5 second role provisioning time
- 99.9% availability SLA
- Support for 100+ AWS accounts

### Optimization Strategies
- Cache IAM policies in ElastiCache/DynamoDB
- Use connection pooling for AWS API calls
- Implement request batching where possible
- Pre-warm Lambda functions for critical paths
- Use Lambda provisioned concurrency for consistent performance

## Testing Requirements

### Test Coverage
- Unit tests: Minimum 80% code coverage
- Integration tests for all AWS service interactions
- Load testing: Validate 2x expected peak load
- Security testing: OWASP Top 10 validation
- Chaos engineering: Test failure scenarios

### Test Scenarios
- MFA token expiration during request
- Network partition between services
- DynamoDB throttling
- Lambda cold starts
- KMS key rotation during operation
- Cross-account role assumption failures

## Deployment & Operations

### Infrastructure as Code
- Use CDK or Terraform for all infrastructure
- Implement blue-green deployments
- Automated rollback on failure
- Environment promotion pipeline: Dev → Staging → Prod
- Configuration management via AWS Systems Manager

### Operational Runbooks
- Document procedures for common issues
- Implement automated remediation where possible
- Define escalation paths
- Create disaster recovery procedures
- Maintain service dependency mapping

## Cost Optimization

### Cost Controls
- Use Lambda ARM-based Graviton2 processors
- Implement DynamoDB auto-scaling
- S3 lifecycle policies for log archival
- Reserved capacity for predictable workloads
- Regular permission right-sizing to reduce complexity

### Cost Monitoring
- Tag all resources with cost center
- Set up AWS Budget alerts
- Implement showback/chargeback reporting
- Regular cost optimization reviews
- Track cost per vended credential

## Additional Considerations

### Future Enhancements
- Machine learning for anomaly detection
- Integration with third-party identity providers
- Support for container workloads (EKS Pod Identity)
- GraphQL API for advanced querying
- Self-service web portal

### Migration Strategy
- Support parallel run with existing IAM processes
- Gradual rollout by team/department
- Automated migration tools for existing roles
- Rollback capabilities at each stage
- Success metrics and checkpoints

### Documentation Requirements
- API documentation with OpenAPI spec
- User guides for CLI tool
- Administrator documentation
- Security architecture diagrams
- Troubleshooting guides
- Video tutorials for common workflows

## Success Criteria
- Reduce manual role creation time from 2 hours to <5 minutes
- Achieve 95% reduction in standing privileged access
- Zero security incidents related to credential compromise
- 100% audit compliance for access reviews
- Developer satisfaction score >4.5/5

## Constraints & Assumptions
- Must work within AWS service quotas
- Cannot modify existing production IAM roles
- Must maintain backward compatibility with current workflows
- Assume users have basic AWS CLI knowledge
- Limited to AWS-native services (no third-party dependencies)

Build this system with security as the primary concern, followed by usability and scalability. Every design decision should be traceable to a security requirement or compliance need.