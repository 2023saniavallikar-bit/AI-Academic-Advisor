FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY advisor.py app.py synthetic_students.json ./
RUN mkdir -p /app/data && cp synthetic_students.json /app/data/synthetic_students.json
COPY chroma_db ./chroma_db
COPY cleaned ./cleaned
COPY templates ./templates
COPY static ./static

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "app:app"]
