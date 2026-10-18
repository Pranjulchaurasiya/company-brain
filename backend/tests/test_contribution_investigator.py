import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.falkordb_client import db_client
from backend.ingestion.contribution_investigator import (
    extract_explicit_resolved_issues,
    import_github_engineering_history,
    get_person_contributions
)

client = TestClient(app)
WORKSPACE_ID = "ws_test_contribution_slice"


@pytest.fixture(autouse=True)
def setup_test_graph():
    """Ensure tests run strictly against the isolated company_brain_test graph."""
    db_client.reset_graph()
    db_client.init_schema()
    yield


def test_extract_explicit_resolved_issues_syntax():
    """Verify regex only extracts explicit GitHub closing keywords, not generic mentions."""
    # Explicit single closing keyword
    assert extract_explicit_resolved_issues("Fixes #42") == [("fixes", 42)]
    assert extract_explicit_resolved_issues("Closes #105") == [("closes", 105)]
    assert extract_explicit_resolved_issues("Resolved #7") == [("resolved", 7)]
    assert extract_explicit_resolved_issues("close #88") == [("close", 88)]
    assert extract_explicit_resolved_issues("fixed #19") == [("fixed", 19)]

    # Multiple closing keywords in PR body
    body = "This pull request fixes #101 and closes https://github.com/owner/repo/issues/102. Thanks!"
    matches = extract_explicit_resolved_issues(body)
    assert matches == [("fixes", 101), ("closes", 102)]

    # Non-closing mentions MUST NOT match
    assert extract_explicit_resolved_issues("Discussed in #42 with @alice") == []
    assert extract_explicit_resolved_issues("Assignee: @bob for issue #99") == []
    assert extract_explicit_resolved_issues("Relates to #55 but does not fix it") == []
    assert extract_explicit_resolved_issues(None) == []


def test_import_engineering_history_records_and_graph_persistence():
    """Verify import of public repo history, creating canonical records in FalkorDB."""
    owner = "torvalds"
    repo = "test-kernel"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {
        "name": repo,
        "full_name": f"{owner}/{repo}",
        "default_branch": "main",
        "description": "Kernel repository test",
        "html_url": repo_url
    }

    mock_commits = [
        {
            "sha": "c111111111111111111111111111111111111111",
            "commit": {
                "message": "Init scheduler core",
                "author": {"name": "Linus Torvalds", "email": "torvalds@kernel.org", "date": "2026-01-10T10:00:00Z"},
                "committer": {"name": "Linus Torvalds", "email": "torvalds@kernel.org", "date": "2026-01-10T10:05:00Z"}
            },
            "author": {"login": "torvalds", "id": 1024, "avatar_url": "https://avatars.githubusercontent.com/u/1024", "html_url": "https://github.com/torvalds"},
            "html_url": f"{repo_url}/commit/c11111111111",
            "stats": {"additions": 150, "deletions": 10, "total": 160}
        },
        {
            "sha": "c222222222222222222222222222222222222222",
            "commit": {
                "message": "Fix buffer overflow in net driver. Fixes #101",
                "author": {"name": "Alice Dev", "email": "alice@kernel.org", "date": "2026-01-12T11:00:00Z"},
                "committer": {"name": "Alice Dev", "email": "alice@kernel.org", "date": "2026-01-12T11:00:00Z"}
            },
            "author": {"login": "alice", "id": 2048, "avatar_url": "https://avatars.githubusercontent.com/u/2048", "html_url": "https://github.com/alice"},
            "html_url": f"{repo_url}/commit/c22222222222",
            "stats": {"additions": 25, "deletions": 5, "total": 30}
        }
    ]

    mock_prs = [
        {
            "number": 1,
            "title": "Add net driver fixes",
            "body": "Resolves net driver crash on high packet load. Closes #101",
            "state": "closed",
            "merged_at": "2026-01-13T12:00:00Z",
            "created_at": "2026-01-11T09:00:00Z",
            "updated_at": "2026-01-13T12:00:00Z",
            "closed_at": "2026-01-13T12:00:00Z",
            "html_url": f"{repo_url}/pull/1",
            "user": {"login": "alice", "id": 2048, "avatar_url": "https://avatars.githubusercontent.com/u/2048", "html_url": "https://github.com/alice"},
            "head": {"ref": "patch-net-fix"},
            "base": {"ref": "main"}
        },
        {
            "number": 2,
            "title": "Documentation update",
            "body": "Update README with build instructions. No issue linked.",
            "state": "open",
            "created_at": "2026-01-14T08:00:00Z",
            "updated_at": "2026-01-14T08:00:00Z",
            "html_url": f"{repo_url}/pull/2",
            "user": {"login": "bob", "id": 3096, "avatar_url": "https://avatars.githubusercontent.com/u/3096", "html_url": "https://github.com/bob"},
            "head": {"ref": "docs-readme"},
            "base": {"ref": "main"}
        }
    ]

    mock_issues = [
        {
            "number": 101,
            "title": "Network driver kernel panic under load",
            "body": "Panic occurs when receiving UDP packets > 9000 bytes.",
            "state": "closed",
            "state_reason": "completed",
            "created_at": "2026-01-09T14:00:00Z",
            "updated_at": "2026-01-13T12:00:00Z",
            "closed_at": "2026-01-13T12:00:00Z",
            "html_url": f"{repo_url}/issues/101",
            "user": {"login": "reporter_charlie", "id": 4010, "avatar_url": "https://avatars.githubusercontent.com/u/4010", "html_url": "https://github.com/reporter_charlie"},
            "assignee": {"login": "dave_assignee", "id": 5020, "avatar_url": "https://avatars.githubusercontent.com/u/5020", "html_url": "https://github.com/dave_assignee"},
            "closed_by": {"login": "eve_closer", "id": 6030, "avatar_url": "https://avatars.githubusercontent.com/u/6030", "html_url": "https://github.com/eve_closer"}
        },
        {
            "number": 102,
            "title": "Typo in man page",
            "body": "Minor spelling fix needed in scheduler man page.",
            "state": "open",
            "created_at": "2026-01-10T16:00:00Z",
            "updated_at": "2026-01-10T16:00:00Z",
            "html_url": f"{repo_url}/issues/102",
            "user": {"login": "frank_user", "id": 7040, "avatar_url": "https://avatars.githubusercontent.com/u/7040", "html_url": "https://github.com/frank_user"},
            "assignee": {"login": "dave_assignee", "id": 5020, "avatar_url": "https://avatars.githubusercontent.com/u/5020", "html_url": "https://github.com/dave_assignee"}
        }
    ]

    mock_pr_files = [
        {"filename": "drivers/net/ethernet.c", "status": "modified", "additions": 20, "deletions": 5},
        {"filename": "include/net/driver.h", "status": "modified", "additions": 5, "deletions": 0}
    ]

    mock_pr_reviews = [
        {
            "id": 9991,
            "user": {"login": "torvalds", "id": 1024, "avatar_url": "https://avatars.githubusercontent.com/u/1024", "html_url": "https://github.com/torvalds"},
            "state": "APPROVED",
            "submitted_at": "2026-01-12T15:00:00Z",
            "html_url": f"{repo_url}/pull/1#pullrequestreview-9991"
        }
    ]

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        resp.headers = {"content-type": "application/vnd.github.v3+json", "x-ratelimit-remaining": "50"}

        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp

        if "commits" in url:
            if "c111111111111111111111111111111111111111" in url:
                resp.status_code = 200
                resp.json.return_value = {"files": [{"filename": "kernel/sched/core.c", "status": "added", "additions": 150, "deletions": 10}]}
                return resp
            if "c222222222222222222222222222222222222222" in url:
                resp.status_code = 200
                resp.json.return_value = {"files": [{"filename": "drivers/net/ethernet.c", "status": "modified", "additions": 25, "deletions": 5}]}
                return resp
            resp.status_code = 200
            resp.json.return_value = mock_commits
            return resp

        if "pulls/1/files" in url:
            resp.status_code = 200
            resp.json.return_value = mock_pr_files
            return resp

        if "pulls/1/reviews" in url:
            resp.status_code = 200
            resp.json.return_value = mock_pr_reviews
            return resp

        if "pulls/2/files" in url:
            resp.status_code = 200
            resp.json.return_value = [{"filename": "README.md", "status": "modified", "additions": 10, "deletions": 2}]
            return resp

        if "pulls/2/reviews" in url:
            resp.status_code = 200
            resp.json.return_value = []
            return resp

        if "pulls" in url:
            resp.status_code = 200
            resp.json.return_value = mock_prs
            return resp

        if "issues" in url:
            resp.status_code = 200
            resp.json.return_value = mock_issues
            return resp

        resp.status_code = 404
        resp.text = "Not Found"
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        result = import_github_engineering_history(
            repo_url=repo_url,
            workspace_id=WORKSPACE_ID,
            max_commits=10,
            max_pulls=10,
            max_issues=10
        )

    assert result["status"] == "INGESTED_SUCCESS"
    assert result["counts"]["commits"] == 2
    assert result["counts"]["pull_requests"] == 2
    assert result["counts"]["issues"] == 2
    assert result["counts"]["files"] >= 3
    assert result["counts"]["people"] >= 4
    # PR #1 and Commit 2 both explicitly declare resolution of #101
    assert result["counts"]["resolves_relationships"] >= 1

    # Verify FalkorDB graph persistence
    g = db_client.get_graph()

    # 1. Repository
    repo_rows = g.query("""
    MATCH (r:Repository {workspace_id: $ws, id: $rid})
    RETURN r.name, r.full_name, r.owner, r.default_branch, r.html_url
    """, {"ws": WORKSPACE_ID, "rid": "repo_torvalds_test_kernel"}).result_set
    assert len(repo_rows) == 1
    assert repo_rows[0][0] == repo
    assert repo_rows[0][1] == f"{owner}/{repo}"
    assert repo_rows[0][4] == repo_url

    # 2. People & Authorship
    author_rows = g.query("""
    MATCH (p:Person {workspace_id: $ws, login: 'alice'})-[:AUTHORED_COMMIT]->(c:Commit)
    RETURN c.sha, c.message
    """, {"ws": WORKSPACE_ID}).result_set
    assert len(author_rows) == 1
    assert "Fix buffer overflow" in author_rows[0][1]

    pr_author_rows = g.query("""
    MATCH (p:Person {workspace_id: $ws, login: 'alice'})-[:OPENED_PR]->(pr:PullRequest)
    RETURN pr.number, pr.title, pr.is_merged
    """, {"ws": WORKSPACE_ID}).result_set
    assert len(pr_author_rows) == 1
    assert pr_author_rows[0][0] == 1
    assert pr_author_rows[0][2] is True

    # 3. Reviews
    rev_rows = g.query("""
    MATCH (p:Person {workspace_id: $ws, login: 'torvalds'})-[rev:REVIEWED_PR]->(pr:PullRequest {number: 1})
    RETURN rev.state
    """, {"ws": WORKSPACE_ID}).result_set
    assert len(rev_rows) == 1
    assert rev_rows[0][0] == "APPROVED"

    # 4. Touched Files
    file_rows = g.query("""
    MATCH (pr:PullRequest {workspace_id: $ws, number: 1})-[tf:TOUCHED_FILE]->(f:File)
    RETURN f.path, tf.status, tf.additions
    ORDER BY f.path
    """, {"ws": WORKSPACE_ID}).result_set
    paths = [r[0] for r in file_rows]
    assert "drivers/net/ethernet.c" in paths

    # 5. EXPLICIT RESOLUTION RULE VERIFICATION
    # Rule: "Only create a 'resolves issue' relationship when the GitHub data explicitly supports it. Do not infer that an assignee or closer authored the fix."
    resolves_rows = g.query("""
    MATCH (pr:PullRequest {workspace_id: $ws, number: 1})-[rel:RESOLVES_ISSUE]->(i:Issue)
    RETURN i.number, rel.keyword
    """, {"ws": WORKSPACE_ID}).result_set
    assert len(resolves_rows) == 1
    assert resolves_rows[0][0] == 101

    # PR #2 had NO closing keyword -> must NOT have any RESOLVES_ISSUE edge
    pr2_resolves = g.query("""
    MATCH (pr:PullRequest {workspace_id: $ws, number: 2})-[:RESOLVES_ISSUE]->(i:Issue)
    RETURN i.number
    """, {"ws": WORKSPACE_ID}).result_set
    assert len(pr2_resolves) == 0

    # Negative assertion: dave_assignee and eve_closer MUST NOT be inferred as authoring the fix
    closer_author_rows = g.query("""
    MATCH (p:Person {workspace_id: $ws})-[:AUTHORED_COMMIT]->(c:Commit)
    WHERE p.login IN ['dave_assignee', 'eve_closer']
    RETURN p.login
    """, {"ws": WORKSPACE_ID}).result_set
    assert len(closer_author_rows) == 0

    # Issue #102 had no closing keywords -> no RESOLVES_ISSUE pointing to it
    issue102_resolves = g.query("""
    MATCH (x)-[:RESOLVES_ISSUE]->(i:Issue {workspace_id: $ws, number: 102})
    RETURN x
    """, {"ws": WORKSPACE_ID}).result_set
    assert len(issue102_resolves) == 0


def test_repeat_import_idempotency():
    """Verify that repeating the import produces identical node and relationship counts with zero duplication."""
    owner = "org"
    repo = "idem-repo"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {"name": repo, "full_name": f"{owner}/{repo}", "default_branch": "main", "description": "Idem", "html_url": repo_url}
    mock_commits = [{
        "sha": "a1b2c3d4e5f6789012345678901234567890abcd",
        "commit": {"message": "Single commit", "author": {"name": "Dev", "email": "d@org.com", "date": "2026-02-01T00:00:00Z"}},
        "author": {"login": "dev1", "id": 11, "avatar_url": "", "html_url": ""},
        "html_url": f"{repo_url}/commit/a1b2c3"
    }]
    mock_prs = [{
        "number": 10,
        "title": "PR 10",
        "body": "Fixes #5",
        "state": "closed",
        "created_at": "2026-02-01T01:00:00Z",
        "html_url": f"{repo_url}/pull/10",
        "user": {"login": "dev1", "id": 11}
    }]
    mock_issues = [{
        "number": 5,
        "title": "Bug 5",
        "body": "Bug desc",
        "state": "closed",
        "created_at": "2026-02-01T00:30:00Z",
        "html_url": f"{repo_url}/issues/5",
        "user": {"login": "reporter", "id": 12}
    }]

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        resp.headers = {"content-type": "application/vnd.github.v3+json", "x-ratelimit-remaining": "60"}
        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        if "commits" in url:
            resp.status_code = 200
            resp.json.return_value = mock_commits
            return resp
        if "pulls" in url and "files" not in url and "reviews" not in url:
            resp.status_code = 200
            resp.json.return_value = mock_prs
            return resp
        if "issues" in url:
            resp.status_code = 200
            resp.json.return_value = mock_issues
            return resp
        resp.status_code = 200
        resp.json.return_value = []
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        res1 = import_github_engineering_history(repo_url, workspace_id=WORKSPACE_ID)
        g = db_client.get_graph()
        n1 = g.query("MATCH (n {workspace_id: $ws}) RETURN count(n)", {"ws": WORKSPACE_ID}).result_set[0][0]
        e1 = g.query("MATCH (a {workspace_id: $ws})-[r]->(b {workspace_id: $ws}) RETURN count(r)", {"ws": WORKSPACE_ID}).result_set[0][0]

        # Second identical import
        res2 = import_github_engineering_history(repo_url, workspace_id=WORKSPACE_ID)
        n2 = g.query("MATCH (n {workspace_id: $ws}) RETURN count(n)", {"ws": WORKSPACE_ID}).result_set[0][0]
        e2 = g.query("MATCH (a {workspace_id: $ws})-[r]->(b {workspace_id: $ws}) RETURN count(r)", {"ws": WORKSPACE_ID}).result_set[0][0]

    assert res1["status"] == "INGESTED_SUCCESS"
    assert res2["status"] == "INGESTED_SUCCESS"
    assert n1 == n2, f"Node count mismatch: {n1} vs {n2}"
    assert e1 == e2, f"Edge count mismatch: {e1} vs {e2}"


def test_pagination_and_safe_bounds():
    """Verify pagination across multiple pages up to configured safe bounds."""
    owner = "org"
    repo = "paginated-repo"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {"name": repo, "full_name": f"{owner}/{repo}", "default_branch": "main", "description": "Paging", "html_url": repo_url}

    # Generate 15 distinct commits across page 1 (10) and page 2 (5)
    page1_commits = [
        {"sha": f"sha_{i:04d}", "commit": {"message": f"Commit {i}", "author": {"name": "Dev", "email": "d@org.com", "date": "2026-01-01T00:00:00Z"}}, "author": {"login": f"user_{i}"}, "html_url": f"{repo_url}/commit/{i}"}
        for i in range(1, 11)
    ]
    page2_commits = [
        {"sha": f"sha_{i:04d}", "commit": {"message": f"Commit {i}", "author": {"name": "Dev", "email": "d@org.com", "date": "2026-01-01T00:00:00Z"}}, "author": {"login": f"user_{i}"}, "html_url": f"{repo_url}/commit/{i}"}
        for i in range(11, 16)
    ]

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        resp.headers = {"content-type": "application/vnd.github.v3+json", "x-ratelimit-remaining": "55"}
        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        if "commits" in url:
            if "&page=1" in url or "?page=1" in url:
                resp.status_code = 200
                resp.json.return_value = page1_commits
                return resp
            if "&page=2" in url or "?page=2" in url:
                resp.status_code = 200
                resp.json.return_value = page2_commits
                return resp
        resp.status_code = 200
        resp.json.return_value = []
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        result = import_github_engineering_history(
            repo_url=repo_url,
            workspace_id=WORKSPACE_ID,
            max_commits=15,
            per_page=10,
            fetch_files=False,
            fetch_reviews=False
        )

    assert result["status"] == "INGESTED_SUCCESS"
    assert result["counts"]["commits"] == 15

    g = db_client.get_graph()
    commit_count = g.query("MATCH (c:Commit {workspace_id: $ws}) RETURN count(c)", {"ws": WORKSPACE_ID}).result_set[0][0]
    assert commit_count == 15



def test_rate_limit_and_error_handling():
    """Verify rate-limit resilience, 404 repo not found, and invalid URL handling."""
    # 1. Invalid URL
    res_bad = import_github_engineering_history("not-a-repo", workspace_id=WORKSPACE_ID)
    assert res_bad["status"] == "INGESTION_FAILED"
    assert res_bad["error_code"] == "INVALID_URL"

    # 2. HTTP 404 Repo Not Found
    resp_404 = MagicMock()
    resp_404.status_code = 404
    resp_404.text = "Not Found"
    with patch("httpx.Client.get", return_value=resp_404):
        res_404 = import_github_engineering_history("https://github.com/private/secret-repo", workspace_id=WORKSPACE_ID)
    assert res_404["status"] == "INGESTION_FAILED"
    assert res_404["error_code"] == "REPO_NOT_FOUND"

    # 3. HTTP 403 Rate Limit Exceeded
    resp_403 = MagicMock()
    resp_403.status_code = 403
    resp_403.headers = {"x-ratelimit-remaining": "0"}
    resp_403.text = "API rate limit exceeded for 127.0.0.1"
    with patch("httpx.Client.get", return_value=resp_403):
        res_403 = import_github_engineering_history("https://github.com/owner/rate-limited", workspace_id=WORKSPACE_ID)
    assert res_403["status"] == "INGESTION_FAILED"
    assert res_403["error_code"] == "RATE_LIMIT_EXCEEDED"


def test_read_only_person_contributions_query():
    """Verify read-only query that lists a person's commits, PRs, reviews, and explicitly linked issues."""
    owner = "org"
    repo = "query-repo"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {"name": repo, "full_name": f"{owner}/{repo}", "default_branch": "main", "description": "Query", "html_url": repo_url}
    mock_commits = [{
        "sha": "9999888877776666555544443333222211110000",
        "commit": {
            "message": "Authored fix. Fixes #200",
            "author": {"name": "Alice Expert", "email": "alice@org.com", "date": "2026-03-01T10:00:00Z"},
            "committer": {"name": "Alice Expert", "email": "alice@org.com", "date": "2026-03-01T10:00:00Z"}
        },
        "author": {"login": "alice", "id": 501, "avatar_url": "https://avatars.githubusercontent.com/u/501", "html_url": "https://github.com/alice"},
        "html_url": f"{repo_url}/commit/999988887777",
        "stats": {"additions": 45, "deletions": 2, "total": 47}
    }]
    mock_prs = [{
        "number": 50,
        "title": "Auth enhancement",
        "body": "Resolves #200 by adding JWT signature validation",
        "state": "closed",
        "merged_at": "2026-03-02T12:00:00Z",
        "created_at": "2026-03-01T11:00:00Z",
        "html_url": f"{repo_url}/pull/50",
        "user": {"login": "alice", "id": 501, "avatar_url": "https://avatars.githubusercontent.com/u/501", "html_url": "https://github.com/alice"}
    }]
    mock_issues = [{
        "number": 200,
        "title": "JWT replay attack vulnerability",
        "body": "Vulnerability reported in token verification",
        "state": "closed",
        "created_at": "2026-02-28T09:00:00Z",
        "html_url": f"{repo_url}/issues/200",
        "user": {"login": "sec_reporter", "id": 999}
    }]
    mock_reviews = [{
        "id": 7771,
        "user": {"login": "alice", "id": 501, "avatar_url": "https://avatars.githubusercontent.com/u/501", "html_url": "https://github.com/alice"},
        "state": "CHANGES_REQUESTED",
        "submitted_at": "2026-03-01T15:00:00Z",
        "html_url": f"{repo_url}/pull/50#pullrequestreview-7771"
    }]

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        resp.headers = {"content-type": "application/vnd.github.v3+json", "x-ratelimit-remaining": "50"}
        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        if "commits" in url:
            if "9999888877776666555544443333222211110000" in url:
                resp.status_code = 200
                resp.json.return_value = {"files": [{"filename": "src/auth/jwt.py", "status": "modified", "additions": 45, "deletions": 2}]}
                return resp
            resp.status_code = 200
            resp.json.return_value = mock_commits
            return resp
        if "pulls/50/reviews" in url:
            resp.status_code = 200
            resp.json.return_value = mock_reviews
            return resp
        if "pulls/50/files" in url:
            resp.status_code = 200
            resp.json.return_value = [{"filename": "src/auth/jwt.py", "status": "modified", "additions": 45, "deletions": 2}]
            return resp
        if "pulls" in url:
            resp.status_code = 200
            resp.json.return_value = mock_prs
            return resp
        if "issues" in url:
            resp.status_code = 200
            resp.json.return_value = mock_issues
            return resp
        resp.status_code = 200
        resp.json.return_value = []
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        import_res = import_github_engineering_history(repo_url, workspace_id=WORKSPACE_ID)
        assert import_res["status"] == "INGESTED_SUCCESS"

    # 1. Query for Alice
    alice_contrib = get_person_contributions(WORKSPACE_ID, "alice")
    assert alice_contrib["found"] is True
    assert alice_contrib["person"]["login"] == "alice"
    assert len(alice_contrib["commits"]) == 1
    assert alice_contrib["commits"][0]["sha"] == "9999888877776666555544443333222211110000"
    assert alice_contrib["commits"][0]["touched_files"][0]["path"] == "src/auth/jwt.py"

    assert len(alice_contrib["pull_requests"]) == 1
    assert alice_contrib["pull_requests"][0]["number"] == 50

    assert len(alice_contrib["reviews"]) == 1
    assert alice_contrib["reviews"][0]["state"] == "CHANGES_REQUESTED"

    assert len(alice_contrib["explicitly_linked_issues"]) == 1
    assert alice_contrib["explicitly_linked_issues"][0]["number"] == 200
    assert alice_contrib["explicitly_linked_issues"][0]["title"] == "JWT replay attack vulnerability"

    # 2. Query for non-existent person
    ghost_contrib = get_person_contributions(WORKSPACE_ID, "nonexistent_person")
    assert ghost_contrib["found"] is False


def test_api_investigator_endpoints_integration():
    """Verify HTTP endpoints for investigator import and person contributions query."""
    owner = "org"
    repo = "api-repo"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {"name": repo, "full_name": f"{owner}/{repo}", "default_branch": "main", "description": "API test", "html_url": repo_url}
    mock_commits = [{
        "sha": "1234567890abcdef1234567890abcdef12345678",
        "commit": {"message": "API endpoint commit", "author": {"name": "API Dev", "email": "api@org.com", "date": "2026-03-10T10:00:00Z"}},
        "author": {"login": "apidev", "id": 888},
        "html_url": f"{repo_url}/commit/123456"
    }]

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        resp.headers = {"content-type": "application/vnd.github.v3+json", "x-ratelimit-remaining": "60"}
        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        if "commits" in url:
            resp.status_code = 200
            resp.json.return_value = mock_commits
            return resp
        resp.status_code = 200
        resp.json.return_value = []
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        # 1. POST /api/investigator/import
        post_resp = client.post("/api/investigator/import", json={
            "repo_url": repo_url,
            "workspace_id": WORKSPACE_ID,
            "max_commits": 5,
            "max_pulls": 5,
            "max_issues": 5
        })
        assert post_resp.status_code == 200
        data = post_resp.json()
        assert data["status"] == "INGESTED_SUCCESS"
        assert data["counts"]["commits"] == 1

    # 2. GET /api/investigator/contributions (Read-only from FalkorDB, outside httpx mock)
    get_resp = client.get(f"/api/investigator/contributions?username=apidev&workspace_id={WORKSPACE_ID}")
    assert get_resp.status_code == 200
    contrib_data = get_resp.json()
    assert contrib_data["found"] is True
    assert contrib_data["person"]["login"] == "apidev"
    assert len(contrib_data["commits"]) == 1

    # 3. GET 404 for unknown person
    get_404 = client.get(f"/api/investigator/contributions?username=nobody&workspace_id={WORKSPACE_ID}")
    assert get_404.status_code == 404

