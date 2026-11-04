"""Evaluate every version of the advisor on the same predefined test set.

Versions (Phase 5 progression + Phase 9):
  basic        plain LLM, one-line system prompt, no documents, no student data
  prompting    structured prompt (prompt version B: role, constraints, delimiters,
               output rules, follow-up questioning) but no retrieval
  rag          Assignment 1 RAG advisor (Handbook + SOP + curriculum), no student data
  rag_student  RAG + structured (minimised) student profile  [Assignment 1 final]
  agentic      Assignment 2 agentic pipeline with deterministic tools + verifier

Usage (free tier friendly; results are cached so you can resume):
  python eval/run_eval.py --modes basic,prompting,rag,rag_student,agentic
  python eval/run_eval.py --modes agentic --limit 5          # quick smoke run
  python eval/run_eval.py --report-only                       # rebuild summary
  python eval/run_eval.py --stub --modes basic,agentic        # offline, fake LLM

Outputs: eval/results/raw_<mode>.jsonl, eval/results/summary.md, summary.csv
Scoring rules are documented in docs/evaluation_methodology.md.
"""

from __future__ import annotations

import argparse
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
RESULTS = Path(os.getenv("EVAL_RESULTS_DIR", str(ROOT / "eval" / "results")))
MODES = ["basic", "prompting", "rag", "rag_student", "agentic"]

DECISION_PATTERNS = [  # for free-text answers (non-agentic modes); first match wins
    ("NO_DATA_FOR_BATCH", r"no (curriculum )?(data|information|records?)[^.]{0,40}batch|batch 2021[^.]{0,80}(not|no)"),
    ("NOT_IN_CURRICULUM", r"not (in|part of|included in|listed in|offered in) (the |your )?(batch \d{4} |\d{4} )?(curriculum|programme|program|catalogue)"),
    ("CURRENTLY_REGISTERED", r"(already|currently) (registered|enrolled|taking)"),
    ("NOT_ELIGIBLE", r"not (currently |yet )?eligible|ineligible|cannot (take|register)|can't (take|register)|not (yet )?(able|allowed|permitted) to (take|register)"),
    ("CONDITIONAL", r"conditional(ly)? eligible|provided (that )?you pass|depends on (you )?passing|if you pass"),
    ("NEEDS_REVIEW", r"needs? review|conflict|inconsisten"),
    ("ELIGIBLE", r"(?<!whether )(?<!if )\beligible\b|you can (take|register)|you may (take|register)|meet (all )?the prerequisites"),
]


# ---------------------------------------------------------------- systems
class Systems:
    def __init__(self, stub=False, model=None):
        self.model = model
        self.stub = stub
        self.students = {s["student_id"]: s for s in json.loads((ROOT / "synthetic_students.json").read_text())}
        self._rag = None
        self._agentic = None
        self.prompt_b = (ROOT / "academic_advisor_prompt_version_b.txt").read_text(encoding="utf-8")

    @property
    def rag(self):
        if self._rag is None:
            from advisor import AcademicAdvisor
            self._rag = AcademicAdvisor()
        return self._rag

    @property
    def agentic(self):
        if self._agentic is None:
            from agents import AgenticAdvisor
            self._agentic = AgenticAdvisor(vectorstore=None if self.stub else self.rag.vectorstore)
        return self._agentic

    def run(self, mode, case):
        from llm import call_llm
        import security as SEC
        q, sid, batch = case["question"], case["student_id"], case["batch"]
        student = self.students.get(sid) if sid else None
        out = {"answer": "", "evidence_sources": [], "decision": None, "usage": None}
        if mode == "basic":
            out["answer"], out["usage"] = call_llm("You are a helpful university academic advisor.", q, self.model)
        elif mode == "prompting":
            system = self.prompt_b.replace("{context}", "(No university documents are available in this configuration.)") \
                .replace("{student_profile}", "No student profile is available.")
            out["answer"], out["usage"] = call_llm(system, q, self.model)
        elif mode in ("rag", "rag_student"):
            r = self.rag.answer_question(q, current_student_id=sid if mode == "rag_student" else None,
                                         model=self.model, batch=batch, allow_text_id=False)
            out["answer"], out["usage"] = r["answer"], r["usage"]
        elif mode == "agentic":
            r = self.agentic.answer(q, student=student, batch=batch)
            out.update(answer=r["answer"], usage=r["usage"], status=r["status"], human_review=r["human_review"],
                       evidence_sources=[e["source"] for e in r["evidence"]])
            # decision label as the verifier enforces it
            m = re.search(r"Decision:\s*\**\s*([A-Z_ ]+)", r["answer"])
            out["decision"] = m.group(1).strip().replace(" ", "_") if m else None
        out["answer"], _ = SEC.filter_output(out["answer"], sid, student)
        return out


# ---------------------------------------------------------------- scoring
def contains(text, needle):
    t = text.lower()
    if needle.startswith("re:"):
        return re.search(needle[3:], t, re.I) is not None
    return needle.lower() in t


def text_decision(answer):
    a = answer.lower()
    for label, pat in DECISION_PATTERNS:
        if re.search(pat, a):
            return label
    return None


def score(case, result, markers, known_codes):
    exp = case["expect"]
    ans = result.get("answer") or ""
    a = ans.lower()
    checks = {}
    groups = exp["must_include"]
    hits = [any(contains(ans, n) for n in g) for g in groups]
    checks["content"] = all(hits) if groups else True
    bad = [n for n in exp["must_not"] if contains(ans, n)]
    unknown_codes = sorted({c for c in re.findall(r"\b[A-Z]{4}\d{3}\b", ans) if c not in known_codes})
    insufficient = any(m in a for m in markers["insufficient_markers"])
    conflict = any(m in a for m in markers["conflict_markers"])
    asks = "?" in ans
    beh = exp["behavior"]
    if beh == "say_insufficient":
        checks["behavior"] = insufficient
    elif beh == "flag_conflict":
        checks["behavior"] = conflict
    elif beh in ("ask_follow_up", "needs_login"):
        checks["behavior"] = asks or "log in" in a or "login" in a
    elif beh == "refuse":
        checks["behavior"] = len(ans) < 600 and checks["content"]
    else:
        checks["behavior"] = True
    decision_ok = None
    if exp.get("decision"):
        got = result.get("decision") or text_decision(ans)
        # NEEDS_REVIEW is satisfied by explicitly flagging the conflict
        decision_ok = got == exp["decision"] or (exp["decision"] == "NEEDS_REVIEW" and conflict) or \
            (exp["decision"] == "NO_DATA_FOR_BATCH" and insufficient and "2021" in a)
        checks["decision"] = decision_ok
    src_groups = exp["sources"]
    haystack = ans + " " + " ".join(result.get("evidence_sources") or [])
    checks["sources"] = all(any(contains(haystack, n) for n in g) for g in src_groups) if src_groups else None
    hallucinated = bool(bad) or bool(unknown_codes)
    passed = [v for k, v in checks.items() if v is not None]
    if hallucinated:
        label = "unsupported/hallucinated"
    elif all(passed):
        label = "correct"
    elif sum(passed) >= len(passed) / 2 and (decision_ok is not False):
        label = "partially correct"
    else:
        label = "incorrect"
    # an incorrect recommendation = told the student they can do something they cannot (or vice versa)
    wrong_rec = decision_ok is False and exp["decision"] in ("NOT_ELIGIBLE", "NO_DATA_FOR_BATCH", "NOT_IN_CURRICULUM",
                                                               "NEEDS_REVIEW", "ELIGIBLE", "CONDITIONAL")
    if exp["must_not"] and bad and case["category"] in ("progress", "graduation", "eligibility", "missing_info"):
        wrong_rec = True
    return {"label": label, "checks": checks, "must_not_hits": bad, "unknown_codes": unknown_codes,
            "acknowledged_missing": insufficient, "flagged_conflict": conflict, "incorrect_recommendation": wrong_rec}


# ---------------------------------------------------------------- report
def summarize(cases, markers):
    import academic_tools as T
    # codes that exist anywhere in the source data (offered courses AND listed prerequisites)
    known = {o.code for o in T.catalogue().offerings if o.code} | \
        {p for o in T.catalogue().offerings for p in o.prereqs}
    rows, per_case = [], {}
    for mode in MODES:
        path = RESULTS / f"raw_{mode}.jsonl"
        if not path.exists():
            continue
        res = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            res[r["id"]] = r
        scored = []
        for c in cases:
            if c["id"] not in res or res[c["id"]].get("error"):
                continue
            s = score(c, res[c["id"]], markers, known)
            s["latency_s"] = res[c["id"]]["latency_s"]
            s["tokens"] = (res[c["id"]].get("usage") or {}).get("total_tokens")
            scored.append((c, s))
            per_case.setdefault(c["id"], {})[mode] = s["label"]
        if not scored:
            continue
        n = len(scored)
        pct = lambda k: 100 * sum(1 for c, s in scored if s["label"] == k) / n
        def sub(filter_fn, ok_fn):
            sel = [(c, s) for c, s in scored if filter_fn(c)]
            return (100 * sum(1 for c, s in sel if ok_fn(c, s)) / len(sel), len(sel)) if sel else (None, 0)
        elig = sub(lambda c: c["expect"]["decision"], lambda c, s: s["checks"].get("decision"))
        miss = sub(lambda c: c["expect"]["behavior"] == "say_insufficient", lambda c, s: s["checks"]["behavior"])
        conf = sub(lambda c: c["expect"]["behavior"] == "flag_conflict", lambda c, s: s["checks"]["behavior"])
        srcs = sub(lambda c: c["expect"]["sources"], lambda c, s: s["checks"]["sources"])
        lat = sorted(s["latency_s"] for c, s in scored)
        toks = [s["tokens"] for c, s in scored if s["tokens"]]
        rows.append({
            "mode": mode, "cases": n,
            "accuracy_correct_%": round(pct("correct"), 1),
            "partially_correct_%": round(pct("partially correct"), 1),
            "hallucination_%": round(pct("unsupported/hallucinated"), 1),
            "incorrect_%": round(pct("incorrect"), 1),
            "eligibility_decisions_correct_%": None if elig[0] is None else round(elig[0], 1),
            "source_correct_%": None if srcs[0] is None else round(srcs[0], 1),
            "missing_info_handled_%": None if miss[0] is None else round(miss[0], 1),
            "conflicts_flagged_%": None if conf[0] is None else round(conf[0], 1),
            "incorrect_recommendations": sum(1 for c, s in scored if s["incorrect_recommendation"]),
            "median_latency_s": round(lat[len(lat) // 2], 2),
            "avg_latency_s": round(sum(lat) / n, 2),
            "avg_tokens": round(sum(toks) / len(toks)) if toks else None,
        })
    if not rows:
        print("No results yet.")
        return
    with open(RESULTS / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    keys = list(rows[0])
    md = ["# Evaluation summary", "", f"Test set: {len(cases)} cases (eval/test_cases.json). "
          "Latency excludes free-tier throttling waits.", "",
          "| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    md += ["| " + " | ".join("" if r[k] is None else str(r[k]) for k in keys) + " |" for r in rows]
    md += ["", "## Per-case labels", "", "| case | category | " + " | ".join(r["mode"] for r in rows) + " |",
           "|" + "---|" * (2 + len(rows))]
    for c in cases:
        if c["id"] in per_case:
            md.append(f"| {c['id']} | {c['category']} | " + " | ".join(per_case[c['id']].get(r['mode'], '') for r in rows) + " |")
    (RESULTS / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:6 + len(rows)]))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="", help="comma-separated case ids")
    ap.add_argument("--model", default=None)
    ap.add_argument("--sleep", type=float, default=float(os.getenv("EVAL_SLEEP_SECONDS", "4")))
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--stub", action="store_true", help="offline run with a fake LLM (tests the harness only)")
    ap.add_argument("--fresh", action="store_true", help="ignore cached results")
    args = ap.parse_args()
    data = json.loads((ROOT / "eval" / "test_cases.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.report_only:
        summarize(cases, data)
        return
    if args.stub:
        sys.path.insert(0, str(ROOT / "tests"))
        import llm
        from conftest import fake_backend
        llm.set_backend(fake_backend)
    import llm
    systems = Systems(stub=args.stub, model=args.model)
    selected = [c for c in cases if not args.only or c["id"] in args.only.split(",")]
    if args.limit:
        selected = selected[: args.limit]
    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        path = RESULTS / f"raw_{mode}.jsonl"
        if args.fresh and path.exists():
            path.unlink()
        done = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if not r.get("error"):
                    done.add(r["id"])
        for c in selected:
            if c["id"] in done:
                continue
            for attempt in range(3):
                waited0 = llm.THROTTLE_WAITED[0]
                t0 = time.perf_counter()
                try:
                    r = systems.run(mode, c)
                    err = None
                except Exception as e:  # keep going; record the error
                    r, err = {"answer": ""}, f"{type(e).__name__}: {str(e)[:300]}"
                lat = time.perf_counter() - t0 - (llm.THROTTLE_WAITED[0] - waited0)
                if err and ("429" in err or "quota" in err.lower() or "RateLimit" in err) and attempt < 2:
                    print(f"  rate limited on {c['id']}; sleeping 60s")
                    time.sleep(60)
                    continue
                break
            rec = {"id": c["id"], "mode": mode, "latency_s": round(lat, 3), "error": err, **r}
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, default=str) + "\n")
            print(f"[{mode}] {c['id']} {'ERROR ' + err if err else 'ok'} ({lat:.1f}s)")
            time.sleep(args.sleep if not args.stub else 0)
    summarize(cases, data)


if __name__ == "__main__":
    main()
