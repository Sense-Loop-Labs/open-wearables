# AWS Infrastructure Teardown - August 31, 2026

This document describes the AWS infrastructure teardown performed to pause the Open Wearables platform and eliminate ongoing costs.

---

## Summary

| Item | Value |
|------|-------|
| **Date** | August 31 - September 3, 2026 |
| **Stage** | staging |
| **Region** | us-west-2 |
| **Previous Monthly Cost** | ~$115-125/month |
| **Current Monthly Cost** | ~$0.52/month |

---

## Database Backup

A local backup was created before deleting the RDS snapshot.

| Field | Value |
|-------|-------|
| **Local File** | `backups/open-wearables-staging-20260831.dump` |
| **Format** | PostgreSQL custom format (pg_dump -F c) |
| **Size** | 10 MB |
| **Database** | PostgreSQL 16.13 |
| **Created** | September 3, 2026 |

**Note:** This file is excluded from git via `.gitignore` as it contains patient data.

### To Restore Database

```bash
# After redeploying infrastructure and getting new RDS endpoint:
pg_restore \
  -h <new-rds-host> \
  -p 5432 \
  -U postgres \
  -d open_wearables \
  backups/open-wearables-staging-20260831.dump
```

---

## Resources Removed

### Phase 1: SST Teardown (August 31)

Removed via `npx sst remove --stage staging`:

- **ECS Cluster** - `open-wearables-staging`
- **API Service** - FastAPI backend (Fargate)
- **Worker Service** - Celery worker (Fargate)
- **Beat Service** - Celery beat scheduler (Fargate)
- **Frontend Service** - React dashboard (Fargate)
- **RDS PostgreSQL** - `open-wearables-staging`
- **ElastiCache Redis** - `open-wearables-staging`
- **Load Balancers** (2) - API and Frontend ALBs
- **EC2 Bastion** - `i-09faf67e2d86be85f`
- **Route53 DNS Records** - A/AAAA for staging domains
- **ACM Certificates** - SSL for API and Frontend
- **CloudWatch Log Groups** - API, Worker, Beat, Frontend
- **IAM Roles** - Task and execution roles
- **Security Groups** - DB, Redis, Cluster, Bastion, Load Balancers

### Phase 2: Additional Cleanup (September 3)

Discovered and removed additional resources:

- **CloudFormation Stack** - `SenseLoop-staging-SharedVpc`
  - VPC `vpc-0cfb263873318a2d6` with 6 subnets
  - NAT Instance (t4g.nano) - `i-074a7f82511335e4a`
  - Route tables, internet gateway, etc.
- **RDS Snapshot** - `open-wearables-staging-backup-20260831` (after local backup)
- **ECR Repository** - `sst-asset` (20.4 GB of container images)
- **CloudWatch Log Group** - `/sense-loop/staging/vpc-flow-logs`

---

## Resources Preserved

### Local Database Backup
- **File:** `backups/open-wearables-staging-20260831.dump`
- **Contains:** All patient data, health records, care plans, questionnaires
- **Storage:** Local filesystem (excluded from git)

### AWS Resources (Minimal Cost)
| Resource | Purpose | Monthly Cost |
|----------|---------|--------------|
| Route53 Hosted Zone | DNS for senselooplabs.com | ~$0.50 |
| CDKToolkit Stack | AWS CDK bootstrap | $0 |
| CDK ECR Repository | CDK assets (minimal) | ~$0.01 |
| S3 Buckets | SST/CDK state (few MB) | ~$0.01 |
| **Total** | | **~$0.52/month** |

---

## To Redeploy

When ready to bring the platform back online:

### 1. Redeploy Infrastructure

```bash
cd /Users/mikeaymard/Projects/sense-loop-labs/open-wearables/infra
npm run deploy:pre-pilot
```

This will recreate:
- VPC and networking
- ECS cluster and services
- RDS PostgreSQL (new, empty database)
- ElastiCache Redis
- Load balancers
- DNS records
- SSL certificates

### 2. Restore Database

After deployment completes, restore from local backup:

```bash
# Get the new RDS endpoint from SST outputs
cat infra/.sst/outputs.json | jq -r '.dbHost'

# Restore the database
PGPASSWORD='<db-password>' pg_restore \
  -h <db-host-from-outputs> \
  -p 5432 \
  -U postgres \
  -d open_wearables \
  --no-owner \
  --no-privileges \
  backups/open-wearables-staging-20260831.dump
```

**Note:** Get the database password from SST secrets or the Pulumi state after deployment.

### 3. Run Migrations (if needed)

```bash
cd /Users/mikeaymard/Projects/sense-loop-labs/open-wearables/backend
alembic upgrade head
```

### 4. Verify Deployment

- API: https://wearables.staging.senselooplabs.com/health
- Dashboard: https://dashboard.staging.senselooplabs.com

---

## Cost Comparison

| Resource | Before (Monthly) | After (Monthly) |
|----------|------------------|-----------------|
| RDS PostgreSQL | $35 | $0 |
| ElastiCache Redis | $25 | $0 |
| ECS Fargate | $30-40 | $0 |
| Load Balancers | $20 | $0 |
| EC2 Bastion | $5 | $0 |
| NAT Instance | $3 | $0 |
| ECR Storage | $2 | $0 |
| RDS Snapshot | $2 | $0 |
| Data Transfer | $5-10 | $0 |
| Route53 Zone | $0.50 | $0.50 |
| S3/CDK Assets | $0.02 | $0.02 |
| **Total** | **~$128-143** | **~$0.52** |

**Monthly Savings:** ~$127-142

---

## Cleanup Commands Reference

Commands used during teardown (for reference):

```bash
# SST teardown
cd infra && npx sst remove --stage staging

# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name SenseLoop-staging-SharedVpc

# Delete ECR repository
aws ecr delete-repository --repository-name sst-asset --force

# Delete RDS snapshot (after backing up)
aws rds delete-db-snapshot --db-snapshot-identifier open-wearables-staging-backup-20260831

# Delete CloudWatch log group
aws logs delete-log-group --log-group-name /sense-loop/staging/vpc-flow-logs
```

---

## Further Cleanup (Optional)

To reduce costs to absolute zero:

### Delete Route53 Hosted Zone
```bash
# Warning: This will break DNS for senselooplabs.com
aws route53 delete-hosted-zone --id Z02200073IYX57IAJ0S2T
```

### Delete CDK Bootstrap
```bash
aws cloudformation delete-stack --stack-name CDKToolkit
aws ecr delete-repository --repository-name cdk-hnb659fds-container-assets-663566124074-us-west-2 --force
aws s3 rb s3://cdk-hnb659fds-assets-663566124074-us-west-2 --force
aws s3 rb s3://cdk-hnb659fds-assets-663566124074-us-east-1 --force
```

---

*Document created: August 31, 2026*
*Last updated: September 3, 2026*
