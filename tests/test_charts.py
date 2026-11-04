import re
import multimodal as MM
import academic_tools as T


def test_prerequisite_chart_only_contains_real_codes(students):
    known = {o.code for o in T.catalogue().offerings if o.code}
    for code, batch in [("DATA302", 2023), ("COMP302", 2024), ("DATA403", 2025), ("ECON316", 2025)]:
        svg = MM.prerequisite_svg(code, batch, students["STU_016"])
        codes = set(re.findall(r">([A-Z]{4}\d{3})<", svg))
        assert code in codes
        for unknown in codes - known:  # only prerequisites the source lists but no curriculum contains
            assert "not in this batch" in svg


def test_chart_marks_failed_and_missing():
    import json, pathlib
    s = {x["student_id"]: x for x in json.loads(pathlib.Path("synthetic_students.json").read_text())}
    assert "failed - not cleared" in MM.prerequisite_svg("DATA301", 2024, s["STU_017"])
    assert "not in this batch" in MM.prerequisite_svg("DATA202", 2023)


def test_progress_chart(students):
    svg = MM.progress_svg(students["STU_016"])
    assert "99 of 180" in svg
    assert "No curriculum data" in MM.progress_svg(students["STU_043"])
