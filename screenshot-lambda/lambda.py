import boto3, ipaddress, os, socket, time
from codeguru_profiler_agent import with_lambda_profiler
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from aws_lambda_powertools import Logger, Tracer

# AWS Lambda Powertools
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

# Check if IP address is allow listed for API Gateway
@tracer.capture_method(capture_response = False)
def is_allow_listed(ip):

    # Get allow list IP range
    allow_list_range = os.environ['ip_allowlist']

    if ipaddress.ip_address(ip) in ipaddress.ip_network(allow_list_range):

        print("ALLOW - IP " + ip + " in " + allow_list_range)
        return True

    else:

        print("BLOCK - IP " + ip + " not in " + allow_list_range)
        return False

# Upload screen shot to S3 
@tracer.capture_method(capture_response = False)
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

# Capture screenshot
@tracer.capture_method(capture_response = False)
def get_screenshot(url, tmpfile):

    # Add chromium driver
    options = Options()
    options.binary_location = '/usr/bin/chromium-browser'

    # Add chromium options
    options.add_argument('--start-maximized')
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--single-process')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (X11; NetBSD) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.116 Safari/537.36')

    # Get URL using chromium
    driver = webdriver.Chrome('/usr/bin/chromedriver', chrome_options = options)

    # Get body of website
    driver.get(url)

    # Get screen dimensions
    screenwidth = 1440
    screenheight = driver.execute_script("return document.documentElement.scrollHeight")

    if screenheight == 0:
        screenheight = 1024

    # Maximize screen
    print('dimensions ' + ' ' + str(screenwidth) + ' ' + str(screenheight))
    driver.set_window_size(screenwidth, screenheight)

    # Select body and press escape to close some pop ups
    body = driver.find_element_by_xpath('/html')
    body.send_keys(Keys.ESCAPE)

    # Save screenshot
    body.screenshot(tmpfile)

    # Close chromium
    driver.close()
    driver.quit()


# Lambda handler
@tracer.capture_lambda_handler(capture_response = False)
@logger.inject_lambda_context(log_event = True)
@with_lambda_profiler(profiling_group_name = os.environ['AWS_CODEGURU_PROFILER_GROUP_NAME'])
def handler(event, context):
    
    # Get start timestamp
    startts = time.time()

    # Get url from API input
    if len(event['rawPath']) > 1:

        rawurl = event['rawPath'][1:]
        domain = rawurl.split('/')[0]
        
        src_ip = event['requestContext']['http']['sourceIp']
        print(src_ip)

        # Check if IP address is allow listed
        if is_allow_listed(src_ip):

            # Check if the dns domain is valid
            try: 

                x = socket.gethostbyname(domain)
                print('ip ' + str(x) + ' for ' + rawurl)
                
            # Return error if domain does not return dns record
            except:

                print('invalid dns ' + rawurl + ', setting github.com')
                
                return {
                    "statusCode": 200,
                    "body": '<html><body><center>invalid URL ' + rawurl + ' submitted</center></body></html>',
                    "headers": headers
                } 
        
        # Return error if IP address is not allow listed
        else:
            
            print('unauthorized IP ' + src_ip + ', returning error')

            return {
                "statusCode": 200,
                "body": '<html><body><center>not allowed - IP ' + src_ip + '</center></body></html>',
                "headers": headers
            }

    # If no URL is submitted, return error
    else:

        return {
            "statusCode": 200,
            "body": '<html><body><center>no URL submitted</center></body></html>',
            "headers": headers
        } 


    # Get URL path
    url = 'https://' + rawurl
    print('getting ' + url)

    # Set tmp and file paths
    fname = 'screenshots/' + domain + '/' + str(int(startts)) + '-' + rawurl.replace('.', '_').replace('/','-') + '.png'
    tmpfile = '/tmp/screen.png'

    # Get screenshot
    try:
        get_screenshot(url, tmpfile)

    except Exception as e:
        print('error with get screenshot ' + str(e))

        return {
            "statusCode": 200,
            "body": '<html><body><center>error getting - ' + url + '<br /></center></body></html>',
            "headers": headers
        } 

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
    return {
        "statusCode": 200,
        "body": '<html><body><center>' + url + ' - took ' + str(round(timediff, 2)) + ' seconds <br /><img src = ' + presigned_url + '></center></body></html>',
        "headers": headers
    } 
    