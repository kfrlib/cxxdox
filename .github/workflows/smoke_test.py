"""Smoke-test for a freshly installed mkdocs-cxxdox wheel.

Verifies that:
  * the package imports,
  * a platform-specific libclang binary is bundled inside the package,
  * the clang resource directory (stddef.h, immintrin.h, …) is present, and
  * the mkdocs plugin entry point is registered.

Cross-platform: relies only on the installed package layout, not on any
shell-specific paths, so the same script runs on Windows, Linux, and macOS.
"""

import os
import sys
from importlib.metadata import entry_points

import cxxdox_plugin

pkg_dir = os.path.dirname(cxxdox_plugin.__file__)
print("cxxdox_plugin installed at:", pkg_dir)

lc_dir = os.path.join(pkg_dir, "libclang21")
print("libclang21 contents:", os.listdir(lc_dir))

# A bundled binary is e.g. libclang.dll (Windows) or libclang.so (Linux).
binaries = [
    f
    for f in os.listdir(lc_dir)
    if f.startswith("libclang.") and not f.endswith(".py")
]
assert binaries, "no libclang binary shipped in the wheel!"
print("bundled libclang binary:", binaries)

# ---------------------------------------------------------------------------
# Verify the clang resource directory is bundled.
# The resource dir is at: cxxdox_plugin/libclang21/clang/<major>/include/
# The major version is derived from the 'libclang21' directory name.
# ---------------------------------------------------------------------------
import re as _re

lc_dir_name = os.path.basename(lc_dir)  # e.g. "libclang21"
major = "".join(c for c in lc_dir_name if c.isdigit())
assert major, f"could not determine clang major version from dir name {lc_dir_name!r}"
print("Expected clang major version:", major)

resource_include_dir = os.path.join(lc_dir, "clang", major, "include")
assert os.path.isdir(resource_include_dir), (
    f"Clang resource include dir is missing from the wheel: {resource_include_dir!r}\n"
    f"Headers such as <stddef.h>, <immintrin.h>, <arm_neon.h> will not be "
    f"found during parsing, producing silently incomplete documentation."
)
print("resource include dir:", resource_include_dir)

# Check for specific critical headers.
for critical_header in ("stddef.h", "stdarg.h"):
    header_path = os.path.join(resource_include_dir, critical_header)
    assert os.path.isfile(header_path), (
        f"Critical builtin header {critical_header!r} is missing from the "
        f"bundled resource dir {resource_include_dir!r}."
    )
    print(f"  found: {critical_header}")

# Spot-check for x86 SIMD headers (if the platform is x86 or if headers are
# present regardless of platform — they should always be in the resource dir).
imm_path = os.path.join(resource_include_dir, "immintrin.h")
if os.path.isfile(imm_path):
    print("  found: immintrin.h (x86 SIMD)")
else:
    # This is not fatal; non-x86 resource dirs may not include it.
    print("  NOTE: immintrin.h not found (may be expected on non-x86 builds)")

# ---------------------------------------------------------------------------
# Verify the mkdocs plugin entry point is registered.
# ---------------------------------------------------------------------------
eps = entry_points(group="mkdocs.plugins")
names = [ep.name for ep in eps]
assert "cxxdox" in names, f"cxxdox entry point missing; got {names}"
print("mkdocs.plugins entry points:", names)

# ---------------------------------------------------------------------------
# Verify the parser module imports and exposes the resource-dir args.
# ---------------------------------------------------------------------------
from cxxdox_plugin.parser import _RESOURCE_DIR_ARGS, _CLANG_MAJOR, _LIBCLANG_DIR
print("CLANG_MAJOR from parser:", _CLANG_MAJOR)
print("_RESOURCE_DIR_ARGS from parser:", _RESOURCE_DIR_ARGS)
assert _RESOURCE_DIR_ARGS, (
    "parser._RESOURCE_DIR_ARGS is empty — the bundled resource dir was not "
    "found at import time. The wheel is broken."
)
assert _RESOURCE_DIR_ARGS[0] == "-resource-dir", (
    f"Expected '-resource-dir' as first element, got {_RESOURCE_DIR_ARGS!r}"
)
rdir = _RESOURCE_DIR_ARGS[1]
assert os.path.isdir(rdir), f"resource dir from parser does not exist: {rdir!r}"
print("parser resolved resource dir:", rdir)

print("OK: wheel installs and loads cleanly on", sys.platform)
