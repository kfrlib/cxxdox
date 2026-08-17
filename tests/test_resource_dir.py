"""Tests for the clang resource-directory bundling and resolution logic.

These tests validate the behaviour of the resource-dir detection code that
lives in cxxdox_plugin/parser.py.  They run both in a plain source checkout
(where the resource headers may not be present) and after installing a built
wheel (where they must be present).

The suite is deliberately split into:
  - unit tests that always pass regardless of whether headers are present, and
  - integration tests (prefixed _wheel_*) that are skipped unless the package
    is installed as a wheel with bundled headers.
"""

import importlib
import os
import sys
import unittest
from pathlib import Path


class TestResourceDirHelpers(unittest.TestCase):
    """Unit-test the helper functions in parser.py."""

    def setUp(self) -> None:
        # Reload the module each time to reset any cached state.
        import cxxdox_plugin.parser as _m
        self._mod = _m

    def test_clang_major_is_digit_string(self) -> None:
        major = self._mod._CLANG_MAJOR
        self.assertTrue(major.isdigit(), f"CLANG_MAJOR should be all digits, got {major!r}")
        self.assertGreater(int(major), 0, "CLANG_MAJOR should be a positive integer")

    def test_libclang_dir_points_to_libclang21(self) -> None:
        lc_dir = self._mod._LIBCLANG_DIR
        self.assertTrue(os.path.isdir(lc_dir), f"_LIBCLANG_DIR should exist: {lc_dir!r}")
        self.assertEqual(os.path.basename(lc_dir), "libclang21")

    def test_resource_dir_args_is_list(self) -> None:
        args = self._mod._RESOURCE_DIR_ARGS
        self.assertIsInstance(args, list)

    def test_resource_dir_args_format_if_found(self) -> None:
        """If a resource dir was found, the args must be ['-resource-dir', <path>]."""
        args = self._mod._RESOURCE_DIR_ARGS
        if args:
            self.assertEqual(len(args), 2, "Resource dir args must have exactly 2 elements")
            self.assertEqual(args[0], "-resource-dir")
            rdir = args[1]
            self.assertTrue(os.path.isdir(rdir),
                            f"The -resource-dir path must exist: {rdir!r}")

    def test_find_bundled_resource_dir_returns_none_or_str(self) -> None:
        result = self._mod._find_bundled_resource_dir()
        self.assertIn(type(result), (type(None), str))

    def test_validate_resource_dir_rejects_nonexistent(self) -> None:
        self.assertFalse(
            self._mod._validate_resource_dir("/nonexistent/path/that/does/not/exist")
        )

    def test_validate_resource_dir_rejects_dir_without_stddef(self, tmp_path=None) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # A directory without include/stddef.h should fail validation
            include_dir = os.path.join(tmpdir, "include")
            os.makedirs(include_dir)
            # Put a random file in there but NOT stddef.h
            open(os.path.join(include_dir, "something_else.h"), "w").close()
            self.assertFalse(self._mod._validate_resource_dir(tmpdir))

    def test_validate_resource_dir_accepts_dir_with_stddef(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            include_dir = os.path.join(tmpdir, "include")
            os.makedirs(include_dir)
            open(os.path.join(include_dir, "stddef.h"), "w").close()
            self.assertTrue(self._mod._validate_resource_dir(tmpdir))


class TestResourceDirBundled(unittest.TestCase):
    """Tests that only pass when the wheel has been built with bundled headers.

    These are skipped automatically in a plain source checkout.
    """

    def setUp(self) -> None:
        import cxxdox_plugin.parser as _m
        self._mod = _m
        self._bundled = _m._find_bundled_resource_dir()

    def _skip_if_not_bundled(self) -> None:
        if not self._bundled or not self._mod._validate_resource_dir(self._bundled):
            self.skipTest(
                "Bundled clang resource headers not present. "
                "Run this test after building the wheel with 'python -m build' "
                "and installing it."
            )

    def test_wheel_has_stddef_h(self) -> None:
        self._skip_if_not_bundled()
        stddef = os.path.join(self._bundled, "include", "stddef.h")
        self.assertTrue(os.path.isfile(stddef),
                        f"stddef.h must be present in the bundled resource dir: {stddef!r}")

    def test_wheel_has_stdarg_h(self) -> None:
        self._skip_if_not_bundled()
        stdarg = os.path.join(self._bundled, "include", "stdarg.h")
        self.assertTrue(os.path.isfile(stdarg),
                        f"stdarg.h must be present in the bundled resource dir: {stdarg!r}")

    def test_wheel_resource_dir_args_are_set(self) -> None:
        self._skip_if_not_bundled()
        args = self._mod._RESOURCE_DIR_ARGS
        self.assertEqual(args[0], "-resource-dir",
                         "When bundled headers are present, -resource-dir must be in args")
        self.assertEqual(args[1], self._bundled)

    def test_wheel_resource_dir_is_inside_package(self) -> None:
        """The resource dir must be *inside* the installed package, not a system path."""
        self._skip_if_not_bundled()
        pkg_dir = os.path.dirname(os.path.dirname(self._mod.__file__))
        rdir = self._bundled
        # Normalise paths to compare correctly on all platforms
        pkg_real = os.path.realpath(pkg_dir)
        rdir_real = os.path.realpath(rdir)
        self.assertTrue(
            rdir_real.startswith(pkg_real),
            f"Resource dir {rdir_real!r} is not inside the package dir {pkg_real!r}. "
            f"Are you using a system clang instead of the bundled one?"
        )

    def test_wheel_parser_prepends_resource_dir(self) -> None:
        """Parser.__init__ must prepend -resource-dir before user's compile_options."""
        self._skip_if_not_bundled()
        from cxxdox_plugin.parser import Parser
        from cxxdox_plugin.index import Index
        user_args = ["-std=c++20", "-Ifoo"]
        p = Parser(Index(), clang_args=user_args)
        self.assertGreaterEqual(len(p.clang_args), 2 + len(user_args))
        self.assertEqual(p.clang_args[0], "-resource-dir",
                         "Parser.clang_args must start with -resource-dir")
        # User args must still be there, after the resource-dir prepend
        for ua in user_args:
            self.assertIn(ua, p.clang_args,
                          f"User arg {ua!r} must be preserved in Parser.clang_args")


if __name__ == "__main__":
    unittest.main()
