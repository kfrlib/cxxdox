from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cxxdox_plugin.snippets import (
    SnippetWriter,
    clean_snippets_directory,
    dump_snippet,
    extract_directory,
    extract_fenced_code,
    extract_fenced_code_with_locations,
    render_fenced_code,
    render_snippet,
)
from cxxdox_plugin.config import CxxDoxConfig


class SnippetExtractionTests(unittest.TestCase):
    def test_render_marker_processing_is_enabled_by_default(self) -> None:
        config = CxxDoxConfig()
        config.load_dict({"input": []})

        self.assertTrue(config["render_snippet_markers"])

    def test_render_marker_processing_can_be_disabled(self) -> None:
        config = CxxDoxConfig()
        config.load_dict({"input": [], "render_snippet_markers": False})

        self.assertFalse(config["render_snippet_markers"])

    def test_cleans_existing_snippet_directory(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            snippets_directory = Path(temporary_directory) / "snippets"
            snippets_directory.mkdir()
            (snippets_directory / "stale.cpp").write_text("stale", encoding="utf-8")

            clean_snippets_directory(snippets_directory)

            self.assertEqual(list(snippets_directory.iterdir()), [])

    def test_rejects_file_as_snippet_directory(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "snippets"
            output_path.write_text("not a directory", encoding="utf-8")

            with self.assertRaises(ValueError):
                clean_snippets_directory(output_path)

    def test_renders_snippet_parts(self) -> None:
        self.assertEqual(
            render_snippet(
                "int retained;\n"
                "int rendered;|||\n"
                "|||int dumped;\n"
                "int shown;|||int dumped_too;\n"
            ),
            "int retained;\n"
            "int rendered;\n"
            "int shown;\n",
        )

    def test_dumps_snippet_parts(self) -> None:
        self.assertEqual(
            dump_snippet(
                "int retained;\n"
                "int rendered;|||\n"
                "|||int dumped;\n"
                "int shown;|||int dumped_too;\n"
            ),
            "int retained;\n"
            "int dumped;\n"
            "int dumped_too;\n",
        )

    def test_pipe_markers_make_a_region_render_only(self) -> None:
        content = (
            "    ||||||||||||\n"
            "    template <typename T, size_t N>\n"
            "    struct vec {};\n"
            "    |||||||||||| \n"
            "    void fn(vec<T, N>) {}\n"
        )

        self.assertEqual(
            render_snippet(content),
            "template <typename T, size_t N>\n"
            "struct vec {};\n"
            "void fn(vec<T, N>) {}\n",
        )
        self.assertEqual(dump_snippet(content), "void fn(vec<T, N>) {}\n")

    def test_removes_common_snippet_indentation_before_processing(self) -> None:
        content = (
            "    int outer() {\n"
            "        return 42;\n"
            "    }\n"
        )

        expected = "int outer() {\n    return 42;\n}\n"
        self.assertEqual(render_snippet(content), expected)
        self.assertEqual(dump_snippet(content), expected)

    def test_ignores_separator_like_text_without_a_complete_separator(self) -> None:
        content = 'print("||");\n'

        self.assertEqual(render_snippet(content), content)

    def test_preserves_crlf_line_endings(self) -> None:
        content = "int rendered;|||int dumped;\r\n"

        self.assertEqual(render_snippet(content), "int rendered;\r\n")
        self.assertEqual(dump_snippet(content), "int dumped;\r\n")

    def test_extracts_only_complete_cxx_fences(self) -> None:
        markdown = (
            "Before\n"
            "```c++\n"
            "int first;\n"
            "```\n"
            "```c\n"
            "int second;\n"
            "```\n"
            "````\n"
            "not extracted\n"
            "````\n"
            "```cpp\n"
            "also not extracted\n"
            "```\n"
            "~~~c++\n"
            "still not extracted\n"
            "~~~\n"
            "```\n"
            "unfinished\n"
        )

        self.assertEqual(
            extract_fenced_code(markdown),
            ["int first;\n", "int second;\n"],
        )
        self.assertEqual(
            extract_fenced_code_with_locations(markdown),
            [("int first;\n", 2), ("int second;\n", 5)],
        )

    def test_extracts_cxx_fences_with_parameters(self) -> None:
        markdown = (
            "```c++ linenums=\"1\"\n"
            "int numbered;\n"
            "```\n"
            "```c title=\"Example\"\n"
            "int titled;\n"
            "```\n"
        )

        self.assertEqual(
            extract_fenced_code_with_locations(markdown),
            [("int numbered;\n", 1), ("int titled;\n", 4)],
        )

    def test_renders_parts_in_complete_cxx_fences_only(self) -> None:
        markdown = (
            "Before\n"
            "```c++\n"
            "int hidden;|||\n"
            "|||int shown;\n"
            "```\n"
            "```c++\n"
            "int unfinished;\n"
        )

        self.assertEqual(
            render_fenced_code(markdown),
            "Before\n"
            "```c++\n"
            "int hidden;\n"
            "```\n"
            "```c++\n"
            "int unfinished;\n",
        )

    def test_extracts_markdown_files_to_matching_language_paths(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "docs"
            source.mkdir()
            (source / "guide.md").write_text(
                "```c++\nint first;|||int dumped;\n```\n", encoding="utf-8"
            )
            (source / "nested").mkdir()
            (source / "nested" / "page.md").write_text(
                "```c\nint second;\n```\n", encoding="utf-8"
            )

            extract_directory(source, root / "snippets")

            self.assertEqual(
                (root / "snippets" / "guide.md.cpp").read_text(encoding="utf-8"),
                "// Extracted from guide.md, line 1\nint dumped;\n",
            )
            self.assertEqual(
                (root / "snippets" / "nested" / "page.md.c").read_text(encoding="utf-8"),
                "// Extracted from nested/page.md, line 1\nint second;\n",
            )
            self.assertFalse((root / "snippets" / "nested" / "page.md.cpp").exists())

    def test_separates_c_and_cpp_snippets_from_one_page(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "docs"
            source.mkdir()
            (source / "page.md").write_text(
                "```c\nint c_value;\n```\n"
                "```c++\nint cpp_value;\n```\n",
                encoding="utf-8",
            )

            self.assertEqual(extract_directory(source, root / "snippets"), (1, 1))

            self.assertEqual(
                (root / "snippets" / "page.md.c").read_text(encoding="utf-8"),
                "// Extracted from page.md, line 1\nint c_value;\n",
            )
            self.assertEqual(
                (root / "snippets" / "page.md.cpp").read_text(encoding="utf-8"),
                "// Extracted from page.md, line 4\nint cpp_value;\n",
            )

    def test_extract_directory_rejects_missing_source_directory(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                extract_directory(Path(temporary_directory) / "missing", Path(temporary_directory) / "snippets")

    def test_merges_markdown_fence_snippets_into_one_page_file(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            writer = SnippetWriter(Path(temporary_directory))
            first = writer.write("guide/index.md", "first\n", "guide/index.md", 10)
            second = writer.write("guide/index.md", "second\n", "guide/index.md", 20)
            other = writer.write("reference.md", "other\n", "reference.md", 30)

            self.assertEqual(first, second)
            self.assertEqual(first.relative_to(temporary_directory).as_posix(), "guide/index.md.cpp")
            self.assertEqual(other.relative_to(temporary_directory).as_posix(), "reference.md.cpp")
            self.assertEqual(
                first.read_text(encoding="utf-8"),
                "// Extracted from guide/index.md, line 10\n"
                "first\n"
                "\n"
                "// Extracted from guide/index.md, line 20\n"
                "second\n"
            )

    def test_merges_snippets_by_destination_path(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            writer = SnippetWriter(Path(temporary_directory))

            # Doxygen snippets appearing on different generated pages use
            # their C++ source path as the destination key.
            first = writer.write("include/example.hpp", "first\n", "include/example.hpp", 42)
            second = writer.write("include/example.hpp", "second\n", "include/example.hpp", 99)

            self.assertEqual(first, second)
            self.assertEqual(first.relative_to(temporary_directory).as_posix(), "include/example.hpp.cpp")
            self.assertEqual(
                first.read_text(encoding="utf-8"),
                "// Extracted from include/example.hpp, line 42\n"
                "first\n"
                "\n"
                "// Extracted from include/example.hpp, line 99\n"
                "second\n",
            )

    def test_separates_merged_snippets_without_trailing_newline(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            writer = SnippetWriter(Path(temporary_directory))

            writer.write("guide/index.md", "first", "example.hpp", 10)
            destination = writer.write("guide/index.md", "second", "example.hpp", 20)

            self.assertEqual(
                destination.read_text(encoding="utf-8"),
                "// Extracted from example.hpp, line 10\n"
                "first\n\n"
                "// Extracted from example.hpp, line 20\n"
                "second",
            )

    def test_writer_omits_documentation_only_lines(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            writer = SnippetWriter(Path(temporary_directory))

            destination = writer.write(
                "guide/index.md",
                "int retained;\n"
                "int omitted;|||\n",
                "example.hpp",
                10,
            )

            self.assertEqual(
                destination.read_text(encoding="utf-8"),
                "// Extracted from example.hpp, line 10\n"
                "int retained;\n",
            )

    def test_writer_skips_a_snippet_empty_after_render_only_processing(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            writer = SnippetWriter(directory)

            destination = writer.write(
                "guide/index.md",
                "||||||||||||\n"
                "int shown_only_in_docs;\n"
                "||||||||||||\n",
                "example.hpp",
                10,
            )

            self.assertEqual(destination, directory / "guide" / "index.md.cpp")
            self.assertFalse(destination.exists())
            self.assertEqual(list(directory.iterdir()), [])

    def test_extract_directory_skips_pages_with_only_empty_snippets(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "docs"
            source.mkdir()
            (source / "empty.md").write_text(
                "```c++\n"
                "||||||||||||\n"
                "int shown_only_in_docs;\n"
                "||||||||||||\n"
                "```\n"
                "```c\n"
                "||||||||||||\n"
                "int also_shown_only_in_docs;\n"
                "||||||||||||\n"
                "```\n",
                encoding="utf-8",
            )

            self.assertEqual(extract_directory(source, root / "snippets"), (0, 0))
            self.assertEqual(list((root / "snippets").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
