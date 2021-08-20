FROM amazonlinux:latest

RUN amazon-linux-extras install epel -y
RUN yum update -y
RUN yum install chromium chromedriver python3-pip -y

RUN curl -O https://lambda-insights-extension.s3-ap-northeast-1.amazonaws.com/amazon_linux/lambda-insights-extension.rpm && \
    rpm -U lambda-insights-extension.rpm && \
    rm -f lambda-insights-extension.rpm

RUN yum clean all && rm -rf /var/cache/yum

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

RUN mkdir -p /function
COPY lambda.py /function

WORKDIR /function
ENTRYPOINT [ "/usr/bin/python3", "-m", "awslambdaric" ]
CMD [ "lambda.handler" ]
