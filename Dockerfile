FROM python:3

RUN pip install -U pip
ADD wolt_checker/requirements.txt /app/
RUN pip install -r /app/requirements.txt

ADD wolt_checker /app/wolt_checker

WORKDIR /app/wolt_checker
CMD python telegram_bot.py
