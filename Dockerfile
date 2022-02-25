FROM python:3.9-alpine3.14

WORKDIR /app/wolt_checker

RUN pip install -U pip
RUN apk add linux-headers g++
ADD requirements.txt /app
RUN pip install -r /app/requirements.txt

ADD wolt_checker /app/wolt_checker

CMD python telegram_bot.py
