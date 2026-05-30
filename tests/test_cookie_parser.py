"""Tests for utils/cookie_parser.py — CookieParser class."""

import json

import pytest

from utils.cookie_parser import CookieParser


class TestParseNetscapeSkipsEmptyLines:
    """Called Shot 1: Empty lines in Netscape format are skipped."""

    def test_parse_netscape_skips_empty_lines(self, tmp_path):
        cookie_file = tmp_path / "empty.txt"
        cookie_file.write_text("\n\n\n\n")

        parser = CookieParser(str(cookie_file))
        cookies = parser.parse()

        assert cookies == []


class TestParseNetscapeSkipsCommentLines:
    """Called Shot 2: Lines starting with # (but not #HttpOnly_) are comments."""

    def test_parse_netscape_skips_comment_lines(self, tmp_path):
        cookie_file = tmp_path / "comments.txt"
        cookie_file.write_text(
            "# This is a comment\n"
            "# Another comment line\n"
            "#\n"
        )

        parser = CookieParser(str(cookie_file))
        cookies = parser.parse()

        assert cookies == []


class TestParseNetscapeHandlesHttponlyPrefix:
    """Called Shot 3: Lines starting with #HttpOnly_ are valid cookies."""

    def test_parse_netscape_handles_httponly_prefix(self, tmp_path):
        cookie_file = tmp_path / "httponly.txt"
        cookie_file.write_text(
            "#HttpOnly_.magnific.com\tTRUE\t/\tTRUE\t9999999999\tGR_TOKEN\ttest_value\n"
        )

        parser = CookieParser(str(cookie_file))
        cookies = parser.parse()

        assert len(cookies) == 1
        assert cookies[0]["name"] == "GR_TOKEN"
        assert cookies[0]["value"] == "test_value"
        assert cookies[0]["domain"] == ".magnific.com"
        assert cookies[0]["path"] == "/"
        # httpOnly comes from the subdomain flag field (parts[1]), not the prefix.
        # "TRUE" is not a digit, so httpOnly=False per current logic.
        # The #HttpOnly_ prefix is stripped before parsing.
        assert cookies[0]["httpOnly"] is False
        assert cookies[0]["secure"] is True


class TestParseNetscapeSkipsMalformedLines:
    """Called Shot 4: Lines with less than 7 fields are skipped."""

    def test_parse_netscape_skips_malformed_lines(self, tmp_path):
        cookie_file = tmp_path / "malformed.txt"
        cookie_file.write_text(
            "only\tthree\tfields\n"
            ".domain.com\tTRUE\t/\tTRUE\t9999999999\tname\n"  # only 6 fields
        )

        parser = CookieParser(str(cookie_file))
        cookies = parser.parse()

        assert cookies == []


class TestParseNetscapeSkipsStaleCookies:
    """Called Shot 5: Cookies in SKIP_COOKIES set are filtered out."""

    def test_parse_netscape_skips_stale_cookies(self, tmp_path):
        cookie_file = tmp_path / "stale.txt"
        cookie_file.write_text(
            ".magnific.com\tTRUE\t/\tFALSE\t9999999999\tak_bmsc\tstale_value\n"
            ".magnific.com\tTRUE\t/\tFALSE\t9999999999\t_ga\tGA12345\n"
            ".magnific.com\tTRUE\t/\tFALSE\t9999999999\t_gid\tGID67890\n"
            ".magnific.com\tTRUE\t/\tFALSE\t9999999999\t_gat\tGAT11111\n"
            ".magnific.com\tTRUE\t/\tFALSE\t9999999999\tintercom-id\tintercom_id\n"
            ".magnific.com\tTRUE\t/\tFALSE\t9999999999\tph_\tposthog_val\n"
        )

        parser = CookieParser(str(cookie_file))
        cookies = parser.parse()

        assert cookies == []


class TestParseNetscapeValidCookie:
    """Called Shot 6: Valid 7-field Netscape line is parsed correctly."""

    def test_parse_netscape_valid_cookie(self, tmp_path):
        cookie_file = tmp_path / "valid.txt"
        # Format: domain  flag  path  secure  expiration  name  value
        cookie_file.write_text(
            ".magnific.com\tTRUE\t/\tTRUE\t9999999999\tmy_cookie\thello_world\n"
        )

        parser = CookieParser(str(cookie_file))
        cookies = parser.parse()

        assert len(cookies) == 1
        c = cookies[0]
        assert c["name"] == "my_cookie"
        assert c["value"] == "hello_world"
        assert c["domain"] == ".magnific.com"
        assert c["path"] == "/"
        assert c["secure"] is True


class TestParseJsonCookies:
    """Called Shot 7: JSON array of cookie objects is parsed correctly."""

    def test_parse_json_cookies(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        data = [
            {"name": "session_id", "value": "abc123", "domain": ".magnific.com", "path": "/", "httpOnly": True, "secure": True},
            {"name": "lang", "value": "en", "domain": ".magnific.com", "path": "/", "httpOnly": False, "secure": False},
        ]
        cookie_file.write_text(json.dumps(data))

        parser = CookieParser(str(cookie_file))
        cookies = parser.parse()

        assert len(cookies) == 2
        assert cookies[0]["name"] == "session_id"
        assert cookies[0]["value"] == "abc123"
        assert cookies[0]["domain"] == ".magnific.com"
        assert cookies[1]["name"] == "lang"
        assert cookies[1]["value"] == "en"


class TestToCurlCffiDict:
    """Called Shot 8: Parsed cookies are converted to name->value dict."""

    def test_to_curl_cffi_dict(self, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text(
            ".magnific.com\tTRUE\t/\tTRUE\t9999999999\tsession\tsess_123\n"
            ".magnific.com\tTRUE\t/\tTRUE\t9999999999\tuser\tuser_456\n"
        )

        parser = CookieParser(str(cookie_file))
        result = parser.to_curl_cffi_dict()

        assert result == {"session": "sess_123", "user": "user_456"}


class TestFileNotFound:
    """Called Shot 9: Non-existent file raises FileNotFoundError."""

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            CookieParser("/nonexistent/path/cookies.txt")


class TestParseAutoDetectsJsonVsNetscape:
    """Called Shot 10: Parser auto-detects JSON vs Netscape format."""

    def test_parse_auto_detects_json_vs_netscape(self, tmp_path):
        # JSON file
        json_file = tmp_path / "cookies.json"
        json_file.write_text(json.dumps([{"name": "test", "value": "v1"}]))

        # Netscape file
        netscape_file = tmp_path / "cookies.txt"
        netscape_file.write_text(".magnific.com\tTRUE\t/\tTRUE\t9999999999\ttest\tv2\n")

        json_parser = CookieParser(str(json_file))
        json_cookies = json_parser.parse()
        assert len(json_cookies) == 1
        assert json_cookies[0]["name"] == "test"
        assert json_cookies[0]["value"] == "v1"

        netscape_parser = CookieParser(str(netscape_file))
        netscape_cookies = netscape_parser.parse()
        assert len(netscape_cookies) == 1
        assert netscape_cookies[0]["name"] == "test"
        assert netscape_cookies[0]["value"] == "v2"
