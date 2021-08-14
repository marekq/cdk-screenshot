import boto3, os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

bucketname = os.environ['s3bucket']
s3_client = boto3.client('s3')

def handler(event, context):

    print(event)

    options = Options()
    options.binary_location = '/usr/lib/chromium-browser/chromium-browser'

    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--single-process')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=2560,1600')

    driver = webdriver.Chrome('/usr/lib/chromium-browser/chromedriver', chrome_options = options)
    driver.get(event['url'])
    driver.save_screenshot('/tmp/screen.png')

    driver.close()
    driver.quit()

    s3_client.upload_file('/tmp/screen.png', bucketname, 'screenshot.png')

    s3url = s3_client.generate_presigned_url(
        'get_object',
        Params = {
            'Bucket': bucketname,
            'Key': 'screenshot.png'
        },
        ExpiresIn = 3600
    )

    response = {
        "statusCode": 200,
        "body": "S3 signed URL to screenshot " + s3url
    }

    return response
