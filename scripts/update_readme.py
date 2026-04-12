#!/usr/bin/env python3
"""
Auto-updates the repository table in README files by fetching all public repos
from the GitHub API. Descriptions from the API take priority; existing README
descriptions are kept as a fallback for repos that have no API description.

Usage:
    GITHUB_TOKEN=<token> python3 scripts/update_readme.py
"""

import json
import os
import re
import sys
import urllib.request
from urllib.error import HTTPError

ORG = "Aswintechie"
EXCLUDE = {".github"}  # skip the profile repo itself

MARKER_START = "<!-- REPOS_START -->"
MARKER_END = "<!-- REPOS_END -->"

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
README_FILES = [
    os.path.join(SCRIPT_DIR, "..", "profile", "README.md"),
    os.path.join(SCRIPT_DIR, "..", "README.md"),
]


def fetch_repos(token=None):
    """Return all public, non-fork repos for the org, sorted by created_at."""
    repos = []
    page = 1
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "update-readme-bot",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    while True:
        url = (
            f"https://api.github.com/orgs/{ORG}/repos"
            f"?type=public&per_page=100&page={page}"
        )
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
        except HTTPError as exc:
            print(f"GitHub API error: {exc.code} {exc.reason}", file=sys.stderr)
            sys.exit(1)

        if not data:
            break
        repos.extend(data)
        page += 1

    return sorted(
        [r for r in repos if not r["fork"] and r["name"] not in EXCLUDE],
        key=lambda r: r["created_at"],
    )


def parse_existing_descriptions(content):
    """
    Extract {repo_name: description} from the current README table so we can
    preserve hand-written descriptions for repos that have no GitHub description.
    Strips the *(archived)* suffix from names before storing.
    """
    descriptions = {}
    # Match table rows: | [name](url) ... | description | ... |
    row_re = re.compile(
        r"\|\s*\[([^\]]+)\]\([^)]+\)[^|]*\|\s*([^|]+?)\s*\|"
    )
    for match in row_re.finditer(content):
        name = match.group(1).strip()
        desc = match.group(2).strip()
        if desc and desc != "–":
            descriptions[name] = desc
    return descriptions


def build_table(repos, fallback_descriptions):
    """Build the Markdown table string for the given repos."""
    rows = [
        "| Repository | Description | Language |",
        "|------------|-------------|----------|",
    ]
    for repo in repos:
        name = repo["name"]
        url = repo["html_url"]
        api_desc = (repo.get("description") or "").strip()
        desc = api_desc or fallback_descriptions.get(name, "–")
        lang = repo.get("language") or "–"
        archived = repo.get("archived", False)

        name_cell = f"[{name}]({url}) *(archived)*" if archived else f"[{name}]({url})"
        rows.append(f"| {name_cell} | {desc} | {lang} |")

    return "\n".join(rows)


def replace_between_markers(content, table):
    """Replace the content between REPOS_START and REPOS_END markers."""
    new_block = f"{MARKER_START}\n{table}\n{MARKER_END}"
    pattern = re.compile(
        re.escape(MARKER_START) + ".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    return pattern.sub(new_block, content)


def update_file(path, table):
    """Update a single README file. Returns True if the file was changed."""
    real_path = os.path.realpath(path)
    if not os.path.exists(real_path):
        print(f"File not found, skipping: {real_path}", file=sys.stderr)
        return False

    with open(real_path, encoding="utf-8") as fh:
        content = fh.read()

    if MARKER_START not in content or MARKER_END not in content:
        print(f"Skipping {real_path}: markers not found.", file=sys.stderr)
        return False

    new_content = replace_between_markers(content, table)
    if new_content == content:
        print(f"No changes: {real_path}")
        return False

    with open(real_path, "w", encoding="utf-8") as fh:
        fh.write(new_content)
    print(f"Updated: {real_path}")
    return True


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repos = fetch_repos(token)

    # Collect fallback descriptions from the first README that exists
    fallback_descriptions = {}
    for path in README_FILES:
        real_path = os.path.realpath(path)
        if os.path.exists(real_path):
            with open(real_path, encoding="utf-8") as fh:
                fallback_descriptions.update(parse_existing_descriptions(fh.read()))
            break

    table = build_table(repos, fallback_descriptions)

    for path in README_FILES:
        update_file(path, table)


if __name__ == "__main__":
    main()
