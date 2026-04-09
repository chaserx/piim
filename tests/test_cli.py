"""Tests for CLI argument parsing and pipeline."""

import os

import pytest

from piim.cli import build_parser, main


class TestArgParsing:
    def setup_method(self):
        self.parser = build_parser()

    def test_requires_input_files(self):
        with pytest.raises(SystemExit):
            self.parser.parse_args([])

    def test_accepts_single_file(self):
        args = self.parser.parse_args(["file.pdf"])
        assert args.input == ["file.pdf"]

    def test_accepts_multiple_files(self):
        args = self.parser.parse_args(["a.pdf", "b.pdf"])
        assert args.input == ["a.pdf", "b.pdf"]

    def test_default_mask_type(self):
        args = self.parser.parse_args(["file.pdf"])
        assert args.mask_type == "blackbox"

    def test_fake_mask_type(self):
        args = self.parser.parse_args(["--mask-type", "fake", "file.pdf"])
        assert args.mask_type == "fake"

    def test_default_suffix(self):
        args = self.parser.parse_args(["file.pdf"])
        assert args.suffix == "_redacted"

    def test_custom_suffix(self):
        args = self.parser.parse_args(["--suffix", "_clean", "file.pdf"])
        assert args.suffix == "_clean"

    def test_in_place_flag(self):
        args = self.parser.parse_args(["--in-place", "file.pdf"])
        assert args.in_place is True

    def test_default_min_confidence(self):
        args = self.parser.parse_args(["file.pdf"])
        assert args.min_confidence == 0.5

    def test_custom_min_confidence(self):
        args = self.parser.parse_args(["--min-confidence", "0.8", "file.pdf"])
        assert args.min_confidence == 0.8

    def test_seed_flag(self):
        args = self.parser.parse_args(["--seed", "42", "file.pdf"])
        assert args.seed == 42

    def test_verbose_flag(self):
        args = self.parser.parse_args(["--verbose", "file.pdf"])
        assert args.verbose is True


class TestMutualExclusivity:
    def test_in_place_with_output_dir_rejected(self):
        """Validation in main() calls parser.error() -> SystemExit."""
        with pytest.raises(SystemExit):
            main(["--in-place", "--output-dir", "/tmp", "f.pdf"])

    def test_in_place_with_suffix_rejected(self):
        with pytest.raises(SystemExit):
            main(["--in-place", "--suffix", "_clean", "f.pdf"])


class TestPipeline:
    def test_processes_valid_pdf(self, native_text_pdf, tmp_path):
        output = str(tmp_path / "out")
        os.makedirs(output)

        exit_code = main(["--output-dir", output, "--verbose", native_text_pdf])

        assert exit_code == 0
        # Verify output file was created
        expected = os.path.join(output, "native_redacted.pdf")
        assert os.path.exists(expected)

    def test_rejects_non_pdf_file(self, tmp_path):
        non_pdf = str(tmp_path / "test.txt")
        with open(non_pdf, "w") as f:
            f.write("not a pdf")

        exit_code = main([non_pdf])
        assert exit_code == 1

    def test_skips_corrupted_pdf(self, tmp_path):
        bad_pdf = str(tmp_path / "bad.pdf")
        with open(bad_pdf, "w") as f:
            f.write("this is not a valid pdf")

        exit_code = main([bad_pdf])
        # Should not crash, should skip with error
        assert exit_code == 1
