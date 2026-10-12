"""Render approved git-tracked documentation into an existing GitHub Wiki clone."""

import argparse
import posixpath
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit

REPOSITORY_URL = "https://github.com/wagnerks1990/LabGoblin"
LINK = re.compile(r"(!?\[[^\]\n]*\]\()([^\s)]+)([^)]*\))")
REFERENCE = re.compile(r"^(\s*\[[^\]\n]+\]:\s*)(\S+)", re.MULTILINE)


def page_name(path):
    return "Home" if path == "docs/index.md" else "Docs-" + path[5:-3].replace("/", "-")


def rewrite_target(target, source, pages):
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return target
    path = posixpath.normpath(posixpath.join(posixpath.dirname(source), parsed.path))
    if path.startswith("../") or path.startswith("/"):
        raise ValueError(f"Link escapes repository: {source}: {target}")
    if path in pages:
        url = quote(pages[path])
    else:
        url = f"{REPOSITORY_URL}/blob/main/{quote(path)}"
    if parsed.query:
        url += "?" + parsed.query
    if parsed.fragment:
        url += "#" + parsed.fragment
    return url


def sync(source, destination):
    tracked = subprocess.check_output(
        ["git", "-C", str(source), "ls-files", "-z", "--", "docs"], text=True
    ).split("\0")
    paths = sorted(path for path in tracked if path.endswith(".md"))
    pages = {path: page_name(path) for path in paths}
    if "docs/index.md" not in pages or len(set(pages.values())) != len(pages):
        raise ValueError("Wiki requires docs/index.md and unique page names")
    # Render all documents before writing, so invalid links leave the clone intact.
    rendered = {}
    for path in paths:
        if (source / path).is_symlink():
            raise ValueError(f"Documentation symlink is not approved: {path}")
        text = (source / path).read_text()
        text = LINK.sub(
            lambda match: match[1] + rewrite_target(match[2], path, pages) + match[3],
            text,
        )
        text = REFERENCE.sub(
            lambda match: match[1] + rewrite_target(match[2], path, pages), text
        )
        rendered[pages[path] + ".md"] = text
    destination.mkdir(parents=True, exist_ok=True)
    for name, text in rendered.items():
        target = destination / name
        if target.is_symlink():
            raise ValueError(f"Wiki page is a symlink: {name}")
        target.write_text(text)
    # Existing pages outside these generated names remain untouched.
    return len(rendered)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.cwd())
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(f"Rendered {sync(args.source, args.destination)} tracked documentation pages")
