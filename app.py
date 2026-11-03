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
from agents import AgenticAdvisor
import multimodal as MM
import security as SEC
from models import default_model_id, get_spec, model_options, resolve_model
from periods import parse_period
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
    os.getenv("MAX_REQUEST_BYTES", str(5 * 1024 * 1024))  # room for one image upload
)
advisor = AcademicAdvisor()
agentic = AgenticAdvisor(vectorstore=advisor.vectorstore)
initialize_database(DB_PATH)
USERS = SEC.load_users()
MODES = {"agentic", "rag"}


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
    if request.endpoint not in ("chat_api", "transcript_api"):
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


def model_looks_unavailable(error):
    """True when the provider says the model is gone or unknown (HTTP 404)."""
    text = str(error).lower()
    return (
        "no longer available" in text
        or "not_found" in text
        or ("404" in text and "model" in text)
    )


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


@app.route("/api/options")
def options_api():
    """What the page can offer: the models this deployment allows."""
    return jsonify({
        "models": model_options(),
        "default_model": default_model_id(),
        # Only batches/semesters that really have data in the index.
        "periods": advisor.catalog.to_json(),
    })


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

    requested_model = data.get("model")
    if requested_model is not None and not isinstance(requested_model, str):
        return jsonify({"error": "Model must be text."}), 400
    try:
        model_id = resolve_model(requested_model)
    except ValueError:
        return jsonify({"error": "That model is not available."}), 400

    try:
        batch, semester = parse_period(
            data.get("batch"), data.get("semester"), advisor.catalog
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if not message:
        return jsonify({"error": "Please enter a question."}), 400
    if not valid_uuid(conversation_id):
        return jsonify({"error": "Invalid conversation ID."}), 400

    mode = data.get("mode") or os.getenv("DEFAULT_MODE", "agentic")
    if mode not in MODES:
        return jsonify({"error": "Unknown advisor mode."}), 400

    # ---- Phase 10 safeguards -------------------------------------------
    user = session.get("auth")
    security_events = []
    requested = student_id or None
    if SEC.security_enabled():
        # IDs typed in the message are treated as a request too, so attempts
        # to read another student's record are caught and logged.
        mentioned = SEC.mentioned_student_ids(message)
        if mentioned and not requested:
            requested = mentioned[0]
    allowed_id, denial = SEC.authorize_profile(user, requested)
    if denial:
        security_events.append(denial)
        SEC.log_event("authorization_denied", user=(user or {}).get("username"), reason=denial)
    injection = SEC.detect_injection(message) if SEC.security_enabled() else []
    if injection:
        security_events.append("prompt_injection_blocked")
        SEC.log_event("prompt_injection", user=(user or {}).get("username"), count=len(injection))
        refusal = ("I can't follow instructions that try to change how I work or access other "
                   "students' data. I can help with your courses, credits and university regulations.")
        return jsonify({"answer": refusal, "student_id": allowed_id, "conversation_id": conversation_id,
                        "meta": {"mode": mode, "security_events": security_events, "status": "blocked"}})
    if denial == "other_student_record":
        note = ("For privacy I can only use your own record. I can't look up or share another "
                "student's information.")
        if not SEC.mentioned_student_ids(message) or len(message) < 40:
            return jsonify({"answer": note, "student_id": allowed_id, "conversation_id": conversation_id,
                            "meta": {"mode": mode, "security_events": security_events, "status": "blocked"}})
    if denial == "not_logged_in":
        security_events.append("login_required_for_record")

    try:
        owner_id = get_conversation_owner(conversation_id, DB_PATH)
        if owner_id is not None and owner_id != user_id:
            return jsonify({
                "error": "This conversation belongs to another user."
            }), 403

        history = get_recent_messages(conversation_id, user_id, db_path=DB_PATH)
        student = advisor.students_by_id.get(allowed_id or "")
        if mode == "agentic":
            res = agentic.answer(
                message, student=student,
                history_text=advisor._format_chat_history(history) if history else "",
                batch=batch,
            )
            result = {"answer": res["answer"], "student_id": allowed_id, "model": model_id,
                      "period": {"batch": batch, "semester": semester}, "usage": res["usage"], "cost": None}
            agent_meta = {"trace": res["trace"], "evidence": res["evidence"], "status": res["status"],
                          "human_review": res["human_review"], "elapsed_ms": res["elapsed_ms"]}
        else:
            result = advisor.answer_question(
                message,
                current_student_id=allowed_id,
                chat_history=history,
                model=model_id,
                batch=batch,
                semester=semester,
            )
            agent_meta = {}
        result["answer"], out_events = SEC.filter_output(result["answer"], allowed_id, student)
        security_events += out_events
        answer_meta = {
            "model": result["model"],
            "model_label": get_spec(result["model"]).label,
            "period": result["period"],
            "usage": result["usage"],
            "cost": result["cost"],
            "mode": mode,
            "security_events": security_events,
            **agent_meta,
        }
        save_exchange(
            user_id=user_id,
            conversation_id=conversation_id,
            question=message,
            answer=result["answer"],
            student_id=result["student_id"],
            db_path=DB_PATH,
            answer_meta=answer_meta,
        )
        return jsonify({
            "answer": result["answer"],
            "student_id": result["student_id"],
            "conversation_id": conversation_id,
            "meta": answer_meta,
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
    except Exception as error:
        app.logger.exception("Failed to process advisor chat request (model %s)", model_id)
        if model_looks_unavailable(error):
            return jsonify({
                "error": (
                    f"{get_spec(model_id).label} is no longer available from "
                    "Google, or this API key cannot use it. Please choose "
                    "another model from the list."
                )
            }), 503
        return jsonify({
            "error": (
                f"The advisor could not process your question with "
                f"{get_spec(model_id).label}. Try another model, or check the "
                "server logs for the provider error."
            )
        }), 503


@app.route("/api/login", methods=["POST"])
def login_api():
    data = request.get_json(silent=True) or {}
    user = SEC.authenticate(str(data.get("username", "")), str(data.get("pin", "")), USERS)
    if not user:
        SEC.log_event("login_failed")
        return jsonify({"error": "Wrong ID or PIN."}), 401
    session["auth"] = user
    return jsonify({"user": public_user(user)})


@app.route("/api/logout", methods=["POST"])
def logout_api():
    session.pop("auth", None)
    session.pop("uploaded_record", None)
    return jsonify({"ok": True})


@app.route("/api/me")
def me_api():
    user = session.get("auth")
    return jsonify({"user": public_user(user) if user else None,
                    "security": SEC.security_enabled()})


def public_user(user):
    out = {"username": user["username"], "role": user["role"], "student_id": user.get("student_id")}
    if user["role"] == "advisor":
        out["advisees"] = user.get("advisees", [])
    return out


def current_student(requested=None):
    allowed, _ = SEC.authorize_profile(session.get("auth"), requested)
    return advisor.students_by_id.get(allowed or "")


@app.route("/api/transcript", methods=["POST"])
def transcript_api():
    """Phase 8: image in. Extract -> check -> show for confirmation."""
    file = request.files.get("image")
    if file is None:
        return jsonify({"error": "Please attach an image."}), 400
    data = file.read(MM.MAX_IMAGE_BYTES + 1)
    try:
        result = MM.extract_document(data, file.mimetype, current_student(request.form.get("student_id")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        app.logger.exception("transcript extraction failed")
        return jsonify({"error": "Could not read the image with the vision model."}), 503
    for ev in result["security_events"]:
        SEC.log_event(ev["type"], user=(session.get("auth") or {}).get("username"))
    return jsonify(result)


@app.route("/api/chart/prerequisites")
def prerequisite_chart_api():
    code = (request.args.get("code") or "").upper().strip()
    student = current_student(request.args.get("student_id"))
    try:
        batch = int(request.args.get("batch") or (student or {}).get("batch") or 0)
    except ValueError:
        batch = 0
    if not code or batch not in advisor.catalog.batches:
        return jsonify({"error": "Choose a course code and a batch that has curriculum data."}), 400
    svg = MM.prerequisite_svg(code, batch, student)
    return app.response_class(svg, mimetype="image/svg+xml")


@app.route("/api/chart/progress")
def progress_chart_api():
    student = current_student(request.args.get("student_id"))
    if not student:
        return jsonify({"error": "Log in to see your degree progress."}), 401
    return app.response_class(MM.progress_svg(student), mimetype="image/svg+xml")


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
