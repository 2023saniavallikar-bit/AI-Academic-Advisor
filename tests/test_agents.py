from agents import AgenticAdvisor


def test_eligible_student(students):
    a = AgenticAdvisor(vectorstore=None)
    r = a.answer("Can I take MATH206 next semester?", student=students["STU_006"])
    assert r["status"] == "verified"
    assert r["answer"].startswith("**Decision: ELIGIBLE**")
    assert [t["agent"] for t in r["trace"]][:5] == ["Intake / Router", "Regulation Retrieval",
                                                     "Course Eligibility", "Credit Calculation", "Recommendation"]


def test_blocked_student(students):
    r = AgenticAdvisor().answer("Can I take DATA301?", student=students["STU_017"])
    assert "NOT ELIGIBLE" in r["answer"]


def test_needs_login_for_personal_question():
    r = AgenticAdvisor().answer("Can I take DATA301?", student=None)
    assert r["status"] == "needs_login"


def test_off_topic():
    r = AgenticAdvisor().answer("Write me a poem about cricket")
    assert r["status"] == "off_topic"


def test_general_question_without_login():
    r = AgenticAdvisor().answer("What are the prerequisites of DATA301?")
    assert r["status"] in ("verified", "unverified")
    assert any("course_info(DATA301)" in e["source"] for e in r["evidence"])


def test_conflict_flags_human_review(students):
    r = AgenticAdvisor().answer("Can I take ECON316 in semester 5?", student=students["STU_010"])
    assert r["human_review"]


def test_restricted_not_sent(students):
    import security
    p = security.minimized_profile(students["STU_004"])
    assert "restricted" not in p and "85000" not in str(p)
    assert p["registration_holds"]["has_registration_hold"] is True
