FROM python:3.12-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

RUN mkdir -p /app/data

VOLUME ["/app/data"]

EXPOSE 8080

CMD ["python", "main.py"]
