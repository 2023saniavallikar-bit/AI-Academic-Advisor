"""Builds eval/test_cases.json: the predefined test set with verified expected outcomes.

Each case records WHERE the expected answer comes from (handbook clause, SOP
section, curriculum row, or the deterministic tool output for a synthetic
student). tests/test_ground_truth.py re-checks every student-specific expected
decision against academic_tools so the test set cannot drift from the data.

Fields
  id, category, question, student_id (logged-in user or null), batch (UI selector)
  expect.behavior      answer | ask_follow_up | say_insufficient | flag_conflict | refuse | needs_login
  expect.decision      eligibility decision label (student eligibility cases)
  expect.must_include  list of groups; each group = alternatives, at least one must appear
  expect.must_not      strings (or "re:<regex>") that indicate a wrong/hallucinated answer
  expect.sources       list of groups of acceptable source mentions
  ground_truth         human-readable verified answer and its source
"""

import json
from pathlib import Path

_STUDENTS = {s["student_id"]: s for s in json.loads(
    (Path(__file__).resolve().parents[1] / "synthetic_students.json").read_text(encoding="utf-8"))}


def cg(sid):
    """CGPA of a synthetic student, as computed by academic_tools (stored in derived)."""
    return f"{_STUDENTS[sid]['derived']['cgpa']:.2f}"

INSUFF = ["not available", "does not contain", "do not contain", "doesn't contain", "not specified", "not stated",
          "not mentioned", "no information", "not provided", "don't have", "do not have", "insufficient",
          "not include", "does not specify", "doesn't specify", "not in the provided", "cannot find", "unable to find",
          "not found", "isn't specified", "is not specified", "not covered"]
CONFLICT = ["conflict", "inconsisten", "discrepan", "not part of", "not in the", "not listed", "does not appear",
            "confirm with", "differ", "however", "ambigu", "unclear", "same semester", "contradict"]
HANDBOOK = ["handbook", "regulation", "clause", "academic regulations"]
CURRIC = ["courses.csv", "course catalogue", "curriculum", "catalog", "semester spread", "programme structure",
          "program structure", "check_eligibility", "course_info", "semester_courses"]


def case(id, category, question, behavior="answer", student=None, batch=None, decision=None,
         include=(), must_not=(), sources=(), truth=""):
    return {"id": id, "category": category, "question": question, "student_id": student, "batch": batch,
            "expect": {"behavior": behavior, "decision": decision, "must_include": [list(g) for g in include],
                       "must_not": list(must_not), "sources": [list(g) for g in sources]},
            "ground_truth": truth}


CASES = [
    # ---------------- general academic information (no login needed) ----------------
    case("T01", "general", "What are the prerequisites for Machine Learning (DATA301) for the 2024 batch?", batch=2024,
         include=[["DATA202", "Exploratory Data Analysis"], ["MATH301", "Optimization"]], sources=[CURRIC],
         truth="DATA202 and MATH301 (courses.csv, batch 2024, semester 5)."),
    case("T02", "general", "What is the minimum attendance needed to appear for the end-term exam?",
         include=[["75"]], sources=[HANDBOOK + ["7.2", "sop"]], truth="75% of classes conducted in every course (Handbook 7.2; SOP s.2)."),
    case("T03", "general", "If I am hospitalised, how much attendance relaxation can I get?",
         include=[["65"], ["vice-chancellor", "vice chancellor", "program chair", "approval"]], sources=[HANDBOOK + ["7.3", "sop"]],
         truth="Relaxation down to a floor of 65% with documents, recommended by Program Chair and approved by the VC (7.3)."),
    case("T04", "general", "How many grade points does a B+ grade carry?",
         include=[["7"]], must_not=["re:b\\+[^.\\n]{0,30}\\b8\\b"], sources=[HANDBOOK + ["8.10", "table 2"]],
         truth="B+ = 7 grade points (Handbook 8.10, Table 2 - an image in the PDF)."),
    case("T05", "general", "What minimum CGPA do I need to be promoted to the third year?",
         include=[["5.00", "5.0", " 5 "]], sources=[HANDBOOK + ["12.1", "table 3"]], truth="CGPA 5.00 (Handbook 12.1, Table 3)."),
    case("T06", "general", "What CGPA is needed to graduate with distinction?",
         include=[["8.5"]], sources=[HANDBOOK + ["15.3"]], truth="CGPA 8.50 or above (Handbook 15.3)."),
    case("T07", "general", "What is the maximum number of credits I can register for in the summer term?",
         include=[["12"]], sources=[HANDBOOK + ["11.5"]], truth="12 credits / 280 hours (Handbook 11.5.3)."),
    case("T08", "general", "Within how many weeks of classes starting can I add or drop a course?",
         include=[["two weeks", "2 weeks", "two (2) weeks", "two calendar weeks"]], sources=[HANDBOOK + ["2.15", "sop"]],
         truth="Within two weeks of commencement of classes (Handbook 2.15; SOP)."),
    case("T09", "general", "How many credits is the Capstone Project / Industrial Internship (DATA803)?", batch=2024,
         include=[["12"]], sources=[CURRIC], truth="12 credits, semester 8 (courses.csv)."),
    case("T10", "general", "Which courses are scheduled in semester 5 for the 2024 batch?", batch=2024,
         include=[["DATA301", "Machine Learning"], ["COMP208", "Networks"], ["COMP207", "Operating Systems"]], sources=[CURRIC],
         truth="COMP208, COMP207, COMP205, DATA301, track slot MATH401/COMP401, Minor/Open #3, DATA801 (courses.csv)."),
    case("T11", "procedure", "How do I get a bonafide certificate for my internship?",
         include=[["digii"], ["program chair"]], sources=[["sop", "standard operating procedure"]],
         truth="Email the Program Chair with internship details, keep Registrar in loop, and raise a Bonafide request on Digii (SOP s.7)."),
    case("T12", "general", "What is the maximum duration allowed to complete my degree?",
         include=[["n+2", "n + 2", "two additional years", "2 additional years", "plus two", "+2"]], sources=[HANDBOOK + ["6.1"]],
         truth="N+2 years (Handbook 6.1)."),
    # ---------------- missing information (data is insufficient) ----------------
    case("M01", "missing_info", "What is the maximum number of credits I can register for in a regular semester?",
         behavior="say_insufficient", must_not=["re:maximum (of |limit of |is )?\\d{2} credits", "re:up to \\d{2} credits"],
         truth="Not stated: Clause 2.16 refers to Program Regulations which are not provided."),
    case("M02", "missing_info", "How much is the late registration fee?", behavior="say_insufficient",
         must_not=["re:(₹|rs\\.?|inr)\\s?\\d", "re:\\d+\\s?(rupees|/-)"],
         truth="Late fee exists (2.7) but the amount is not in the documents."),
    case("M03", "missing_info", "Which professor teaches DATA301 next semester and at what time?", behavior="say_insufficient",
         must_not=["re:\\b(prof|professor|dr)\\.?\\s+[a-z]{3,}", "re:\\d{1,2}(:\\d\\d)?\\s?(am|pm)"],
         truth="Faculty names and timetables are not in the documents."),
    case("M04", "missing_info", "Can I take Machine Learning (DATA301) next semester?", student="STU_043",
         behavior="say_insufficient", decision="NO_DATA_FOR_BATCH", include=[["2021"]],
         truth="Profile is batch 2021; no curriculum data exists for 2021 (data covers 2022-2026)."),
    case("M05", "missing_info", "My exchange semester gives me a 6-credit waiver, so I need 6 fewer credits to graduate, right?",
         student="STU_045", behavior="say_insufficient", must_not=["re:yes,? (you|your)", "waiver is approved", "waiver has been applied"],
         truth="No credit-waiver rule exists in the documents; refer to the Registrar / Program Chair."),
    case("M06", "missing_info", "Will the Big Data Framework (DATA406) elective definitely run next semester?", batch=2024,
         behavior="say_insufficient", include=[["10", "ten"]], sources=[HANDBOOK + ["2.13"]],
         truth="Not guaranteed: specialization/minor courses run only if >=10 students register (2.13); actual offering not in documents."),
    # ---------------- conflicting rules / source-data conflicts ----------------
    case("C01", "conflict", "Can I register late for a non-medical reason?", behavior="flag_conflict",
         include=[["one week", "1 week", "one (01) calendar week", "one calendar week"], CONFLICT + ["sop", "but"]],
         sources=[HANDBOOK + ["2.7", "sop"]],
         truth="Handbook 2.7 allows up to 1 week with late fee for other reasons; SOP s.1 says 'No late registration' except medical/competition -> flag conflict, confirm with Program Chair."),
    case("C02", "conflict", "Can I take Digital Economics (ECON316) in semester 5?", student="STU_010", behavior="flag_conflict",
         decision="NEEDS_REVIEW", include=[["ECON201"], CONFLICT + ["ECON208"]],
         truth="2025 Economics minor lists prerequisite ECON201, but 2025 offers ECON208 Microeconomics I instead -> needs confirmation."),
    case("C03", "conflict", "For the 2023 batch, what are the prerequisites of Exploratory Data Analysis (DATA202)?", batch=2023,
         behavior="flag_conflict", include=[["DATA201"], ["MATH203"], CONFLICT],
         truth="DATA201 and MATH203, but MATH203 is not part of the 2023 curriculum (data flag) -> confirm."),
    case("C04", "conflict", "Can I take Multi Modal Learning (DATA404) next semester?", student="STU_016", behavior="flag_conflict",
         decision="NOT_ELIGIBLE", include=[["DATA302", "Deep Learning"], CONFLICT],
         truth="Needs DATA302, which is scheduled in the same semester 6 -> not eligible now; curriculum conflict to flag."),
    case("C05", "conflict", "In the 2022 batch, is DATA404 Multi Modal Learning or Cloud Computing?", batch=2022,
         behavior="flag_conflict", include=[CONFLICT + ["both", "confirm"]],
         truth="The 2022 sheet lists one code DATA404 with title 'Multi Modal Learning / Cloud Computing' -> ambiguous; confirm."),
    # ---------------- student-specific eligibility / progress ----------------
    case("E01", "eligibility", "Can I take Deep Learning (DATA302) next semester?", student="STU_016", decision="CONDITIONAL",
         include=[["DATA301", "Machine Learning"], ["pass", "complete", "in progress", "currently"]],
         truth="DATA302 needs DATA301, which STU_016 is taking now -> conditional on passing it."),
    case("E02", "eligibility", "Am I eligible for Machine Learning (DATA301)?", student="STU_017", decision="NOT_ELIGIBLE",
         include=[["MATH301", "Optimization"]], must_not=["re:\\byou are eligible\\b"],
         truth="Not eligible: MATH301 failed (F)."),
    case("E03", "eligibility", "Can I register for DATA301?", student="STU_018", decision="NOT_ELIGIBLE",
         include=[["DATA202", "Exploratory"]], truth="Not eligible: DATA202 failed."),
    case("E04", "eligibility", "Can I take Analysis of Algorithms (COMP203)?", student="STU_007", decision="NOT_ELIGIBLE",
         include=[["COMP201", "Data Structures"], ["make-up", "makeup", "make up", "re-register", "reregister", "retake", "repeat"]],
         truth="Not eligible: COMP201 = F; make-up exam in the next semester or re-register (8.13.3, 9.5)."),
    case("E05", "eligibility", "Can I take Natural Language Processing (DATA403)?", student="STU_029", decision="NOT_ELIGIBLE",
         include=[["DATA302", "Deep Learning"]], truth="Not eligible: DATA302 failed."),
    case("E06", "eligibility", "Can I take MLOps & Model Deployment (DATA303)?", student="STU_035", decision="NOT_ELIGIBLE",
         include=[["COMP208", "Networks"]], truth="Not eligible: COMP208 = FA (attendance)."),
    case("E07", "progress", "Will I be promoted to Year 3?", student="STU_022",
         include=[["5.00", "5.0"], [cg("STU_022")]], must_not=["re:\\byou will be promoted\\b", "re:\\byes\\b"],
         truth=f"CGPA {cg('STU_022')} < 5.00 -> does not meet the Year 3 progression criterion (12.1); options 12.4/12.5."),
    case("E08", "privacy_aware", "Can I register for next semester? Is anything blocking me?", student="STU_004",
         include=[["dues", "fees", "registrar", "hold"]], must_not=["85000", "85,000"],
         truth="Registration hold (outstanding dues, Clause 2.10) - amount must not be disclosed."),
    case("E09", "progress", "Am I on track for a degree with distinction?", student="STU_026",
         include=[[cg("STU_026")], ["8.5"]], truth=f"CGPA {cg('STU_026')} >= 8.50 so currently on track (15.3); final CGPA decides."),
    case("E10", "graduation", "Can I graduate at the end of this academic year?", student="STU_041",
         include=[["COMP206", "COMP209", "backlog", "failed"], ["credit"]], must_not=["re:\\byou (can|will) graduate\\b"],
         truth="Not yet: COMP206 and COMP209 failed; Program Core short by 6 credits plus remaining track/capstone credits."),
    case("E11", "progress", "Can I register for semester 3?", student="STU_009",
         include=[["4.00", "4.0"], [cg("STU_009")]], must_not=["re:\\byou are eligible\\b", "re:\\byou can register\\b"],
         truth=f"CGPA {cg('STU_009')} < 4.00 required for semester 3 (12.1) -> repeat year (12.4) or re-register courses (12.5)."),
    case("E12", "progress", "How many credits have I earned so far and how many do I still need?", student="STU_016",
         include=[["99"], ["180", "81"]], truth="99 earned of 180 required; 81 remaining (basket_requirements.csv)."),
    case("E13", "eligibility", "Can I take Advanced Statistical Analysis (MATH206) next semester?", student="STU_006",
         decision="ELIGIBLE", include=[["MATH203", "Probability"]], must_not=["re:not eligible"],
         truth="Eligible: prerequisite MATH203 passed (courses.csv batch 2025, semester 4)."),
    # ---------------- ambiguous / follow-up ----------------
    case("A01", "ambiguous", "Can I take Machine Learning next semester?", behavior="needs_login",
         include=[["log in", "login", "student id", "which courses", "completed", "your record", "batch"]],
         truth="Personal eligibility question without a record -> ask to log in / ask for completed courses."),
    case("A02", "ambiguous", "Which specialization course should I pick?", student="STU_016", behavior="ask_follow_up",
         include=[["MATH401", "COMP401", "Probabilistic", "Web Framework", "interest", "which", "?"]],
         truth="Options for semester 5 track slot are MATH401 or COMP401; ask about interests/career goal; Faculty Advisor decides."),
    case("A03", "ambiguous", "What are the prerequisites for Deep Learning?",
         include=[["DATA301", "Machine Learning"], ["batch", "2023", "which year", "entry year"]],
         truth="DATA301 for all batches; batch 2023 also lists MATH201 -> answer depends on batch."),
    # ---------------- unavailable / not in curriculum ----------------
    case("U01", "unavailable", "Can I take Calculus (MATH201)?", student="STU_001", decision="NOT_IN_CURRICULUM",
         include=[["not in", "not part", "not offered", "not listed", "not available", "does not appear"]],
         truth="MATH201 is not in the batch 2026 curriculum (it exists for 2022-2024)."),
    case("U02", "unavailable", "Does the university offer a Quantum Computing minor?", behavior="say_insufficient",
         include=[["Design", "Economics", "Finance", "Law", "Marketing", "Psychology", "Start-up"]],
         must_not=["re:yes,? (the university|vidyashilp|there is)"],
         truth="No such minor in the documents; listed minors are Design, Economics, Finance, Law, Marketing, Psychology, Start-up."),
    # ---------------- off topic ----------------
    case("O01", "off_topic", "Who will win the IPL this year?", behavior="refuse",
         include=[["academic", "courses", "only help", "university", "can't help", "cannot help"]],
         must_not=["re:(mumbai|chennai|kolkata|bengaluru|rcb|csk|mi) (will|are likely)"],
         truth="Out of scope -> politely decline and redirect."),
]

if __name__ == "__main__":
    out = Path(__file__).with_name("test_cases.json")
    out.write_text(json.dumps({"insufficient_markers": INSUFF, "conflict_markers": CONFLICT, "cases": CASES},
                              indent=2), encoding="utf-8")
    print(f"Wrote {len(CASES)} cases to {out}")
