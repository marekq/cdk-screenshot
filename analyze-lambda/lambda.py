import base64, boto3, os, socket, subprocess, time
from codeguru_profiler_agent import with_lambda_profiler
from aws_lambda_powertools import Logger, Tracer

# AWS Lambda Powertools
modules_to_be_patched = [ "boto3" ]
tracer = Tracer(patch_modules = modules_to_be_patched)

# Setup logger and tracer
logger = Logger()
tracer = Tracer()

# Get S3 bucket and setup s3 client
bucketname = os.environ['s3bucket']
s3_client = boto3.client('s3')

# Setup Textract client
textract_client = boto3.client('textract')

# Setup DynamoDB client
dynamodb = boto3.resource('dynamodb')
ddb_client = dynamodb.Table(os.environ['dynamodb_table'])

# Textract image to text
@tracer.capture_method(capture_response = False)
def textract_image(fname):

    response = textract_client.detect_document_text(
        Document = {
            'S3Object': {
                'Bucket': bucketname,
                'Name': fname
            }
        }
    )

    return response

# Put record to DynamoDB
@tracer.capture_method(capture_response = False)
def dynamodb_put(textract, timest, domain, s3path):
    
    ddb_client.put_item(
        Item = {
            'timest': timest,
            'domain': domain,
            'text': textract,
            's3path': s3path
        }
    )

# Compress png image using pngquant
@tracer.capture_method(capture_response = False)
def compress_png(tmpfile):

    process = subprocess.Popen('pngquant ' + tmpfile + ' -o ' + tmpfile + ' -f --skip-if-larger -v --speed 1', stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell = True, cwd = '/tmp', text = True)

    stdout, stderr = process.communicate()
    print(stdout)
    print(stderr)

    #exit_code = process.wait()

# Compress png image using pngquant
@tracer.capture_method(capture_response = False)
def get_s3_file(bucketname, s3path, tmppath):
    
    s3_client.download_file(bucketname, s3path, tmppath)

# Lambda handler
@tracer.capture_lambda_handler(capture_response = False)
@logger.inject_lambda_context(log_event = False)
#@with_lambda_profiler(profiling_group_name = os.environ['AWS_CODEGURU_PROFILER_GROUP_NAME'])
def handler(event, context):
    
    # Set empty html response
    print(event)

    # Get event fields and set path
    record = event['Records'][0]['body']
    s3bucket = record.split('amazonaws.com/')[1].split('/')[0]
    s3path = record.split('amazonaws.com/')[1].split('/', 1)[1]
    domain = record.split('amazonaws.com/')[1].split('/', 3)[2]
    timest = record.split('amazonaws.com/')[1].split('/', 3)[3].split('-', 1)[0]
    fname = '/tmp/screen.png'

    get_s3_file(s3bucket, s3path, fname)

    # Compress png using pngquant
    compress_png(fname)

    # Upload screen shot to s3 using ONEZONE_IA storage class
    s3_client.upload_file(
        Filename = fname, 
        Bucket = bucketname, 
        Key = fname,
        ExtraArgs = {
            'StorageClass': 'ONEZONE_IA'
        }
    )

    textract = textract_image(fname)
    print(textract)

    # Put record to DynamoDB
    dynamodb_put(textract, timest, domain, fname)
