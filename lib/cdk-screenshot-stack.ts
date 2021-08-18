import path = require("path");
import { Bucket } from '@aws-cdk/aws-s3';
import { CfnOutput, Construct, Duration, Stack, StackProps } from '@aws-cdk/core';
import { ComputePlatform, ProfilingGroup } from "@aws-cdk/aws-codeguruprofiler";
import { DockerImageCode, DockerImageFunction, Tracing } from "@aws-cdk/aws-lambda";
import { HttpApi, HttpMethod } from '@aws-cdk/aws-apigatewayv2';
import { HttpProxyIntegration, LambdaProxyIntegration } from '@aws-cdk/aws-apigatewayv2-integrations';
import { ManagedPolicy, Role, ServicePrincipal } from '@aws-cdk/aws-iam';

export class CdkScreenshotStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Create S3 bucket
    const s3bucket = new Bucket(this, 'screenshotBucket');

    // Define Docker file for Lambda function
    const dockerfile = path.join(__dirname, "./../lambda");

    // create the Lambda IAM role
    const lambdaRole = new Role(this, 'lambdaRole', {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        ManagedPolicy.fromAwsManagedPolicyName('AWSXRayDaemonWriteAccess'),
        ManagedPolicy.fromAwsManagedPolicyName('AmazonCodeGuruProfilerAgentAccess')
      ]
    });

    // create the codeguru profiling group
    const pgroup = new ProfilingGroup(this, 'screenshotProfiling', {
      computePlatform: ComputePlatform.AWS_LAMBDA
    });

    // create Lambda function using Docker image
    const lambda = new DockerImageFunction(this, "screenshotLambda", {
      code: DockerImageCode.fromImageAsset(dockerfile),
      memorySize: 4096,
      timeout: Duration.seconds(30),
      tracing: Tracing.ACTIVE,
      reservedConcurrentExecutions: 2,
      retryAttempts: 0,
      role: lambdaRole,
      environment: {
        "s3bucket": s3bucket.bucketName,
        "AWS_CODEGURU_PROFILER_GROUP_NAME": pgroup.profilingGroupName
      }
    });

    // Grant s3 read write access to lambda function
    s3bucket.grantReadWrite(lambda);

    // Create HTTP API Gateway
    const apigw = new HttpApi(this, 'screenshotAPI', {
      createDefaultStage: true,
      defaultIntegration: new LambdaProxyIntegration({
        handler: lambda
      })
    });

    // Create a GET route for favicon, so it doesn't trigger the Lambda function
    const faviconIntegration = new HttpProxyIntegration({
      url: 'https://marek.rocks/favicon.ico'
    });

    // Add favicon route to API Gateway
    apigw.addRoutes({
      integration: faviconIntegration,
      path: '/favicon.ico',
      methods: [ HttpMethod.ANY ]
    })

    // Print API Gateway URL
    new CfnOutput(this, 'API URL', { value: apigw.url ?? 'deployment error' });

  }
}
