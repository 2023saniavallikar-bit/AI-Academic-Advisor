FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY advisor.py app.py chat_history.py models.py periods.py synthetic_students.json \
     academic_tools.py agents.py llm.py security.py multimodal.py ./
COPY data/regulations.json data/demo_users.json ./data/
COPY chroma_db_gemini ./chroma_db_gemini
COPY cleaned ./cleaned
COPY templates ./templates
COPY static ./static

ENV STUDENT_DB_PATH=/app/synthetic_students.json \
    CHROMA_DB_DIR=/app/chroma_db_gemini \
    CHAT_HISTORY_DB_PATH=/app/data/chat_history.sqlite3

VOLUME ["/app/data"]

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "app:app"]
