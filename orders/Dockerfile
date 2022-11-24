FROM python:3.7-alpine
WORKDIR /app
COPY ./requirements.txt .
RUN apk add libpq-dev python3-dev; pip install --upgrade pip; pip install --no-cache-dir -r requirements.txt
