# AWS Infrastructure Teardown - August 31, 2026

This document describes the AWS infrastructure teardown performed to pause the Open Wearables platform and eliminate ongoing costs.

---

## Summary

| Item | Value |
|------|-------|
| **Date** | August 31, 2026 |
| **Stage** | staging |
| **Region** | us-west-2 |
| **Previous Monthly Cost** | ~$115-125/month |
| **Current Monthly Cost** | ~$2/month (snapshot storage only) |

---

## Database Backup

A full RDS snapshot was created before teardown.

| Field | Value |
|-------|-------|
| **Snapshot ID** | `open-wearables-staging-backup-20260831` |
| **Database** | PostgreSQL 16.13 |
| **Size** | 20 GB |
| **Status** | Available |
| **Storage Cost** | ~$2/month |

### To Restore Database

```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier open-wearables-staging \
  --db-snapshot-identifier open-wearables-staging-backup-20260831 \
  --db-instance-class db.t3.micro \
  --vpc-security-group-ids <security-group-id> \
  --db-subnet-group-name <subnet-group-name>
```

**Note:** When redeploying with SST, a new database will be created. You may need to manually migrate data from the snapshot if you want to preserve existing patient/health data.

---

## Resources Removed

### Compute
- **ECS Cluster** - `open-wearables-staging`
- **API Service** - FastAPI backend (Fargate)
- **Worker Service** - Celery worker (Fargate)
- **Beat Service** - Celery beat scheduler (Fargate)
- **Frontend Service** - React dashboard (Fargate)

### Database & Cache
- **RDS PostgreSQL** - `open-wearables-staging` (snapshot preserved)
- **ElastiCache Redis** - `open-wearables-staging`

### Networking
- **VPC** - `vpc-0cfb263873318a2d6`
- **Load Balancers** (2) - API and Frontend ALBs
- **Security Groups** - DB, Redis, Cluster, Bastion, Load Balancers
- **Subnets** - Public and private subnets
- **Route Tables** - Associated routing

### Compute (Other)
- **EC2 Bastion** - `i-09faf67e2d86be85f`

### DNS
- **Route53 Records** - A and AAAA records for:
  - `wearables.staging.senselooplabs.com`
  - `dashboard.staging.senselooplabs.com`

### SSL/TLS
- **ACM Certificates** - For API and Frontend domains

### Logging
- **CloudWatch Log Groups** - API, Worker, Beat, Frontend logs

### IAM
- **Task Roles** - ECS task execution roles
- **Execution Roles** - ECS service roles
- **Bastion Role** - SSM access role

---

## Resources Preserved

### Database Snapshot
- **ID:** `open-wearables-staging-backup-20260831`
- **Cost:** ~$2/month (20GB × $0.10/GB)
- **Contains:** All patient data, health records, care plans, questionnaires

### SST Secrets (AWS SSM Parameter Store)
These secrets remain in SSM and will be reused on redeployment:
- `SecretKey` - Application secret key
- `DbPassword` - Database password
- `GarminClientId` / `GarminClientSecret`
- `FitbitClientId` / `FitbitClientSecret`
- `SlSendgridApiKey` - SendGrid API key
- `SlFirebaseCredentials` - Firebase push notification credentials
- `SlAdminPassword` - Admin password

**Cost:** Free (SSM Parameter Store standard parameters)

### Route53 Hosted Zone
- Domain configuration for `senselooplabs.com` remains active
- **Cost:** $0.50/month per hosted zone

### ECR Container Images
- Docker images may remain in ECR
- **Cost:** ~$0.10/GB/month

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

### 2. Restore Database (Optional)

If you need to restore the previous data:

**Option A: Manual Migration**
1. Create a temporary RDS instance from snapshot
2. Use `pg_dump` to export data
3. Import into the new SST-created database
4. Delete temporary instance

**Option B: Use Snapshot Directly**
1. After SST deploy, note the new DB security group and subnet group
2. Delete the SST-created empty database
3. Restore from snapshot with same identifier
4. Update SST configuration if needed

### 3. Run Migrations

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
| Data Transfer | $5-10 | $0 |
| **RDS Snapshot** | - | **$2** |
| Route53 Zone | $0.50 | $0.50 |
| **Total** | **~$120-155** | **~$2.50** |

**Monthly Savings:** ~$117-152

---

## Cleanup Tasks (Optional)

To further reduce costs to zero:

### Delete Database Snapshot
```bash
aws rds delete-db-snapshot \
  --db-snapshot-identifier open-wearables-staging-backup-20260831
```
**Warning:** This permanently deletes all backed-up data.

### Delete ECR Images
```bash
aws ecr batch-delete-image \
  --repository-name open-wearables-staging \
  --image-ids imageTag=latest
```

### Delete SST Secrets
```bash
npx sst secrets remove SecretKey --stage staging
# Repeat for other secrets...
```

---

## Contact

For questions about redeployment or data restoration, refer to:
- [CODE_STRUCTURE.md](../platform_code_structure.md) - Codebase overview
- [SST Documentation](https://sst.dev/docs/) - Infrastructure framework

---

*Document created: August 31, 2026*
