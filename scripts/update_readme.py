#!/usr/bin/env python3
"""
Auto-updates the repository table in README files by fetching all public repos
from the GitHub API. Descriptions from the API take priority; CUSTOM_DESCRIPTIONS
below are used as fallback for repos with no GitHub description.

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
EXCLUDE = {".github"}

MARKER_START = "<!-- REPOS_START -->"
MARKER_END = "<!-- REPOS_END -->"

# Repos shown first, in this order. Anything not listed here follows alphabetically.
PINNED_ORDER = [
    "ttperf",
    "ttnn-performance-dashboard",
    "portfolio",
    "whatsapp_bot",
    "3d_printing",
    "AiBuddy",
]

# Fallback descriptions when GitHub API returns none.
CUSTOM_DESCRIPTIONS = {
    "3d_printing": "3D print portfolio and showcase site — custom figurines, decor, and art pieces. Orders via DM",
    "AiBuddy": "AI-powered chatbot for Microsoft Teams — brings conversational AI into team channels and group chats",
    "whatsapp_bot": "WhatsApp AI assistant bot powered by Claude — conversational AI for everyday use",
    "cheap-domain": "Get custom subdomains under aswincloud.com for just ₹20/month",
}

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
README_FILES = [
    os.path.join(SCRIPT_DIR, "..", "profile", "README.md"),
    os.path.join(SCRIPT_DIR, "..", "README.md"),
]


def fetch_repos(token=None):
    """Return all public, non-fork repos for the org."""
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

    return [r for r in repos if not r["fork"] and r["name"] not in EXCLUDE]


def sort_repos(repos):
    """Sort: pinned in order first, then rest alphabetically."""
    pinned_index = {name: i for i, name in enumerate(PINNED_ORDER)}
    pinned = sorted(
        [r for r in repos if r["name"] in pinned_index],
        key=lambda r: pinned_index[r["name"]],
    )
    rest = sorted(
        [r for r in repos if r["name"] not in pinned_index],
        key=lambda r: r["name"].lower(),
    )
    return pinned + rest


def build_table(repos):
    """Build the Markdown table string for the given repos."""
    rows = [
        "| Repository | Description | Language |",
        "|------------|-------------|----------|",
    ]
    for repo in repos:
        name = repo["name"]
        url = repo["html_url"]
        api_desc = (repo.get("description") or "").strip()
        desc = api_desc or CUSTOM_DESCRIPTIONS.get(name, "–")
        lang = repo.get("language") or "–"
        archived = repo.get("archived", False)

        name_cell = f"[{name}]({url}) *(archived)*" if archived else f"[{name}]({url})"
        rows.append(f"| {name_cell} | {desc} | {lang} |")

    return "\n".join(rows)


def replace_between_markers(content, table):
    new_block = f"{MARKER_START}\n{table}\n{MARKER_END}"
    pattern = re.compile(
        re.escape(MARKER_START) + ".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    return pattern.sub(new_block, content)


def update_file(path, table):
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
    sorted_repos = sort_repos(repos)
    table = build_table(sorted_repos)

    for path in README_FILES:
        update_file(path, table)


if __name__ == "__main__":
    main()
