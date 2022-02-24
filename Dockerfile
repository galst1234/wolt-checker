FROM python:3

WORKDIR /app/wolt_checker

RUN pip install -U pip
ADD wolt_checker/requirements.txt /app/wolt_checker
RUN pip install -r /app/wolt_checker/requirements.txt

ADD wolt_checker /app/wolt_checker

CMD python telegram_bot.py
