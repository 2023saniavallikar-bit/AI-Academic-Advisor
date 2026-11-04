"""Phase 8 evaluation of the non-text modalities.

1. Image in (vision): every document in data/synthetic_records/manifest.json is
   sent to the vision model; extracted rows are compared with the synthetic
   student record (ground truth). Metrics: course-code recall/precision, grade
   accuracy, safeguards triggered on the problem documents, latency.
       python eval/run_multimodal.py vision            (live Gemini, ~17 calls)

2. Voice in (browser speech-to-text): read the 15 prompts in
   eval/voice_prompts.csv into the mic (Chrome, en-IN), paste what appeared in
   the text box into the 'hypothesis' column, then:
       python eval/run_multimodal.py voice
   Metrics: word error rate (WER) overall and on course codes.

3. Visual out (charts) is deterministic: checked by tests/test_charts.py.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
RESULTS = ROOT / "eval" / "results"
RECORDS = ROOT / "data" / "synthetic_records"
ONLY = set(a for a in sys.argv[2:])  # optional file names to (re)run

VOICE_PROMPTS = [
    "Can I take machine learning DATA301 next semester",
    "What are the prerequisites for COMP203",
    "What is the minimum attendance required for the end term exam",
    "How many credits can I register for in the summer term",
    "Am I eligible for deep learning DATA302",
    "What happens if I get an FA grade",
    "When can I take a make up examination",
    "What CGPA do I need to graduate with distinction",
    "Can I change my minor again",
    "How do I get a bonafide certificate for my internship",
    "What is the maximum duration to finish my degree",
    "Which courses are in semester five for the 2024 batch",
    "Can I register late because I was in hospital",
    "How many credits have I earned so far",
    "Can I drop a course after three weeks",
]


def wer(ref: str, hyp: str) -> float:
    r, h = ref.lower().split(), re.sub(r"[^\w\s]", " ", hyp.lower()).split()
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    return d[-1][-1] / max(1, len(r))


def voice():
    path = ROOT / "eval" / "voice_prompts.csv"
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "reference", "speaker_note", "hypothesis"])
            for i, p in enumerate(VOICE_PROMPTS, 1):
                w.writerow([f"V{i:02d}", p, "", ""])
        print(f"Created {path}. Fill the 'hypothesis' column, then run again.")
        return
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8")) if r["hypothesis"].strip()]
    if not rows:
        print("No hypotheses filled in yet.")
        return
    total = sum(wer(r["reference"], r["hypothesis"]) for r in rows) / len(rows)
    code_rows = [r for r in rows if re.search(r"[A-Z]{4}\d{3}", r["reference"])]
    code_ok = sum(1 for r in code_rows if re.findall(r"[A-Z]{4}\d{3}", r["reference"])[0].lower()
                  in re.sub(r"\s", "", r["hypothesis"].lower())) if code_rows else 0
    md = ["# Voice input (browser speech-to-text) results", "",
          f"Prompts: {len(rows)} · mean WER {total:.1%} · course codes recognised exactly: {code_ok}/{len(code_rows)}", "",
          "| id | reference | hypothesis | WER |", "|---|---|---|---|"]
    md += [f"| {r['id']} | {r['reference']} | {r['hypothesis']} | {wer(r['reference'], r['hypothesis']):.0%} |" for r in rows]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "voice_results.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:3]))


def vision():
    import academic_tools as T
    import multimodal as MM
    students = {s["student_id"]: s for s in json.loads((ROOT / "synthetic_students.json").read_text())}
    manifest = json.loads((RECORDS / "manifest.json").read_text())
    rows = []
    for item in manifest:
        img = next(f for f in item["files"] if f.endswith((".png", ".jpg")))
        mime = "image/jpeg" if img.endswith(".jpg") else "image/png"
        owner = item["expected"].get("upload_as", item["student_id"])
        student = students[owner]
        if ONLY and img not in ONLY:
            continue
        retries = 0
        for attempt in range(3):
            t0 = time.perf_counter()
            try:
                res = MM.extract_document((RECORDS / img).read_bytes(), mime, student)
                err = None
            except Exception as e:
                res, err = {"courses": [], "security_events": [], "discrepancies": []}, str(e)[:200]
            lat = time.perf_counter() - t0
            # transient provider errors (503) or an empty/unparseable reply: retry, and record it
            if (err and ("503" in err or "429" in err)) or (not err and not res["courses"]):
                retries += 1
                time.sleep(20)
                continue
            break
        truth_student = students[item["student_id"]]
        if img.startswith(("registration_", "adddrop_")):
            listed = truth_student["current_courses"][:2] if img.startswith("adddrop_") else truth_student["current_courses"]
            truth = {c["course_code"]: None for c in listed if c["course_code"]}
        else:
            truth = {c["course_code"]: c["grade"] for c in truth_student["course_history"] if c["course_code"]}
            if "TAMPERED" in img:
                truth["MATH301"] = "B"  # what is printed on the tampered document
        got = {c["course_code"]: c["grade"] for c in res["courses"] if c["course_code"]}
        tp = len(set(got) & set(truth))
        grade_ok = sum(1 for k in set(got) & set(truth) if truth[k] is None or got[k] == truth[k])
        events = [e["type"] for e in res["security_events"]]
        exp_event = item["expected"].get("security_event")
        rows.append({"file": img, "purpose": item["purpose"], "error": err, "retries": retries, "latency_s": round(lat, 1),
                     "recall": round(tp / max(1, len(truth)), 3), "precision": round(tp / max(1, len(got)), 3),
                     "grade_accuracy": round(grade_ok / max(1, tp), 3),
                     "expected_safeguard": exp_event or item["expected"].get("discrepancy", "-"),
                     "triggered": ", ".join(events) or ("; ".join(res.get("discrepancies", []))[:80] or "-")})
        print(rows[-1])
    RESULTS.mkdir(parents=True, exist_ok=True)
    cache = RESULTS / "vision_rows.json"
    if ONLY and cache.exists():
        old_rows = {r["file"]: r for r in json.loads(cache.read_text())}
        old_rows.update({r["file"]: r for r in rows})
        rows = [old_rows[i_file] for i_file in old_rows]
    cache.write_text(json.dumps(rows, indent=2))
    for r in rows:
        r.setdefault("retries", 0)
    keys = list(rows[0])
    md = ["# Vision (transcript image) extraction results", "",
          "| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    md += ["| " + " | ".join(str(r[k]) for k in keys) + " |" for r in rows]
    ok = [r for r in rows if not r["error"]]
    if ok:
        md += ["", f"Mean recall {sum(r['recall'] for r in ok) / len(ok):.1%} · mean precision "
               f"{sum(r['precision'] for r in ok) / len(ok):.1%} · mean grade accuracy "
               f"{sum(r['grade_accuracy'] for r in ok) / len(ok):.1%} · median latency "
               f"{sorted(r['latency_s'] for r in ok)[len(ok) // 2]}s"]
    (RESULTS / "vision_results.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    {"vision": vision, "voice": voice}[sys.argv[1] if len(sys.argv) > 1 else "voice"]()
