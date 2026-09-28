import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
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
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

class AcademicAdvisor:

    def __init__(self):
        print("Initializing AI Academic Advisor with Ollama...")

        try:
            # ---------------------------------------------------------
            # Ollama embeddings
            # ---------------------------------------------------------
            self.embeddings = OpenAIEmbeddings(
                model=EMBEDDING_MODEL
            )

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
            self.llm = ChatOpenAI(
                model=CHAT_MODEL,
                temperature=0
            )

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

3. First determine whether the user's question is asking for
   GENERAL ACADEMIC INFORMATION or STUDENT-SPECIFIC ADVICE.

   GENERAL ACADEMIC INFORMATION includes questions such as:
   - "What are the prerequisites for DATA301?"
   - "What are the prerequisites for DATA301 for the 2022 batch?"
   - "How many credits is DATA301?"
   - "When is DATA301 offered?"
   - "What are the requirements for Machine Learning?"
   - "What is the university rule for late registration?"
   - "What does the Student Handbook say about registration?"
   - "What courses are offered in semester 5?"

   For GENERAL ACADEMIC INFORMATION questions:
   - Answer directly using the UNIVERSITY CONTEXT.
   - Use the course catalogue, handbook, SOPs, and other
     university documents available in the context.
   - Do NOT ask for a Student ID.
   - Do NOT require the STUDENT PROFILE.
   - Do NOT evaluate the student's eligibility.
   - Do NOT ask for personal academic information.
   - If a Student ID happens to be present, ignore it unless
     the question explicitly asks for a student-specific decision.
   - If the required university information is not present in
     the CONTEXT, clearly state that the available information
     is insufficient. Do not invent an answer.

   STUDENT-SPECIFIC QUESTIONS include questions such as:
   - "Can I take DATA301?"
   - "Am I eligible for DATA301?"
   - "Can STU001 take DATA301?"
   - "Can I register for Machine Learning?"
   - "What courses can I take next semester?"
   - "Have I completed the prerequisites for DATA301?"

   For STUDENT-SPECIFIC QUESTIONS:
   - Use the UNIVERSITY CONTEXT to determine the applicable
     academic rules and course requirements.
   - Use the STUDENT PROFILE to determine the student's
     completed courses, current semester, programme, or other
     relevant academic information.
   - Check prerequisites and other eligibility requirements
     before making a student-specific determination.
   - If the required student information is unavailable and
     the Student ID has not been provided, ask for the Student ID.
   - Do not make assumptions about completed courses, current
     semester, programme, batch, or eligibility.
   - If the Student ID is provided but the profile cannot be
     found, clearly state that the student profile could not
     be found and do not invent student information.

4. For STUDENT-SPECIFIC questions:

   - If a STUDENT PROFILE is already provided in the context,
     use that profile directly.
   - If the profile contains a Student ID, do NOT ask the user
     for their Student ID again.
   - Check the student's completed courses, current semester,
     programme, and other relevant information from the provided
     STUDENT PROFILE.
   - Only ask for the Student ID when no student profile is
     available and the question requires student-specific
     information.

   If no student profile is available, politely ask:

   "Could you please provide your Student ID so I can check
   your academic profile?"

5. For student-specific course eligibility questions, always use
   the student's batch or entry year from the STUDENT PROFILE.

   Match the course requirements to the student's applicable
   curriculum or batch.

   Do NOT use prerequisites or course requirements from a
   different batch when determining eligibility.

   If the CONTEXT contains different requirements for different
   batches, identify the student's batch first and use the
   requirements applicable to that batch.

   If the student's batch cannot be determined from the
   STUDENT PROFILE, clearly state that the batch information
   is unavailable and do not guess.

6. If the Student ID is provided but cannot be found in the
   student database, clearly state that the student profile
   could not be found.

7. If there are conflicting rules or missing information in the
   CONTEXT, explicitly state that the information is insufficient
   or conflicting.

8. Cite the source or evidence for your answer whenever possible.

   Examples:

   "According to the Student Handbook..."

   "Based on the Course Catalogue..."

   "According to the academic regulations..."

9. Do not claim that a student is eligible for a course unless
   the provided information supports that conclusion.

10. Be helpful, conversational, concise, and precise.

11. Never invent information that is not present in the
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
                "NO STUDENT PROFILE IS REQUIRED FOR GENERAL COURSE "
                "INFORMATION QUESTIONS.\n"
                "The user has not provided a Student ID.\n"
                "If the question asks about general course information "
                "such as prerequisites, credits, semester, course "
                "requirements, or course description, answer directly "
                "from the university CONTEXT.\n"
                "Do NOT ask for a Student ID for such questions.\n"
                "Only require a Student ID when the user asks for "
                "student-specific eligibility, registration, or "
                "planning based on their academic history."
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

        retrieval_input = user_input

        if current_student_id:
            retrieval_input = (
                f"{user_input}\n"
                f"Student ID: {current_student_id}\n"
                f"Student profile:\n{profile_text}"
            )

        response = self.chain.invoke(
            {
                "input": retrieval_input,
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
