"""Smoke-test for a freshly installed mkdocs-cxxdox wheel.

Verifies that:
  * the package imports,
  * a platform-specific libclang binary is bundled inside the package, and
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

# Verify the mkdocs plugin entry point is registered.
eps = entry_points(group="mkdocs.plugins")
names = [ep.name for ep in eps]
assert "cxxdox" in names, f"cxxdox entry point missing; got {names}"
print("mkdocs.plugins entry points:", names)

print("OK: wheel installs and loads cleanly on", sys.platform)
