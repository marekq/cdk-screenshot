import * as cdk from '@aws-cdk/core';
import * as path from "path";
import { DockerImageFunction, DockerImageCode, Function } from "@aws-cdk/aws-lambda";
import { Runtime, Tracing } from '@aws-cdk/aws-lambda';
import { CfnOutput, Construct, Duration, RemovalPolicy, Stack, StackProps } from '@aws-cdk/core';
import { Bucket } from '@aws-cdk/aws-s3';

export class CdkScreenshotStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const s3bucket = new Bucket(this, 'screenshotbucket');

    const dockerfile = path.join(__dirname, "./../lambda");

    const lambda = new DockerImageFunction(this, "screenshot", {
      code: DockerImageCode.fromImageAsset(dockerfile),
      memorySize: 2048,
      timeout: Duration.seconds(60)
    });

  }
}
