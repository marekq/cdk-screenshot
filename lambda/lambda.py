import base64, boto3, os, socket, time
from codeguru_profiler_agent import with_lambda_profiler
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from aws_lambda_powertools import Logger, Tracer

# aws powertools
modules_to_be_patched = [ "boto3" ]
tracer = Tracer(patch_modules = modules_to_be_patched)

logger = Logger()
tracer = Tracer()

# get s3 bucket and setup client
bucketname = os.environ['s3bucket']
s3_client = boto3.client('s3')

# convert image to base64
def get_base64_encoded_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

# lambda handler
@logger.inject_lambda_context(log_event = True)
@tracer.capture_lambda_handler
@with_lambda_profiler(profiling_group_name = os.environ['AWS_CODEGURU_PROFILER_GROUP_NAME'])
def handler(event, context):
    
    # set empty html response
    response = ''

    # get url from API input
    if len(event['rawPath']) > 1:
        rawurl = event['rawPath'][1:]
        domain = rawurl.split('/')[0]

        # check if the dns domain is valid
        try: 

            x = socket.gethostbyname(domain)
            print('ip ' + str(x) + ' for ' + rawurl)
            response = ''

        # return error if domain does not return dns record
        except:

            print('invalid dns ' + rawurl + ', setting github.com')
            
            response = {
                "statusCode": 200,
                "body": '<html><body>invalid URL ' + rawurl + ' submitted</body></html>',
                "headers": {
                    'Content-Type': 'text/html'
                }
            } 

    # if no URL is submitted, return error
    else:

        response = {
            "statusCode": 200,
            "body": '<html><body>no URL submitted</body></html>',
            "headers": {
                'Content-Type': 'text/html'
            }
        } 

    # if response is empty, run chromium browser to take screenshot
    if response == '':

        # get url to resolve
        url = 'https://' + rawurl
        print('getting ' + url)

        # set tmp and file paths
        fname = rawurl.replace('.', '_').replace('/','-') + '-screen.png'
        tmpfile = '/tmp/screen.png'

        # add chromium driver
        options = Options()
        options.binary_location = '/usr/lib/chromium-browser/chromium-browser'
    
        # add chromium options
        options.add_argument('window-size=1440,900')
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--single-process')
        options.add_argument('--disable-dev-shm-usage')

        # get start timestamp
        startts = time.time()

        # get url using chromium
        driver = webdriver.Chrome('/usr/lib/chromium-browser/chromedriver', chrome_options = options)

        # get body of website
        driver.get(url)

        # press escape to close some pop ups
        body = driver.find_element_by_tag_name('body')
        body.send_keys(Keys.ESCAPE)

        # save screenshot
        body.screenshot(tmpfile)

        # close chromium
        driver.close()
        driver.quit()

        # get end timestamp
        endts = time.time()
        timediff = endts - startts

        # upload screen shot to s3
        s3_client.upload_file(tmpfile, bucketname, fname)
        b64img = get_base64_encoded_image(tmpfile)
        
        # return HTML response
        response = {
            "statusCode": 200,
            "body": '<html><body><center>' + url + ' - took ' + str(round(timediff, 2)) + ' seconds <br /><img height = "100%" src = "data:image/png;base64,' + b64img + '" /></center></body></html>',
            "headers": {
                'Content-Type': 'text/html'
            }
        } 
        
    # return html response    
    return response
