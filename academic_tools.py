"""Deterministic academic tools (no AI model involved).

These functions answer the parts of advising that are pure lookups and
arithmetic: what a course requires, whether a student meets it, how many
credits are earned per basket, what the CGPA is, whether progression or
graduation criteria are met. The agentic advisor calls them as tools, the
student generator and validator use them to keep the synthetic data
consistent with the real curriculum, and the evaluation uses them to compute
verified expected answers.

Every result carries ``evidence``: the file/row or handbook clause it came
from, so the model can cite it and the verifier can check it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CLEANED = BASE_DIR / "cleaned"
REGULATIONS_PATH = BASE_DIR / "data" / "regulations.json"
CODE_RE = re.compile(r"[A-Z]{4}\d{3}")


def load_regulations(path: Path = REGULATIONS_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


REGULATIONS = load_regulations()
GRADE_POINTS = REGULATIONS["grade_points"]["scale"]
EARNED_GRADES = set(REGULATIONS["grade_points"]["earned_credit_grades"])
FAIL_GRADES = {"F", "FA"}


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

@dataclass
class Offering:
    """One course a student of a batch can take (alternatives split out)."""

    batch: int
    semester: int
    basket_id: str
    basket: str
    code: str | None
    title: str
    credits: float | None
    prereqs: list[str]
    slot_id: str
    placeholder: bool = False
    alternatives: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    source: str = ""
    kind: str = "programme"  # programme | minor
    minor: str | None = None

    def to_dict(self) -> dict:
        return {
            "batch": self.batch, "semester": self.semester,
            "basket_id": self.basket_id, "basket": self.basket,
            "course_code": self.code, "course_title": self.title,
            "credits": self.credits, "prerequisites": self.prereqs,
            "slot_id": self.slot_id, "placeholder": self.placeholder,
            "alternatives": self.alternatives, "flags": self.flags,
            "source": self.source, "kind": self.kind, "minor": self.minor,
        }


def _codes(text) -> list[str]:
    if not isinstance(text, str):
        return []
    return CODE_RE.findall(text.upper())


def _split_titles(title: str, n: int) -> tuple[list[str], bool]:
    t = re.sub(r"SPT-Course\s*#\d+\s*[-:]?\s*", "", str(title))
    t = re.sub(r"LTP:\s*\d-\d-\d", "", t).strip()
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1]
    parts = [p.strip(" ()") for p in t.split("/") if p.strip(" ()")]
    if len(parts) == n:
        return parts, False
    if n == 1 and parts:
        # e.g. "Multi Modal Learning / Cloud Computing" with one code
        ambiguous = len(set(p.lower() for p in parts)) > 1
        return [parts[0]], ambiguous
    return [t] * n, True


class Catalogue:
    def __init__(self, cleaned_dir: Path = CLEANED):
        self.courses_df = pd.read_csv(cleaned_dir / "courses.csv")
        self.minors_df = pd.read_csv(cleaned_dir / "minor_courses.csv")
        self.baskets_df = pd.read_csv(cleaned_dir / "basket_requirements.csv")
        self.offerings: list[Offering] = []
        self._build()

    # -- build -------------------------------------------------------------
    def _build(self):
        for _, r in self.courses_df.iterrows():
            batch, sem = int(r.batch), int(r.semester)
            raw_code = r.course_code if isinstance(r.course_code, str) else ""
            src = f"cleaned/courses.csv row {r.course_id} (sheet '{r.source_sheet}' row {r.source_row})"
            base_flags = [f for f in str(r.data_flags).split(";") if f and f != "nan"]
            if r.basket_id == "B6" and not _codes(raw_code):
                # Minor/Open slot: resolved per student (minor course or open elective)
                self.offerings.append(Offering(
                    batch, sem, r.basket_id, r.basket, None, str(r.course_title),
                    float(r.credits), [], slot_id=r.course_id, placeholder=True,
                    flags=base_flags + ["minor_or_open_slot"], source=src))
                continue
            codes = [c if CODE_RE.fullmatch(c) else None
                     for c in (p.strip() for p in raw_code.split("/"))] if raw_code else [None]
            n = len(codes)
            titles, ambiguous = _split_titles(r.course_title, n)
            raw_pr = r.prereq_raw if isinstance(r.prereq_raw, str) else "NIL"
            pr_parts = raw_pr.split("/")
            if n > 1 and len(pr_parts) == n:
                per_alt = [_codes(p) for p in pr_parts]
            else:
                per_alt = [_codes(raw_pr)] * n
            for i, code in enumerate(codes):
                flags = list(base_flags)
                if ambiguous:
                    flags.append("title_ambiguous_in_source")
                if code is None:
                    flags.append("course_code_tba")
                if str(r.prereq_type) == "TBA" or "TBA" in raw_pr.upper():
                    flags.append("prerequisite_tba")
                self.offerings.append(Offering(
                    batch, sem, r.basket_id, r.basket, code, titles[i],
                    float(r.credits), per_alt[i], slot_id=r.course_id,
                    placeholder=code is None or bool(r.is_placeholder) and n > 1,
                    alternatives=[c for c in codes if c and c != code],
                    flags=flags, source=src))
        for _, r in self.minors_df.iterrows():
            code = r.course_code if isinstance(r.course_code, str) and CODE_RE.fullmatch(r.course_code.strip()) else None
            credits = None if pd.isna(r.credits) else float(r.credits)
            sem = None if pd.isna(r.semester) else int(r.semester)
            flags = [] if r.status == "OK" else [str(r.status).lower()]
            self.offerings.append(Offering(
                int(r.batch), sem, "B6", "Open/Minor", code, str(r.course_title),
                credits, _codes(r.prereq_raw), slot_id=f"minor-{r.minor}-{r.batch}-{r.source_row}",
                placeholder=code is None, flags=flags,
                source=f"cleaned/minor_courses.csv ({r.minor} minor, sheet '{r.source_sheet}' row {r.source_row})",
                kind="minor", minor=str(r.minor)))
        # prerequisite codes that are not in that batch's curriculum, or that are
        # scheduled in the same/later semester (both are conflicts in the source)
        for o in self.offerings:
            batch_codes = self.batch_codes(o.batch)
            sem_of = {}
            for x in self.offerings:
                if x.batch == o.batch and x.code and x.kind == "programme":
                    sem_of.setdefault(x.code, x.semester)
            for p in o.prereqs:
                if p not in batch_codes:
                    tag = f"prereq_{p}_not_in_{o.batch}_curriculum"
                    if tag not in o.flags:
                        o.flags.append(tag)
                elif o.semester and sem_of.get(p) and sem_of[p] >= o.semester:
                    o.flags.append(f"prereq_{p}_scheduled_same_or_later_semester")

    # -- queries -----------------------------------------------------------
    @property
    def batches(self) -> list[int]:
        return sorted(self.courses_df.batch.unique().tolist())

    @property
    def minors(self) -> list[str]:
        return sorted(self.minors_df.minor.unique().tolist())

    def batch_codes(self, batch: int, include_minors: bool = True) -> set[str]:
        return {o.code for o in self.offerings
                if o.batch == batch and o.code and (include_minors or o.kind == "programme")}

    def find(self, code: str, batch: int | None = None, minor: str | None = None) -> list[Offering]:
        code = (code or "").upper().strip()
        out = [o for o in self.offerings if o.code == code and (batch is None or o.batch == batch)]
        if minor:
            # Prefer the row of the student's own minor when a code appears in several
            out.sort(key=lambda o: (o.kind == "minor" and o.minor != minor))
        return out

    def programme_offerings(self, batch: int, semester: int | None = None) -> list[Offering]:
        return [o for o in self.offerings if o.batch == batch and o.kind == "programme"
                and (semester is None or o.semester == semester)]

    def minor_offerings(self, minor: str, batch: int) -> list[Offering]:
        return sorted([o for o in self.offerings if o.kind == "minor" and o.minor == minor
                       and o.batch == batch], key=lambda o: (o.semester or 99, o.slot_id))

    def basket_requirements(self, batch: int) -> list[dict]:
        rows = self.baskets_df[self.baskets_df.batch == batch]
        return [{"basket_id": r.basket_id, "basket": r.basket,
                 "min_credits": int(r.fixed_min_credits),
                 "scheduled_credits": int(r.scheduled_credits),
                 "differs": bool(r.differs)} for _, r in rows.iterrows()]

    def total_required_credits(self, batch: int) -> int:
        return sum(b["min_credits"] for b in self.basket_requirements(batch))


_CATALOGUE: Catalogue | None = None


def catalogue() -> Catalogue:
    global _CATALOGUE
    if _CATALOGUE is None:
        _CATALOGUE = Catalogue()
    return _CATALOGUE


# ---------------------------------------------------------------------------
# Student record helpers
# ---------------------------------------------------------------------------

def latest_attempts(student: dict) -> dict[str, dict]:
    """Most recent attempt per course (code, or slot for placeholders)."""
    latest: dict[str, dict] = {}
    for c in student.get("course_history", []):
        key = c.get("course_code") or c.get("slot_id") or c.get("course_title")
        prev = latest.get(key)
        if prev is None or (c.get("semester_taken", 0), c.get("attempt", 1)) >= (
                prev.get("semester_taken", 0), prev.get("attempt", 1)):
            latest[key] = c
    return latest


def passed_codes(student: dict) -> set[str]:
    return {k for k, c in latest_attempts(student).items()
            if c.get("course_code") and c.get("grade") in EARNED_GRADES}


def failed_codes(student: dict) -> set[str]:
    return {k for k, c in latest_attempts(student).items()
            if c.get("course_code") and c.get("grade") in FAIL_GRADES}


def in_progress_codes(student: dict) -> set[str]:
    return {c["course_code"] for c in student.get("current_courses", []) if c.get("course_code")}


def compute_cgpa(student: dict) -> dict:
    """Clause 8.16: credit-weighted over graded courses incl. F/FA; latest attempt only."""
    num = den = 0.0
    counted = []
    for key, c in latest_attempts(student).items():
        g = c.get("grade")
        if g in GRADE_POINTS and c.get("credits"):
            num += GRADE_POINTS[g] * float(c["credits"])
            den += float(c["credits"])
            counted.append(key)
    cgpa = round(num / den, 2) if den else None
    return {"cgpa": cgpa, "graded_credits": den, "courses_counted": len(counted),
            "evidence": [REGULATIONS["cgpa"]["source"], REGULATIONS["grade_points"]["source"]]}


def credit_summary(student: dict, cat: Catalogue | None = None) -> dict:
    cat = cat or catalogue()
    batch = student.get("batch")
    earned_by_basket: dict[str, float] = {}
    total = 0.0
    for c in latest_attempts(student).values():
        if c.get("grade") in EARNED_GRADES and c.get("credits"):
            b = c.get("basket_id") or "UNKNOWN"
            earned_by_basket[b] = earned_by_basket.get(b, 0) + float(c["credits"])
            total += float(c["credits"])
    for t in student.get("transfer_credits", []):
        earned_by_basket["TRANSFER"] = earned_by_basket.get("TRANSFER", 0) + float(t.get("credits", 0))
        total += float(t.get("credits", 0))
    reqs = cat.basket_requirements(batch) if batch in cat.batches else []
    baskets = []
    for r in reqs:
        e = earned_by_basket.get(r["basket_id"], 0)
        baskets.append({**r, "earned": e, "remaining": max(0, r["min_credits"] - e)})
    result = {
        "batch": batch, "total_earned": total,
        "total_required": sum(r["min_credits"] for r in reqs) if reqs else None,
        "baskets": baskets,
        "unmapped_credits": {k: v for k, v in earned_by_basket.items()
                             if k not in {r["basket_id"] for r in reqs}},
        "evidence": ["cleaned/basket_requirements.csv", REGULATIONS["grade_points"]["earned_credit_source"]],
    }
    if not reqs:
        result["warning"] = f"No curriculum/basket data exists for batch {batch} in the provided documents."
    if result["total_required"]:
        result["total_remaining"] = max(0, result["total_required"] - total)
    return result


def year_of_semester(sem: int) -> int:
    return (sem + 1) // 2


def progression_status(student: dict, target_semester: int | None = None) -> dict:
    """Clause 12.1: CGPA needed to register at the start of an academic year."""
    target = target_semester or (student.get("current_semester", 1) + 1)
    cg = compute_cgpa(student)["cgpa"]
    reg = REGULATIONS["progression"]
    needed = None
    if target % 2 == 1 and target >= 3:  # start of an academic year (odd semester)
        needed = reg["to_year_2_min_cgpa"] if target == 3 else reg["to_year_3_plus_min_cgpa"]
    ok = None if needed is None or cg is None else cg >= needed
    return {"target_semester": target, "cgpa": cg, "min_cgpa_required": needed,
            "meets_progression": ok,
            "note": ("No yearly progression check applies to an even semester "
                     "(progression is checked at the start of each academic year).")
            if needed is None else f"Progression to year {year_of_semester(target)} needs CGPA >= {needed:.2f}.",
            "evidence": [reg["source"]]}


def registration_holds(student: dict) -> dict:
    """Only yes/no flags leave this function: amounts and reasons stay private
    (data minimisation). Clause 2.10 / SOP sections 1 and 5."""
    r = student.get("restricted", {}) or {}
    holds = []
    if float(r.get("fee_dues_inr") or 0) > 0:
        holds.append("outstanding_fees_or_dues")
    if r.get("debarred"):
        holds.append("debarred_from_registration")
    if (student.get("academic_status") or "").lower() in {"withdrawn", "terminated"}:
        holds.append(f"academic_status_{student['academic_status'].lower()}")
    return {"has_hold": bool(holds), "holds": holds,
            "evidence": [REGULATIONS["registration_conditions"]["source"]]}


def check_eligibility(student: dict, code: str, target_semester: int | None = None,
                      cat: Catalogue | None = None) -> dict:
    """Can this student register for this course? Returns a decision plus reasons.

    decision: ELIGIBLE | NOT_ELIGIBLE | CONDITIONAL | NEEDS_REVIEW | NOT_IN_CURRICULUM
              | ALREADY_PASSED | CURRENTLY_REGISTERED | NO_DATA_FOR_BATCH
    """
    cat = cat or catalogue()
    code = (code or "").upper().strip()
    batch = student.get("batch")
    target = target_semester or (student.get("current_semester", 1) + 1)
    out = {"student_id": student.get("student_id"), "course_code": code, "batch": batch,
           "target_semester": target, "reasons": [], "evidence": [], "conflicts": []}
    if batch not in cat.batches:
        out.update(decision="NO_DATA_FOR_BATCH",
                   reasons=[f"The provided curriculum has no data for batch {batch}."],
                   evidence=["cleaned/courses.csv (batches available: "
                             + ", ".join(map(str, cat.batches)) + ")"])
        return out
    rows = cat.find(code, batch, minor=student.get("minor"))
    if not rows:
        elsewhere = sorted({o.batch for o in cat.find(code)})
        out["decision"] = "NOT_IN_CURRICULUM"
        out["reasons"].append(
            f"{code} is not in the batch {batch} curriculum or its minor lists"
            + (f" (it appears for batch(es) {', '.join(map(str, elsewhere))})." if elsewhere else
               " and does not appear anywhere in the provided catalogue."))
        out["evidence"].append("cleaned/courses.csv, cleaned/minor_courses.csv")
        return out
    o = rows[0]
    out["course"] = {"title": o.course_title if hasattr(o, "course_title") else o.title,
                     "credits": o.credits, "scheduled_semester": o.semester,
                     "basket": o.basket, "kind": o.kind, "minor": o.minor,
                     "prerequisites": o.prereqs, "alternatives": o.alternatives}
    out["evidence"].append(o.source)
    passed, failed, current = passed_codes(student), failed_codes(student), in_progress_codes(student)
    if code in passed:
        out["decision"] = "ALREADY_PASSED"
        out["reasons"].append(f"{code} is already passed; re-registration of a passed course is only for "
                              "grade improvement (Clause 2.9, 11.4.3, 12.5).")
        out["evidence"].append(REGULATIONS["no_reregistration_of_passed"]["source"])
        return out
    if code in current:
        out["decision"] = "CURRENTLY_REGISTERED"
        out["reasons"].append(f"{code} is already in the student's current-semester registration.")
        return out
    missing, pending, conflict = [], [], []
    for p in o.prereqs:
        if p in passed:
            out["reasons"].append(f"Prerequisite {p} passed.")
        elif p in current:
            pending.append(p)
        elif p not in cat.batch_codes(batch):
            conflict.append(p)
        else:
            missing.append(p)
            out["reasons"].append(f"Prerequisite {p} " + ("failed (F/FA) and not yet cleared." if p in failed
                                                           else "not completed."))
    for p in pending:
        out["reasons"].append(f"Prerequisite {p} is in progress this semester; eligibility depends on passing it.")
    for p in conflict:
        msg = (f"Prerequisite {p} is listed for {code} but {p} is not part of the batch {batch} curriculum "
               "(conflict in source data) - needs confirmation from the Program Chair/Faculty Advisor.")
        out["conflicts"].append(msg)
        out["reasons"].append(msg)
    for f in o.flags:
        if f.endswith("_scheduled_same_or_later_semester"):
            out["conflicts"].append(
                f"Source data conflict: prerequisite {f.split('_')[1]} is scheduled in the same (or a later) "
                f"semester as {code} in the batch {batch} curriculum.")
        if f in ("title_ambiguous_in_source", "prerequisite_tba", "course_code_tba", "credits_tbd",
                 "new_course_incomplete"):
            out["conflicts"].append(f"Source data flag: {f}")
    if o.kind == "minor":
        if student.get("minor") != o.minor:
            out["reasons"].append(f"{code} belongs to the {o.minor} minor; the student's minor is "
                                  f"{student.get('minor') or 'not declared'}. Minor courses need pre-registration "
                                  "(Clause 2.13).")
        out["evidence"].append(REGULATIONS["pre_registration_minor"]["source"])
    if o.semester and target_semester and o.semester != target_semester:
        out["reasons"].append(f"Timing note (not a prerequisite issue): the batch {batch} curriculum schedules "
                              f"{code} in semester {o.semester}; whether it is offered in semester "
                              f"{target_semester} is not stated in the documents.")
    holds = registration_holds(student)
    prog = progression_status(student, target)
    if holds["has_hold"]:
        out["reasons"].append("There is a registration hold on the student record (Clause 2.10). "
                              "Details are restricted; contact the Office of the Registrar.")
        out["evidence"] += holds["evidence"]
    if prog["meets_progression"] is False:
        out["reasons"].append(f"CGPA {prog['cgpa']} is below the {prog['min_cgpa_required']:.2f} needed to "
                              f"register for semester {target} (Clause 12.1).")
        out["evidence"] += prog["evidence"]
    if missing or holds["has_hold"] or prog["meets_progression"] is False:
        out["decision"] = "NOT_ELIGIBLE"
    elif conflict or out["conflicts"]:
        out["decision"] = "NEEDS_REVIEW"
    elif pending:
        out["decision"] = "CONDITIONAL"
    else:
        out["decision"] = "ELIGIBLE"
        if not o.prereqs:
            out["reasons"].append(f"{code} has no prerequisites in the batch {batch} curriculum.")
    return out


def graduation_check(student: dict, cat: Catalogue | None = None) -> dict:
    cat = cat or catalogue()
    cs = credit_summary(student, cat)
    cg = compute_cgpa(student)["cgpa"]
    r = student.get("restricted", {}) or {}
    g = REGULATIONS["graduation"]
    short = [b for b in cs["baskets"] if b["remaining"] > 0]
    checks = {
        "credits_met": bool(cs["baskets"]) and not short,
        "cgpa_met": cg is not None and cg >= g["min_cgpa"],
        "dues_clear": not float(r.get("fee_dues_inr") or 0) > 0,
        "no_disciplinary_pending": not r.get("disciplinary_action_pending"),
    }
    return {"eligible": all(checks.values()), "checks": checks, "cgpa": cg,
            "distinction": cg is not None and cg >= g["distinction_min_cgpa"],
            "baskets_short": [{"basket": b["basket"], "remaining": b["remaining"]} for b in short],
            "evidence": [g["source"], g["distinction_source"], "cleaned/basket_requirements.csv"]}


def semester_courses(batch: int, semester: int, cat: Catalogue | None = None) -> dict:
    cat = cat or catalogue()
    if batch not in cat.batches:
        return {"batch": batch, "semester": semester, "courses": [],
                "warning": f"No curriculum data for batch {batch}."}
    rows = cat.programme_offerings(batch, semester)
    return {"batch": batch, "semester": semester,
            "courses": [{"course_code": o.code, "course_title": o.title, "credits": o.credits,
                         "basket": o.basket, "prerequisites": o.prereqs,
                         "alternatives": o.alternatives, "placeholder": o.placeholder,
                         "flags": o.flags} for o in rows],
            "total_scheduled_credits": sum(o.credits or 0 for o in {o.slot_id: o for o in rows}.values()),
            "evidence": [f"cleaned/courses.csv (batch {batch}, semester {semester})"]}


def course_info(code: str, batch: int | None = None, cat: Catalogue | None = None) -> dict:
    cat = cat or catalogue()
    rows = cat.find(code, batch)
    if not rows:
        return {"course_code": code.upper(), "found": False,
                "batches_with_course": sorted({o.batch for o in cat.find(code)}),
                "evidence": ["cleaned/courses.csv", "cleaned/minor_courses.csv"]}
    return {"course_code": code.upper(), "found": True,
            "rows": [o.to_dict() for o in rows], "evidence": [o.source for o in rows]}


def prerequisite_chain(code: str, batch: int, cat: Catalogue | None = None, _seen=None) -> dict:
    """Recursive prerequisite tree, used for the chart."""
    cat = cat or catalogue()
    _seen = _seen or set()
    rows = cat.find(code, batch)
    node = {"code": code, "title": rows[0].title if rows else None,
            "semester": rows[0].semester if rows else None,
            "in_curriculum": bool(rows), "children": []}
    if rows and code not in _seen:
        _seen.add(code)
        for p in rows[0].prereqs:
            node["children"].append(prerequisite_chain(p, batch, cat, _seen))
    return node


def sanitize_for_model(value):
    """NaN -> None so json.dumps output is valid."""
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: sanitize_for_model(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_for_model(v) for v in value]
    return value
