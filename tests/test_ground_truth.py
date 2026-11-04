"""The expected decisions in eval/test_cases.json must match the deterministic tools."""
import json
from pathlib import Path
import academic_tools as T

ROOT = Path(__file__).resolve().parents[1]


def test_expected_decisions_match_tools(students):
    cases = json.loads((ROOT / "eval" / "test_cases.json").read_text())["cases"]
    checked = 0
    for c in cases:
        dec = c["expect"]["decision"]
        if not dec or not c["student_id"]:
            continue
        s = students[c["student_id"]]
        code = T.CODE_RE.findall(c["question"])[0]
        target = 5 if "semester 5" in c["question"] else None
        assert T.check_eligibility(s, code, target)["decision"] == dec, c["id"]
        checked += 1
    assert checked >= 9


def test_numeric_ground_truth(students):
    assert students["STU_022"]["derived"]["cgpa"] < 5.0
    assert students["STU_026"]["derived"]["cgpa"] >= 8.5
    assert students["STU_009"]["derived"]["cgpa"] < 4.0
    assert students["STU_016"]["derived"]["credits_earned"] == 99
    assert T.REGULATIONS["grade_points"]["scale"]["B+"] == 7
    g = T.graduation_check(students["STU_041"])
    assert not g["eligible"] and not g["checks"]["credits_met"]
    assert T.registration_holds(students["STU_004"])["has_hold"]
