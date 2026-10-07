"""Conservative course-alias expansion and lightweight query intent routing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from amu_admissions_rag.models import (
    CourseAliasMatch,
    QueryAnalysis,
    QueryIntent,
)

SEPARATOR = r"[\s._-]*"


@dataclass(frozen=True)
class CourseAlias:
    """A course abbreviation and the spellings that expand to its full name.

    By default the letters of ``abbreviation`` match in any case, optionally
    separated by spaces, periods, underscores or hyphens (``MCA``, ``m.c.a.``,
    ``M CA``). ``spellings`` add multi-letter segment forms such as
    ``B.Lib.I.Sc.``. A ``word_like`` alias spells an ordinary word (``bed``,
    ``med``, ``ma``, ``march``), so it matches only in upper case, in the segment
    case of its spelling (``BEd``, ``M Arch``) or when a period follows the
    first segment (``b.ed``, ``M. Arch.``).
    """

    abbreviation: str
    full_name: str
    spellings: tuple[str, ...] = ()
    word_like: bool = False

    @property
    def pattern(self) -> re.Pattern[str]:
        return _alias_pattern(self.abbreviation, self.spellings, self.word_like)


@cache
def _alias_pattern(
    abbreviation: str,
    spellings: tuple[str, ...],
    word_like: bool,
) -> re.Pattern[str]:
    forms = [list(abbreviation)] + [_segments(spelling) for spelling in spellings]
    if not word_like:
        alternatives = [SEPARATOR.join(map(re.escape, form)) for form in forms]
        return re.compile(
            rf"(?<!\w)(?:{'|'.join(alternatives)})(?!\w)",
            re.IGNORECASE,
        )

    segments = forms[1] if len(forms) > 1 else forms[0]
    exact = [abbreviation.upper(), "".join(segments)]
    alternatives = [re.escape(form) for form in dict.fromkeys(exact)]
    alternatives.append(r"\s+".join(map(re.escape, segments)))
    dotted = re.escape(segments[0]) + r"[\s_-]*\.[\s._-]*"
    dotted += SEPARATOR.join(map(re.escape, segments[1:]))
    alternatives.append(f"(?i:{dotted})")
    return re.compile(rf"(?<!\w)(?:{'|'.join(alternatives)})(?!\w)")


def _segments(spelling: str) -> list[str]:
    return re.findall(r"[A-Za-z]+", spelling)


COURSE_ALIASES: tuple[CourseAlias, ...] = (
    CourseAlias("BALLB", "Bachelor of Arts and Bachelor of Laws"),
    CourseAlias(
        "BLIS",
        "Bachelor of Library and Information Science",
        spellings=("B.Lib.I.Sc.", "B.Lib."),
    ),
    CourseAlias(
        "MLIS",
        "Master of Library and Information Science",
        spellings=("M.Lib.I.Sc.", "M.Lib."),
    ),
    CourseAlias("BTECH", "Bachelor of Technology"),
    CourseAlias("MTECH", "Master of Technology"),
    CourseAlias("BARCH", "Bachelor of Architecture"),
    CourseAlias("MARCH", "Master of Architecture", spellings=("M.Arch.",), word_like=True),
    CourseAlias("MPLAN", "Master of Planning", spellings=("M.Plan.",), word_like=True),
    CourseAlias("MBBS", "Bachelor of Medicine and Bachelor of Surgery"),
    CourseAlias("BUMS", "Kamil-e-Tib-o-Jarahat (Bachelor of Unani Medicine and Surgery)"),
    CourseAlias("BVOC", "Bachelor of Vocation"),
    CourseAlias("BPHARM", "Bachelor of Pharmacy"),
    CourseAlias("MPHARM", "Master of Pharmacy"),
    CourseAlias("PGDCP", "Post Graduate Diploma in Computer Programming"),
    CourseAlias("PGD", "Post Graduate Diploma", spellings=("P.G. Diploma", "P.G. Dip.")),
    CourseAlias("SSSC", "Senior Secondary School Certificate"),
    CourseAlias("BPED", "Bachelor of Physical Education"),
    CourseAlias("MPED", "Master of Physical Education"),
    CourseAlias("BSC", "Bachelor of Science"),
    CourseAlias("MSC", "Master of Science"),
    CourseAlias("BCOM", "Bachelor of Commerce"),
    CourseAlias("MCOM", "Master of Commerce"),
    CourseAlias("BBA", "Bachelor of Business Administration"),
    CourseAlias("MBA", "Master of Business Administration"),
    CourseAlias("BCA", "Bachelor of Computer Applications"),
    CourseAlias("MCA", "Master of Computer Science and Applications"),
    CourseAlias("BDS", "Bachelor of Dental Surgery"),
    CourseAlias("BPT", "Bachelor of Physiotherapy"),
    CourseAlias("BED", "Bachelor of Education", spellings=("B.Ed.",), word_like=True),
    CourseAlias("MED", "Master of Education", spellings=("M.Ed.",), word_like=True),
    CourseAlias("LLB", "Bachelor of Laws"),
    CourseAlias("LLM", "Master of Laws"),
    CourseAlias("MSW", "Master of Social Work"),
    CourseAlias("MPH", "Master of Public Health"),
    CourseAlias("BVA", "Bachelor of Visual Arts"),
    CourseAlias("MVA", "Master of Visual Arts"),
    CourseAlias("PHD", "Doctor of Philosophy"),
    CourseAlias("BE", "Bachelor of Engineering", word_like=True),
    CourseAlias("BA", "Bachelor of Arts", word_like=True),
    CourseAlias("MA", "Master of Arts", word_like=True),
)

# Acronyms in course names that are subject names, not course abbreviations.
NON_COURSE_ACRONYMS = frozenset({"GIS"})

ABBREVIATION_CANDIDATE = re.compile(
    r"(?<![\w.])(?:[A-Z][A-Za-z]{0,3}\.\s?)+[A-Z][A-Za-z]{0,3}\.?(?!\w)"
    r"|\b[A-Z]{3,}\b"
)


INTENT_RULES: tuple[tuple[QueryIntent, re.Pattern[str], tuple[str, ...]], ...] = (
    (
        QueryIntent.ELIGIBILITY,
        re.compile(
            r"\b(?:eligible|eligibility|qualif(?:y|ies|ied|ication)|"
            r"require(?:s|d|ments?)?)\b|\bapply(?:ing)?\s+for\b|"
            r"\b(?:what|which)\s+(?:degree|qualification)\b.*\bneed\b|"
            r"\bcan\s+i\s+(?:do|join|pursue)\b",
            re.I,
        ),
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
        re.compile(
            r"\b(?:exam pattern|test pattern|syllabus)\b|"
            r"\b(?:test|exam|paper)\s+(?:questions?|marks?)\b|"
            r"\b(?:questions?|marks?)\s+(?:in|on)\s+(?:the\s+)?"
            r"(?:test|exam|paper)\b",
            re.I,
        ),
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
        re.compile(r"\b(?:duration|semesters?|years? long|how\s+long)\b", re.I),
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
    """Return the longest course abbreviation expansion found in a title."""

    candidates: list[tuple[int, str]] = []
    for alias in COURSE_ALIASES:
        match = alias.pattern.search(course_name)
        if match:
            candidates.append((len(alias.abbreviation), alias.full_name))
    if not candidates:
        return []
    longest = max(length for length, _ in candidates)
    return list(
        dict.fromkeys(
            full_name for length, full_name in candidates if length == longest
        )
    )


def unrecognised_abbreviations(
    text: str,
    processor: QueryProcessor | None = None,
) -> list[str]:
    """Return abbreviation-like spans in ``text`` that no course alias covers.

    Used to check that every abbreviation printed in a guide's course names is
    expandable, so a new guide cannot silently lose query coverage.
    """

    processor = processor or QueryProcessor()
    covered: set[int] = set()
    for match in processor.analyze(text).aliases:
        covered.update(range(match.start, match.end))
    missing: list[str] = []
    for candidate in ABBREVIATION_CANDIDATE.finditer(text):
        if candidate.group(0) in NON_COURSE_ACRONYMS:
            continue
        letters = [
            index
            for index in range(candidate.start(), candidate.end())
            if text[index].isalpha()
        ]
        if not all(index in covered for index in letters):
            missing.append(candidate.group(0).strip())
    return missing

