FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY bot ./bot

RUN useradd -m bot && mkdir /data && chown bot /data
USER bot

ENV DB_PATH=/data/orders.db
CMD ["python", "main.py"]
