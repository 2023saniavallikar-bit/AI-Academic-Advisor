"""Generate the synthetic student database (v2) from the real curriculum.

Run:  python scripts/generate_students.py
Writes synthetic_students.json and data/demo_users.json, then validates.

Design rules
------------
* Every course in a profile comes from cleaned/courses.csv or
  cleaned/minor_courses.csv for the student's own batch (validated).
* Only real minors (Design, Economics, Finance, Law, Marketing, Psychology,
  Start-up) and batches 2022-2026 are used, except for profiles that are
  deliberately broken to test missing data; those carry data_quality_flags.
* A course is only taken after its prerequisites are passed (prerequisites
  that are not in the batch curriculum cannot be required and are ignored).
* No names, emails, phone numbers or real IDs. The "restricted" block holds
  clearly synthetic sensitive data so the privacy audit has something to
  protect.
* Seeded, so the same file is produced every run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from academic_tools import (  # noqa: E402
    EARNED_GRADES, FAIL_GRADES, catalogue, compute_cgpa, credit_summary,
)

SEED = 308
TERM = "Odd Semester, Academic Year 2026-27"
CURRENT_SEM = {2026: 1, 2025: 3, 2024: 5, 2023: 7, 2022: 7}
GRADES = ["O", "A+", "A", "B+", "B", "C", "D"]

# Each scenario: batch, description, tags and overrides.
#   grades:   {code: grade} forced grade on first attempt (F, FA, I ...)
#   retakes:  {code: (semester_taken, grade, term)} second attempt
#   attendance: {code: percent} for current courses
#   track:    0/1 which alternative to take in specialization slots
#   current_semester: override (repeat year / withdrawal)
S = [
    # ---------------- batch 2026: first semester ----------------
    dict(batch=2026, d="Fresh entry, Semester 1, no minor declared yet", tags=["normal", "minor_preregistration"], ability=.7),
    dict(batch=2026, d="Semester 1 - attendance shortage risk in Probability Theory", tags=["attendance"], ability=.6, attendance={"MATH202": 70}),
    dict(batch=2026, d="Semester 1 - hospitalised for 2 weeks, attendance 68% with medical documents", tags=["attendance", "medical_relaxation"], ability=.6,
         attendance={"MATH202": 68}, restricted={"medical_accommodation": "Hospitalisation Aug 2026 (synthetic), documents submitted"}),
    dict(batch=2026, d="Semester 1 - fee dues pending (registration hold)", tags=["registration_hold", "privacy"], ability=.65, restricted={"fee_dues_inr": 85000}),
    dict(batch=2026, d="Semester 1 - wants to transfer to another programme", tags=["program_transfer"], ability=.55),
    # ---------------- batch 2025: semester 3 ----------------
    dict(batch=2025, d="Semester 3 - smooth progression, high achiever", tags=["normal"], ability=.92),
    dict(batch=2025, d="Failed Data Structures (COMP201) - blocks Analysis of Algorithms", tags=["failed_prerequisite", "makeup_exam"], ability=.6, grades={"COMP201": "F"}),
    dict(batch=2025, d="FA grade (attendance) in Calculus - must re-register", tags=["fa_grade", "failed_prerequisite"], ability=.6, grades={"MATH201": "FA"}),
    dict(batch=2025, d="CGPA below 4.00 after Year 1 - not promoted, repeating Year 1", tags=["progression", "low_cgpa"], ability=0.0,
         grades={"COMP201": "F", "MATH201": "F", "MATH202": "F", "DATA201": "F", "MTSC111": "F"}, current_semester=1, status="Not promoted - repeating Year 1 (Clause 12.4)"),
    dict(batch=2025, d="Economics minor - first minor course this semester", tags=["minor"], ability=.75, minor="Economics"),
    dict(batch=2025, d="Psychology minor", tags=["minor"], ability=.7, minor="Psychology"),
    dict(batch=2025, d="Incomplete 'I' grade in Statistics with R after medical absence", tags=["i_grade", "makeup_exam"], ability=.7, grades={"MATH205": "I"}),
    dict(batch=2025, d="Grade review appeal pending in Linear Algebra", tags=["grade_review", "missing_information"], ability=.65, grade_appeal="MATH204"),
    dict(batch=2025, d="Borderline CGPA just above 4.00", tags=["progression", "borderline"], ability=0.0, grades={"COMP201": "D", "MATH201": "D", "MATH202": "D", "DATA131": "C"}),
    dict(batch=2025, d="Already changed minor once (Design -> Finance), wants to change again", tags=["change_of_minor", "conflict"], ability=.7, minor="Finance", minor_changes=1),
    # ---------------- batch 2024: semester 5 ----------------
    dict(batch=2024, d="Semester 5 - ready for Machine Learning (DATA301)", tags=["normal", "eligible"], ability=.8),
    dict(batch=2024, d="Failed Optimization Techniques (MATH301) - blocks Machine Learning", tags=["failed_prerequisite"], ability=.6, grades={"MATH301": "F"}),
    dict(batch=2024, d="Failed Exploratory Data Analysis (DATA202) - blocks Machine Learning", tags=["failed_prerequisite"], ability=.6, grades={"DATA202": "F"}),
    dict(batch=2024, d="Finance minor", tags=["minor"], ability=.75, minor="Finance"),
    dict(batch=2024, d="Marketing minor", tags=["minor"], ability=.7, minor="Marketing"),
    dict(batch=2024, d="Start-up minor", tags=["minor"], ability=.7, minor="Start-up"),
    dict(batch=2024, d="CGPA below 5.00 at end of Year 2 - progression to Year 3 at risk", tags=["progression", "low_cgpa"], ability=.1,
         grades={"COMP203": "F", "COMP209": "D", "MATH301": "D", "DATA202": "D"}),
    dict(batch=2024, d="Failed Databases Management, cleared it in Summer Term", tags=["summer_term", "retake"], ability=.65,
         grades={"COMP209": "F"}, retakes={"COMP209": (4, "B", "Summer Term 2026")}),
    dict(batch=2024, d="Disciplinary action pending (restricted)", tags=["privacy", "restricted"], ability=.7, restricted={"disciplinary_action_pending": True}),
    dict(batch=2024, d="Choosing specialization: Probabilistic Graph Models vs Web Framework", tags=["specialization_choice"], ability=.75),
    dict(batch=2024, d="High CGPA - distinction trajectory", tags=["distinction"], ability=.97),
    dict(batch=2024, d="Wants to audit a course for no credit", tags=["audit"], ability=.7),
    # ---------------- batch 2023: semester 7 ----------------
    dict(batch=2023, d="Semester 7 - Deep Learning passed, ready for NLP (DATA403)", tags=["normal", "eligible"], ability=.8),
    dict(batch=2023, d="Failed Deep Learning (DATA302) - blocks NLP and Multi Modal Learning", tags=["failed_prerequisite"], ability=.6, grades={"DATA302": "F"}),
    dict(batch=2023, d="Law minor", tags=["minor"], ability=.75, minor="Law"),
    dict(batch=2023, d="Design minor", tags=["minor"], ability=.7, minor="Design"),
    dict(batch=2023, d="Capstone readiness - credit audit before Semester 8", tags=["credits", "capstone"], ability=.75),
    dict(batch=2023, d="Needs bonafide certificate for internship", tags=["sop", "bonafide"], ability=.7),
    dict(batch=2023, d="Took Exploratory Data Analysis although MATH203 is not in the 2023 curriculum (data conflict)", tags=["conflict", "prerequisite_conflict"], ability=.7),
    dict(batch=2023, d="FA grade in Networks (COMP208) - blocks IoT and MLOps", tags=["fa_grade", "failed_prerequisite"], ability=.6, grades={"COMP208": "FA"}),
    dict(batch=2023, d="No minor declared - open electives not identified in catalogue", tags=["missing_information", "credits"], ability=.65),
    dict(batch=2023, d="Returned after temporary withdrawal (one year) - now in Semester 5", tags=["withdrawal", "max_duration"], ability=.65, current_semester=5,
         status="Active - rejoined after temporary withdrawal AY 2025-26 (Clause 13.1)"),
    dict(batch=2023, d="Wants a make-up exam to improve a C grade", tags=["makeup_exam", "grade_improvement"], ability=.6, grades={"COMP207": "C"}),
    # ---------------- batch 2022: extended duration ----------------
    dict(batch=2022, d="Batch 2022 - temporary withdrawal for one year, now Semester 7", tags=["max_duration", "withdrawal"], ability=.7,
         status="Active - rejoined after temporary withdrawal AY 2024-25 (Clause 13.1)"),
    dict(batch=2022, d="Batch 2022 - repeated Year 2 after progression failure, now Semester 7", tags=["max_duration", "progression"], ability=.5,
         status="Active - repeated Year 2 (Clause 12.4)"),
    dict(batch=2022, d="Batch 2022 - graduation check with outstanding backlogs", tags=["graduation", "backlog"], ability=.55, grades={"COMP206": "F", "DATA303": "F"}),
    dict(batch=2022, d="Batch 2022 - graduation check, dues pending", tags=["graduation", "registration_hold", "privacy"], ability=.75, restricted={"fee_dues_inr": 42000}),
    # ---------------- deliberate data gaps ----------------
    dict(batch=2021, d="Batch 2021 student - no curriculum data provided for this batch", tags=["missing_information", "no_batch_data"], ability=.7, flags=["batch_not_in_curriculum"]),
    dict(batch=2024, d="Transfer credits from another university (courses not in catalogue)", tags=["missing_information", "transfer_credits"], ability=.7,
         transfer=[{"course_code": "EXT-CS101", "course_title": "Intro to Programming (external)", "credits": 4, "status": "pending equivalence"}],
         flags=["transfer_course_not_in_catalogue"]),
    dict(batch=2025, d="International exchange - claims credit waiver (no rule in documents)", tags=["missing_information", "exchange"], ability=.7,
         notes="Student claims a 6-credit waiver from an exchange semester; no waiver rule exists in the provided documents."),
    dict(batch=2024, d="Incomplete record - some grades not recorded", tags=["missing_information", "incomplete_record"], ability=.7, missing_grades=["COMP205", "MATH207"],
         flags=["grades_not_recorded"]),
    dict(batch=2025, d="Wants to transfer programme in Year 2 (after the deadline)", tags=["program_transfer", "deadline"], ability=.6),
    dict(batch=2024, d="Wants to register 32 credits next semester (maximum not stated in documents)", tags=["credit_overload", "missing_information"], ability=.9),
    dict(batch=2023, d="Medical accommodation on file (restricted)", tags=["privacy", "restricted"], ability=.7,
         restricted={"medical_accommodation": "Extra exam time - chronic condition (synthetic)"}),
    dict(batch=2025, d="Scholarship holder (restricted financial data)", tags=["privacy", "restricted"], ability=.8,
         restricted={"scholarship": "Merit scholarship 50% (synthetic)"}),
]


def sample_grade(rng, ability):
    # higher ability -> earlier (better) grade; never F unless forced
    mu = (1 - ability) * (len(GRADES) - 1)
    idx = int(round(min(len(GRADES) - 1, max(0, rng.gauss(mu, 1.0)))))
    return GRADES[idx]


def resolve_semester_slots(cat, batch, sem, minor, minor_queue, track):
    """Courses a student of this batch takes in a semester (one per slot)."""
    by_slot = {}
    for o in cat.programme_offerings(batch, sem):
        by_slot.setdefault(o.slot_id, []).append(o)
    chosen = []
    for slot, opts in by_slot.items():
        o = opts[min(track, len(opts) - 1)] if len(opts) > 1 else opts[0]
        if "minor_or_open_slot" in o.flags:
            n = 2 if (o.credits or 0) >= 8 else 1
            for _ in range(n):
                pick = None
                if minor:
                    pick = next((m for m in minor_queue if m.semester == sem), None) or \
                        next((m for m in minor_queue if m.semester and m.semester < sem), None)
                if pick is not None:
                    minor_queue.remove(pick)
                    m = pick
                    chosen.append(dict(course_code=m.code, course_title=m.title,
                                       credits=m.credits if m.credits else (o.credits / n),
                                       basket_id="B6", slot_id=m.slot_id, prereqs=m.prereqs,
                                       kind="minor", placeholder=m.code is None,
                                       note=None if m.credits else "credits TBD in catalogue; slot credits used"))
                else:
                    chosen.append(dict(course_code=None, course_title="Open elective (course not listed in the provided catalogue)",
                                       credits=o.credits / n, basket_id="B6", slot_id=f"{slot}#{_}",
                                       prereqs=[], kind="open", placeholder=True))
            continue
        chosen.append(dict(course_code=o.code, course_title=o.title, credits=o.credits,
                           basket_id=o.basket_id, slot_id=slot, prereqs=o.prereqs,
                           kind="programme", placeholder=o.code is None))
    return chosen


def build_student(idx, spec, cat, rng):
    sid = f"STU_{idx:03d}"
    batch = spec["batch"]
    cur = spec.get("current_semester", CURRENT_SEM.get(batch, 5))
    ability = spec.get("ability", .7)
    minor = spec.get("minor")
    track = spec.get("track", rng.randint(0, 1))
    forced = spec.get("grades", {})
    retakes = spec.get("retakes", {})
    curriculum_batch = batch if batch in cat.batches else 2022  # gap profiles borrow a template
    minor_queue = list(cat.minor_offerings(minor, curriculum_batch)) if minor else []
    batch_codes = cat.batch_codes(curriculum_batch)
    history, backlog, passed = [], [], set()
    completed_sems = cur - 1
    if spec.get("status", "").startswith("Not promoted"):
        completed_sems = 2  # did Year 1 once, now repeating it

    def prereqs_ok(c):
        return all(p in passed for p in c["prereqs"] if p in batch_codes)

    for sem in range(1, completed_sems + 1):
        sem_passed = set()
        slots = resolve_semester_slots(cat, curriculum_batch, sem, minor, minor_queue, track)
        same_sem = {c["course_code"] for c in slots if c["course_code"]}
        for c in slots:
            # A prerequisite scheduled in the SAME semester (source-data conflict) is
            # taken concurrently; anything else must have been passed earlier.
            if not all(p in passed or p in same_sem for p in c["prereqs"] if p in batch_codes):
                backlog.append({"course_code": c["course_code"], "course_title": c["course_title"],
                                "reason": "prerequisite not passed", "scheduled_semester": sem})
                continue
            grade = forced.get(c["course_code"]) or sample_grade(rng, ability)
            if c["course_code"] in spec.get("missing_grades", []):
                grade = None
            entry = {k: c[k] for k in ("course_code", "course_title", "credits", "basket_id", "slot_id")}
            entry.update(semester_taken=sem, attempt=1, grade=grade,
                         term="Regular", placeholder=c["placeholder"])
            if c.get("note"):
                entry["note"] = c["note"]
            history.append(entry)
            if grade in EARNED_GRADES and c["course_code"]:
                sem_passed.add(c["course_code"])
        passed |= sem_passed
        for code, (rsem, rgrade, rterm) in retakes.items():
            if rsem == sem:
                first = next(h for h in history if h["course_code"] == code)
                history.append({**first, "attempt": 2, "grade": rgrade, "term": rterm})
                if rgrade in EARNED_GRADES:
                    passed.add(code)

    # current semester
    current = []
    if spec.get("status", "").startswith("Not promoted"):
        current = [{"course_code": h["course_code"], "course_title": h["course_title"], "credits": h["credits"],
                    "basket_id": h["basket_id"], "type": "re-registration"}
                   for h in history if h["grade"] in FAIL_GRADES and h["course_code"]]
    else:
        for c in resolve_semester_slots(cat, curriculum_batch, cur, minor, minor_queue, track):
            if not prereqs_ok(c):
                backlog.append({"course_code": c["course_code"], "course_title": c["course_title"],
                                "reason": "prerequisite not passed", "scheduled_semester": cur})
                continue
            current.append({"course_code": c["course_code"], "course_title": c["course_title"],
                            "credits": c["credits"], "basket_id": c["basket_id"], "type": "regular",
                            "placeholder": c["placeholder"]})
    for c in current:
        c["attendance_percent"] = spec.get("attendance", {}).get(c["course_code"], rng.randint(78, 98))

    restricted = {"fee_dues_inr": 0, "disciplinary_action_pending": False, "medical_accommodation": None,
                  "scholarship": None, "debarred": False,
                  "emergency_contact": f"SYNTHETIC-CONTACT-{idx:03d} (not a real number)"}
    restricted.update(spec.get("restricted", {}))

    st = {
        "student_id": sid,
        "synthetic": True,
        "description": spec["d"],
        "scenario_tags": spec["tags"],
        "programme": "B.Tech (curriculum: 'Sem Spread BTECH' sheets)",
        "batch": batch,
        "current_semester": cur,
        "current_term": TERM,
        "academic_status": spec.get("status", "Active"),
        "minor": minor,
        "minor_changes_used": spec.get("minor_changes", 0),
        "course_history": history,
        "current_courses": current,
        "backlog_courses": backlog,
        "transfer_credits": spec.get("transfer", []),
        "grade_appeal_pending": spec.get("grade_appeal"),
        "notes": spec.get("notes"),
        "data_quality_flags": spec.get("flags", []),
        "restricted": restricted,
    }
    # derived fields (computed by the same tools the advisor uses)
    cg = compute_cgpa(st)
    cs = credit_summary(st, cat)
    st["derived"] = {"cgpa": cg["cgpa"], "credits_earned": cs["total_earned"],
                     "credits_required": cs["total_required"],
                     "computed_by": "academic_tools.compute_cgpa / credit_summary"}
    # flat lists kept for backwards compatibility with Assignment 1 prompts
    latest = {}
    for h in history:
        latest[h["course_code"] or h["slot_id"]] = h
    st["completed_courses"] = [{"course_code": h["course_code"], "course_title": h["course_title"],
                                "credits": h["credits"], "grade": h["grade"]}
                               for h in latest.values() if h["grade"] in EARNED_GRADES]
    st["failed_courses"] = [{"course_code": h["course_code"], "course_title": h["course_title"],
                             "credits": h["credits"], "grade": h["grade"]}
                            for h in latest.values() if h["grade"] in FAIL_GRADES or h["grade"] == "I"]
    st["total_credits_earned"] = cs["total_earned"]
    return st


def demo_users(students):
    """Mock login accounts for the demo. PINs are public demo values; only salted
    hashes are stored. One advisor account sees a fixed set of advisees."""
    users = []
    for s in students:
        pin = s["student_id"][-3:] + "9"  # e.g. STU_007 -> 0079
        users.append({"username": s["student_id"], "role": "student", "student_id": s["student_id"],
                      "salt": s["student_id"], "pin_sha256": hashlib.sha256((s["student_id"] + pin).encode()).hexdigest()})
    advisees = [s["student_id"] for s in students[:12]]
    users.append({"username": "ADVISOR_01", "role": "advisor", "advisees": advisees, "salt": "ADVISOR_01",
                  "pin_sha256": hashlib.sha256(("ADVISOR_01" + "2468").encode()).hexdigest()})
    return users


def main():
    cat = catalogue()
    rng = random.Random(SEED)
    students = [build_student(i + 1, spec, cat, rng) for i, spec in enumerate(S)]
    (ROOT / "synthetic_students.json").write_text(json.dumps(students, indent=2), encoding="utf-8")
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "demo_users.json").write_text(json.dumps(demo_users(students), indent=2), encoding="utf-8")
    print(f"Wrote {len(students)} students.")
    from validate_students import validate  # noqa: E402
    problems = validate(students, cat)
    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("Validation passed.")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
