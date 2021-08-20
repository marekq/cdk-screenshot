import boto3, os, socket, time
from codeguru_profiler_agent import with_lambda_profiler
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
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

# Get SQS queue and setup sqs client
sqs_queue_url = os.environ['sqsqueue']
sqs_client = boto3.client('sqs')

# Set static return headers
headers = {
    'Content-Type': 'text/html',
    "strict-transport-security": "max-age=31536000; includeSubDomains; preload"
}

# Upload screen shot to s3 using ONEZONE_IA storage class
def upload_screenshot(tmpfile, bucketname, fname):
    s3_client.upload_file(
        Filename = tmpfile, 
        Bucket = bucketname, 
        Key = fname,
        ExtraArgs = {
            'StorageClass': 'STANDARD',
            'ACL': 'public-read',
            'ContentType': 'image/png'
        }
    )

# Send S3 path URI to SQS queue
@tracer.capture_method(capture_response = False)
def sqs_send(sqs_queue_url, bucketname, fname):
    sqs_client.send_message(
        QueueUrl = sqs_queue_url,
        MessageBody = 'https://s3.amazonaws.com/' + bucketname + '/' + fname,
    )

# Generate S3 Signed URL
@tracer.capture_method(capture_response = False)
def generate_signed_url(bucketname, fname):
    presigned_url = s3_client.generate_presigned_url(
        ClientMethod = 'get_object',
        Params = {
            'Bucket': bucketname,
            'Key': fname
        },
        ExpiresIn = 3600
    )

    return presigned_url

# Lambda handler
@tracer.capture_lambda_handler(capture_response = False)
@logger.inject_lambda_context(log_event = False)
@with_lambda_profiler(profiling_group_name = os.environ['AWS_CODEGURU_PROFILER_GROUP_NAME'])
def handler(event, context):
    
    # Set empty html response
    response = ''

    # Get url from API input
    if len(event['rawPath']) > 1:
        rawurl = event['rawPath'][1:]
        domain = rawurl.split('/')[0]

        # Check if the dns domain is valid
        try: 

            x = socket.gethostbyname(domain)
            print('ip ' + str(x) + ' for ' + rawurl)
            response = ''

        # Return error if domain does not return dns record
        except:

            print('invalid dns ' + rawurl + ', setting github.com')
            
            response = {
                "statusCode": 200,
                "body": '<html><body><center>invalid URL ' + rawurl + ' submitted</center></body></html>',
                "headers": headers
            } 

    # If no URL is submitted, return error
    else:

        response = {
            "statusCode": 200,
            "body": '<html><body><center>no URL submitted</center></body></html>',
            "headers": headers
        } 

    # If response is empty, run chromium browser to take screenshot
    if response == '':

        # Get start timestamp
        startts = time.time()

        # Get url to resolve
        url = 'https://' + rawurl
        print('getting ' + url)

        # Set tmp and file paths
        fname = 'screenshots/' + domain + '/' + str(int(startts)) + '-' + rawurl.replace('.', '_').replace('/','-') + '.png'
        tmpfile = '/tmp/screen.png'

        # Add chromium driver
        options = Options()
        options.binary_location = '/usr/lib/chromium-browser/chromium-browser'
    
        # Add chromium options
        options.add_argument('--start-maximized')
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--single-process')
        options.add_argument('--disable-dev-shm-usage')

        # Get url using chromium
        driver = webdriver.Chrome('/usr/lib/chromium-browser/chromedriver', chrome_options = options)

        # Get body of website
        driver.get(url)

        # Get screen dimensions
        #screenwidth = driver.execute_script("return document.documentElement.scrollWidth")
        screenwidth = 1440
        screenheight = driver.execute_script("return document.documentElement.scrollHeight")

        if screenheight == 0:
            screenheight = 1024

        # Maximize screen
        print('dimensions ' + ' ' + str(screenwidth) + ' ' + str(screenheight))
        driver.set_window_size(screenwidth, screenheight)

        # Select body and press escape to close some pop ups
        body = driver.find_element_by_tag_name('body')
        body.send_keys(Keys.ESCAPE)

        # Save screenshot
        body.screenshot(tmpfile)

        # Close chromium
        driver.close()
        driver.quit()

        # Upload screenshot to S3
        upload_screenshot(tmpfile, bucketname, fname)

        # Send SQS message with screenshot url
        sqs_send(sqs_queue_url, bucketname, fname)

        # Generate S3 pre-signed URL
        presigned_url = generate_signed_url(bucketname, fname)

        # Get end timestamp
        endts = time.time()
        timediff = endts - startts

        # Return HTML response
        response = {
            "statusCode": 200,
            "body": '<html><body><center>' + url + ' - took ' + str(round(timediff, 2)) + ' seconds <br /><img src = ' + presigned_url + '></center></body></html>',
            "headers": headers
        } 
        
    # Return HTML response    
    return response
