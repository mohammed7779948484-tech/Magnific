"""User-Agent strings for TLS fingerprint impersonation."""


class UserAgents:
    """Windows User-Agent strings that bypass Cloudflare and give 15 device slots."""

    # The impersonate target for curl_cffi (must match an available browser)
    IMPERSONATE = "chrome136"

    # Chrome 136 on Windows — primary (matches curl_cffi impersonation target)
    CHROME_136_WINDOWS = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    )

    # Fallback UAs
    CHROME_131_WINDOWS = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    DEFAULT = CHROME_136_WINDOWS
