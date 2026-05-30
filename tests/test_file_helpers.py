"""Tests for utils/file_helpers.py — FileHelpers class."""

import pytest

from utils.file_helpers import FileHelpers


class TestFileNotFoundRaisesError:
    """Called Shot 1: Converting non-existent file to base64 raises FileNotFoundError."""

    def test_file_not_found_raises_error(self):
        with pytest.raises(FileNotFoundError):
            FileHelpers.file_to_base64("/nonexistent/path/file.jpg")


class TestRoundtripBase64:
    """Called Shot 2: file_to_base64 → base64_to_bytes preserves original bytes."""

    def test_roundtrip_base64(self, tmp_path):
        # Create a temp file with known content
        original = b"Hello, Magnific API! \x89PNG\r\n\x1a\n"  # some bytes
        test_file = tmp_path / "test.png"
        test_file.write_bytes(original)

        # Round-trip
        b64_uri = FileHelpers.file_to_base64(str(test_file))
        recovered = FileHelpers.base64_to_bytes(b64_uri)

        assert recovered == original


class TestBase64ToBytesInvalidFormat:
    """Called Shot 3: Invalid base64 URI raises ValueError."""

    def test_base64_to_bytes_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid base64 data URI"):
            FileHelpers.base64_to_bytes("not-a-valid-data-uri")

        with pytest.raises(ValueError):
            FileHelpers.base64_to_bytes("data:application/octet-stream;base64,")

        with pytest.raises(ValueError):
            FileHelpers.base64_to_bytes("")


class TestParseReferenceInputWithLabel:
    """Called Shot 4: 'file.jpg|mylabel' → {"source": "file.jpg", "name": "mylabel"}."""

    def test_parse_reference_input_with_label(self):
        result = FileHelpers.parse_reference_input("file.jpg|mylabel")
        assert result == {"source": "file.jpg", "name": "mylabel"}


class TestParseReferenceInputWithoutLabel:
    """Called Shot 5: 'file.jpg' → {"source": "file.jpg", "name": None}."""

    def test_parse_reference_input_without_label(self):
        result = FileHelpers.parse_reference_input("file.jpg")
        assert result == {"source": "file.jpg", "name": None}


class TestIsUrl:
    """Called Shot 6: http/https URLs return True, other strings return False."""

    def test_is_url(self):
        assert FileHelpers.is_url("https://example.com/path") is True
        assert FileHelpers.is_url("http://localhost:8000/api") is True
        assert FileHelpers.is_url("file.jpg") is False
        assert FileHelpers.is_url("ftp://files.server.com") is False
        assert FileHelpers.is_url("") is False
        assert FileHelpers.is_url("data:image/png;base64,abc") is False
