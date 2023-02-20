FROM python:3.9-alpine
ENV PYTHONUNBUFFERED 1
WORKDIR /app

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY ./requirements.txt .
RUN pip install --upgrade pip; pip install --use-pep517 --no-cache-dir -r requirements.txt
