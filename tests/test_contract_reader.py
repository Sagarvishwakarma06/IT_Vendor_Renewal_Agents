"""Tests for contract_reader.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.contract_reader import read_contract, SUPPORTED_EXTENSIONS


class TestReadContract:
    """Tests for the read_contract() function."""

    def test_read_valid_txt(self, tmp_path):
        """A valid TXT file should be read successfully."""
        f = tmp_path / "test.txt"
        f.write_text("Vendor: TestCorp\nContract Start Date: 1 January 2024", encoding="utf-8")
        result = read_contract(f)
        assert result.success is True
        assert "TestCorp" in result.text
        assert result.error == ""

    def test_missing_file_returns_failure(self, tmp_path):
        """A non-existent file should return success=False and a clear error."""
        result = read_contract(tmp_path / "nonexistent.txt")
        assert result.success is False
        assert "not found" in result.error.lower()
        assert result.text == ""

    def test_empty_txt_returns_failure(self, tmp_path):
        """An empty TXT file should return success=False."""
        f = tmp_path / "empty.txt"
        f.write_text("   \n  \n", encoding="utf-8")
        result = read_contract(f)
        assert result.success is False
        assert "empty" in result.error.lower() or result.warnings

    def test_unsupported_extension_returns_failure(self, tmp_path):
        """A .csv file should be rejected as unsupported."""
        f = tmp_path / "bad.csv"
        f.write_text("some,data", encoding="utf-8")
        result = read_contract(f)
        assert result.success is False
        assert "unsupported" in result.error.lower()

    def test_source_file_preserved(self, tmp_path):
        """The source_file attribute should be the input path."""
        f = tmp_path / "contract.txt"
        f.write_text("Vendor: Alpha", encoding="utf-8")
        result = read_contract(f)
        assert result.source_file == f

    def test_result_repr_contains_filename(self, tmp_path):
        """__repr__ should include the filename."""
        f = tmp_path / "mycontract.txt"
        f.write_text("Some content", encoding="utf-8")
        result = read_contract(f)
        assert "mycontract.txt" in repr(result)

    def test_directory_path_returns_failure(self, tmp_path):
        """Passing a directory instead of a file should return failure."""
        result = read_contract(tmp_path)
        assert result.success is False

    def test_supported_extensions_set(self):
        """The supported extensions should include .txt, .pdf, .docx."""
        assert ".txt" in SUPPORTED_EXTENSIONS
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS


class TestReadContractSampleFiles:
    """Tests against the real sample contract files."""

    def test_vendora_contract_readable(self):
        path = Path("data/contracts/VendorA_Contract.txt")
        if not path.exists():
            pytest.skip("Sample file not found")
        result = read_contract(path)
        assert result.success is True
        assert "VendorA" in result.text or "Vendor" in result.text

    def test_vendorb_contract_readable(self):
        path = Path("data/contracts/VendorB_Contract.txt")
        if not path.exists():
            pytest.skip("Sample file not found")
        result = read_contract(path)
        assert result.success is True
        assert len(result.text) > 100
