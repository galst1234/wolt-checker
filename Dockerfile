FROM python:3

WORKDIR /app/wolt_checker

RUN pip install -U pip
ADD requirements.txt /app
RUN pip install -r /app/requirements.txt

ADD wolt_checker /app/wolt_checker

CMD python telegram_bot.py
