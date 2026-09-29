from contextlib import contextmanager
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(
    os.getenv("CHAT_HISTORY_DB_PATH", str(BASE_DIR / "data" / "chat_history.sqlite3"))
)
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH


def connect(db_path=DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database(db_path=DB_PATH):
    connection = connect(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path=DB_PATH):
    with database(db_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                student_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL
                    REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
                ON conversations(user_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, id);
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(conversations)")
        }
        if "student_id" not in columns:
            connection.execute("ALTER TABLE conversations ADD COLUMN student_id TEXT")


def list_conversations(user_id, db_path=DB_PATH):
    with database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, title, student_id, created_at, updated_at
            FROM conversations
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 50
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_conversation(conversation_id, user_id, db_path=DB_PATH):
    with database(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, title, student_id, created_at, updated_at
            FROM conversations
            WHERE id = ? AND user_id = ?
            """,
            (conversation_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def get_conversation_owner(conversation_id, db_path=DB_PATH):
    with database(db_path) as connection:
        row = connection.execute(
            "SELECT user_id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
    return row["user_id"] if row else None


def get_messages(conversation_id, user_id, db_path=DB_PATH):
    with database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT messages.role, messages.content, messages.created_at
            FROM messages
            JOIN conversations ON conversations.id = messages.conversation_id
            WHERE conversations.id = ? AND conversations.user_id = ?
            ORDER BY messages.id
            """,
            (conversation_id, user_id),
        ).fetchall()
    return [dict(row) for row in rows]


def get_recent_messages(conversation_id, user_id, limit=8, db_path=DB_PATH):
    with database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT messages.role, messages.content
            FROM messages
            JOIN conversations ON conversations.id = messages.conversation_id
            WHERE conversations.id = ? AND conversations.user_id = ?
            ORDER BY messages.id DESC
            LIMIT ?
            """,
            (conversation_id, user_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def save_exchange(
    user_id,
    conversation_id,
    question,
    answer,
    student_id=None,
    db_path=DB_PATH,
):
    title = " ".join(question.split())[:80]
    with database(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT user_id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if existing and existing["user_id"] != user_id:
            raise PermissionError("Conversation does not belong to this user.")

        connection.execute(
            """
            INSERT INTO conversations (id, user_id, title, student_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                student_id = excluded.student_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (conversation_id, user_id, title, student_id),
        )
        connection.executemany(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (?, ?, ?)
            """,
            (
                (conversation_id, "user", question),
                (conversation_id, "assistant", answer),
            ),
        )


def delete_conversation(conversation_id, user_id, db_path=DB_PATH):
    with database(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
    return cursor.rowcount > 0
