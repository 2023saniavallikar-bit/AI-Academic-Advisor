"""Batch and semester selection: what exists, what is valid, what to retrieve.

Simple idea
-----------
* The list of batches and semesters is read from the search index itself (the
  metadata stored with each course row). Nothing is typed in by hand, so the
  dropdown can never offer a period that has no data.
* The server checks the choice again. A batch or semester that is not in the
  data is refused. It is never invented or assumed.
* When a batch (and semester) is chosen, the advisor is also handed the exact
  rows stored for that period, plus the usual similarity search limited to that
  batch, so rows of other batches do not leak into the answer.
"""

from __future__ import annotations

from collections import defaultdict
import logging
from pathlib import Path
import re

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

COURSE_FILE = "courses.csv"
BASKET_FILE = "basket_requirements.csv"
MAX_SEMESTER = 8


def source_name(metadata) -> str:
    return Path(str((metadata or {}).get("source") or "")).name


def _as_int(value):
    """1, 1.0, '1' -> 1.  Anything else (None, 'abc', True) -> None."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number == int(number) else None


# ---------------------------------------------------------------------------
# What periods exist
# ---------------------------------------------------------------------------

class PeriodCatalog:
    """Batches -> semesters that really have course rows in the index."""

    def __init__(self, semesters_by_batch=None):
        self._by_batch = {
            int(b): sorted(set(sems))
            for b, sems in (semesters_by_batch or {}).items()
            if sems
        }

    @classmethod
    def from_metadatas(cls, metadatas):
        found = defaultdict(set)
        for meta in metadatas:
            if source_name(meta) != COURSE_FILE:
                continue
            batch, semester = _as_int(meta.get("batch")), _as_int(meta.get("semester"))
            if batch is not None and semester is not None:
                found[batch].add(semester)
        return cls(found)

    @property
    def batches(self) -> list[int]:
        return sorted(self._by_batch)

    def semesters(self, batch: int) -> list[int]:
        return list(self._by_batch.get(batch, []))

    def to_json(self) -> dict:
        return {
            "batches": [
                {"batch": b, "semesters": self.semesters(b)} for b in self.batches
            ]
        }


def load_catalog(vectorstore) -> PeriodCatalog:
    """Read the periods from the index. An unreadable index gives an empty
    catalog (the selectors then simply offer nothing) instead of a crash."""
    try:
        data = vectorstore.get(include=["metadatas"])
        return PeriodCatalog.from_metadatas(data.get("metadatas") or [])
    except Exception:
        logger.exception("Could not read batches and semesters from the index")
        return PeriodCatalog()


# ---------------------------------------------------------------------------
# Checking what the browser sent
# ---------------------------------------------------------------------------

_NOT_SET = {"", "none", "null", "not specified", "any", "all"}


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip().lower() in _NOT_SET)


def parse_period(raw_batch, raw_semester, catalog: PeriodCatalog):
    """Return (batch, semester); either can be None ("not specified").

    Raises ValueError with a message that is safe to show the student.
    """
    batch = semester = None

    if not _blank(raw_batch):
        batch = _as_int(raw_batch if not isinstance(raw_batch, str) else raw_batch.strip())
        if batch is None:
            raise ValueError("Batch must be a year such as 2022.")
        if batch not in catalog.batches:
            raise ValueError(f"There is no curriculum data for batch {batch}.")

    if not _blank(raw_semester):
        semester = _as_int(raw_semester if not isinstance(raw_semester, str) else raw_semester.strip())
        if semester is None or not 1 <= semester <= MAX_SEMESTER:
            raise ValueError(f"Semester must be a number from 1 to {MAX_SEMESTER}.")
        if batch is None:
            raise ValueError("Please choose a batch together with the semester.")
        if semester not in catalog.semesters(batch):
            raise ValueError(
                f"There is no curriculum data for batch {batch}, semester {semester}."
            )

    return batch, semester


# ---------------------------------------------------------------------------
# Retrieval for a chosen period
# ---------------------------------------------------------------------------

def _normal_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def dedupe_documents(documents, limit=None):
    """Drop repeated passages (the shipped index can hold the same chunk up to
    4 times). Keeps the first copy and the original order."""
    seen, unique = set(), []
    for doc in documents:
        meta = doc.metadata or {}
        key = (_normal_text(doc.page_content), source_name(meta), meta.get("page"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(doc)
        if limit is not None and len(unique) >= limit:
            break
    return unique


def _to_documents(raw: dict) -> list[Document]:
    docs = raw.get("documents") or []
    metas = raw.get("metadatas") or []
    ordered = [
        Document(page_content=text or "", metadata=meta or {})
        for text, meta in zip(docs, metas)
    ]
    # Same order every time: by sheet row when known.
    return sorted(ordered, key=lambda d: (_as_int(d.metadata.get("source_row")) or 0))


def exact_period_rows(vectorstore, batch: int, semester: int):
    """Every course row stored for this batch+semester, and every basket
    (credit requirement) row for the batch. Returns (courses, baskets)."""
    courses_raw = vectorstore.get(
        where={"$and": [{"batch": {"$eq": batch}}, {"semester": {"$eq": semester}}]},
        include=["documents", "metadatas"],
    )
    baskets_raw = vectorstore.get(
        where={"batch": {"$eq": batch}}, include=["documents", "metadatas"]
    )
    # De-duplicated here, so the counts we report are the passages really sent.
    courses = dedupe_documents(
        d for d in _to_documents(courses_raw) if source_name(d.metadata) == COURSE_FILE
    )
    baskets = dedupe_documents(
        d for d in _to_documents(baskets_raw) if source_name(d.metadata) == BASKET_FILE
    )
    return courses, baskets


def is_other_batch(doc, batch: int) -> bool:
    """True for a course/minor/basket row of a different batch. PDF passages
    carry no batch, so they are never 'other batch'."""
    stored = _as_int((doc.metadata or {}).get("batch"))
    return stored is not None and stored != batch


def select_documents(vectorstore, query: str, k: int, batch=None, semester=None):
    """Passages for the model, plus a small report about what was found.

    Returns (documents, info). info keys: course_rows, basket_rows.
    No batch chosen: plain similarity search, de-duplicated (as before).
    Batch chosen: exact rows (when a semester is chosen) + search limited to
    the batch + search limited to the PDFs. Rows of other batches never enter.
    """
    info = {"course_rows": 0, "basket_rows": 0}
    wide = k * 4  # look at more candidates so de-duplication still leaves k

    if batch is None:
        return dedupe_documents(vectorstore.similarity_search(query, k=wide), k), info

    exact: list[Document] = []
    if semester is not None:
        courses, baskets = exact_period_rows(vectorstore, batch, semester)
        info["course_rows"], info["basket_rows"] = len(courses), len(baskets)
        exact = courses + baskets

    in_batch = vectorstore.similarity_search(query, k=wide, filter={"batch": {"$eq": batch}})
    # Handbook / SOP passages carry a PDF page number and no batch. Searching
    # them on their own means a chosen batch never pushes the rules out.
    pdf_passages = vectorstore.similarity_search(query, k=wide, filter={"page": {"$gte": 0}})
    documents = (
        exact
        + dedupe_documents(in_batch, k)
        + dedupe_documents(pdf_passages, k)
    )
    return dedupe_documents(documents), info


# ---------------------------------------------------------------------------
# The note the model reads about the chosen period
# ---------------------------------------------------------------------------

def describe_selection(batch, semester, info, profile_batch=None, catalog=None) -> str:
    """Plain-English block for the prompt. States only what is known."""
    lines = []
    if batch is None:
        lines.append(
            "No batch or semester was selected. Do not assume one. If the "
            "answer depends on the batch or semester and the STUDENT PROFILE "
            "does not give it, ask which one the student means."
        )
    elif semester is None:
        lines.append(
            f"The student selected batch {batch} (entry year). No semester was "
            f"selected. Use only context rows marked batch {batch} for "
            "curriculum questions; do not use another batch's requirements."
        )
    else:
        lines.append(
            f"The student selected batch {batch}, semester {semester}. The "
            f"CONTEXT lists every course row found for that period "
            f"({info.get('course_rows', 0)} course rows, "
            f"{info.get('basket_rows', 0)} credit-requirement rows for the batch). "
            "If a course is not among them, say it is not listed for that "
            "period. Do not guess."
        )
        if not info.get("course_rows"):
            lines.append(
                f"No course rows were found for batch {batch}, semester "
                f"{semester}. Say that the data is not available."
            )

    profile_batch = _as_int(profile_batch)
    if profile_batch is not None:
        if catalog is not None and profile_batch not in catalog.batches:
            lines.append(
                f"The student profile says batch {profile_batch}, but this "
                "knowledge base has no curriculum data for that batch. Say so "
                "if the question needs that batch's curriculum."
            )
        elif batch is not None and profile_batch != batch:
            lines.append(
                f"The student profile says batch {profile_batch}, which differs "
                f"from the selected batch {batch}. Answer for the selected "
                f"batch {batch} and mention the difference briefly."
            )
    return "\n".join(lines)
