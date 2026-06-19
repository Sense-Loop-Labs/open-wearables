# Open Wearables AWS Deployment Guide

This guide covers deploying Open Wearables to AWS using SST (Serverless Stack).

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Deployment Tiers](#deployment-tiers)
- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Deployment Commands](#deployment-commands)
- [Post-Deploy Steps](#post-deploy-steps)
- [Scaling Up](#scaling-up)
- [Security](#security)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Cost Optimization](#cost-optimization)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS VPC                               │
│  ┌─────────────────┐                                        │
│  │       ALB       │ ◄─── HTTPS (ACM certificate)          │
│  │   (Port 443)    │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│  ┌────────┴─────────────────────────────────────────────┐   │
│  │         ECS Cluster (Fargate) - PUBLIC SUBNETS*       │   │
│  │  ┌──────────┐ ┌──────────────┐                        │   │
│  │  │   API    │ │  WorkerBeat  │  (pre-pilot: combined) │   │
│  │  │ (FastAPI)│ │   (Celery)   │                        │   │
│  │  └──────────┘ └──────────────┘                        │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                    │
│         ┌───────────────┼───────────────┐                   │
│         ▼               ▼               ▼                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │    RDS     │  │ ElastiCache│  │S3+CloudFront│           │
│  │ PostgreSQL │  │   Redis    │  │  Frontend   │            │
│  │ (isolated) │  │ (isolated) │  │             │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└─────────────────────────────────────────────────────────────┘

* Pre-pilot/Pilot: ECS tasks run in PUBLIC subnets with public IPs to avoid NAT Gateway costs.
  Production: Switch to private subnets with NAT Gateway for better security.
```

### Components

| Component | Description |
|-----------|-------------|
| **API** | FastAPI backend serving REST endpoints |
| **Worker** | Celery workers processing background tasks |
| **Beat** | Celery Beat scheduler for periodic tasks |
| **Redis** | Message broker for Celery + caching |
| **PostgreSQL** | Primary database (RDS) |
| **Frontend** | TanStack Start SSR app (requires ECS deployment - TODO) |
| **ALB** | Application Load Balancer with HTTPS |

---

## Deployment Tiers

### Pre-Pilot (~$65-75/month)

Best for: Early testing, < 10 users, development validation

| Component | Specification |
|-----------|---------------|
| API | 0.25 vCPU, 0.5 GB, 1 task |
| Worker+Beat | 0.25 vCPU, 0.5 GB, 1 task (combined) |
| Redis | ElastiCache t4g.micro |
| RDS | db.t4g.micro, 20 GB, Single-AZ |
| Frontend | S3 + CloudFront |

**Trade-offs:**
- Worker and Beat run in same container (resource contention possible)
- Single-AZ database (brief downtime during maintenance)
- No auto-scaling
- ECS tasks run in public subnets (public IPs enabled automatically)

---

### Pilot (~$100-120/month)

Best for: Pilot phase, 10-50 users, production validation

| Component | Specification |
|-----------|---------------|
| API | 0.5 vCPU, 1 GB, 1-2 tasks |
| Worker | 0.5 vCPU, 1 GB, 1-2 tasks |
| Beat | 0.25 vCPU, 0.5 GB, 1 task (singleton) |
| Redis | ElastiCache t4g.micro |
| RDS | db.t4g.micro, 20 GB, Single-AZ |
| Frontend | S3 + CloudFront |

**Improvements over Pre-Pilot:**
- Separate Worker and Beat services
- Managed Redis with better reliability
- Can scale API/Worker independently
- More memory for data processing

---

### Production (~$250-350/month)

Best for: Production workloads, 50+ users, high reliability

| Component | Specification |
|-----------|---------------|
| API | 0.5 vCPU, 1 GB, 2-10 tasks (auto-scaling) |
| Worker | 0.5 vCPU, 1 GB, 2-10 tasks |
| Beat | 0.25 vCPU, 0.5 GB, 1 task (singleton) |
| Redis | ElastiCache t4g.small |
| RDS | db.t4g.small, 50 GB, Multi-AZ |
| Frontend | S3 + CloudFront |

**Improvements over Pilot:**
- Multi-AZ database (automatic failover)
- Auto-scaling on CPU utilization
- Larger Redis for more connections
- 7-year log retention (HIPAA)
- Performance Insights enabled

---

## Prerequisites

### 1. AWS Account Setup

- AWS account with admin access
- AWS CLI configured (`aws configure`)
- Domain registered and Route53 hosted zone created

### 2. Shared VPC

The shared VPC must be deployed first. This creates the networking infrastructure shared across Sense Loop services.

```bash
cd ../sense-loop-infra/shared-vpc
npm install
npm run deploy:staging
```

This creates SSM parameters that Open Wearables reads:
- `/sense-loop/staging/vpc-id`
- `/sense-loop/staging/private-subnet-ids`
- `/sense-loop/staging/public-subnet-ids`
- `/sense-loop/staging/isolated-subnet-ids`

### 3. DNS Configuration

Ensure these DNS records can be created (SST handles this automatically if Route53 is configured):

| Record | Domain |
|--------|--------|
| API | `wearables.staging.senselooplabs.com` |
| Frontend | `dashboard.wearables.staging.senselooplabs.com` |

### 4. External Service Credentials

Gather credentials for:
- Garmin Connect API (optional, for wearable sync)
- Fitbit API (optional, for wearable sync)
- Firebase (push notifications for Sense Loop mobile app)
- SendGrid (email notifications)

---

## Initial Setup

### 1. Install Dependencies

```bash
cd infra
npm install
```

### 2. Configure Secrets

Set all required secrets for your stage:

```bash
# Core secrets (required)
npx sst secret set SecretKey "$(openssl rand -hex 32)" --stage staging

# Wearable providers (optional - only if using Garmin/Fitbit sync)
npx sst secret set GarminClientId "your-garmin-id" --stage staging
npx sst secret set GarminClientSecret "your-garmin-secret" --stage staging
npx sst secret set FitbitClientId "your-fitbit-id" --stage staging
npx sst secret set FitbitClientSecret "your-fitbit-secret" --stage staging

# Sense Loop services (required for mobile app)
npx sst secret set SlFirebaseCredentials '{"type":"service_account",...}' --stage staging
npx sst secret set SlSendgridApiKey "SG.your-sendgrid-key" --stage staging
```

### 3. Verify Secrets

```bash
npx sst secret list --stage staging
```

---

## Deployment Commands

### Pre-Pilot Deployment

```bash
# Deploy backend only (API + Worker+Beat + ElastiCache)
npm run deploy:pre-pilot
```

> **Note:** Frontend deployment (`DEPLOY_FRONTEND=true`) is not yet supported. The frontend uses TanStack Start with SSR which requires server-side rendering. It needs to be deployed as an ECS service or Lambda, not as a static S3 site. For now, run the frontend locally with `npm run dev` in the `/frontend` directory.

### Pilot Deployment

```bash
# Deploy backend only (API + Worker + Beat + ElastiCache)
npm run deploy:pilot

# Deploy with frontend dashboard
npm run deploy:pilot:with-frontend
```

### Production Deployment

```bash
# Deploy backend only
npm run deploy:production

# Deploy with frontend dashboard
npm run deploy:production:with-frontend
```

### Check Deployment Status

After deployment, SST outputs key information:

```
Outputs:
  mode: pre-pilot
  apiUrl: https://wearables.staging.senselooplabs.com
  frontendUrl: https://dashboard.wearables.staging.senselooplabs.com
  dbHost: open-wearables-staging.xxxxx.us-west-2.rds.amazonaws.com
  redisHost: open-wearables-staging.xxxxx.cache.amazonaws.com
  estimatedMonthlyCost: $65-75
```

### Post-Deploy Steps

**DNS Configuration**

After deployment, configure DNS to point to the ALB. SST handles this automatically if Route53 is configured for your domain. If using external DNS:

```bash
# Get ALB DNS name
aws elbv2 describe-load-balancers --query 'LoadBalancers[0].DNSName' --output text

# Create CNAME record pointing your domain to the ALB DNS name
# Example: wearables.staging.senselooplabs.com -> ApiLoadBalancer-xxx.us-west-2.elb.amazonaws.com
```

**Verify Services Are Running**

```bash
# Check ECS services status
CLUSTER=$(aws ecs list-clusters --query 'clusterArns[0]' --output text | xargs basename)
aws ecs describe-services --cluster $CLUSTER --services Api WorkerBeat \
  --query 'services[*].{name:serviceName,status:status,running:runningCount,desired:desiredCount}' \
  --output table
```

**Note:** Public IPs are automatically enabled for pre-pilot/pilot deployments via the SST config. No manual intervention required.

### Verify Deployment

```bash
# Check API health
curl https://wearables.staging.senselooplabs.com/

# Expected response:
# {"message": "Server is running!"}
```

---

## Scaling Up

### Pre-Pilot → Pilot

When you're ready for more users or need better reliability:

```bash
# This will:
# - Split Worker+Beat into separate services
# - Increase API/Worker memory to 1 GB
npm run deploy:pilot:with-frontend
```

**What changes:**
| Component | Before | After |
|-----------|--------|-------|
| Worker | Combined with Beat | Separate service |
| Beat | Combined with Worker | Dedicated singleton |
| Memory | 0.5 GB each | 1 GB for API/Worker |
| Cost | ~$70/month | ~$110/month |

**Downtime:** Minimal (rolling deployment).

---

### Pilot → Production

When you're ready for production workloads:

```bash
npm run deploy:production:with-frontend
```

**What changes:**
| Component | Before | After |
|-----------|--------|-------|
| RDS | Single-AZ, micro | Multi-AZ, small |
| API scaling | 1-2 tasks | 2-10 tasks (auto) |
| Worker scaling | 1-2 tasks | 2-10 tasks |
| Redis | t4g.micro | t4g.small |
| Logs | 1 month | 7 years (HIPAA) |
| Cost | ~$110/month | ~$300/month |

**Downtime:** RDS Multi-AZ conversion takes 10-30 minutes with potential brief interruption.

---

## Security

### Included Security Measures

| Layer | Measure | Pre-Pilot/Pilot | Production |
|-------|---------|-----------------|------------|
| Network | VPC isolation | ✅ | ✅ |
| Network | Private subnets for ECS | ❌ (public*) | ✅ |
| Network | Security groups (least privilege) | ✅ | ✅ |
| Transport | HTTPS/TLS via ALB | ✅ | ✅ |
| Transport | SSL required for RDS | ✅ | ✅ |
| Data | RDS encryption at rest | ✅ | ✅ |
| Data | S3 encryption (SSE-S3) | ✅ | ✅ |
| Secrets | SST Secrets (AWS SSM) | ✅ | ✅ |
| Auth | JWT tokens | ✅ | ✅ |
| Audit | pgAudit logging | ✅ | ✅ |

*Pre-pilot/Pilot use public subnets with public IPs to avoid NAT Gateway costs. Production should use private subnets with NAT Gateway.

### HIPAA Compliance Checklist

| Requirement | Pre-Pilot | Pilot | Production |
|-------------|-----------|-------|------------|
| Encryption at rest | ✅ | ✅ | ✅ |
| Encryption in transit | ✅ | ✅ | ✅ |
| Access controls | ✅ | ✅ | ✅ |
| Audit logging | ⚠️ 1 month | ⚠️ 1 month | ✅ 7 years |
| Multi-AZ (availability) | ❌ | ❌ | ✅ |
| AWS BAA signed | Required before PHI | Required | Required |

### Before Handling Real PHI

1. Sign AWS Business Associate Agreement (BAA)
2. Upgrade to Production tier (7-year log retention)
3. Enable CloudTrail for AWS API auditing
4. Consider adding WAF for additional protection

---

## Monitoring

### CloudWatch Logs

All services log to CloudWatch. Log groups:

- `/aws/ecs/open-wearables-staging-Api`
- `/aws/ecs/open-wearables-staging-Worker` (or WorkerBeat)
- `/aws/ecs/open-wearables-staging-Beat` (pilot/prod only)

### Key Metrics to Watch

| Metric | Location | Alert Threshold |
|--------|----------|-----------------|
| API CPU | ECS Console | > 80% sustained |
| API Memory | ECS Console | > 85% |
| RDS CPU | RDS Console | > 80% sustained |
| RDS Connections | RDS Console | > 80% of max |
| RDS Storage | RDS Console | > 80% used |
| Celery Queue Depth | Application logs | > 100 pending |

### Health Check Endpoints

| Service | Endpoint | Expected |
|---------|----------|----------|
| API | `GET /` | `{"message": "Server is running!"}` |
| Celery | `GET /api/v1/celery/health` | `{"status": "healthy"}` |

---

## Troubleshooting

### Deployment Fails

**"Cannot find VPC parameters"**
```bash
# Ensure shared VPC is deployed
cd ../sense-loop-infra/shared-vpc
npm run deploy:staging
```

**"Secret not found"**
```bash
# List secrets to see what's missing
npx sst secret list --stage staging

# Set missing secret
npx sst secret set SecretName "value" --stage staging
```

### Service Won't Start

**Check ECS logs:**
```bash
# Via AWS CLI
aws logs tail /aws/ecs/open-wearables-staging-Api --follow

# Or use AWS Console → CloudWatch → Log Groups
```

**Common issues:**
- Database connection failed: Check security groups allow 5432 from ECS
- Redis connection failed: Check Redis is running and accessible
- Migration failed: Check database credentials and connectivity

### ECR Pull Failures / Tasks Won't Start

**Error:** `ResourceInitializationError: unable to pull secrets or registry auth... i/o timeout`

**Cause:** ECS tasks in public subnets without public IPs cannot reach ECR.

**Solution:** This is now handled automatically in the SST config. Pre-pilot/pilot deployments set `assignPublicIp: ENABLED` via the service transform. If you still see this error after a fresh deployment, verify the services are using the latest task definition:

```bash
# Force new deployment to pick up network config changes
CLUSTER=$(aws ecs list-clusters --query 'clusterArns[0]' --output text | xargs basename)
aws ecs update-service --cluster $CLUSTER --service Api --force-new-deployment
aws ecs update-service --cluster $CLUSTER --service WorkerBeat --force-new-deployment
```

**For production:** Switch to private subnets with NAT Gateway for better security (set `USE_PRIVATE_SUBNETS=true`).

### DNS Not Resolving

**Error:** `Could not resolve host: wearables.staging.senselooplabs.com`

**Cause:** DNS records haven't been created for the API domain.

**Solution:** SST automatically creates Route53 records if:
1. The domain's hosted zone exists in Route53
2. The ACM certificate is valid for the domain

Check these:
```bash
# Verify hosted zone exists
aws route53 list-hosted-zones --query 'HostedZones[*].Name' --output text | grep senselooplabs

# Check ACM certificate status
aws acm list-certificates --query 'CertificateSummaryList[?contains(DomainName, `senselooplabs`)].{Domain:DomainName,Status:Status}' --output table
```

If using external DNS (not Route53), manually create a CNAME record:
```bash
# Get ALB DNS name
aws elbv2 describe-load-balancers --query 'LoadBalancers[0].DNSName' --output text
# Create: wearables.staging.senselooplabs.com CNAME -> <ALB DNS name>
```

---

### Database Connection Issues

```bash
# Test from local (requires VPN or bastion)
psql -h <rds-endpoint> -U postgres -d open_wearables

# Check security group allows your IP
aws ec2 describe-security-groups --group-ids <sg-id>
```

### Redis Connection Issues

**All tiers use ElastiCache:**
```bash
# Check ElastiCache status
aws elasticache describe-cache-clusters --cache-cluster-id open-wearables-staging

# Check security group allows ECS → Redis on port 6379
aws ec2 describe-security-groups --group-ids <redis-sg-id>
```

---

## Cost Optimization

### Quick Wins

| Optimization | Savings | Command/Action |
|--------------|---------|----------------|
| Use Pre-Pilot mode | ~$40/month | `npm run deploy:pre-pilot` |
| 1-month log retention | ~$10/month | Default in staging |
| Single-AZ RDS | ~$15/month | Default in staging |
| Public subnets (no NAT) | ~$32/month | Default in pre-pilot/pilot |

### Reserved Instances (for stable workloads)

| Resource | On-Demand | 1-Year Reserved | Savings |
|----------|-----------|-----------------|---------|
| RDS db.t4g.micro | $15/month | $9/month | 40% |
| ElastiCache t4g.micro | $12/month | $8/month | 33% |

### Scaling Down Off-Hours

For non-production, you can scale to zero at night:

```bash
# Scale down (manual)
aws ecs update-service --cluster open-wearables-staging \
  --service Api --desired-count 0

# Scale up
aws ecs update-service --cluster open-wearables-staging \
  --service Api --desired-count 1
```

---

## Teardown

### Remove Staging Environment

```bash
# This will delete ALL resources except RDS (if skip_final_snapshot=false)
npm run remove:staging
```

**Warning:** This is destructive. Ensure you have backups if needed.

### Remove Production

Production has `protect: true` and `removal: retain`. To remove:

1. Manually disable protection in AWS Console
2. Run `sst remove --stage production`
3. Manually delete retained resources (RDS snapshots, etc.)

---

## Quick Reference

### Deployment Commands

| Command | Description | Cost |
|---------|-------------|------|
| `npm run deploy:pre-pilot` | Cheapest staging | ~$70/month |
| `npm run deploy:pre-pilot:with-frontend` | + Dashboard | ~$72/month |
| `npm run deploy:pilot` | Full staging | ~$110/month |
| `npm run deploy:pilot:with-frontend` | + Dashboard | ~$112/month |
| `npm run deploy:production` | Production | ~$300/month |
| `npm run deploy:production:with-frontend` | + Dashboard | ~$302/month |

### Useful Commands

```bash
# Check deployment outputs
npx sst output --stage staging

# View logs
aws logs tail /aws/ecs/open-wearables-staging-Api --follow

# List secrets
npx sst secret list --stage staging

# Update a secret
npx sst secret set SecretName "new-value" --stage staging

# Remove deployment
npm run remove:staging
```

### Support

- SST Documentation: https://docs.sst.dev/
- AWS ECS Documentation: https://docs.aws.amazon.com/ecs/
- Project Issues: https://github.com/Sense-Loop-Labs/open-wearables/issues
