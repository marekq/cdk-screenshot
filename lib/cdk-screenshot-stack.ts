import path = require('path');
import { AttributeType, BillingMode, Table } from '@aws-cdk/aws-dynamodb';
import { Bucket } from '@aws-cdk/aws-s3';
import { CfnOutput, Construct, Duration, Stack, StackProps } from '@aws-cdk/core';
import { ComputePlatform, ProfilingGroup } from '@aws-cdk/aws-codeguruprofiler';
import { DockerImageCode, DockerImageFunction, Tracing } from '@aws-cdk/aws-lambda';
import { Effect, ManagedPolicy, PolicyDocument, PolicyStatement, Role, ServicePrincipal } from '@aws-cdk/aws-iam';
import { HttpApi, HttpMethod } from '@aws-cdk/aws-apigatewayv2';
import { HttpProxyIntegration, LambdaProxyIntegration } from '@aws-cdk/aws-apigatewayv2-integrations';
import { Queue } from '@aws-cdk/aws-sqs';
import { SqsEventSource } from '@aws-cdk/aws-lambda-event-sources';

export class CdkScreenshotStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Create DynamoDB table for meta data
    const dynamodbTable = new Table(this, 'screenshotTable', {
      billingMode: BillingMode.PAY_PER_REQUEST,
      partitionKey: { 
        name: 'domain', 
        type: AttributeType.STRING 
      },
      sortKey: {
        name: 'timestamp',
        type: AttributeType.NUMBER
      },
    })

    // Create S3 bucket
    const s3bucket = new Bucket(this, 'screenshotBucket');

    // Create the codeguru profiling group
    const pgroup = new ProfilingGroup(this, 'screenshotProfiling', {
      computePlatform: ComputePlatform.AWS_LAMBDA
    });

    // Create SQS queue
    const sqsQueue = new Queue(this, 'screenshotQueue', {
      visibilityTimeout: Duration.seconds(30),
    });

    // Define Docker file for Lambda function
    const screenshotDocker = path.join(__dirname, './../screenshot-lambda');
    const analyzeDocker = path.join(__dirname, './../analyze-lambda');

    // Create the screenshot Lambda IAM role
    const screenshotRole = new Role(this, 'screenshotRole', {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      inlinePolicies: {
        translation: new PolicyDocument({
          statements: [ new PolicyStatement(
            {
              effect: Effect.ALLOW,
              actions: [
                'dynamodb:PutItem'
              ],
              resources: [
                dynamodbTable.tableArn
              ]
            }
          )]
        })
      },
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        ManagedPolicy.fromAwsManagedPolicyName('AWSXRayDaemonWriteAccess'),
        ManagedPolicy.fromAwsManagedPolicyName('AmazonCodeGuruProfilerAgentAccess'),
        ManagedPolicy.fromAwsManagedPolicyName('AmazonTextractFullAccess')
      ]
    });

    // Create the analyze Lambda IAM role
    const analyzeRole = new Role(this, 'analyzeRole', {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      inlinePolicies: {
        translation: new PolicyDocument({
          statements: [ new PolicyStatement(
            {
              effect: Effect.ALLOW,
              actions: [
                'dynamodb:PutItem'
              ],
              resources: [
                dynamodbTable.tableArn
              ]
            }
          )]
        })
      },
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        ManagedPolicy.fromAwsManagedPolicyName('AWSXRayDaemonWriteAccess'),
        ManagedPolicy.fromAwsManagedPolicyName('AmazonCodeGuruProfilerAgentAccess'),
        ManagedPolicy.fromAwsManagedPolicyName('AmazonTextractFullAccess')
      ]
    });

    // create Analyze Lambda function using Docker image
    const analyzeLambda = new DockerImageFunction(this, 'analyzeLambda', {
      code: DockerImageCode.fromImageAsset(analyzeDocker),
      memorySize: 1024,
      timeout: Duration.seconds(15),
      tracing: Tracing.ACTIVE,
      reservedConcurrentExecutions: 3,
      retryAttempts: 0,
      role: analyzeRole,
      deadLetterQueueEnabled: true,
      environment: {
        's3bucket': s3bucket.bucketName,
        'dynamodb_table': dynamodbTable.tableName,
        'AWS_CODEGURU_PROFILER_GROUP_NAME': pgroup.profilingGroupName
      }
    });

    // create Chrome Lambda function using Docker image
    const screenshotLambda = new DockerImageFunction(this, 'screenshotLambda', {
      code: DockerImageCode.fromImageAsset(screenshotDocker),
      memorySize: 2048,
      timeout: Duration.seconds(30),
      tracing: Tracing.ACTIVE,
      reservedConcurrentExecutions: 3,
      retryAttempts: 0,
      role: screenshotRole,
      deadLetterQueueEnabled: true,
      environment: {
        'sqsqueue': sqsQueue.queueUrl,
        's3bucket': s3bucket.bucketName,
        'AWS_CODEGURU_PROFILER_GROUP_NAME': pgroup.profilingGroupName
      }
    });

    // Add SQS event source for analyze Lambda function
    analyzeLambda.addEventSource(new SqsEventSource(sqsQueue, {
      batchSize: 1
    }));

    // Add SQS read and write permissions to Lambda functions
    sqsQueue.grantSendMessages(screenshotLambda);
    sqsQueue.grantConsumeMessages(analyzeLambda);

    // Grant S3 and DynamoDB read write access to Lambda function
    s3bucket.grantWrite(screenshotLambda);

    // Create HTTP API Gateway with route to screenshot Lambda function
    const apigw = new HttpApi(this, 'screenshotAPI', {
      createDefaultStage: true,
      defaultIntegration: new LambdaProxyIntegration({
        handler: screenshotLambda
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
