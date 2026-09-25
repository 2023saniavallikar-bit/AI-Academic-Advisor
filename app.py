import os

from flask import Flask, jsonify, render_template, request

from advisor import AcademicAdvisor

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(
    os.getenv("MAX_REQUEST_BYTES", "32768")
)
advisor = AcademicAdvisor()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/api/chat", methods=["POST"])
def chat_api():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    student_id = (data.get("student_id") or "").strip()

    if not message:
        return jsonify({"error": "Please enter a question."}), 400

    try:
        result = advisor.answer_question(
            message,
            current_student_id=student_id or None,
        )
        return jsonify({
            "answer": result["answer"],
            "student_id": result["student_id"],
        })
    except Exception:
        return jsonify({
            "error": "The advisor could not process your question."
        }), 503


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
