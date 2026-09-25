import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate

# LangChain 1.x compatibility
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = os.getenv("CHROMA_DB_DIR", str(BASE_DIR / "chroma_db"))
STUDENT_DB_PATH = Path(
    os.getenv("STUDENT_DB_PATH", str(BASE_DIR / "synthetic_students.json"))
)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama3.1")


class AcademicAdvisor:

    def __init__(self):
        print("Initializing AI Academic Advisor with Ollama...")

        try:
            # ---------------------------------------------------------
            # Ollama embeddings
            # ---------------------------------------------------------
            embedding_options = {"model": EMBEDDING_MODEL}
            if OLLAMA_BASE_URL:
                embedding_options["base_url"] = OLLAMA_BASE_URL
            self.embeddings = OllamaEmbeddings(**embedding_options)

            # ---------------------------------------------------------
            # Chroma vector database
            # ---------------------------------------------------------
            self.vectorstore = Chroma(
                persist_directory=DB_DIR,
                embedding_function=self.embeddings
            )

            self.retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": 5}
            )

            # ---------------------------------------------------------
            # Ollama chat model
            # ---------------------------------------------------------
            llm_options = {
                "model": CHAT_MODEL,
                "temperature": 0,
            }
            if OLLAMA_BASE_URL:
                llm_options["base_url"] = OLLAMA_BASE_URL
            self.llm = ChatOllama(**llm_options)

        except Exception as e:
            print(f"\nError initializing models: {e}")

            print(
                "\nMake sure:"
                "\n1. Ollama is installed and running."
                "\n2. llama3.1 is installed."
                "\n3. nomic-embed-text is installed."
                "\n4. The Chroma database exists."
            )

            raise

        # Load student database
        self.students = []
        self.students_by_id = {}
        self._student_db_mtime_ns = None
        self.students = self._load_students()

        # Build RAG chain
        self.chain = self._build_chain()

    # -----------------------------------------------------------------
    # Load students
    # -----------------------------------------------------------------
    def _load_students(self):

        try:

            with open(STUDENT_DB_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)

            if isinstance(payload, list):
                students = payload
            elif isinstance(payload, dict) and isinstance(
                payload.get("students"), list
            ):
                students = payload["students"]
            else:
                raise ValueError(
                    "synthetic_students.json must contain a list of "
                    "student records or an object with a 'students' list."
                )

            valid_students = []
            students_by_id = {}

            for index, student in enumerate(students):
                if not isinstance(student, dict):
                    print(
                        f"Skipping student record {index + 1}: "
                        "record is not an object."
                    )
                    continue

                raw_student_id = student.get("student_id")
                normalized_id = self.normalize_student_id(raw_student_id)

                if not normalized_id:
                    print(
                        f"Skipping student record {index + 1}: "
                        f"invalid student_id {raw_student_id!r}."
                    )
                    continue

                if normalized_id in students_by_id:
                    raise ValueError(
                        f"Duplicate student_id found: {normalized_id}"
                    )

                valid_students.append(student)
                students_by_id[normalized_id] = student

            self.students_by_id = students_by_id
            self._student_db_mtime_ns = STUDENT_DB_PATH.stat().st_mtime_ns

            print(
                f"Loaded {len(valid_students)} of {len(students)} student "
                "profiles successfully."
            )

            return valid_students

        except FileNotFoundError:

            print(
                "\nCould not find synthetic_students.json."
                "\nMake sure it is in the same directory as advisor.py."
            )

            self.students_by_id = {}
            self._student_db_mtime_ns = None
            return []

        except json.JSONDecodeError as e:

            print(
                f"\nInvalid JSON in synthetic_students.json: {e}"
            )

            self.students_by_id = {}
            self._student_db_mtime_ns = None
            return []

        except Exception as e:

            print(
                f"\nCould not load synthetic students: {e}"
            )

            self.students_by_id = {}
            self._student_db_mtime_ns = None
            return []

    def _refresh_student_index_if_changed(self):
        """Reload all student records when the JSON file changes."""

        try:
            current_mtime_ns = STUDENT_DB_PATH.stat().st_mtime_ns
        except FileNotFoundError:
            current_mtime_ns = None

        if current_mtime_ns != self._student_db_mtime_ns:
            self.students = self._load_students()

    # -----------------------------------------------------------------
    # Build RAG chain
    # -----------------------------------------------------------------
    def _build_chain(self):

        system_prompt = """
You are an AI Academic Advisor for a University.

Your objective is to provide accurate academic advice based ONLY on:

1. The university's rules.
2. The course catalogue.
3. University SOPs.
4. The provided student profile.

============================================================
CONTEXT PROVIDED FROM KNOWLEDGE BASE
============================================================

{context}

============================================================
STUDENT PROFILE
============================================================

{student_profile}

============================================================
INSTRUCTIONS
============================================================

1. Answer the student's question using ONLY the provided
   CONTEXT and STUDENT PROFILE.

2. Do not hallucinate or invent university rules, courses,
   prerequisites, credits, policies, or academic requirements.

3. If the user asks about taking a course, check whether the
   student meets the prerequisites using the CONTEXT and
   STUDENT PROFILE.

4. If the student has NOT provided a Student ID and the question
   requires knowing their completed courses or current semester,
   do NOT make assumptions.

   Politely ask:

   "Could you please provide your Student ID so I can check
   your completed courses?"

5. If the Student ID is provided but cannot be found in the
   student database, clearly state that the student profile
   could not be found.

6. If there are conflicting rules or missing information in the
   CONTEXT, explicitly state that the information is insufficient
   or conflicting.

7. Cite the source or evidence for your answer whenever possible.

   Examples:

   "According to the Student Handbook..."

   "Based on the Course Catalogue..."

   "According to the academic regulations..."

8. Do not claim that a student is eligible for a course unless
   the provided information supports that conclusion.

9. Be helpful, conversational, concise, and precise.

10. Never invent information that is not present in the
    CONTEXT or STUDENT PROFILE.
"""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}")
            ]
        )

        # Create document question-answering chain
        question_answer_chain = create_stuff_documents_chain(
            self.llm,
            prompt
        )

        # Create retrieval chain
        retrieval_chain = create_retrieval_chain(
            self.retriever,
            question_answer_chain
        )

        return retrieval_chain

    # -----------------------------------------------------------------
    # Normalize Student ID
    # -----------------------------------------------------------------
    def normalize_student_id(self, student_id):

        if not student_id:
            return None

        # Convert to uppercase
        student_id = student_id.upper().strip()

        # Remove spaces and underscores
        cleaned = re.sub(r"[\s_]+", "", student_id)

        # Check for STU followed by numbers
        match = re.fullmatch(r"STU(\d+)", cleaned)

        if match:

            number = match.group(1)

            # Convert:
            # STU002 -> STU_002
            return f"STU_{number}"

        return None

    # -----------------------------------------------------------------
    # Detect Student ID from user input
    # -----------------------------------------------------------------
    def extract_student_id(self, user_input):

        if not user_input:
            return None

        text = user_input.upper()

        # -------------------------------------------------------------
        # Detect:
        #
        # STU_002
        # STU002
        # STU 002
        #
        # The underscore is optional.
        # -------------------------------------------------------------
        patterns = [
            r"\bSTU[_\s]?(\d+)\b",
            r"\bSTUDENT[_\s]?(\d+)\b"
        ]

        for pattern in patterns:

            match = re.search(pattern, text)

            if match:

                number = match.group(1)

                return f"STU_{number}"

        return None

    # -----------------------------------------------------------------
    # Get student profile
    # -----------------------------------------------------------------
    def get_student_profile_text(self, student_id):

        self._refresh_student_index_if_changed()

        if not student_id:

            return (
                "No student profile loaded. "
                "The user is anonymous. "
                "Do not assume any completed courses."
            )

        # Normalize ID before searching
        normalized_id = self.normalize_student_id(student_id)

        if not normalized_id:

            return (
                f"Student ID '{student_id}' is invalid. "
                "Treat the student as anonymous."
            )

        student = getattr(self, "students_by_id", {}).get(normalized_id)

        if student:
            return json.dumps(student, indent=2)

        return (
            f"Student ID '{normalized_id}' was not found "
            "in the student database. Treat the student "
            "as anonymous."
        )

    # -----------------------------------------------------------------
    # Ask a single question and return answer
    # -----------------------------------------------------------------
    def answer_question(self, user_input, current_student_id=None):

        if not user_input or not str(user_input).strip():
            raise ValueError("A question is required.")

        user_input = str(user_input).strip()

        detected_student_id = self.extract_student_id(user_input)

        if detected_student_id:
            current_student_id = detected_student_id

        profile_text = self.get_student_profile_text(current_student_id)

        response = self.chain.invoke(
            {
                "input": user_input,
                "student_profile": profile_text
            }
        )

        answer = response.get(
            "answer",
            "I could not generate an answer."
        )

        return {
            "answer": answer,
            "student_id": current_student_id,
            "detected_student_id": detected_student_id,
        }

    # -----------------------------------------------------------------
    # Chat interface
    # -----------------------------------------------------------------
    def chat(self):

        print("\n=======================================================")
        print("🎓 AI Academic Advisor is ready!")
        print("Type 'exit' or 'quit' to stop.")
        print("-------------------------------------------------------")
        print("You can enter your Student ID in any of these formats:")
        print("  STU_002")
        print("  STU002")
        print("  STU 002")
        print("  STUDENT 002")
        print("-------------------------------------------------------")
        print("Example:")
        print("  I am student STU002. Can I take COMP203?")
        print("=======================================================\n")

        current_student_id = None

        while True:

            try:

                user_input = input("Student: ").strip()

            except (KeyboardInterrupt, EOFError):

                print("\n\nExiting Academic Advisor.")
                break

            # Ignore empty input
            if not user_input:
                continue

            # ---------------------------------------------------------
            # Exit commands
            # ---------------------------------------------------------
            if user_input.lower() in ["exit", "quit"]:

                print("\nGoodbye! 👋")
                break

            try:
                result = self.answer_question(
                    user_input,
                    current_student_id=current_student_id
                )

                current_student_id = result.get("student_id")

                if result.get("detected_student_id"):
                    print(
                        f"\n[System: Loaded context for "
                        f"{current_student_id}]"
                    )

                print(
                    f"\nAI Advisor: {result['answer']}\n"
                )

            except Exception as e:

                print(
                    "\nError while processing your question:"
                )

                print(e)

                print(
                    "\nPlease check that Ollama is running "
                    "and that the required models are installed.\n"
                )


# ---------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------
if __name__ == "__main__":

    advisor = AcademicAdvisor()
    advisor.chat()
