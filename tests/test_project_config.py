"""Tests for project configuration files (requirements.txt, .gitignore, pyproject.toml)."""

import ast
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestRequirementsTxt:
    """Verify requirements.txt contains all necessary dependencies."""

    def test_requirements_has_runtime_deps(self):
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        required = ["curl_cffi", "fastapi", "uvicorn", "pydantic", "python-dotenv"]
        for dep in required:
            assert dep in content, f"Missing runtime dependency: {dep}"

    def test_requirements_has_test_deps(self):
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        required = ["pytest", "pytest-asyncio", "starlette"]
        for dep in required:
            assert dep in content, f"Missing test dependency: {dep}"


class TestGitignore:
    """Verify .gitignore properly excludes sensitive files."""

    def test_gitignore_exists(self):
        assert (PROJECT_ROOT / ".gitignore").exists()

    def test_gitignore_ignores_env(self):
        content = (PROJECT_ROOT / ".gitignore").read_text()
        lines = content.strip().splitlines()
        # Must have an exact ".env" line (not just as part of ".env.example")
        env_lines = [l.strip() for l in lines if l.strip() == ".env"]
        assert env_lines, ".gitignore must have an explicit '.env' line"

    def test_gitignore_ignores_pycache(self):
        content = (PROJECT_ROOT / ".gitignore").read_text()
        assert "__pycache__" in content

    def test_gitignore_allows_env_example(self):
        content = (PROJECT_ROOT / ".gitignore").read_text()
        assert ".env.example" in content

    def test_gitignore_allows_requirements(self):
        """requirements.txt must NOT be blocked by .gitignore."""
        content = (PROJECT_ROOT / ".gitignore").read_text()
        lines = content.strip().splitlines()
        has_broad_txt = any(l.strip() == "*.txt" for l in lines)
        assert not has_broad_txt, (
            ".gitignore uses overly broad *.txt which blocks LICENSE.txt, "
            "CHANGELOG.txt, etc. Use specific cookie patterns instead."
        )
        # requirements.txt should not appear in a negation exception
        # since it's not blocked in the first place
        assert "!requirements.txt" not in content, (
            "No need for !requirements.txt exception if *.txt is not used"
        )

    def test_gitignore_blocks_cookie_files(self):
        """Cookie files must be ignored to prevent credential leaks."""
        content = (PROJECT_ROOT / ".gitignore").read_text()
        cookie_patterns = ["cookies", "_cookies.txt", "_magnific.txt"]
        has_cookie_pattern = any(p in content for p in cookie_patterns)
        assert has_cookie_pattern, (
            ".gitignore must have specific patterns to block cookie files"
        )


class TestPyprojectToml:
    """Verify pyproject.toml exists with basic project metadata."""

    def test_pyproject_toml_exists(self):
        assert (PROJECT_ROOT / "pyproject.toml").exists(), "pyproject.toml must exist"

    def test_pyproject_has_project_name(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        assert "[project]" in content or "name" in content

    def test_pyproject_build_backend_is_valid(self):
        """pyproject.toml must use a valid build-backend path."""
        import tomllib
        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        backend = data.get("build-system", {}).get("build-backend", "")
        valid_backends = [
            "setuptools.build_meta",
            "setuptools.build_meta:__legacy__",
            "hatchling.build",
            "flit_core.buildapi",
        ]
        assert backend in valid_backends, (
            f"Invalid build-backend: {backend!r}. Must be one of: {valid_backends}"
        )


class TestRouteCodeQuality:
    """Verify route files follow code quality standards."""

    ROUTE_FILES = [
        PROJECT_ROOT / "api" / "routes" / "image.py",
        PROJECT_ROOT / "api" / "routes" / "video.py",
        PROJECT_ROOT / "api" / "routes" / "status.py",
    ]

    def test_no_assert_in_route_handlers(self):
        """Route handlers must use explicit if+raise, not assert (stripped with python -O)."""
        for filepath in self.ROUTE_FILES:
            tree = ast.parse(filepath.read_text())
            asserts = [
                (node.lineno, ast.unparse(node))
                for node in ast.walk(tree)
                if isinstance(node, ast.Assert)
            ]
            assert not asserts, (
                f"{filepath.name} contains assert statements that would be "
                f"stripped with python -O. Use if + raise HTTPException instead. "
                f"Found at lines: {[a[0] for a in asserts]}"
            )

    def test_routes_import_http_exception(self):
        """Route files that raise HTTPException must import it."""
        for filepath in self.ROUTE_FILES:
            tree = ast.parse(filepath.read_text())
            source = filepath.read_text()
            # If file has raise HTTPException, it must import it
            if "HTTPException" in source:
                assert "from fastapi import" in source and "HTTPException" in source, (
                    f"{filepath.name} uses HTTPException but doesn't import it"
                )

    def test_no_dead_code_in_sync_wrappers(self):
        """Sync wrappers decorated with retry must not have unreachable _client None guards.
        The caller (async handler) already checks this. Use type: ignore instead."""
        for filepath in self.ROUTE_FILES:
            tree = ast.parse(filepath.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for deco in node.decorator_list:
                        if "retry_with_backoff" in ast.unparse(deco):
                            for stmt in node.body:
                                if isinstance(stmt, ast.If):
                                    test_str = ast.unparse(stmt.test)
                                    if "_client" in test_str and "None" in test_str:
                                        assert False, (
                                            f"{filepath.name}:{node.name}:{stmt.lineno} has "
                                            f"unreachable _client None guard inside sync wrapper. "
                                            f"The caller already validates deps. Remove and use type: ignore."
                                        )


class TestCORSConfig:
    """Verify CORS configuration follows security best practices."""

    def test_cors_no_wildcard_with_credentials(self):
        """CORS must not use allow_origins=['*'] with allow_credentials=True."""
        server_src = (PROJECT_ROOT / "api" / "server.py").read_text()
        lines = server_src.split("\n")
        has_wildcard = any('allow_origins' in l and '"*"' in l for l in lines)
        has_credentials = any('allow_credentials' in l and 'True' in l for l in lines)
        assert not (has_wildcard and has_credentials), (
            "CORS uses allow_origins=['*'] with allow_credentials=True. "
            "Per CORS spec, this is invalid — use specific origins instead."
        )


class TestSSEAsync:
    """Verify SSE endpoint streams progressively without blocking."""

    def test_sse_uses_async_poller(self):
        """SSE must use async_poll_creation_stream with async for — not list() on sync generator."""
        import ast
        status_src = (PROJECT_ROOT / "api" / "routes" / "status.py").read_text()
        tree = ast.parse(status_src)

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "stream_status":
                func_src = ast.unparse(node)

                # Must NOT use list() to consume generator
                assert not ("list(" in func_src and "poll_creation_stream" in func_src), (
                    "SSE must NOT use list() on poll_creation_stream — defeats streaming"
                )

                # Must use async_poll_creation_stream
                assert "async_poll_creation_stream" in func_src, (
                    "SSE must use async_poll_creation_stream for progressive updates"
                )

                # Must have async for loop
                assert "async for" in func_src, (
                    "SSE must iterate with 'async for' to yield progressively"
                )
                return

        assert False, "stream_status function not found in status.py"

    def test_poller_has_async_method(self):
        """Poller class must have async_poll_creation_stream async generator method."""
        import inspect
        from core.poller import Poller
        assert hasattr(Poller, "async_poll_creation_stream"), (
            "Poller must have async_poll_creation_stream method"
        )
        method = getattr(Poller, "async_poll_creation_stream")
        assert inspect.isasyncgenfunction(method), (
            "async_poll_creation_stream must be an async generator function"
        )


class TestCLIOptions:
    """Verify CLI has all necessary options."""

    def test_serve_has_cookies_dict(self):
        """serve command must support --cookies-dict for inline cookie passing."""
        main_src = (PROJECT_ROOT / "main.py").read_text()
        assert "--cookies-dict" in main_src, (
            "serve command must have --cookies-dict option"
        )
        assert "cookies_dict" in main_src, (
            "cmd_serve must handle cookies_dict parameter"
        )


class TestAsyncIOThreadWrapping:
    """Verify all I/O calls in async handlers are wrapped in asyncio.to_thread.

    Direct I/O calls in async handlers block the event loop. All calls to
    _client.post/get, _poller.poll_creation, _uploader.upload_*, and
    FileHelpers.file_to_base64 must be wrapped in asyncio.to_thread().
    """

    ROUTE_FILES = [
        PROJECT_ROOT / "api" / "routes" / "image.py",
        PROJECT_ROOT / "api" / "routes" / "video.py",
        PROJECT_ROOT / "api" / "routes" / "status.py",
    ]

    # Patterns that indicate direct I/O in async handlers
    IO_PATTERNS = [
        "_client.get(",
        "_client.post(",
        "_client.download(",
        "_poller.poll_creation(",
        "_uploader.upload_reference_frame(",
        "_uploader.upload_video_audio(",
        "_uploader.upload_temporal(",
        "_uploader.upload_frame(",
        "FileHelpers.file_to_base64(",
    ]

    def test_no_direct_io_in_async_handlers(self):
        """All I/O calls inside async def must be wrapped in asyncio.to_thread."""
        violations = []
        for filepath in self.ROUTE_FILES:
            tree = ast.parse(filepath.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef):
                    func_src = ast.unparse(node)
                    for pattern in self.IO_PATTERNS:
                        # Check if the pattern appears in the function source
                        if pattern in func_src:
                            # Check if it's NOT inside an asyncio.to_thread call
                            # by verifying there's no asyncio.to_thread( on the same line
                            # or that the pattern is not preceded by asyncio.to_thread
                            source_lines = filepath.read_text().split("\n")
                            for lineno in range(node.lineno - 1, node.end_lineno):
                                line = source_lines[lineno] if lineno < len(source_lines) else ""
                                if pattern in line:
                                    # This is a violation if not wrapped in to_thread
                                    # Look for asyncio.to_thread wrapping on same or previous line
                                    is_wrapped = False
                                    for check_line in source_lines[max(0, lineno - 2):lineno + 1]:
                                        if "asyncio.to_thread" in check_line:
                                            is_wrapped = True
                                            break
                                    if not is_wrapped:
                                        violations.append(
                                            f"{filepath.name}:{lineno + 1} has unwrapped "
                                            f"I/O call '{pattern.rstrip('(')}' in async handler "
                                            f"'{node.name}' — wrap in asyncio.to_thread()"
                                        )

        assert not violations, (
            f"Found {len(violations)} direct I/O call(s) in async handlers:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestNoMockImports:
    """Verify no test files import unittest.mock — permanent guard.

    Per PDCA Cycle 4 working agreement: 'No unittest.mock' rule.
    All tests must use real objects, lightweight fakes, or TestClient.
    """

    def test_no_unittest_mock_in_tests(self):
        """No test file should import from unittest.mock."""
        test_dir = PROJECT_ROOT / "tests"
        violations = []
        for test_file in sorted(test_dir.glob("test_*.py")):
            source = test_file.read_text()
            lines = source.split("\n")
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Check for import statements
                if stripped.startswith("from unittest.mock import"):
                    violations.append(
                        f"{test_file.name}:{i + 1} has '{stripped}'"
                    )
                elif stripped.startswith("import unittest.mock"):
                    violations.append(
                        f"{test_file.name}:{i + 1} has '{stripped}'"
                    )

        assert not violations, (
            f"Found {len(violations)} unittest.mock import(s) in test files:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\nUse real objects, lightweight fakes (tests.helpers.fake_deps), "
            "or TestClient instead."
        )
