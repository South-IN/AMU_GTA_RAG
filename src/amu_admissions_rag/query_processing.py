"""Conservative course-alias expansion and lightweight query intent routing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from amu_admissions_rag.models import (
    CourseAliasMatch,
    QueryAnalysis,
    QueryIntent,
)


@dataclass(frozen=True)
class CourseAlias:
    abbreviation: str
    full_name: str

    @property
    def pattern(self) -> re.Pattern[str]:
        letters = [re.escape(character) for character in self.abbreviation]
        separated = r"[\s._-]*".join(letters)
        return re.compile(rf"(?<!\w){separated}(?!\w)", re.IGNORECASE)


COURSE_ALIASES: tuple[CourseAlias, ...] = (
    CourseAlias("BALLB", "Bachelor of Arts and Bachelor of Laws"),
    CourseAlias("BLIS", "Bachelor of Library and Information Science"),
    CourseAlias("MLIS", "Master of Library and Information Science"),
    CourseAlias("BTECH", "Bachelor of Technology"),
    CourseAlias("MTECH", "Master of Technology"),
    CourseAlias("BARCH", "Bachelor of Architecture"),
    CourseAlias("MBBS", "Bachelor of Medicine and Bachelor of Surgery"),
    CourseAlias("BUMS", "Kamil-e-Tib-o-Jarahat (Bachelor of Unani Medicine and Surgery)"),
    CourseAlias("BVOC", "Bachelor of Vocation"),
    CourseAlias("BPHARM", "Bachelor of Pharmacy"),
    CourseAlias("MPHARM", "Master of Pharmacy"),
    CourseAlias("SSSC", "Senior Secondary School Certificate"),
    CourseAlias("BSC", "Bachelor of Science"),
    CourseAlias("MSC", "Master of Science"),
    CourseAlias("BCOM", "Bachelor of Commerce"),
    CourseAlias("MCOM", "Master of Commerce"),
    CourseAlias("BBA", "Bachelor of Business Administration"),
    CourseAlias("MBA", "Master of Business Administration"),
    CourseAlias("BCA", "Bachelor of Computer Applications"),
    CourseAlias("MCA", "Master of Computer Science and Applications"),
    CourseAlias("BDS", "Bachelor of Dental Surgery"),
    CourseAlias("BED", "Bachelor of Education"),
    CourseAlias("MED", "Master of Education"),
    CourseAlias("LLB", "Bachelor of Laws"),
    CourseAlias("LLM", "Master of Laws"),
    CourseAlias("MSW", "Master of Social Work"),
    CourseAlias("MPH", "Master of Public Health"),
    CourseAlias("BVA", "Bachelor of Visual Arts"),
    CourseAlias("MVA", "Master of Visual Arts"),
    CourseAlias("PHD", "Doctor of Philosophy"),
    CourseAlias("BE", "Bachelor of Engineering"),
    CourseAlias("BA", "Bachelor of Arts"),
    CourseAlias("MA", "Master of Arts"),
)


INTENT_RULES: tuple[tuple[QueryIntent, re.Pattern[str], tuple[str, ...]], ...] = (
    (
        QueryIntent.ELIGIBILITY,
        re.compile(r"\b(?:eligible|eligibility|qualify|qualification|requirement)\b", re.I),
        ("qualifying_examination",),
    ),
    (
        QueryIntent.AGE_LIMIT,
        re.compile(r"\b(?:age|older|younger)\b", re.I),
        ("age_limit",),
    ),
    (
        QueryIntent.SELECTION_PROCESS,
        re.compile(r"\b(?:selection|selected|admission process)\b", re.I),
        ("selection_process",),
    ),
    (
        QueryIntent.TEST_DETAILS,
        re.compile(r"\b(?:exam pattern|test pattern|syllabus|questions?|marks?)\b", re.I),
        ("test_paper_details",),
    ),
    (
        QueryIntent.TEST_CENTRES,
        re.compile(r"\b(?:test|exam)\s+(?:centre|center|location)s?\b", re.I),
        ("test_centres",),
    ),
    (
        QueryIntent.INTAKE,
        re.compile(r"\b(?:intake|seats?|vacancies)\b", re.I),
        ("course_details",),
    ),
    (
        QueryIntent.DURATION,
        re.compile(r"\b(?:duration|semesters?|years? long)\b", re.I),
        ("course_details",),
    ),
    (
        QueryIntent.FEES,
        re.compile(r"\b(?:fee|fees|cost|charges?)\b", re.I),
        ("fee_summary",),
    ),
    (
        QueryIntent.APPLICATION_DATES,
        re.compile(r"\b(?:application|form)\s+(?:date|deadline|closing|open(?:ing)?)\b", re.I),
        ("application_summary",),
    ),
    (
        QueryIntent.TEST_SCHEDULE,
        re.compile(
            r"\b(?:test|exam)\s+(?:date|time|schedule|when)\b"
            r"|\bwhen.*(?:test|exam)\b",
            re.I,
        ),
        ("test_schedule",),
    ),
)


class QueryProcessor:
    """Expand only recognized course aliases; preserve all other query text."""

    def __init__(self, aliases: tuple[CourseAlias, ...] = COURSE_ALIASES) -> None:
        seen: set[str] = set()
        unique: list[CourseAlias] = []
        for alias in aliases:
            key = alias.abbreviation.upper()
            if key not in seen:
                seen.add(key)
                unique.append(alias)
        self.aliases = tuple(unique)

    def expand(self, query: str) -> str:
        return self.analyze(query).expanded_query

    def analyze(self, query: str) -> QueryAnalysis:
        if not query.strip():
            raise ValueError("query cannot be empty")
        matches = self._alias_matches(query)
        expanded = self._replace_matches(query, matches)
        intents: list[QueryIntent] = []
        fields: list[str] = []
        for intent, pattern, preferred_fields in INTENT_RULES:
            if pattern.search(expanded):
                intents.append(intent)
                fields.extend(preferred_fields)
        if not intents:
            intents.append(QueryIntent.GENERAL)
        return QueryAnalysis(
            original_query=query,
            expanded_query=expanded,
            aliases=matches,
            intents=intents,
            preferred_fields=list(dict.fromkeys(fields)),
        )

    def _alias_matches(self, query: str) -> list[CourseAliasMatch]:
        candidates: list[CourseAliasMatch] = []
        for alias in self.aliases:
            for match in alias.pattern.finditer(query):
                end = match.end()
                if end + 1 < len(query) and query[end] == ".":
                    end += 1
                candidates.append(
                    CourseAliasMatch(
                        abbreviation=alias.abbreviation,
                        full_name=alias.full_name,
                        matched_text=query[match.start() : end],
                        start=match.start(),
                        end=end,
                    )
                )
        candidates.sort(key=lambda item: (item.start, -(item.end - item.start)))
        accepted: list[CourseAliasMatch] = []
        occupied_until = -1
        for candidate in candidates:
            if candidate.start >= occupied_until:
                accepted.append(candidate)
                occupied_until = candidate.end
        return accepted

    @staticmethod
    def _replace_matches(
        query: str,
        matches: list[CourseAliasMatch],
    ) -> str:
        pieces: list[str] = []
        cursor = 0
        for match in matches:
            pieces.append(query[cursor : match.start])
            pieces.append(match.full_name)
            cursor = match.end
        pieces.append(query[cursor:])
        return "".join(pieces)


def course_name_expansions(course_name: str) -> list[str]:
    """Return the longest leading abbreviation expansion for a course name."""

    candidates: list[tuple[int, str]] = []
    for alias in COURSE_ALIASES:
        match = alias.pattern.match(course_name)
        if match:
            candidates.append((match.end(), alias.full_name))
    if not candidates:
        return []
    longest = max(end for end, _ in candidates)
    return list(
        dict.fromkeys(full_name for end, full_name in candidates if end == longest)
    )
