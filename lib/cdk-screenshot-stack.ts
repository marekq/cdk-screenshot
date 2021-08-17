import * as cdk from '@aws-cdk/core';
import * as path from "path";
import { ComputePlatform, ProfilingGroup } from "@aws-cdk/aws-codeguruprofiler";
import { DockerImageFunction, DockerImageCode } from "@aws-cdk/aws-lambda";
import { Tracing } from '@aws-cdk/aws-lambda';
import { CfnOutput, Duration } from '@aws-cdk/core';
import { Bucket } from '@aws-cdk/aws-s3';
import { HttpApi, HttpMethod } from '@aws-cdk/aws-apigatewayv2';
import { LambdaProxyIntegration, HttpProxyIntegration } from '@aws-cdk/aws-apigatewayv2-integrations';
import { ServicePrincipal, Role, ManagedPolicy } from '@aws-cdk/aws-iam';

export class CdkScreenshotStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // create S3 bucket
    const s3bucket = new Bucket(this, 'screenshotBucket');

    // define Docker file for Lambda function
    const dockerfile = path.join(__dirname, "./../lambda");

    const lambdaRole = new Role(this, 'lambdaRole', {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        ManagedPolicy.fromAwsManagedPolicyName('AWSXRayDaemonWriteAccess'),
        ManagedPolicy.fromAwsManagedPolicyName('AmazonCodeGuruProfilerAgentAccess')
      ]
    });

    const pgroup = new ProfilingGroup(this, 'screenshotProfiling', {
      computePlatform: ComputePlatform.AWS_LAMBDA
    });

    // define Lambda function using Docker image
    const lambda = new DockerImageFunction(this, "screenshotLambda", {
      code: DockerImageCode.fromImageAsset(dockerfile),
      memorySize: 2048,
      timeout: Duration.seconds(10),
      tracing: Tracing.ACTIVE,
      reservedConcurrentExecutions: 2,
      retryAttempts: 0,
      role: lambdaRole,
      environment: {
        "s3bucket": s3bucket.bucketName,
        "AWS_CODEGURU_PROFILER_GROUP_NAME": pgroup.profilingGroupName
      }
    });

    s3bucket.grantReadWrite(lambda);

    // Create HTTP API Gateway
    const apigw = new HttpApi(this, 'screenshotAPI', {
      createDefaultStage: true,
      defaultIntegration: new LambdaProxyIntegration({
        handler: lambda
      })
    });

    const faviconIntegration = new HttpProxyIntegration({
      url: 'https://marek.rocks/favicon.ico'
    });

    apigw.addRoutes({
      integration: faviconIntegration,
      path: '/favicon.ico',
      methods: [ HttpMethod.ANY ]
    })

    // Print API Gateway URL
    new CfnOutput(this, 'API URL', { value: apigw.url ?? 'deployment error' });

  }
}
