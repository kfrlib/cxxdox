import unittest

from cxxdox_plugin.doxygen import doxygen_to_html
from cxxdox_plugin.index import Index


class DoxygenRenderingTests(unittest.TestCase):
    def test_renders_doxygen_code_without_snippet_marker_processing(self) -> None:
        html = doxygen_to_html(
            [{"code": "int hidden;|||\n|||int shown;"}],
            Index(),
            "",
            lambda link: link,
        )

        self.assertEqual(
            html,
            '<pre><code class="language-cpp">int hidden;|||\n|||int shown;</code></pre>',
        )


if __name__ == "__main__":
    unittest.main()
