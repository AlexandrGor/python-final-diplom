FROM python:3.7-alpine
ENV PYTHONUNBUFFERED 1
WORKDIR /app

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY ./requirements.txt .
RUN apk add python3-dev libpq-dev; pip install --upgrade pip; pip install --no-cache-dir -r requirements.txt
