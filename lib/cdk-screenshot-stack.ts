import * as cdk from '@aws-cdk/core';
import * as path from "path";
import { DockerImageFunction, DockerImageCode } from "@aws-cdk/aws-lambda";
import { Tracing } from '@aws-cdk/aws-lambda';
import { CfnOutput, Duration } from '@aws-cdk/core';
import { Bucket } from '@aws-cdk/aws-s3';
import { HttpApi } from '@aws-cdk/aws-apigatewayv2';
import { LambdaProxyIntegration } from '@aws-cdk/aws-apigatewayv2-integrations';

export class CdkScreenshotStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // create S3 bucket
    const s3bucket = new Bucket(this, 'screenshotbucket');

    // define Docker file for Lambda function
    const dockerfile = path.join(__dirname, "./../lambda");
    
    // define Lambda function using Docker image
    const lambda = new DockerImageFunction(this, "screenshot", {
      code: DockerImageCode.fromImageAsset(dockerfile),
      memorySize: 2048,
      timeout: Duration.seconds(15),
      tracing: Tracing.ACTIVE,
      reservedConcurrentExecutions: 3,
      environment: {
        "s3bucket": s3bucket.bucketName,
        "AWS_CODEGURU_PROFILER_GROUP_NAME": "screenshot"
      }
    });

    s3bucket.grantReadWrite(lambda);

    // Create HTTP API Gateway
    const apigw = new HttpApi(this, 'CdkTypescriptApi', {
      createDefaultStage: true,
      defaultIntegration: new LambdaProxyIntegration({
        handler: lambda
      })
    });

    // Print API Gateway URL
    new CfnOutput(this, 'API URL', { value: apigw.url ?? 'deployment error' });

  }
}
