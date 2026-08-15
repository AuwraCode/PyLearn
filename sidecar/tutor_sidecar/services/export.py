from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect

DEFAULT_EXPORT_DIR = Path.home() / "Documents" / "PyLearn-eksport"

# NFKD nie rozkłada „ł" (brak dekompozycji w Unicode) — bez tej mapy „pętla łańcuchów"
# zgubiłoby literę w slugu pliku.
_PL_MAP = str.maketrans({"ł": "l", "Ł": "L"})


def slugify(name: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", name.translate(_PL_MAP))
        .encode("ascii", "ignore")
        .decode()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "notatka"


def resolve_target_dir(raw_path: str) -> Path:
    target = Path(raw_path).expanduser() if raw_path.strip() else DEFAULT_EXPORT_DIR
    if target.exists() and not target.is_dir():
        raise ValueError(f"Ścieżka {target} wskazuje plik, nie katalog.")
    target.mkdir(parents=True, exist_ok=True)
    return target


def _yaml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)  # JSON string to poprawny skalar YAML


def _frontmatter(concept: sqlite3.Row, tags: list[str]) -> str:
    lines = [
        "---",
        f"aliases: [{_yaml_str(str(concept['name']))}]",
        f"tags: [{', '.join(_yaml_str(tag) for tag in tags)}]",
        f"language: {concept['language']}",
        f"status: {concept['status']}",
        f"created: {str(concept['created_at'])[:10]}",
        "---",
    ]
    return "\n".join(lines)


def _concept_markdown(detail: dict[str, Any], tags: list[str]) -> str:
    concept = detail["concept"]
    parts: list[str] = [_frontmatter(concept, tags), "", f"# {concept['name']}", ""]

    if concept["signature"]:
        parts += [f"`{concept['signature']}`", ""]
    if concept["tldr"]:
        parts += [f"> {concept['tldr']}", ""]
    if concept["explanation"]:
        parts += [str(concept["explanation"]), ""]

    if detail["examples"]:
        parts.append("## Przykłady")
        for example in detail["examples"]:
            parts += ["", f"### {example['title']}", "```python", str(example["code"]), "```"]
            if example["output"]:
                parts += ["Wynik:", "```", str(example["output"]), "```"]
            if example["comment"]:
                parts.append(str(example["comment"]))
        parts.append("")

    gotchas = json.loads(concept["gotchas_json"])
    if gotchas:
        parts += ["## Pułapki", *[f"- {gotcha}" for gotcha in gotchas], ""]

    if detail["related"]:
        parts += ["## Powiązane", " · ".join(f"[[{name}]]" for name in detail["related"]), ""]

    exercise = detail.get("exercise_full")
    if exercise is not None:
        parts += ["## Zadanie", str(exercise["prompt"]), ""]
        parts += ["```python", str(exercise["starter_code"]), "```", ""]
        if exercise["hint"]:
            parts += [f"Podpowiedź: {exercise['hint']}", ""]
        if exercise["solution"]:
            parts += ["### Rozwiązanie", "```python", str(exercise["solution"]), "```", ""]

    if detail["flashcards"]:
        parts.append("## Fiszki")
        parts += [f"- **{card['q']}** — {card['a']}" for card in detail["flashcards"]]
        parts.append("")

    if detail["notes"]:
        parts.append("## Moje notatki")
        for note in detail["notes"]:
            date = str(note["created_at"])[:10]
            body = str(note["body_md"]).replace("\n", "\n> ")
            parts.append(f"> [{date}] {body}")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


_STATUS_HEADING = {"learning": "W nauce", "known": "Znane", "new": "Nowe"}


def export_markdown(db_path: Path, target_dir: Path) -> int:
    conn = connect(db_path)
    try:
        concept_ids = repo.all_content_concept_ids(conn)
        used_slugs: set[str] = set()
        index_by_status: dict[str, list[str]] = {"learning": [], "known": [], "new": []}
        written = 0

        for concept_id in concept_ids:
            detail = repo.get_concept_detail(conn, concept_id)
            if detail is None:
                continue
            detail["exercise_full"] = repo.exercise_full(conn, concept_id)
            detail["flashcards"] = repo.cards_for_concept(conn, concept_id)

            slug = slugify(str(detail["concept"]["name"]))
            candidate, counter = slug, 2
            while candidate in used_slugs:
                candidate = f"{slug}-{counter}"
                counter += 1
            used_slugs.add(candidate)

            (target_dir / f"{candidate}.md").write_text(
                _concept_markdown(detail, detail["tags"]), encoding="utf-8"
            )
            written += 1

            concept = detail["concept"]
            tldr = str(concept["tldr"] or "").split("\n")[0]
            entry = f"- [[{concept['name']}]]" + (f" — {tldr}" if tldr else "")
            index_by_status[str(concept["status"])].append(entry)
    finally:
        conn.close()

    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    index_parts = ["# PyLearn — indeks", ""]
    for status in ("learning", "known", "new"):
        if index_by_status[status]:
            index_parts += [f"## {_STATUS_HEADING[status]}", *index_by_status[status], ""]
    index_parts.append(f"_Eksport: {stamp}, notatek: {written}._")
    (target_dir / "index.md").write_text("\n".join(index_parts) + "\n", encoding="utf-8")
    return written + 1


def export_json(db_path: Path, target_dir: Path) -> Path:
    conn = connect(db_path)
    try:
        dump = {
            "app": "PyLearn",
            "exported_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "tables": repo.dump_tables(conn),
        }
    finally:
        conn.close()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out = target_dir / f"pylearn-backup-{stamp}.json"
    out.write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
