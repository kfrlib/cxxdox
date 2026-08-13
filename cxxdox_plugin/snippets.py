"""Extract C/C++ snippets from Markdown files."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import shutil
import textwrap


# Markdown permits an optional info string after the fence language, e.g.
# ````c++ linenums="1"``.  Keep the language match bounded by whitespace so
# similarly named languages such as ``cpp`` are not treated as C++ snippets.
_opening_fence = re.compile(r"^[ ]{0,3}(?P<fence>`{3})(?P<language>c\+\+|c)(?:[ \t]+[^\r\n]*)?$")
_snippet_separator = "|||"
_render_only_marker = re.compile(r"^\|{10,} *$")


def _snippet_parts(line: str) -> tuple[str, str]:
    """Return the rendered and dumped parts of one snippet line."""
    rendered, separator, dumped = line.partition(_snippet_separator)
    if not separator:
        return line, line

    newline = ""
    if line.endswith("\r\n"):
        newline = "\r\n"
        rendered = rendered.removesuffix("\r\n")
        dumped = dumped.removesuffix("\r\n")
    elif line.endswith(("\r", "\n")):
        newline = line[-1]
        rendered = rendered.removesuffix(newline)
        dumped = dumped.removesuffix(newline)

    return rendered + newline if rendered else "", dumped + newline if dumped else ""


def _snippet_views(content: str) -> tuple[str, str]:
    """Return the dedented rendered and dumped views of snippet *content*."""
    rendered: list[str] = []
    dumped: list[str] = []
    render_only = False

    # Fenced blocks are frequently indented by their surrounding Markdown
    # structure.  Normalize their common indentation before recognizing
    # marker-only lines, whose syntax deliberately permits no leading spaces.
    for line in textwrap.dedent(content).splitlines(keepends=True):
        if _render_only_marker.fullmatch(line.rstrip("\r\n")):
            render_only = not render_only
            continue

        rendered_part, dumped_part = _snippet_parts(line)
        rendered.append(rendered_part)
        if not render_only:
            dumped.append(dumped_part)

    return "".join(rendered), "".join(dumped)


def render_snippet(content: str) -> str:
    """Return a snippet's documentation view.

    ``render|||dump`` lines can contain separate rendered and dumped text.
    An empty side makes the line render-only or dump-only.
    """
    return _snippet_views(content)[0]


def dump_snippet(content: str) -> str:
    """Return the content that should be written to a dumped C++ snippet.

    ``render|||dump`` lines can contain separate rendered and dumped text.
    An empty side makes the line render-only or dump-only.
    """
    return _snippet_views(content)[1]


def _extract_fenced_code_with_languages(markdown: str) -> list[tuple[str, int, str]]:
    """Return bodies, opening lines, and languages from complete C/C++ fences.

    Only triple-backtick blocks whose language tag is ``c++`` or ``c`` are
    extracted; the language may be followed by Markdown fence parameters. The
    scanner intentionally works on lines so a fence can only close with at
    least three backticks.
    """
    snippets: list[tuple[str, int, str]] = []
    opening: str | None = None
    opening_line = 0
    language = ""
    body: list[str] = []

    for line_number, line in enumerate(markdown.splitlines(keepends=True), start=1):
        if opening is None:
            match = _opening_fence.match(line.rstrip("\r\n"))
            if match:
                opening = match.group("fence")
                opening_line = line_number
                language = match.group("language")
                body = []
            continue

        closing = re.match(
            rf"^[ ]{{0,3}}{re.escape(opening[0])}{{{len(opening)},}}[ \t]*$",
            line.rstrip("\r\n"),
        )
        if closing:
            snippets.append(("".join(body), opening_line, language))
            opening = None
            body = []
        else:
            body.append(line)

    return snippets


def extract_fenced_code_with_locations(markdown: str) -> list[tuple[str, int]]:
    """Return code bodies and opening line numbers from complete C/C++ fences."""
    return [(content, line) for content, line, _ in _extract_fenced_code_with_languages(markdown)]


def extract_fenced_code(markdown: str) -> list[str]:
    """Return code bodies from complete C/C++ fenced blocks."""
    return [content for content, _ in extract_fenced_code_with_locations(markdown)]


def render_fenced_code(markdown: str) -> str:
    """Apply snippet render/dump splits inside complete C/C++ fenced blocks."""
    rendered: list[str] = []
    opening: str | None = None
    body: list[str] = []

    for line in markdown.splitlines(keepends=True):
        if opening is None:
            match = _opening_fence.match(line.rstrip("\r\n"))
            if match:
                opening = match.group("fence")
                body = []
            rendered.append(line)
            continue

        closing = re.match(
            rf"^[ ]{{0,3}}{re.escape(opening[0])}{{{len(opening)},}}[ \t]*$",
            line.rstrip("\r\n"),
        )
        if closing:
            rendered.append(render_snippet("".join(body)))
            rendered.append(line)
            opening = None
            body = []
        else:
            body.append(line)

    # Preserve unterminated blocks exactly, matching extraction behavior.
    rendered.extend(body)
    return "".join(rendered)


def clean_snippets_directory(directory: Path) -> Path:
    """Remove prior snippets and recreate the configured output directory."""
    if directory.exists():
        if not directory.is_dir():
            raise ValueError(f"Snippet output path is not a directory: {directory}")
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class SnippetWriter:
    """Write C and C++ snippets grouped by destination key and language."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._destinations: dict[str, Path] = {}

    def write(
        self,
        destination_key: str,
        content: str,
        source_path: str,
        source_line: int,
        language: str = "c++",
    ) -> Path:
        """Append a non-empty dumped snippet to its page's source file."""
        extension = {"c": "c", "c++": "cpp"}.get(language)
        if extension is None:
            raise ValueError(f"Unsupported snippet language: {language}")
        destination_path = PurePosixPath(destination_key)
        key = f"{destination_path.as_posix()}.{extension}"
        destination_dir = self.directory.joinpath(*destination_path.parts[:-1])
        destination_path = destination_dir / f"{destination_path.name}.{extension}"
        content = dump_snippet(content)
        if not content:
            return destination_path

        extracted_from = f"// Extracted from {source_path}, line {source_line}\n"
        destination = self._destinations.get(key)
        if destination is None:
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_path
            self._destinations[key] = destination
            destination.write_text(extracted_from + content, encoding="utf-8", newline="")
        else:
            with destination.open("a", encoding="utf-8", newline="") as output:
                existing = destination.read_bytes()
                if existing.endswith((b"\r\n", b"\n", b"\r")):
                    output.write("\n")
                else:
                    output.write("\n\n")
                output.write(extracted_from + content)
        return destination


def extract_directory(source_directory: Path, output_directory: Path) -> tuple[int, int]:
    """Extract fenced C/C++ snippets and return dumped C and C++ file counts."""
    if not source_directory.is_dir():
        raise ValueError(f"Snippet source path is not a directory: {source_directory}")

    writer = SnippetWriter(clean_snippets_directory(output_directory))
    for source_path in sorted(source_directory.rglob("*.md")):
        markdown = source_path.read_text(encoding="utf-8")
        destination_key = source_path.relative_to(source_directory).as_posix()
        for snippet, line, language in _extract_fenced_code_with_languages(markdown):
            writer.write(destination_key, snippet, destination_key, line, language)

    c_files = sum(path.suffix == ".c" for path in writer._destinations.values())
    cpp_files = sum(path.suffix == ".cpp" for path in writer._destinations.values())
    return c_files, cpp_files


def main() -> None:
    """Run the standalone snippet extraction command."""
    parser = argparse.ArgumentParser(description="Extract C/C++ snippets from Markdown files.")
    parser.add_argument("source_directory", type=Path, help="Directory containing Markdown files")
    parser.add_argument("output_directory", type=Path, help="Directory where .cpp snippets are written")
    args = parser.parse_args()
    c_files, cpp_files = extract_directory(args.source_directory, args.output_directory)
    print(f"Dumped {c_files} C file(s) and {cpp_files} C++ file(s).")


if __name__ == "__main__":
    main()
