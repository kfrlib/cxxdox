
from mkdocs.config.config_options import Type, ListOfItems, SubConfig, Dir
from mkdocs.config.base import Config
import re

class InputDict(Config):
    include = ListOfItems(Type(str))
    exclude = ListOfItems(Type(str), default=[])
    exclude_symbols = ListOfItems(Type(str), default=[])
    compile_options = ListOfItems(Type(str), default=[])
    hide_tokens = ListOfItems(Type(str), default=[])


def _gitignore_pattern_to_regex(pattern: str) -> tuple[re.Pattern, bool, bool]:
    """Compile a gitignore-style pattern.

    Returns ``(regex, anchored, unanchored_basename)``.
    Supports ``*`` ``**`` ``?``; leading ``/`` anchors; trailing ``/``
    is ignored. Last match wins; no directory quirk.
    """
    # leading / is purely cosmetic -- still anchored though
    leading_slash = pattern.startswith("/")
    if leading_slash:
        pattern = pattern[1:]

    while pattern.endswith("/"):
        pattern = pattern[:-1]

    anchored = leading_slash or "/" in pattern
    regex_parts: list[str] = []

    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                # `**/` -> zero or more dirs; `**` -> any chars incl. /
                if i + 2 < n and pattern[i + 2] == "/":
                    regex_parts.append("(?:.*/)?")
                    i += 3
                else:
                    regex_parts.append(".*")
                    i += 2
            else:
                regex_parts.append("[^/]*")
                i += 1
        elif c == "?":
            regex_parts.append("[^/]")
            i += 1
        elif c == "/":
            regex_parts.append("/")
            i += 1
        else:
            regex_parts.append(re.escape(c))
            i += 1

    body = "".join(regex_parts)
    if anchored:
        # rooted: match the entry or any path beneath it
        return re.compile(f"^{body}(/.*)?$"), anchored, False
    # unanchored: match the body as a full path segment anywhere
    return re.compile(f"(?:(?<=^)|(?<=/)){body}(?=$|/)"), False, True


def _normalise_path(file_path: str) -> str:
    """Normalise separators and strip leading ``./``."""
    normalised = file_path.replace("\\", "/")
    if normalised.startswith("./"):
        normalised = normalised[2:]
    return normalised


class GroupDict(Config):
    id = Type(str)
    title = Type(str)
    description = Type(str, default="")
    file = ListOfItems(Type(str))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # list[(regex, negated, anchored, unanchored)]
        self._compiled: list[tuple[re.Pattern, bool, bool, bool]] | None = None

    def _ensure_compiled(self) -> list[tuple[re.Pattern, bool, bool, bool]]:
        """Compile patterns from ``self.file`` on first use."""
        if self._compiled is not None:
            return self._compiled

        compiled: list[tuple[re.Pattern, bool, bool, bool]] = []
        for raw in self.file or []:
            pattern = raw.strip()
            if not pattern or pattern.startswith("#"):
                continue

            negated = pattern.startswith("!")
            if negated:
                pattern = pattern[1:].strip()
                if not pattern:
                    continue

            regex, anchored, unanchored = _gitignore_pattern_to_regex(pattern)
            compiled.append((regex, negated, anchored, unanchored))

        self._compiled = compiled
        return compiled

    def matches(self, file_path: str) -> bool:
        """Return True if *file_path* is included by this group's patterns.

        Pure last-match-wins gitignore subset: ``*`` ``**`` ``?`` ``!``
        and ``#`` comments. ``data`` matches ``data`` and ``x/data``
        but NOT ``dataset``. ``/data`` is rooted; trailing ``/`` is
        ignored (no directory quirk).
        """
        if not self.file:
            return False

        normalised = _normalise_path(file_path)
        matched = False
        for regex, negated, _, unanchored in self._ensure_compiled():
            hit = regex.search(normalised) if unanchored else regex.match(normalised)
            if hit is not None:
                matched = not negated
        return matched

class CxxDoxConfig(Config):
    title = Type(str, default="CxxDox Documentation")
    input = ListOfItems(SubConfig(InputDict))
    path_prefix = Type(str, default="cxxdox/")
    root = Dir(default=".")
    groups = ListOfItems(SubConfig(GroupDict), default=[])
    # Optional default namespace used purely for display. When set, symbol
    # names that are members of this namespace have the namespace prefix
    # stripped when rendered (e.g. `ns::func` -> `func`), and names in
    # other namespaces are displayed with a leading `::` for clarity and
    # C++ correctness (e.g. `other::func` -> `::other::func`). Lookup
    # logic is unaffected. Leave empty/None to disable the transform.
    default_namespace = Type(str, default="")
