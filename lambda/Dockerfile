FROM ubuntu:latest

RUN apt-get update
RUN apt-get install --no-install-recommends software-properties-common -y
RUN add-apt-repository ppa:saiarcot895/chromium-beta -y
RUN apt-get install --no-install-recommends chromium-browser chromium-chromedriver curl unzip wget python3-pip -y
RUN apt-get autoremove && apt-get autoclean

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

RUN mkdir -p /function
COPY lambda.py /function

WORKDIR /function
ENTRYPOINT [ "/usr/bin/python3", "-m", "awslambdaric" ]
CMD [ "lambda.handler" ]
