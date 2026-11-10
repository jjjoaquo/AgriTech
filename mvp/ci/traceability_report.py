"""Record the GitHub commit evidence that can be compared with a Jira story."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8").strip()


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    commit = git("rev-parse", "HEAD")
    subject = git("show", "-s", "--format=%s", "HEAD")
    author = git("show", "-s", "--format=%an", "HEAD")
    committed_at = git("show", "-s", "--format=%aI", "HEAD")
    parents = git("show", "-s", "--format=%P", "HEAD").split()
    issue = re.search(r"\bSCRUM-\d+\b", subject, re.IGNORECASE)
    is_merge = len(parents) > 1
    result = {
        "commit": commit,
        "author": author,
        "committed_at": committed_at,
        "subject": subject,
        "jira_issue": issue.group().upper() if issue else None,
        "merge_commit": is_merge,
        "repository": os.environ.get("GITHUB_REPOSITORY", "jjjoaquo/AgriTech"),
    }
    output = root / "mvp" / "test-results"
    output.mkdir(exist_ok=True)
    (output / "trazabilidad-github.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "### Evidencia GitHub / Jira\n\n"
        f"- Commit: `{commit}`\n"
        f"- Historia Jira: `{result['jira_issue'] or 'sin identificador'}`\n"
        f"- Autor: {author}\n"
        f"- Fecha del commit: {committed_at}\n"
        f"- Cambio: {subject}\n\n"
        "El estado y las fechas reales de Jira deben comprobarse en el tablero; "
        "este reporte no marca historias como terminadas.\n"
    )
    (output / "trazabilidad-github.md").write_text(summary, encoding="utf-8")
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary_path, "a", encoding="utf-8") as summary_file:
            summary_file.write(summary)
    print(summary)
    if not issue and not is_merge:
        raise SystemExit("El commit debe incluir su identificador SCRUM-n en el título.")


if __name__ == "__main__":
    main()
