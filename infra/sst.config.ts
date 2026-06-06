/// <reference path="./.sst/platform/config.d.ts" />

/**
 * Open Wearables SST Configuration for Sense Loop
 *
 * This config deploys Open Wearables into the shared Sense Loop VPC,
 * allowing internal communication with Medplum.
 *
 * Prerequisites:
 * 1. Deploy the shared VPC first:
 *    cd ../sense-loop-infra/shared-vpc && npm run deploy:staging
 *
 * 2. Set required secrets:
 *    npx sst secret set SecretKey "$(openssl rand -hex 32)" --stage staging
 *    npx sst secret set MedplumClientId "<client-id>" --stage staging
 *    npx sst secret set MedplumClientSecret "<client-secret>" --stage staging
 *
 * Deployment (API only):
 *    npm run deploy:staging
 *    npm run deploy:production
 *
 * Deployment (with Frontend dashboard):
 *    DEPLOY_FRONTEND=true npm run deploy:staging
 *    DEPLOY_FRONTEND=true npm run deploy:production
 */

export default $config({
  app(input) {
    return {
      name: "open-wearables",
      removal: input.stage === "production" ? "retain" : "remove",
      protect: ["production"].includes(input.stage),
      home: "aws",
      providers: {
        aws: {
          region: "us-west-2",
        },
        random: true,
      },
    };
  },

  async run() {
    const stage = $app.stage;
    const isProduction = stage === "production";

    // ================================================================
    // SECRETS
    // ================================================================
    const secretKey = new sst.Secret("SecretKey");
    const medplumClientId = new sst.Secret("MedplumClientId");
    const medplumClientSecret = new sst.Secret("MedplumClientSecret");
    // Webhook URL to FHIR Conversion Bot (format: https://api.xxx/fhir/R4/Bot/{BOT_ID}/$execute)
    const medplumWebhookUrl = new sst.Secret("MedplumWebhookUrl");

    // Wearable provider OAuth credentials (add as needed)
    const garminClientId = new sst.Secret("GarminClientId");
    const garminClientSecret = new sst.Secret("GarminClientSecret");
    const fitbitClientId = new sst.Secret("FitbitClientId");
    const fitbitClientSecret = new sst.Secret("FitbitClientSecret");

    // Optional frontend deployment
    // Set DEPLOY_FRONTEND=true environment variable or pass --deploy-frontend flag
    const deployFrontend = process.env.DEPLOY_FRONTEND === "true";

    // Cost optimization mode - reduces log retention for staging (~$3/month savings)
    // Set COST_OPTIMIZED=true to enable
    const costOptimized = process.env.COST_OPTIMIZED === "true";
    const logRetention = (costOptimized && !isProduction) ? "1 month" : "7 years";

    if (costOptimized && !isProduction) {
      console.log("\n⚠️  COST_OPTIMIZED=true: Log retention reduced to 1 month (~$3/month savings)");
      console.log("   To restore full infrastructure: COST_OPTIMIZED=false npm run deploy:staging\n");
    }

    // ================================================================
    // IMPORT SHARED VPC
    // ================================================================
    // The shared VPC is created by the CDK stack in sense-loop-infra/shared-vpc
    // Get the VPC ID from SSM Parameter Store

    const vpcId = await aws.ssm.getParameter({
      name: `/sense-loop/${stage}/vpc-id`,
    }).then(p => p.value!);

    const privateSubnetIds = await aws.ssm.getParameter({
      name: `/sense-loop/${stage}/private-subnet-ids`,
    }).then(p => p.value!.split(","));

    const isolatedSubnetIds = await aws.ssm.getParameter({
      name: `/sense-loop/${stage}/isolated-subnet-ids`,
    }).then(p => p.value!.split(","));

    // Import the VPC
    const vpc = aws.ec2.Vpc.get("SharedVpc", vpcId);

    // ================================================================
    // DATABASE (RDS PostgreSQL)
    // ================================================================
    const dbSecurityGroup = new aws.ec2.SecurityGroup("DbSecurityGroup", {
      vpcId: vpc.id,
      description: "Security group for Open Wearables RDS",
      ingress: [
        {
          protocol: "tcp",
          fromPort: 5432,
          toPort: 5432,
          cidrBlocks: ["10.0.0.0/16"], // Allow from within VPC
        },
      ],
      egress: [
        {
          protocol: "-1",
          fromPort: 0,
          toPort: 0,
          cidrBlocks: ["0.0.0.0/0"],
        },
      ],
    });

    const dbSubnetGroup = new aws.rds.SubnetGroup("DbSubnetGroup", {
      name: `open-wearables-${stage}-db`,
      subnetIds: isolatedSubnetIds,
      description: "Subnet group for Open Wearables RDS",
    });

    // RDS Parameter Group with pgaudit for HIPAA compliance
    const dbParameterGroup = new aws.rds.ParameterGroup("DbParameterGroup", {
      name: `open-wearables-${stage}-pg16`,
      family: "postgres16",
      description: "Open Wearables PostgreSQL parameters with pgaudit",
      parameters: [
        { name: "shared_preload_libraries", value: "pgaudit", applyMethod: "pending-reboot" },
        { name: "pgaudit.log", value: "all", applyMethod: "pending-reboot" },
        { name: "pgaudit.log_catalog", value: "on", applyMethod: "pending-reboot" },
        { name: "pgaudit.log_parameter", value: "on", applyMethod: "pending-reboot" },
        { name: "pgaudit.log_statement_once", value: "on", applyMethod: "pending-reboot" },
      ],
    });

    const dbPassword = new random.RandomPassword("DbPassword", {
      length: 32,
      special: false,
    });

    const db = new aws.rds.Instance("Database", {
      identifier: `open-wearables-${stage}`,
      engine: "postgres",
      engineVersion: "16",
      instanceClass: isProduction ? "db.t4g.small" : "db.t4g.micro",
      allocatedStorage: isProduction ? 50 : 20,
      maxAllocatedStorage: isProduction ? 200 : 50,
      dbName: "open_wearables",
      username: "postgres",
      password: dbPassword.result,
      dbSubnetGroupName: dbSubnetGroup.name,
      vpcSecurityGroupIds: [dbSecurityGroup.id],
      parameterGroupName: dbParameterGroup.name,
      multiAz: isProduction,
      storageEncrypted: true,
      performanceInsightsEnabled: isProduction,
      backupRetentionPeriod: isProduction ? 7 : 1,
      skipFinalSnapshot: !isProduction,
      finalSnapshotIdentifier: isProduction ? `open-wearables-${stage}-final` : undefined,
      publiclyAccessible: false,
      tags: {
        Name: `open-wearables-${stage}`,
        Project: "SenseLoop",
        Stage: stage,
      },
    });

    // ================================================================
    // REDIS (ElastiCache)
    // ================================================================
    const redisSecurityGroup = new aws.ec2.SecurityGroup("RedisSecurityGroup", {
      vpcId: vpc.id,
      description: "Security group for Open Wearables Redis",
      ingress: [
        {
          protocol: "tcp",
          fromPort: 6379,
          toPort: 6379,
          cidrBlocks: ["10.0.0.0/16"], // Allow from within VPC
        },
      ],
      egress: [
        {
          protocol: "-1",
          fromPort: 0,
          toPort: 0,
          cidrBlocks: ["0.0.0.0/0"],
        },
      ],
    });

    const redisSubnetGroup = new aws.elasticache.SubnetGroup("RedisSubnetGroup", {
      subnetIds: isolatedSubnetIds,
      description: "Subnet group for Open Wearables Redis",
    });

    const redis = new aws.elasticache.Cluster("Redis", {
      clusterId: `open-wearables-${stage}`,
      engine: "redis",
      nodeType: isProduction ? "cache.t4g.small" : "cache.t4g.micro",
      numCacheNodes: 1,
      parameterGroupName: "default.redis7",
      subnetGroupName: redisSubnetGroup.name,
      securityGroupIds: [redisSecurityGroup.id],
      tags: {
        Name: `open-wearables-${stage}`,
        Project: "SenseLoop",
        Stage: stage,
      },
    });

    // ================================================================
    // ECS CLUSTER
    // ================================================================
    const publicSubnetIds = await aws.ssm.getParameter({
      name: `/sense-loop/${stage}/public-subnet-ids`,
    }).then(p => p.value!.split(","));

    // Security group for ECS tasks
    const clusterSecurityGroup = new aws.ec2.SecurityGroup("ClusterSecurityGroup", {
      vpcId: vpc.id,
      description: "Security group for Open Wearables ECS cluster",
      ingress: [
        {
          protocol: "tcp",
          fromPort: 8000,
          toPort: 8000,
          cidrBlocks: ["10.0.0.0/16"], // Allow API from within VPC
        },
        {
          protocol: "tcp",
          fromPort: 3000,
          toPort: 3000,
          cidrBlocks: ["10.0.0.0/16"], // Allow Frontend from within VPC
        },
      ],
      egress: [
        {
          protocol: "-1",
          fromPort: 0,
          toPort: 0,
          cidrBlocks: ["0.0.0.0/0"],
        },
      ],
    });

    const cluster = new sst.aws.Cluster("Cluster", {
      vpc: {
        id: vpcId,
        publicSubnets: publicSubnetIds,
        privateSubnets: privateSubnetIds,
        containerSubnets: privateSubnetIds, // ECS tasks run in private subnets
        securityGroups: [clusterSecurityGroup.id],
      },
    });

    // ================================================================
    // SHARED ENVIRONMENT VARIABLES
    // ================================================================
    const sharedEnv = {
      ENVIRONMENT: stage,
      SECRET_KEY: secretKey.value,

      // Database
      DB_HOST: db.address,
      DB_PORT: "5432",
      DB_NAME: "open_wearables",
      DB_USER: "postgres",
      DB_PASSWORD: dbPassword.result,
      DB_SSL: "require",

      // Redis
      REDIS_HOST: redis.cacheNodes[0].address,
      REDIS_PORT: "6379",

      // Medplum integration
      MEDPLUM_ENABLED: "true",
      MEDPLUM_WEBHOOK_URL: medplumWebhookUrl.value,
      MEDPLUM_CLIENT_ID: medplumClientId.value,
      MEDPLUM_CLIENT_SECRET: medplumClientSecret.value,

      // Wearable providers (optional)
      GARMIN_CLIENT_ID: garminClientId.value,
      GARMIN_CLIENT_SECRET: garminClientSecret.value,
      FITBIT_CLIENT_ID: fitbitClientId.value,
      FITBIT_CLIENT_SECRET: fitbitClientSecret.value,
    };

    // ================================================================
    // API SERVICE
    // ================================================================
    const api = new sst.aws.Service("Api", {
      cluster,
      cpu: isProduction ? "0.5 vCPU" : "0.25 vCPU",
      memory: isProduction ? "1 GB" : "0.5 GB",
      image: {
        context: "../backend",
        dockerfile: "Dockerfile",
      },
      command: ["scripts/start/app.sh"],
      // Allow seed_sense_loop.py to write credentials to SSM for Medplum integration
      permissions: [
        {
          actions: ["ssm:PutParameter", "ssm:AddTagsToResource"],
          resources: [`arn:aws:ssm:us-west-2:*:parameter/sense-loop/${stage}/open-wearables/*`],
        },
      ],
      environment: {
        ...sharedEnv,
        CORS_ORIGINS: JSON.stringify(
          isProduction
            ? ["https://app.senseloop.health", "https://dashboard.senseloop.health", "https://dashboard.wearables.senseloop.health"]
            : ["https://app.staging.senselooplabs.com", "https://dashboard.wearables.staging.senselooplabs.com", "http://localhost:3000"]
        ),
      },
      health: {
        command: ["CMD-SHELL", "curl -f http://localhost:8000/ || exit 1"],
        interval: "30 seconds",
        timeout: "5 seconds",
        startPeriod: "3 minutes", // Allow time for initialization scripts
      },
      scaling: isProduction
        ? { min: 2, max: 10, cpuUtilization: 70 }
        : { min: 1, max: 2 },
      vpc: {
        id: vpcId,
        publicSubnets: publicSubnetIds,
        privateSubnets: privateSubnetIds,
        securityGroups: [clusterSecurityGroup.id],
      },
      loadBalancer: {
        domain: isProduction
          ? "wearables.senseloop.health"
          : "wearables.staging.senselooplabs.com",
        rules: [{ listen: "443/https", forward: "8000/http" }],
      },
      logging: {
        retention: logRetention, // HIPAA: 7 years in production, 1 month if COST_OPTIMIZED
      },
      transform: {
        loadBalancer: {
          subnets: publicSubnetIds,
        },
        service: {
          healthCheckGracePeriodSeconds: 300, // 5 min grace for initialization
        },
      },
    });

    // ================================================================
    // WORKER SERVICE (Celery)
    // ================================================================
    const worker = new sst.aws.Service("Worker", {
      cluster,
      cpu: isProduction ? "0.5 vCPU" : "0.25 vCPU",
      memory: isProduction ? "1 GB" : "0.5 GB",
      image: {
        context: "../backend",
        dockerfile: "Dockerfile",
      },
      command: ["scripts/start/worker.sh"],
      environment: sharedEnv,
      scaling: isProduction
        ? { min: 2, max: 10 }
        : { min: 1, max: 2 },
      logging: {
        retention: logRetention,
      },
    });

    // ================================================================
    // BEAT SERVICE (Celery Scheduler - Singleton)
    // ================================================================
    const beat = new sst.aws.Service("Beat", {
      cluster,
      cpu: "0.25 vCPU",
      memory: "0.5 GB",
      image: {
        context: "../backend",
        dockerfile: "Dockerfile",
      },
      command: ["scripts/start/beat.sh"],
      environment: sharedEnv,
      // Beat must be a singleton - no scaling
      logging: {
        retention: logRetention,
      },
    });

    // ================================================================
    // FRONTEND (Optional)
    // ================================================================
    // To deploy with frontend: DEPLOY_FRONTEND=true npm run deploy:staging
    // To deploy without frontend: npm run deploy:staging

    const frontendDomain = isProduction
      ? "dashboard.wearables.senseloop.health"
      : "dashboard.wearables.staging.senselooplabs.com";

    let frontendUrl: string | undefined;

    if (deployFrontend) {
      const frontend = new sst.aws.Service("Frontend", {
        cluster,
        cpu: "0.25 vCPU",
        memory: "0.5 GB",
        image: {
          context: "../frontend",
          dockerfile: "Dockerfile",
          args: {
            VITE_API_URL: `https://${isProduction ? "wearables.senseloop.health" : "wearables.staging.senselooplabs.com"}`,
          },
        },
        // No container health check - rely on ALB health check only
        scaling: { min: 1, max: 2 },
        vpc: {
          id: vpcId,
          publicSubnets: publicSubnetIds,
          privateSubnets: privateSubnetIds,
          securityGroups: [clusterSecurityGroup.id],
        },
        loadBalancer: {
          domain: frontendDomain,
          rules: [{ listen: "443/https", forward: "3000/http" }],
        },
        logging: {
          retention: "1 month",
        },
        transform: {
          loadBalancer: {
            subnets: publicSubnetIds,
          },
        },
      });

      frontendUrl = `https://${frontendDomain}`;
    }

    // ================================================================
    // OUTPUTS
    // ================================================================
    const outputs: Record<string, unknown> = {
      apiUrl: api.url,
      dbHost: db.address,
      dbName: db.dbName,
      redisHost: redis.cacheNodes[0].address,
      vpcId: vpcId,
    };

    if (frontendUrl) {
      outputs.frontendUrl = frontendUrl;
    }

    return outputs;
  },
});
