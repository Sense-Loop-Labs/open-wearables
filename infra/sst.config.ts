/// <reference path="./.sst/platform/config.d.ts" />

/**
 * Open Wearables SST Configuration for Sense Loop
 *
 * Deployment Modes:
 * - PRE_PILOT (staging): ~$55-65/month - Combined worker+beat, Redis container, S3 frontend
 * - PILOT (staging):     ~$100-120/month - Separate services, ElastiCache, S3 frontend
 * - PRODUCTION:          ~$250-350/month - Multi-AZ, full scaling, all features
 *
 * Prerequisites:
 * 1. Deploy the shared VPC first:
 *    cd ../sense-loop-infra/shared-vpc && npm run deploy:staging
 *
 * 2. Set required secrets:
 *    npx sst secret set SecretKey "$(openssl rand -hex 32)" --stage staging
 *
 * Deployment Commands:
 *    # Pre-pilot (cheapest, ~$55-65/month):
 *    PRE_PILOT=true npm run deploy:staging
 *
 *    # Pilot (full staging, ~$100-120/month):
 *    npm run deploy:staging
 *
 *    # With frontend dashboard:
 *    PRE_PILOT=true DEPLOY_FRONTEND=true npm run deploy:staging
 *
 *    # Production:
 *    npm run deploy:production
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
        command: true,
      },
    };
  },

  async run() {
    const stage = $app.stage;
    const isProduction = stage === "production";
    const isPrePilot = process.env.PRE_PILOT === "true" && !isProduction;
    const deployFrontend = process.env.DEPLOY_FRONTEND === "true";

    // Log deployment mode
    if (isPrePilot) {
      console.log("\n🚀 PRE-PILOT MODE: Cost-optimized deployment (~$65-75/month)");
      console.log("   - Combined Worker+Beat service");
      console.log("   - ElastiCache Redis (t4g.micro)");
      console.log("   - S3 + CloudFront for frontend");
      console.log("   To upgrade to pilot: npm run deploy:staging (without PRE_PILOT)\n");
    } else if (!isProduction) {
      console.log("\n🚀 PILOT MODE: Full staging deployment (~$100-120/month)");
      console.log("   - Separate Worker and Beat services");
      console.log("   - ElastiCache Redis (t4g.micro)");
      console.log("   - S3 + CloudFront for frontend\n");
    }

    // Cost optimization: reduce log retention for staging
    const logRetention = isProduction ? "7 years" : "1 month";

    // ================================================================
    // SECRETS
    // ================================================================
    const secretKey = new sst.Secret("SecretKey");

    // Wearable provider OAuth credentials
    const garminClientId = new sst.Secret("GarminClientId");
    const garminClientSecret = new sst.Secret("GarminClientSecret");
    const fitbitClientId = new sst.Secret("FitbitClientId");
    const fitbitClientSecret = new sst.Secret("FitbitClientSecret");

    // Sense Loop specific secrets
    const slFirebaseCredentials = new sst.Secret("SlFirebaseCredentials");
    const slSendgridApiKey = new sst.Secret("SlSendgridApiKey");

    // ================================================================
    // IMPORT SHARED VPC
    // ================================================================
    const vpcId = await aws.ssm.getParameter({
      name: `/sense-loop/${stage}/vpc-id`,
    }).then(p => p.value!);

    const privateSubnetIds = await aws.ssm.getParameter({
      name: `/sense-loop/${stage}/private-subnet-ids`,
    }).then(p => p.value!.split(","));

    const isolatedSubnetIds = await aws.ssm.getParameter({
      name: `/sense-loop/${stage}/isolated-subnet-ids`,
    }).then(p => p.value!.split(","));

    const publicSubnetIds = await aws.ssm.getParameter({
      name: `/sense-loop/${stage}/public-subnet-ids`,
    }).then(p => p.value!.split(","));

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
          cidrBlocks: ["10.0.0.0/16"],
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
      multiAz: isProduction, // Only production gets Multi-AZ
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
    // REDIS (ElastiCache - t4g.micro for staging, t4g.small for production)
    // ================================================================
    let redisHost: pulumi.Output<string>;
    let redisPort = "6379";

    const redisSecurityGroup = new aws.ec2.SecurityGroup("RedisSecurityGroup", {
      vpcId: vpc.id,
      description: "Security group for Open Wearables Redis",
      ingress: [
        {
          protocol: "tcp",
          fromPort: 6379,
          toPort: 6379,
          cidrBlocks: ["10.0.0.0/16"],
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

    const elasticacheCluster = new aws.elasticache.Cluster("Redis", {
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

    redisHost = elasticacheCluster.cacheNodes[0].address;

    // ================================================================
    // ECS CLUSTER
    // ================================================================
    const clusterSecurityGroup = new aws.ec2.SecurityGroup("ClusterSecurityGroup", {
      vpcId: vpc.id,
      description: "Security group for Open Wearables ECS cluster",
      ingress: [
        {
          protocol: "tcp",
          fromPort: 8000,
          toPort: 8000,
          cidrBlocks: ["10.0.0.0/16"],
        },
        {
          protocol: "tcp",
          fromPort: 3000,
          toPort: 3000,
          cidrBlocks: ["10.0.0.0/16"],
        },
        {
          protocol: "tcp",
          fromPort: 6379,
          toPort: 6379,
          cidrBlocks: ["10.0.0.0/16"],
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

    // For pre-pilot/pilot: use public subnets to avoid NAT Gateway costs (~$35/month savings)
    // For production: switch to private subnets and add NAT Gateway for better security
    const usePrivateSubnets = isProduction || process.env.USE_PRIVATE_SUBNETS === "true";

    if (!usePrivateSubnets) {
      console.log("   - ECS tasks in PUBLIC subnets (no NAT Gateway costs)");
    }

    const cluster = new sst.aws.Cluster("Cluster", {
      vpc: {
        id: vpcId,
        publicSubnets: publicSubnetIds,
        privateSubnets: privateSubnetIds,
        // Use public subnets for staging to avoid NAT costs, private for production
        containerSubnets: usePrivateSubnets ? privateSubnetIds : publicSubnetIds,
        securityGroups: [clusterSecurityGroup.id],
      },
    });

    // ================================================================
    // SHARED ENVIRONMENT VARIABLES
    // ================================================================
    const getSharedEnv = () => ({
      ENVIRONMENT: stage,
      SECRET_KEY: secretKey.value,

      // Database (SSL required for security)
      DB_HOST: db.address,
      DB_PORT: "5432",
      DB_NAME: "open_wearables",
      DB_USER: "postgres",
      DB_PASSWORD: dbPassword.result,
      DB_SSL: "require",

      // Redis
      REDIS_HOST: redisHost!,
      REDIS_PORT: redisPort,

      // Medplum integration (disabled - using Sense Loop extension)
      MEDPLUM_ENABLED: "false",

      // Svix webhooks (disabled - not deployed yet)
      SVIX_ENABLED: "false",

      // Wearable providers
      GARMIN_CLIENT_ID: garminClientId.value,
      GARMIN_CLIENT_SECRET: garminClientSecret.value,
      FITBIT_CLIENT_ID: fitbitClientId.value,
      FITBIT_CLIENT_SECRET: fitbitClientSecret.value,

      // Sense Loop
      SL_FIREBASE_CREDENTIALS_JSON: slFirebaseCredentials.value,
      SL_SENDGRID_API_KEY: slSendgridApiKey.value,
      SL_PUSH_NOTIFICATIONS_ENABLED: "true",

      // Sentry (optional - set via secret if needed)
      SENTRY_ENABLED: isProduction ? "true" : "false",
    });

    // ================================================================
    // API SERVICE
    // ================================================================
    const apiDomain = isProduction
      ? "wearables.senseloop.health"
      : "wearables.staging.senselooplabs.com";

    const api = new sst.aws.Service("Api", {
      cluster,
      cpu: isPrePilot ? "0.25 vCPU" : (isProduction ? "0.5 vCPU" : "0.5 vCPU"),
      memory: isPrePilot ? "0.5 GB" : "1 GB",
      image: {
        context: "../backend",
        dockerfile: "Dockerfile",
      },
      command: ["scripts/start/app.sh"],
      permissions: [
        {
          actions: ["ssm:PutParameter", "ssm:AddTagsToResource"],
          resources: [`arn:aws:ssm:us-west-2:*:parameter/sense-loop/${stage}/open-wearables/*`],
        },
      ],
      environment: {
        ...getSharedEnv(),
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
        startPeriod: "5 minutes",
      },
      scaling: isProduction
        ? { min: 2, max: 10, cpuUtilization: 70 }
        : { min: 1, max: 2 },
      loadBalancer: {
        domain: apiDomain,
        rules: [{ listen: "443/https", forward: "8000/http" }],
      },
      logging: {
        retention: logRetention,
      },
      transform: {
        loadBalancer: {
          subnets: publicSubnetIds,
        },
        service: {
          healthCheckGracePeriodSeconds: 300,
        },
      },
    });

    // ================================================================
    // WORKER SERVICE (Separate in pilot/prod, combined with beat in pre-pilot)
    // ================================================================
    let worker: sst.aws.Service | undefined;
    let beat: sst.aws.Service | undefined;

    if (isPrePilot) {
      // Pre-pilot: Combined Worker + Beat in one service
      worker = new sst.aws.Service("WorkerBeat", {
        cluster,
        cpu: "0.25 vCPU",
        memory: "0.5 GB",
        image: {
          context: "../backend",
          dockerfile: "Dockerfile",
        },
        command: ["scripts/start/worker-beat.sh"],
        environment: getSharedEnv(),
        logging: {
          retention: logRetention,
        },
      });
    } else {
      // Pilot/Production: Separate Worker and Beat services
      worker = new sst.aws.Service("Worker", {
        cluster,
        cpu: isProduction ? "0.5 vCPU" : "0.5 vCPU",
        memory: "1 GB",
        image: {
          context: "../backend",
          dockerfile: "Dockerfile",
        },
        command: ["scripts/start/worker.sh"],
        environment: getSharedEnv(),
        scaling: isProduction
          ? { min: 2, max: 10 }
          : { min: 1, max: 2 },
        logging: {
          retention: logRetention,
        },
      });

      beat = new sst.aws.Service("Beat", {
        cluster,
        cpu: "0.25 vCPU",
        memory: "0.5 GB",
        image: {
          context: "../backend",
          dockerfile: "Dockerfile",
        },
        command: ["scripts/start/beat.sh"],
        environment: getSharedEnv(),
        // Beat is a singleton - no scaling
        logging: {
          retention: logRetention,
        },
      });
    }

    // ================================================================
    // ENABLE PUBLIC IPs FOR ECS TASKS (Pre-Pilot/Pilot only)
    // ================================================================
    // Tasks in public subnets need public IPs to reach ECR (no NAT Gateway)
    // This runs after services are created to update the network configuration
    if (!usePrivateSubnets) {
      const subnetsJson = JSON.stringify(publicSubnetIds);
      const securityGroupsJson = clusterSecurityGroup.id.apply(id => JSON.stringify([id]));

      // Enable public IP on API service
      new command.local.Command("EnablePublicIpApi", {
        create: $interpolate`aws ecs update-service --cluster ${cluster.nodes.cluster.name} --service Api --network-configuration "awsvpcConfiguration={subnets=${subnetsJson},securityGroups=${securityGroupsJson},assignPublicIp=ENABLED}" --query 'service.serviceName' --output text`,
        triggers: [Date.now()], // Always run on deploy to ensure config is correct
      }, { dependsOn: [api] });

      // Enable public IP on Worker/WorkerBeat service
      if (isPrePilot) {
        new command.local.Command("EnablePublicIpWorkerBeat", {
          create: $interpolate`aws ecs update-service --cluster ${cluster.nodes.cluster.name} --service WorkerBeat --network-configuration "awsvpcConfiguration={subnets=${subnetsJson},securityGroups=${securityGroupsJson},assignPublicIp=ENABLED}" --query 'service.serviceName' --output text`,
          triggers: [Date.now()],
        }, { dependsOn: [worker!] });
      } else {
        new command.local.Command("EnablePublicIpWorker", {
          create: $interpolate`aws ecs update-service --cluster ${cluster.nodes.cluster.name} --service Worker --network-configuration "awsvpcConfiguration={subnets=${subnetsJson},securityGroups=${securityGroupsJson},assignPublicIp=ENABLED}" --query 'service.serviceName' --output text`,
          triggers: [Date.now()],
        }, { dependsOn: [worker!] });

        new command.local.Command("EnablePublicIpBeat", {
          create: $interpolate`aws ecs update-service --cluster ${cluster.nodes.cluster.name} --service Beat --network-configuration "awsvpcConfiguration={subnets=${subnetsJson},securityGroups=${securityGroupsJson},assignPublicIp=ENABLED}" --query 'service.serviceName' --output text`,
          triggers: [Date.now()],
        }, { dependsOn: [beat!] });
      }
    }

    // ================================================================
    // FRONTEND (S3 + CloudFront for all environments)
    // ================================================================
    const frontendDomain = isProduction
      ? "dashboard.wearables.senseloop.health"
      : "dashboard.wearables.staging.senselooplabs.com";

    let frontendUrl: string | undefined;

    if (deployFrontend) {
      // Build frontend and deploy to S3 + CloudFront
      const frontend = new sst.aws.StaticSite("Frontend", {
        path: "../frontend",
        build: {
          command: "pnpm run build",
          output: "dist",
        },
        environment: {
          VITE_API_URL: `https://${apiDomain}`,
        },
        domain: frontendDomain,
        // Enable SPA routing (fallback to index.html)
        errorPage: "index.html",
      });

      frontendUrl = frontend.url;
    }

    // ================================================================
    // OUTPUTS
    // ================================================================
    const outputs: Record<string, unknown> = {
      mode: isPrePilot ? "pre-pilot" : (isProduction ? "production" : "pilot"),
      apiUrl: `https://${apiDomain}`,
      dbHost: db.address,
      dbName: db.dbName,
      redisHost: redisHost!,
      vpcId: vpcId,
      estimatedMonthlyCost: isPrePilot ? "$65-75" : (isProduction ? "$250-350" : "$100-120"),
    };

    if (frontendUrl) {
      outputs.frontendUrl = frontendUrl;
    }

    // Security summary
    outputs.security = {
      dbEncryption: "enabled",
      dbSsl: "required",
      httpsOnly: true,
      vpcIsolation: true,
      privateSubnets: true,
      secretsManager: "SST Secrets (SSM)",
    };

    return outputs;
  },
});
