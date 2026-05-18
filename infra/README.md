# Open Wearables Infrastructure (SST)

This folder contains the SST configuration for deploying Open Wearables as part of the Sense Loop platform.

## Architecture

Open Wearables is deployed into the **shared Sense Loop VPC**, allowing internal communication with Medplum:

```
┌─────────────────────── Shared VPC ────────────────────────────┐
│                                                               │
│  ┌─────────────────────────┐    ┌─────────────────────────┐  │
│  │ Open Wearables (SST)    │    │ Medplum (CDK)           │  │
│  │                         │    │                         │  │
│  │ • API Service           │◄──►│ • FHIR Server           │  │
│  │ • Worker Service        │    │ • Bots                  │  │
│  │ • Beat Service          │    │                         │  │
│  │ • RDS PostgreSQL        │    │                         │  │
│  │ • ElastiCache Redis     │    │                         │  │
│  └─────────────────────────┘    └─────────────────────────┘  │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. Deploy the Shared VPC

The shared VPC must be deployed first:

```bash
cd ../../sense-loop-infra/shared-vpc
npm install
npm run deploy:staging
```

### 2. Configure AWS Credentials

Ensure your AWS CLI is configured:

```bash
aws configure
# Or use environment variables:
export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=xxx
export AWS_REGION=us-east-1
```

### 3. Set Required Secrets

```bash
cd infra

# Application secret key
npx sst secret set SecretKey "$(openssl rand -hex 32)" --stage staging

# Medplum integration (get these from Medplum admin UI)
npx sst secret set MedplumClientId "<your-client-id>" --stage staging
npx sst secret set MedplumClientSecret "<your-client-secret>" --stage staging

# Wearable providers (optional, add as needed)
npx sst secret set GarminClientId "<garmin-client-id>" --stage staging
npx sst secret set GarminClientSecret "<garmin-client-secret>" --stage staging
npx sst secret set FitbitClientId "<fitbit-client-id>" --stage staging
npx sst secret set FitbitClientSecret "<fitbit-client-secret>" --stage staging
```

## Deployment

### Staging

```bash
cd infra
npm install

# Deploy
npm run deploy:staging

# View outputs
npx sst outputs --stage staging
```

### Production

```bash
# First, set production secrets
npx sst secret set SecretKey "$(openssl rand -hex 32)" --stage production
npx sst secret set MedplumClientId "<prod-client-id>" --stage production
npx sst secret set MedplumClientSecret "<prod-client-secret>" --stage production

# Deploy
npm run deploy:production
```

## Services Deployed

| Service | Purpose | Scaling |
|---------|---------|---------|
| **API** | FastAPI backend, REST endpoints, OAuth flows | Auto-scale 1-10 |
| **Worker** | Celery workers for async tasks, webhooks | Auto-scale 1-10 |
| **Beat** | Celery scheduler for periodic sync jobs | Singleton (1 only) |
| **RDS** | PostgreSQL database with pgaudit | Single instance / Multi-AZ |
| **Redis** | Celery broker, caching | Single node |

## Environment Variables

The following environment variables are automatically configured:

| Variable | Source |
|----------|--------|
| `SECRET_KEY` | SST Secret |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | RDS instance |
| `REDIS_HOST`, `REDIS_PORT` | ElastiCache cluster |
| `MEDPLUM_BASE_URL`, `MEDPLUM_CLIENT_ID`, `MEDPLUM_CLIENT_SECRET` | SST Secrets |
| `GARMIN_CLIENT_ID`, `GARMIN_CLIENT_SECRET` | SST Secrets (optional) |
| `FITBIT_CLIENT_ID`, `FITBIT_CLIENT_SECRET` | SST Secrets (optional) |

## HIPAA Compliance

This deployment includes:

- **pgaudit** enabled on RDS for database audit logging
- **7-year log retention** on all CloudWatch log groups
- **Encryption at rest** for RDS and Redis
- **Encryption in transit** via TLS
- **Private subnets** for all services
- **Isolated subnets** for databases (no internet access)

## Costs (Estimated)

| Component | Staging | Production |
|-----------|---------|------------|
| ECS Fargate (3 services) | ~$27/mo | ~$80/mo |
| RDS PostgreSQL | ~$12/mo | ~$50/mo |
| ElastiCache Redis | ~$12/mo | ~$25/mo |
| ALB | ~$18/mo | ~$25/mo |
| **Total** | **~$70/mo** | **~$180/mo** |

*Note: VPC costs (NAT, endpoints) are shared with Medplum via the shared VPC stack.*

## Troubleshooting

### View Logs

```bash
# API logs
npx sst logs --stage staging

# Specific service
npx sst logs Api --stage staging
npx sst logs Worker --stage staging
```

### Connect to Database

```bash
# Get connection info
npx sst outputs --stage staging

# Use a bastion or SSM Session Manager to connect
```

### Check Service Health

```bash
# Get API URL
API_URL=$(npx sst outputs --stage staging | grep apiUrl | awk '{print $2}')
curl $API_URL/health
```

## Removing

```bash
# Remove staging (data will be lost!)
npm run remove:staging

# Production should NEVER be removed via CLI
# Use AWS Console if absolutely necessary
```
