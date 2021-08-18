FROM ubuntu:latest

RUN apt-get update 
RUN apt-get install python3-pip pngquant -y
RUN apt-get autoremove && apt-get autoclean

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

RUN mkdir -p /function
COPY lambda.py /function

WORKDIR /function
ENTRYPOINT [ "/usr/bin/python3", "-m", "awslambdaric" ]
CMD [ "lambda.handler" ]
