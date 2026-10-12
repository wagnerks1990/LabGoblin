"""Render tracked public Markdown documentation for GitHub's flat Wiki pages."""

import argparse
from pathlib import Path
import re


def page_name(path: Path) -> str:
    return (
        "Home"
        if path.as_posix() == "index.md"
        else "--".join(path.with_suffix("").parts)
    )


def render(source: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.rglob("*.md")):
        relative = path.relative_to(source)

        def rewrite(match: re.Match, path: Path = path) -> str:
            destination = match.group(1)
            if ":" in destination or destination.startswith(("#", "/")):
                return match.group(0)
            target, separator, fragment = destination.partition("#")
            resolved = (path.parent / target).resolve()
            if resolved.suffix != ".md" or not resolved.is_file():
                return match.group(0)
            try:
                document = resolved.relative_to(source.resolve())
            except ValueError:
                return match.group(0)
            return (
                "]("
                + page_name(document)
                + (separator + fragment if separator else "")
                + ")"
            )

        content = re.sub(r"\]\(([^\s)]+)\)", rewrite, path.read_text())
        (output / (page_name(relative) + ".md")).write_text(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, default=Path("docs"))
    options = parser.parse_args()
    render(options.source, options.output)
