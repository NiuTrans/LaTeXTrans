import unittest

from src.formats.latex.parser import LatexParser
from src.formats.latex.reconstruct import LatexConstructor
from src.formats.latex.utils import get_captionof_pattern


class CaptionOfTests(unittest.TestCase):
    def test_distinct_arguments_and_nested_escaped_braces(self):
        source = r"\captionof{figure}{Different text with \textbf{nested} and \{literal\}}"
        match = get_captionof_pattern().fullmatch(source)
        self.assertIsNotNone(match)
        self.assertEqual(match.group("type"), "{figure}")
        self.assertEqual(match.group("text"), r"{Different text with \textbf{nested} and \{literal\}}")

    def test_star_and_optional_short_caption(self):
        source = r"\captionof*{table}[Short title]{Long \emph{caption}}"
        match = get_captionof_pattern().fullmatch(source)
        self.assertEqual(match.group("command"), "captionof*")
        self.assertEqual(match.group("type"), "{table}")

    def test_unsupported_command_and_unbalanced_arguments_do_not_match(self):
        for source in (r"\captionoffset{figure}{Text}", r"\captionof{figure}{Unclosed", r"\captionof{figure}"):
            with self.subTest(source=source):
                self.assertIsNone(get_captionof_pattern().fullmatch(source))

    def test_parser_extracts_captionof_without_changing_regular_captions(self):
        parser = LatexParser(".", ".")
        source = r"Before \caption{Regular} middle \captionof{figure}{Independent} after"
        result = parser._extract_captions(source)
        self.assertEqual(result, "Before <PLACEHOLDER_CAP_1> middle <PLACEHOLDER_CAP_2> after")
        self.assertEqual([c["cap_type"] for c in parser.captions_json], ["caption", "captionof"])
        self.assertEqual(parser.captions_json[1]["content"], r"\captionof{figure}{Independent}")

    def test_repeated_captionof_occurrences_have_unique_placeholders(self):
        parser = LatexParser(".", ".")
        source = r"\captionof{figure}{Same} \captionof{figure}{Same}"
        result = parser._extract_captions(source)
        self.assertEqual(result, "<PLACEHOLDER_CAP_1> <PLACEHOLDER_CAP_2>")
        self.assertEqual(len(parser.captions_json), 2)

    def recover(self, original, translated):
        match = get_captionof_pattern().fullmatch(original)
        constructor = LatexConstructor([], [{
            "placeholder": "<PLACEHOLDER_CAP_1>",
            "cap_type": match.group("command"),
            "content": original,
            "trans_content": translated,
        }], [], [], [], ".")
        return constructor._revert_captions("<PLACEHOLDER_CAP_1>")

    def test_reconstruction_keeps_valid_translated_caption(self):
        self.assertEqual(self.recover(r"\captionof{figure}{Original}", r"\captionof{figure}{译文}"), r"\captionof{figure}{译文}")
        self.assertEqual(self.recover(r"\captionof*{table}[Short]{Original}", r"\captionof*{table}[简]{译文}"), r"\captionof*{table}[简]{译文}")

    def test_regular_caption_without_type_metadata_remains_compatible(self):
        constructor = LatexConstructor([], [{"placeholder": "CAP", "trans_content": r"\caption{译文}"}], [], [], [], ".")
        self.assertEqual(constructor._revert_captions("CAP"), r"\caption{译文}")

    def test_reconstruction_falls_back_if_model_changes_float_type_or_command(self):
        original = r"\captionof{figure}{Original}"
        for translated in (r"\captionof{图}{译文}", r"\captionof{table}{译文}", r"\captionof*{figure}{译文}", r"\caption{译文}", "Malformed output"):
            with self.subTest(translated=translated):
                self.assertEqual(self.recover(original, translated), original)


if __name__ == "__main__":
    unittest.main()
