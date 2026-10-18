import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.falkordb_client import db_client
from backend.ingestion.importer import import_all_fixtures
from backend.ingestion.external_importer import (
    parse_github_repo_url,
    parse_github_url_details,
    import_github_repo,
    chunk_text_into_evidence
)

client = TestClient(app)
WORKSPACE_ID = "ws_test_github_ingest"


@pytest.fixture(autouse=True)
def setup_test_graph():
    """Ensure tests run against the isolated company_brain_test graph."""
    db_client.reset_graph()
    import_all_fixtures(workspace_id=WORKSPACE_ID)
    yield


def test_url_parser_variants():
    # 1. Standard https URL
    assert parse_github_repo_url("https://github.com/torvalds/linux") == ("torvalds", "linux")
    assert parse_github_repo_url("https://github.com/torvalds/linux.git") == ("torvalds", "linux")
    assert parse_github_repo_url("https://github.com/torvalds/linux/") == ("torvalds", "linux")

    # 2. Short owner/repo format
    assert parse_github_repo_url("facebook/react") == ("facebook", "react")

    # 3. Invalid formats
    assert parse_github_repo_url("https://gitlab.com/owner/repo") is None
    assert parse_github_repo_url("just_a_string") is None

    # 4. Detailed parser with ref
    details = parse_github_url_details("https://github.com/pallets/flask/tree/2.3.x")
    assert details["owner"] == "pallets"
    assert details["repo"] == "flask"
    assert details["ref"] == "2.3.x"


def test_chunk_text_into_evidence_locators():
    sample_text = (
        "Line 1: System initialization sequence.\n"
        "Line 2: Allocating 4GB memory pool.\n\n"
        "Line 4: Connecting to cluster leader on port 9092.\n"
        "Line 5: Verification handshake completed successfully."
    )
    chunks = chunk_text_into_evidence(sample_text)
    assert len(chunks) == 2
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 2
    assert "System initialization" in chunks[0]["excerpt"]

    assert chunks[1]["start_line"] == 4
    assert chunks[1]["end_line"] == 5
    assert "Connecting to cluster leader" in chunks[1]["excerpt"]


def test_nested_files_and_tree_retrieval():
    """Verify recursive tree fetching, nested directories, and FalkorDB storage with line locators."""
    owner = "acme-corp"
    repo = "infra-platform"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {
        "full_name": f"{owner}/{repo}",
        "default_branch": "main",
        "description": "Acme Core Infrastructure Platform",
        "html_url": repo_url
    }

    mock_tree = {
        "sha": "tree_sha_12345",
        "truncated": False,
        "tree": [
            {"path": "README.md", "type": "blob", "size": 350},
            {"path": "docs/architecture/rfc-009.md", "type": "blob", "size": 650},
            {"path": "src/gateway/router.py", "type": "blob", "size": 800},
            {"path": "configs/production.yaml", "type": "blob", "size": 400},
            {"path": "docs", "type": "tree"},  # directory entry should be ignored
        ]
    }

    file_contents = {
        "README.md": "# Infra Platform\nMain entrypoint for cloud clusters.\nManaged by SRE team.",
        "docs/architecture/rfc-009.md": "# RFC-009: Service Mesh\nDefines Envoy proxy routing.\nRequires TLS 1.3.",
        "src/gateway/router.py": "def route_request(req):\n    # Routing logic\n    return 'OK'",
        "configs/production.yaml": "env: production\ncluster_size: 16\nregion: us-east-1"
    }

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        resp.headers = {"content-type": "application/vnd.github.v3+json"}

        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp

        if f"git/trees/main" in url:
            resp.status_code = 200
            resp.json.return_value = mock_tree
            return resp

        for path, content in file_contents.items():
            if f"contents/{path}" in url:
                resp.status_code = 200
                resp.headers = {"content-type": "text/plain"}
                resp.text = content
                return resp

        resp.status_code = 404
        resp.text = "Not Found"
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        result = import_github_repo(repo_url, workspace_id=WORKSPACE_ID, max_files=10)

    assert result["status"] == "INGESTED_SUCCESS"
    assert result["sources_created"] == 4
    assert result["evidence_created"] >= 4
    assert set(result["files_imported"]) == set(file_contents.keys())
    assert len(result["files_failed"]) == 0

    # Verify FalkorDB persistence
    g = db_client.get_graph()
    proj_rows = g.query("""
    MATCH (p:Project {workspace_id: $ws, id: $pid})
    RETURN p.name, p.repo_url, p.default_branch, p.commit_sha
    """, {"ws": WORKSPACE_ID, "pid": result["project_id"]}).result_set

    assert len(proj_rows) == 1
    assert proj_rows[0][0] == f"{owner}/{repo}"
    assert proj_rows[0][1] == repo_url
    assert proj_rows[0][2] == "main"

    # Verify nested source paths and line locators
    src_rows = g.query("""
    MATCH (p:Project {workspace_id: $ws, id: $pid})-[:HAS_SOURCE]->(s:Source)
    RETURN s.path, s.source_type, s.repo_url
    """, {"ws": WORKSPACE_ID, "pid": result["project_id"]}).result_set

    stored_paths = {r[0] for r in src_rows}
    assert "docs/architecture/rfc-009.md" in stored_paths
    assert "src/gateway/router.py" in stored_paths
    assert all(r[1] == "GITHUB_PUBLIC_REPO" for r in src_rows)

    # Verify evidence locator format
    ev_rows = g.query("""
    MATCH (p:Project {workspace_id: $ws, id: $pid})-[:HAS_EVIDENCE]->(ev:Evidence)
    RETURN ev.locator, ev.excerpt, ev.source_uri
    """, {"ws": WORKSPACE_ID, "pid": result["project_id"]}).result_set

    assert len(ev_rows) >= 4
    locators = [r[0] for r in ev_rows]
    assert any("docs/architecture/rfc-009.md#L" in loc for loc in locators)
    assert any("src/gateway/router.py#L" in loc for loc in locators)


def test_stable_reimport_idempotency():
    """Re-importing the same repository must update nodes idempotently without duplicating."""
    owner = "acme-corp"
    repo = "idempotent-repo"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {
        "full_name": f"{owner}/{repo}",
        "default_branch": "main",
        "description": "Idempotent Repo",
        "html_url": repo_url
    }

    mock_tree = {
        "sha": "tree_1",
        "truncated": False,
        "tree": [
            {"path": "README.md", "type": "blob", "size": 100},
            {"path": "docs/guide.md", "type": "blob", "size": 150}
        ]
    }

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        if "git/trees/main" in url:
            resp.status_code = 200
            resp.json.return_value = mock_tree
            return resp
        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        if "README.md" in url:
            resp.status_code = 200
            resp.headers = {"content-type": "text/plain"}
            resp.text = "# Idempotent Test\nFirst line.\nSecond line."
            return resp
        if "guide.md" in url:
            resp.status_code = 200
            resp.headers = {"content-type": "text/plain"}
            resp.text = "# Guide\nStep 1: Check inputs.\nStep 2: Run verification."
            return resp
        resp.status_code = 404
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        res1 = import_github_repo(repo_url, workspace_id=WORKSPACE_ID)
        assert res1["status"] == "INGESTED_SUCCESS"

        g = db_client.get_graph()
        sources_count_1 = g.query("MATCH (s:Source {workspace_id: $ws, repo_url: $url}) RETURN count(s)", {"ws": WORKSPACE_ID, "url": repo_url}).result_set[0][0]
        evidence_count_1 = g.query("MATCH (p:Project {workspace_id: $ws, id: $pid})-[:HAS_EVIDENCE]->(ev) RETURN count(ev)", {"ws": WORKSPACE_ID, "pid": res1["project_id"]}).result_set[0][0]

        # Re-import identical repository
        res2 = import_github_repo(repo_url, workspace_id=WORKSPACE_ID)
        assert res2["status"] == "INGESTED_SUCCESS"

        sources_count_2 = g.query("MATCH (s:Source {workspace_id: $ws, repo_url: $url}) RETURN count(s)", {"ws": WORKSPACE_ID, "url": repo_url}).result_set[0][0]
        evidence_count_2 = g.query("MATCH (p:Project {workspace_id: $ws, id: $pid})-[:HAS_EVIDENCE]->(ev) RETURN count(ev)", {"ws": WORKSPACE_ID, "pid": res1["project_id"]}).result_set[0][0]

        # Assert no duplicate nodes were created
        assert sources_count_1 == sources_count_2
        assert evidence_count_1 == evidence_count_2


def test_skipped_files_binary_and_oversized():
    """Verify that binary extensions and oversized files (> 60KB) are skipped with recorded reasons."""
    owner = "acme-corp"
    repo = "mixed-media-repo"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {
        "full_name": f"{owner}/{repo}",
        "default_branch": "main",
        "description": "Mixed Media Repo",
        "html_url": repo_url
    }

    mock_tree = {
        "sha": "tree_2",
        "truncated": False,
        "tree": [
            {"path": "assets/logo.png", "type": "blob", "size": 15000},
            {"path": "bin/binary_executable.exe", "type": "blob", "size": 25000},
            {"path": "releases/bundle.zip", "type": "blob", "size": 45000},
            {"path": "data/huge_dump.csv", "type": "blob", "size": 150_000},  # Oversized (> 60,000)
            {"path": "README.md", "type": "blob", "size": 200},
            {"path": "docs/spec.md", "type": "blob", "size": 300}
        ]
    }

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        if "git/trees/main" in url:
            resp.status_code = 200
            resp.json.return_value = mock_tree
            return resp
        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        if "README.md" in url:
            resp.status_code = 200
            resp.headers = {"content-type": "text/plain"}
            resp.text = "# Readme\nWelcome."
            return resp
        if "spec.md" in url:
            resp.status_code = 200
            resp.headers = {"content-type": "text/plain"}
            resp.text = "# Spec\nProtocol details."
            return resp
        resp.status_code = 404
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        result = import_github_repo(
            repo_url,
            workspace_id=WORKSPACE_ID,
            max_files=10,
            max_file_size_bytes=60_000
        )

    assert result["status"] == "INGESTED_SUCCESS"
    assert result["sources_created"] == 2
    assert set(result["files_imported"]) == {"README.md", "docs/spec.md"}

    # Verify skipped files list
    skipped = {s["path"]: s["reason"] for s in result["skipped_files"]}
    assert "assets/logo.png" in skipped
    assert skipped["assets/logo.png"] == "BINARY_FILE"
    assert "bin/binary_executable.exe" in skipped
    assert skipped["bin/binary_executable.exe"] == "BINARY_FILE"
    assert "releases/bundle.zip" in skipped
    assert skipped["releases/bundle.zip"] == "BINARY_FILE"
    assert "data/huge_dump.csv" in skipped
    assert "OVERSIZED" in skipped["data/huge_dump.csv"]


def test_partial_failure_handling():
    """When some files fail to download, status must be INGESTION_PARTIAL and detail failed files."""
    owner = "acme-corp"
    repo = "flaky-repo"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {
        "full_name": f"{owner}/{repo}",
        "default_branch": "main",
        "description": "Flaky Repo",
        "html_url": repo_url
    }

    mock_tree = {
        "sha": "tree_3",
        "truncated": False,
        "tree": [
            {"path": "README.md", "type": "blob", "size": 100},
            {"path": "docs/failing_file.md", "type": "blob", "size": 200}
        ]
    }

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        if "git/trees/main" in url:
            resp.status_code = 200
            resp.json.return_value = mock_tree
            return resp
        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        if "README.md" in url:
            resp.status_code = 200
            resp.headers = {"content-type": "text/plain"}
            resp.text = "# Healthy File\nImported successfully."
            return resp
        if "failing_file.md" in url:
            resp.status_code = 500
            resp.text = "Internal Server Error in blob storage"
            return resp
        resp.status_code = 404
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        result = import_github_repo(repo_url, workspace_id=WORKSPACE_ID)

    assert result["status"] == "INGESTION_PARTIAL"
    assert "README.md" in result["files_imported"]
    assert len(result["files_failed"]) == 1
    assert result["files_failed"][0]["path"] == "docs/failing_file.md"
    assert "500" in result["files_failed"][0]["error"]
    assert "Partially imported" in result["message"]


def test_rate_limit_handling():
    """Verify graceful handling when GitHub API rate limit is exceeded."""
    owner = "acme-corp"
    repo = "ratelimited-repo"
    repo_url = f"https://github.com/{owner}/{repo}"

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        resp.status_code = 403
        resp.headers = {"x-ratelimit-remaining": "0"}
        resp.text = '{"message": "API rate limit exceeded for 192.0.2.1."}'
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        result = import_github_repo(repo_url, workspace_id=WORKSPACE_ID)

    assert result["status"] == "INGESTION_FAILED"
    assert result["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert "rate limit exceeded" in result["error"].lower()


def test_missing_or_private_repo():
    """Verify clear error when repository is 404 not found or private."""
    owner = "acme-corp"
    repo = "private-vault"
    repo_url = f"https://github.com/{owner}/{repo}"

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        resp.status_code = 404
        resp.text = '{"message": "Not Found"}'
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        result = import_github_repo(repo_url, workspace_id=WORKSPACE_ID)

    assert result["status"] == "INGESTION_FAILED"
    assert result["error_code"] == "REPO_NOT_FOUND"
    assert "not found or is private" in result["error"].lower()


def test_truncated_tree_flag():
    """Verify that tree truncation from GitHub API (> 100k objects) is preserved in status."""
    owner = "acme-corp"
    repo = "monorepo"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {
        "full_name": f"{owner}/{repo}",
        "default_branch": "main",
        "description": "Monorepo",
        "html_url": repo_url
    }

    mock_tree = {
        "sha": "tree_truncated",
        "truncated": True,  # Flagged by GitHub API
        "tree": [
            {"path": "README.md", "type": "blob", "size": 100}
        ]
    }

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        if "git/trees/main" in url:
            resp.status_code = 200
            resp.json.return_value = mock_tree
            return resp
        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        if "README.md" in url:
            resp.status_code = 200
            resp.headers = {"content-type": "text/plain"}
            resp.text = "# Monorepo\nTop level."
            return resp
        resp.status_code = 404
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        result = import_github_repo(repo_url, workspace_id=WORKSPACE_ID)

    assert result["status"] == "INGESTED_SUCCESS"
    assert result["tree_truncated"] is True
    assert result["repo_metadata"]["tree_truncated"] is True


def test_api_ingest_github_endpoint_flow():
    """Test POST /api/ingest/github endpoint with mocked backend."""
    mock_repo_meta = {
        "full_name": "acme/api-test",
        "default_branch": "main",
        "description": "API Test",
        "html_url": "https://github.com/acme/api-test"
    }

    mock_tree = {
        "sha": "tree_api",
        "truncated": False,
        "tree": [
            {"path": "README.md", "type": "blob", "size": 80}
        ]
    }

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        if "README.md" in url:
            resp.status_code = 200
            resp.headers = {"content-type": "text/plain"}
            resp.text = "# API Test\nEndpoints working."
            return resp
        if "git/trees/main" in url:
            resp.status_code = 200
            resp.json.return_value = mock_tree
            return resp
        if "repos/acme/api-test" in url:
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        resp.status_code = 404
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        res = client.post("/api/ingest/github", json={
            "repo_url": "https://github.com/acme/api-test",
            "workspace_id": WORKSPACE_ID,
            "max_files": 5
        })

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "INGESTED_SUCCESS"
    assert "README.md" in data["files_imported"]
