FROM python:3.10

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

ENV TELEGRAM_API_TOKEN=NotSet

CMD ["python", "bot.py"]