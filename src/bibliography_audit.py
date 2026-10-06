"""Offline integrity audit for the manuscript bibliography and curated source ledger.

This stage does not pretend to contact publishers during reproduction. It checks
that the retained, source-verified ledger covers every entry in the frozen
bibliography snapshot, that all entries are cited, that identifiers are unique
and syntactically valid, and that known high-risk records retain their corrected
primary-source metadata. When the artifact is inside the complete project, the
snapshot is also compared field-for-field with the manuscript sources. The same
check remains runnable from the standalone artifact, where paper/ is absent.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
BIB_PATH = PROJECT / "paper" / "references.bib"
TEX_PATH = PROJECT / "paper" / "main.tex"
SNAPSHOT_PATH = ROOT / "reference_snapshot.json"
LEDGER_PATH = ROOT / "reference_audit.csv"

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}")


class AuditError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def strip_outer(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0], value[-1]) in (("{", "}"), ('"', '"'))):
        return value[1:-1].strip()
    return value


def parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    index = 0
    length = len(body)
    while index < length:
        while index < length and (body[index].isspace() or body[index] == ","):
            index += 1
        if index >= length:
            break
        name_match = re.match(r"[A-Za-z][A-Za-z0-9_-]*", body[index:])
        require(name_match is not None, f"cannot parse BibTeX field near {body[index:index+40]!r}")
        name = name_match.group(0).lower()
        index += len(name_match.group(0))
        while index < length and body[index].isspace():
            index += 1
        require(index < length and body[index] == "=", f"missing '=' after field {name}")
        index += 1
        while index < length and body[index].isspace():
            index += 1
        require(index < length, f"missing value for field {name}")
        start = index
        if body[index] == "{":
            depth = 0
            while index < length:
                if body[index] == "{":
                    depth += 1
                elif body[index] == "}":
                    depth -= 1
                    if depth == 0:
                        index += 1
                        break
                index += 1
            require(depth == 0, f"unbalanced braces in field {name}")
        elif body[index] == '"':
            index += 1
            escaped = False
            while index < length:
                char = body[index]
                if char == '"' and not escaped:
                    index += 1
                    break
                escaped = char == "\\" and not escaped
                if char != "\\":
                    escaped = False
                index += 1
        else:
            while index < length and body[index] != ",":
                index += 1
        require(name not in fields, f"duplicate field {name}")
        fields[name] = strip_outer(body[start:index])
    return fields


def parse_bibtex(text: str) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    index = 0
    while True:
        marker = text.find("@", index)
        if marker < 0:
            break
        type_match = re.match(r"@([A-Za-z]+)\s*\{", text[marker:])
        require(type_match is not None, f"invalid BibTeX entry at byte {marker}")
        entry_type = type_match.group(1).lower()
        open_brace = marker + type_match.end() - 1
        depth = 1
        cursor = open_brace + 1
        while cursor < len(text) and depth:
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1
        require(depth == 0, f"unbalanced BibTeX entry at byte {marker}")
        content = text[open_brace + 1 : cursor - 1]
        comma = content.find(",")
        require(comma > 0, "BibTeX entry has no key/body separator")
        key = content[:comma].strip()
        require(key and key not in entries, f"duplicate/empty BibTeX key {key!r}")
        entries[key] = {"entry_type": entry_type, **parse_fields(content[comma + 1 :])}
        index = cursor
    return entries


def normalize_text(value: str) -> str:
    value = re.sub(r"\\[A-Za-z]+\s*", "", value)
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\s+", " ", value).strip().casefold()
    return value


def load_ledger() -> dict[str, dict[str, str]]:
    with LEDGER_PATH.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "key",
        "title",
        "year",
        "identifier_type",
        "identifier",
        "verification_source",
        "verification_level",
        "metadata_status",
        "calibration_group",
        "claim_use",
        "verification_date",
        "notes",
    }
    require(rows and set(rows[0]) == required, "reference ledger columns mismatch")
    by_key: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row["key"]
        require(key and key not in by_key, f"duplicate ledger key {key!r}")
        by_key[key] = row
    return by_key


def load_snapshot() -> tuple[dict[str, dict[str, Any]], set[str]]:
    snapshot = json.loads(SNAPSHOT_PATH.read_text())
    require(snapshot.get("schema") == "reference-snapshot-v1", "reference snapshot schema mismatch")
    entries = snapshot.get("entries")
    cited_keys = snapshot.get("cited_keys")
    require(isinstance(entries, dict) and entries, "reference snapshot has no entries")
    require(isinstance(cited_keys, list), "reference snapshot cited_keys is not a list")
    require(len(cited_keys) == len(set(cited_keys)), "reference snapshot contains duplicate cited keys")
    return entries, set(cited_keys)


def manuscript_citations(tex: str) -> set[str]:
    cited: list[str] = []
    for match in CITE_RE.finditer(tex):
        cited.extend(key.strip() for key in match.group(1).split(",") if key.strip())
    return set(cited)


def cross_check_manuscript(entries: dict[str, dict[str, Any]], cited_set: set[str]) -> None:
    paper_files = (BIB_PATH.exists(), TEX_PATH.exists())
    require(paper_files[0] == paper_files[1], "complete-project paper cross-check is only partially available")
    if not paper_files[0]:
        return
    live_entries = parse_bibtex(BIB_PATH.read_text())
    live_citations = manuscript_citations(TEX_PATH.read_text())
    require(live_entries == entries, "reference snapshot differs from paper/references.bib")
    require(live_citations == cited_set, "reference snapshot differs from citations in paper/main.tex")


def audit() -> dict[str, Any]:
    entries, cited_set = load_snapshot()
    cross_check_manuscript(entries, cited_set)
    ledger = load_ledger()

    require(len(entries) >= 70, "bibliography contains fewer than 70 entries")
    require(len(entries) == 70, "frozen manuscript is expected to contain exactly 70 entries")
    require(cited_set == set(entries), "every and only BibTeX entries must be cited")
    require(set(ledger) == set(entries), "reference ledger must cover every BibTeX entry exactly once")
    frozen_text = json.dumps(entries, sort_keys=True).casefold()
    require("and others" not in frozen_text, "truncated author list remains")
    require("todo" not in frozen_text, "TODO remains in bibliography")

    dois: dict[str, str] = {}
    titles: dict[str, str] = {}
    identifier_counts = {"doi": 0, "url": 0, "isbn": 0}
    levels: dict[str, int] = {}
    groups: dict[str, int] = {}
    for key, entry in entries.items():
        for required_field in ("author", "title", "year"):
            require(entry.get(required_field, "").strip(), f"{key} lacks {required_field}")
        year = entry["year"].strip()
        require(year.isdigit() and 1900 <= int(year) <= 2026, f"{key} has implausible year {year}")
        title_norm = normalize_text(entry["title"])
        require(title_norm not in titles, f"duplicate title in {key} and {titles.get(title_norm)}")
        titles[title_norm] = key

        doi = entry.get("doi", "").strip()
        url = entry.get("url", "").strip()
        isbn = entry.get("isbn", "").strip()
        require(doi or url or isbn, f"{key} has no DOI, official URL, or ISBN")
        if doi:
            doi_norm = doi.casefold()
            require(DOI_RE.match(doi) is not None, f"{key} has malformed DOI {doi}")
            require(doi_norm not in dois, f"duplicate DOI in {key} and {dois.get(doi_norm)}")
            dois[doi_norm] = key
            identifier_counts["doi"] += 1
        elif url:
            require(url.startswith("https://"), f"{key} URL is not HTTPS")
            identifier_counts["url"] += 1
        else:
            identifier_counts["isbn"] += 1

        row = ledger[key]
        require(normalize_text(row["title"]) == title_norm, f"ledger title mismatch for {key}")
        require(row["year"] == year, f"ledger year mismatch for {key}")
        expected_type = "doi" if doi else "url" if url else "isbn"
        expected_identifier = doi if doi else url if url else isbn
        require(row["identifier_type"] == expected_type, f"ledger identifier type mismatch for {key}")
        require(row["identifier"].casefold() == expected_identifier.casefold(), f"ledger identifier mismatch for {key}")
        require(row["metadata_status"] == "verified", f"unverified ledger row {key}")
        require(row["verification_source"].startswith("https://"), f"non-HTTPS verification source for {key}")
        # This is provenance, not an invariant that forbids later corrections.
        # Validate the recorded date without pretending to resolve the source.
        try:
            verified_on = date.fromisoformat(row["verification_date"])
        except ValueError:
            raise AuditError(f"invalid verification date for {key}")
        require(date(1900, 1, 1) <= verified_on <= date(2026, 12, 31),
                f"implausible verification date for {key}")
        level = row["verification_level"]
        require(level in {"official-current-document", "publisher-or-primary-metadata", "primary-preprint", "authoritative-book-record"}, f"unknown verification level for {key}")
        levels[level] = levels.get(level, 0) + 1
        group = row["calibration_group"]
        require(group in {"toplas", "foundational", "adjacent", "none"}, f"unknown calibration group for {key}")
        groups[group] = groups.get(group, 0) + 1

    require(groups == {"toplas": 12, "foundational": 5, "adjacent": 5, "none": 48}, f"calibration counts mismatch: {groups}")

    # High-risk records that were corrected after source verification.
    handbook = entries["MullerHandbook"]["author"]
    for author in ("Nicolas Brunie", "Mioara Joldes", "Serge Torres"):
        require(author in handbook, f"correct Handbook author missing: {author}")
    for wrong in ("Nicolas Brisebarre", "Damien Stehl"):
        require(wrong not in handbook, f"wrong Handbook author remains: {wrong}")
    souper = entries["Souper"]
    require(souper["doi"].casefold() == "10.48550/arxiv.1711.04422".casefold(), "Souper DOI regressed")
    require("Raimondas Sasnauskas" in souper["author"] and "John Regehr" in souper["author"], "Souper author list regressed")
    green = entries["GreenThumb"]
    require(green["doi"] == "10.1145/2892208.2892233", "GreenThumb DOI regressed")
    require("Aditya V. Thakur" in green["author"] and "Dinakar Dhurjati" in green["author"],
            "GreenThumb CC author list regressed")
    intel = entries["IntelSDM"]
    require(intel["year"] == "2026" and "Version 092" in intel["note"], "Intel manual is not the verified 2026 Version 092 record")
    smtlib = entries["SMTLIB"]
    require("Version 2.7" in smtlib["title"] and smtlib["year"] == "2026", "SMT-LIB record is not current")

    return {
        "schema": "bibliography-audit-result-v1",
        "passed": True,
        "bibtex_entries": len(entries),
        "unique_cited_keys": len(cited_set),
        "uncited_entries": [],
        "unknown_citations": [],
        "ledger_rows": len(ledger),
        "identifier_counts": identifier_counts,
        "verification_levels": levels,
        "calibration_counts": groups,
        "known_corrections_locked": [
            "Handbook second-edition author list",
            "Souper arXiv authors and DOI",
            "GreenThumb CC 2016 authors and DOI",
            "Intel SDM Version 092 (2026)",
            "SMT-LIB Version 2.7 (2026)",
        ],
        "interpretation": (
            "Offline replay of a source-verified bibliography snapshot and ledger. It checks retained "
            "metadata, identifiers, citation coverage, and calibration counts; it does not perform live "
            "DOI resolution. Inside the complete project it also requires exact agreement with the paper sources."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit()
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
