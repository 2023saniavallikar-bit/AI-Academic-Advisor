"""Check that every synthetic profile is consistent with the real curriculum.

Run: python scripts/validate_students.py
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from academic_tools import EARNED_GRADES, catalogue, compute_cgpa  # noqa: E402

PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "phone": re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)"),
    "aadhaar": re.compile(r"(?<!\d)\d{4}\s\d{4}\s\d{4}(?!\d)"),
}


def validate(students, cat=None):
    cat = cat or catalogue()
    problems = []
    seen = set()
    for s in students:
        sid = s.get("student_id")
        if sid in seen:
            problems.append(f"{sid}: duplicate id")
        seen.add(sid)
        flags = set(s.get("data_quality_flags", []))
        batch = s.get("batch")
        if batch not in cat.batches and "batch_not_in_curriculum" not in flags:
            problems.append(f"{sid}: batch {batch} has no curriculum data and is not flagged")
        if s.get("minor") and s["minor"] not in cat.minors:
            problems.append(f"{sid}: minor {s['minor']} is not offered")
        check_batch = batch if batch in cat.batches else None
        passed_by_sem = {}
        for h in s.get("course_history", []):
            code = h.get("course_code")
            if code is None:
                if not h.get("placeholder"):
                    problems.append(f"{sid}: course without code is not marked placeholder")
                continue
            if check_batch is None:
                continue
            rows = cat.find(code, check_batch)
            if not rows:
                problems.append(f"{sid}: {code} not in batch {batch} catalogue")
                continue
            if rows[0].credits and h.get("credits") != rows[0].credits:
                problems.append(f"{sid}: {code} credits {h.get('credits')} != catalogue {rows[0].credits}")
            if h.get("grade") in EARNED_GRADES:
                passed_by_sem.setdefault(code, h["semester_taken"])
        if check_batch is not None:
            bc = cat.batch_codes(check_batch)
            for h in s.get("course_history", []):
                code = h.get("course_code")
                if not code or h.get("attempt", 1) != 1:
                    continue
                for p in (cat.find(code, check_batch) or [None])[0].prereqs if cat.find(code, check_batch) else []:
                    if p in bc and not (p in passed_by_sem and passed_by_sem[p] <= h["semester_taken"]):
                        problems.append(f"{sid}: took {code} in sem {h['semester_taken']} without passing {p} first")
        stored = (s.get("derived") or {}).get("cgpa")
        if stored != compute_cgpa(s)["cgpa"]:
            problems.append(f"{sid}: stored CGPA {stored} != recomputed")
        text = json.dumps({k: v for k, v in s.items() if k != "restricted"})
        for name, pat in PII_PATTERNS.items():
            if pat.search(text):
                problems.append(f"{sid}: looks like it contains a real {name}")
        if not s.get("synthetic"):
            problems.append(f"{sid}: missing synthetic=true marker")
    return problems


if __name__ == "__main__":
    data = json.loads((ROOT / "synthetic_students.json").read_text(encoding="utf-8"))
    probs = validate(data)
    print("\n".join(probs) if probs else f"OK: {len(data)} profiles valid")
    sys.exit(1 if probs else 0)
