import boto3
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def handler(event, context):
    options = Options()
    options.binary_location = '/usr/lib/chromium-browser/chromium-browser'

    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--single-process')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome('/usr/lib/chromium-browser/chromedriver', chrome_options = options)
    driver.get('https://marek.rocks/')
    driver.save_screenshot('/tmp/screen.png')

    driver.close()
    driver.quit()

    response = {
        "statusCode": 200,
        "body": "S3 signed URL to screenshot"
    }

    return response