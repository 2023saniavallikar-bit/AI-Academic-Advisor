from collections import deque
from datetime import timedelta
import logging
import os
from pathlib import Path
import secrets
from threading import Lock
import time
import uuid

from flask import Flask, jsonify, render_template, request, session

from langchain_google_genai.chat_models import GoogleRateLimitError

from advisor import AcademicAdvisor
from chat_history import (
    DB_PATH,
    delete_conversation,
    get_conversation,
    get_conversation_owner,
    get_messages,
    get_recent_messages,
    initialize_database,
    list_conversations,
    save_exchange,
)

app = Flask(__name__)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
app.config["MAX_CONTENT_LENGTH"] = int(
    os.getenv("MAX_REQUEST_BYTES", "32768")
)
advisor = AcademicAdvisor()
initialize_database(DB_PATH)


def load_session_secret():
    configured_secret = os.getenv("FLASK_SECRET_KEY")
    if configured_secret:
        return configured_secret

    secret_path = DB_PATH.parent / "flask_session_secret"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with secret_path.open("x", encoding="utf-8") as secret_file:
            secret_file.write(secrets.token_urlsafe(48))
        secret_path.chmod(0o600)
    except FileExistsError:
        pass
    return secret_path.read_text(encoding="utf-8").strip()


app.secret_key = load_session_secret()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

CHAT_RATE_LIMIT = int(os.getenv("CHAT_RATE_LIMIT", "10"))
CHAT_RATE_WINDOW_SECONDS = int(os.getenv("CHAT_RATE_WINDOW_SECONDS", "60"))
if CHAT_RATE_LIMIT < 1 or CHAT_RATE_WINDOW_SECONDS < 1:
    raise ValueError("Chat rate limit and window must be positive integers.")
request_times_by_ip = {}
request_times_lock = Lock()


@app.before_request
def assign_anonymous_session():
    session.permanent = True
    if not valid_uuid(session.get("user_id")):
        session["user_id"] = str(uuid.uuid4())


@app.before_request
def limit_chat_requests():
    if request.endpoint != "chat_api":
        return None

    client_ip = request.remote_addr or "unknown"
    now = time.monotonic()
    cutoff = now - CHAT_RATE_WINDOW_SECONDS
    with request_times_lock:
        timestamps = request_times_by_ip.setdefault(client_ip, deque())
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

        if len(timestamps) >= CHAT_RATE_LIMIT:
            retry_after = max(
                1,
                int(CHAT_RATE_WINDOW_SECONDS - (now - timestamps[0])),
            )
            response = jsonify({
                "error": "Too many questions. Please wait before trying again."
            })
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

        timestamps.append(now)
        stale_ips = [
            ip for ip, entries in request_times_by_ip.items()
            if not entries or entries[-1] <= cutoff
        ]
        for ip in stale_ips:
            request_times_by_ip.pop(ip, None)

    return None


def valid_uuid(value):
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/api/chat", methods=["POST"])
def chat_api():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400
    message = data.get("message")
    student_id = data.get("student_id") or ""
    user_id = session["user_id"]
    conversation_id = data.get("conversation_id") or str(uuid.uuid4())

    if not isinstance(message, str):
        return jsonify({"error": "Please enter a question."}), 400
    message = message.strip()
    if not isinstance(student_id, str):
        return jsonify({"error": "Student ID must be text."}), 400
    student_id = student_id.strip()

    if not message:
        return jsonify({"error": "Please enter a question."}), 400
    if not valid_uuid(conversation_id):
        return jsonify({"error": "Invalid conversation ID."}), 400

    try:
        owner_id = get_conversation_owner(conversation_id, DB_PATH)
        if owner_id is not None and owner_id != user_id:
            return jsonify({
                "error": "This conversation belongs to another user."
            }), 403

        history = get_recent_messages(conversation_id, user_id, db_path=DB_PATH)
        result = advisor.answer_question(
            message,
            current_student_id=student_id or None,
            chat_history=history,
        )
        save_exchange(
            user_id=user_id,
            conversation_id=conversation_id,
            question=message,
            answer=result["answer"],
            student_id=result["student_id"],
            db_path=DB_PATH,
        )
        return jsonify({
            "answer": result["answer"],
            "student_id": result["student_id"],
            "conversation_id": conversation_id,
        })
    except PermissionError:
        return jsonify({"error": "This conversation belongs to another user."}), 403
    except GoogleRateLimitError:
        app.logger.warning("Gemini request quota was exceeded")
        return jsonify({
            "error": (
                "The advisor has reached its AI request quota. "
                "Please try again later or check the Gemini API quota."
            )
        }), 429
    except Exception:
        app.logger.exception("Failed to process advisor chat request")
        return jsonify({
            "error": (
                "The advisor could not process your question. "
                "Check the server logs for the provider error."
            )
        }), 503


@app.route("/api/conversations")
def conversations_api():
    return jsonify({"conversations": list_conversations(session["user_id"], DB_PATH)})


@app.route("/api/conversations/<conversation_id>/messages")
def conversation_messages_api(conversation_id):
    user_id = session["user_id"]
    if not valid_uuid(conversation_id):
        return jsonify({"error": "Invalid conversation ID."}), 400

    conversation = get_conversation(conversation_id, user_id, DB_PATH)
    if conversation is None:
        return jsonify({"error": "Conversation not found."}), 404

    return jsonify({
        "conversation": conversation,
        "messages": get_messages(conversation_id, user_id, DB_PATH),
    })


@app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
def delete_conversation_api(conversation_id):
    user_id = session["user_id"]
    if not valid_uuid(conversation_id):
        return jsonify({"error": "Invalid conversation ID."}), 400

    if not delete_conversation(conversation_id, user_id, DB_PATH):
        return jsonify({"error": "Conversation not found."}), 404
    return jsonify({"deleted": True})


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
