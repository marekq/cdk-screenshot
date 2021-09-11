import boto3, os, pytesseract, subprocess, time
from codeguru_profiler_agent import with_lambda_profiler
from aws_lambda_powertools import Logger, Tracer

# AWS Lambda Powertools
logger = Logger()
tracer = Tracer()

# Get S3 bucket and setup s3 client
bucketname = os.environ['s3bucket']
s3_client = boto3.client('s3')

# Setup DynamoDB client
dynamodb = boto3.resource('dynamodb')
ddb_client = dynamodb.Table(os.environ['dynamodb_table'])

# Put record to DynamoDB
@tracer.capture_method(capture_response = False)
def dynamodb_put(rekognition_text, timest, domain, s3path, beforesize, aftersize, compress_time, ocr_time, url):
    
    ddb_client.put_item(
        Item = {
            'timestamp': int(timest),
            'domain': domain,
            'url': url,
            'text': rekognition_text,
            's3bucket': bucketname,
            's3path': s3path,
            'beforesize': beforesize,
            'aftersize': aftersize,
            'ocrtime': ocr_time,
            'compresstime': compress_time
        }
    )

# Compress png image using pngquant
@tracer.capture_method(capture_response = False)
def compress_png(tmpfile):

    before_size = os.stat(tmpfile).st_size

    startts = time.time()
    process = subprocess.Popen('pngquant ' + tmpfile + ' -o ' + tmpfile + ' -f --skip-if-larger -v --speed 1', stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell = True, cwd = '/tmp', text = True)

    stdout, stderr = process.communicate()
    #print(stdout)
    #print(stderr)

    endts = time.time()
    compress_time = int((endts - startts) * 1000)
    after_size = os.stat(tmpfile).st_size

    print('compressed png in ' + str(compress_time) + ' ms - ' + tmpfile + ' from ' + str(before_size) + ' to ' + str(after_size))

    return before_size, after_size, compress_time

# Compress png image using pngquant
@tracer.capture_method(capture_response = False)
def get_s3_file(bucketname, s3path, fname):
    
    print('downloading bucket: ' + bucketname + ' , s3path: ' + s3path + ' , tmppath: ' + fname)

    s3_client.download_file(bucketname, s3path, fname)

# Upload screen shot to s3 using ONEZONE_IA storage class
@tracer.capture_method(capture_response = False)
def put_s3_file(bucketname, s3path, fname):

    print('uploading bucket: ' + bucketname + ' , s3path: ' + s3path + ' , tmppath: ' + fname)

    s3_client.upload_file(
        Filename = fname, 
        Bucket = bucketname, 
        Key = s3path,
        ExtraArgs = {
            'StorageClass': 'ONEZONE_IA',
            'ACL': 'public-read',
            'ContentType': 'image/png'
        }
    )


# Convert image to text
@tracer.capture_method(capture_response = False)
def image_to_text(fname):

    startts = time.time()
    text = ''
    ocr_time = 0

    try:
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        text = pytesseract.image_to_string(fname, lang = 'eng', timeout = 20)
    
        endts = time.time()
        ocr_time = int((endts - startts) * 1000)
        print('done OCR in ' + str(ocr_time) + ' ms with ' + str(len(text)) + ' chars output')

    except Exception as e:

        text = ''

        endts = time.time()
        ocr_time = int((endts - startts) * 1000)
        print('failed OCR in ' + str(ocr_time) + ' ms - ' + str(e))
    
    return text, ocr_time

# Lambda handler
@tracer.capture_lambda_handler(capture_response = False)
@logger.inject_lambda_context(log_event = True)
@with_lambda_profiler(profiling_group_name = os.environ['AWS_CODEGURU_PROFILER_GROUP_NAME'])
def handler(event, context):
    
    # Get event fields and set path
    record = event['Records'][0]['body']
    s3bucket = record.split('amazonaws.com/')[1].split('/')[0]
    s3path = record.split('amazonaws.com/')[1].split('/', 1)[1]
    
    # Get domain and URL
    domain = record.split('amazonaws.com/')[1].split('/', 3)[2]
    url = 'https://' + domain + '/' + s3path.split('/', 1)[1]

    # Get timestamp
    timest = record.split('amazonaws.com/')[1].split('/')[-1:][0][:10]
    fname = '/tmp/screen.png'

    print(' s3bucket ' + s3bucket + '\n s3path ' + s3path + '\n domain ' + domain + '\n url ' + url + '\n timest ' + str(timest))

    # Get S3 file
    get_s3_file(s3bucket, s3path, fname)

    # Compress png using pngquant
    before_size, after_size, compress_time = compress_png(fname)

    # Upload S3 file
    put_s3_file(s3bucket, s3path, fname)

    # Get text from image
    text, ocr_time = image_to_text(fname)

    # Put record to DynamoDB
    dynamodb_put(text, timest, domain, s3path, before_size, after_size, compress_time, ocr_time, url)
