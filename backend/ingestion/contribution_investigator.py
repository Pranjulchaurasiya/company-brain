import os
import re
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone
import httpx

from backend.config import DEFAULT_WORKSPACE_ID
from backend.db.falkordb_client import db_client
from backend.ingestion.external_importer import parse_github_url_details

logger = logging.getLogger("company_brain.contribution_investigator")

# Regex to detect explicit issue resolution keywords supported by GitHub
# e.g., "Fixes #12", "Closes #42", "resolved https://github.com/owner/repo/issues/99"
CLOSING_KEYWORD_REGEX = re.compile(
    r"(?i)\b(close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+(?:https?://github\.com/[^/\s]+/[^/\s]+/issues/|#)(\d+)\b"
)


def extract_explicit_resolved_issues(text: Optional[str]) -> List[Tuple[str, int]]:
    """
    Extract explicitly declared issue resolutions from PR body or commit message.
    Returns list of (keyword, issue_number).
    Only matches explicit GitHub closing syntax; does not infer from mentions or closer status.
    """
    if not text:
        return []
    matches = CLOSING_KEYWORD_REGEX.findall(text)
    results = []
    for kw, num_str in matches:
        try:
            results.append((kw.lower(), int(num_str)))
        except ValueError:
            continue
    return results


def import_github_engineering_history(
    repo_url: str,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    max_commits: int = 20,
    max_pulls: int = 20,
    max_issues: int = 20,
    per_page: int = 30,
    fetch_files: bool = True,
    fetch_reviews: bool = True,
    client: Optional[httpx.Client] = None
) -> Dict[str, Any]:
    """
    Import a bounded slice of real engineering history from a public GitHub repository:
    commits, pull requests, issues, touched files, reviews, and explicit issue resolutions.
    
    Preserves:
    - GitHub IDs, logins, avatars, html_urls
    - Timestamps (created, updated, closed, merged, authored, committed)
    - State (open, closed, merged) and state_reason
    - Changed-file information (filename, status, additions, deletions)
    - Direct source URLs (html_url)
    
    Guarantees:
    - Zero frontend secrets (optional GITHUB_TOKEN read strictly from server environment)
    - Rate-limit resilience (HTTP 403/429 handled cleanly)
    - Bounded pagination and safe execution
    - Canonical graph storage in FalkorDB with idempotent upserts
    - Strict 'resolves issue' relationship creation only when explicitly supported by GitHub data
    """
    parsed = parse_github_url_details(repo_url)
    if not parsed:
        return {
            "status": "INGESTION_FAILED",
            "error_code": "INVALID_URL",
            "error": f"Invalid GitHub URL: '{repo_url}'. Expected format: https://github.com/owner/repo or owner/repo.",
            "counts": {"commits": 0, "pull_requests": 0, "issues": 0, "people": 0, "files": 0, "resolves_relationships": 0}
        }

    owner = parsed["owner"]
    repo = parsed["repo"]
    canonical_repo_url = f"https://github.com/{owner}/{repo}"

    headers = {
        "User-Agent": "CompanyBrain-Investigator/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    gh_token = os.getenv("GITHUB_TOKEN")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    owns_client = False
    if client is None:
        client = httpx.Client(timeout=20.0)
        owns_client = True

    try:
        # 1. Fetch Repository Metadata
        repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
        repo_resp = client.get(repo_api_url, headers=headers)

        if repo_resp.status_code == 404:
            return {
                "status": "INGESTION_FAILED",
                "error_code": "REPO_NOT_FOUND",
                "error": f"Repository '{owner}/{repo}' not found or is private. Only public repositories can be imported without OAuth.",
                "counts": {"commits": 0, "pull_requests": 0, "issues": 0, "people": 0, "files": 0, "resolves_relationships": 0}
            }
        elif repo_resp.status_code in (403, 429):
            is_rate_limit = (
                repo_resp.headers.get("x-ratelimit-remaining") == "0"
                or "rate limit" in repo_resp.text.lower()
            )
            if is_rate_limit:
                return {
                    "status": "INGESTION_FAILED",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "error": f"GitHub API rate limit exceeded for '{owner}/{repo}'. Please configure GITHUB_TOKEN or try again later.",
                    "counts": {"commits": 0, "pull_requests": 0, "issues": 0, "people": 0, "files": 0, "resolves_relationships": 0}
                }
            return {
                "status": "INGESTION_FAILED",
                "error_code": "ACCESS_FORBIDDEN",
                "error": f"Access forbidden to repository '{owner}/{repo}' (HTTP 403).",
                "counts": {"commits": 0, "pull_requests": 0, "issues": 0, "people": 0, "files": 0, "resolves_relationships": 0}
            }
        elif repo_resp.status_code != 200:
            return {
                "status": "INGESTION_FAILED",
                "error_code": f"HTTP_{repo_resp.status_code}",
                "error": f"GitHub API returned HTTP {repo_resp.status_code}: {repo_resp.text[:200]}",
                "counts": {"commits": 0, "pull_requests": 0, "issues": 0, "people": 0, "files": 0, "resolves_relationships": 0}
            }

        repo_meta = repo_resp.json()
        default_branch = repo_meta.get("default_branch", "main")
        description = repo_meta.get("description") or ""

        # 2. Fetch Commits (with pagination support)
        raw_commits: List[Dict[str, Any]] = []
        page = 1
        commit_per_page = max(1, min(per_page, max_commits))
        while len(raw_commits) < max_commits:
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page={commit_per_page}&page={page}"
            c_resp = client.get(commits_url, headers=headers)
            if c_resp.status_code in (403, 429) and c_resp.headers.get("x-ratelimit-remaining") == "0":
                logger.warning("GitHub rate limit reached while fetching commits")
                break
            if c_resp.status_code != 200:
                logger.warning(f"Failed to fetch commits page {page}: HTTP {c_resp.status_code}")
                break
            page_data = c_resp.json()
            if not page_data or not isinstance(page_data, list):
                break
            for c in page_data:
                raw_commits.append(c)
                if len(raw_commits) >= max_commits:
                    break
            if len(page_data) < commit_per_page or len(raw_commits) >= max_commits or page >= 10:
                break
            page += 1

        # 3. Fetch Pull Requests (state=all, with pagination support)
        raw_prs: List[Dict[str, Any]] = []
        page = 1
        pr_per_page = max(1, min(per_page, max_pulls))
        while len(raw_prs) < max_pulls:
            pulls_url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page={pr_per_page}&page={page}"
            p_resp = client.get(pulls_url, headers=headers)
            if p_resp.status_code in (403, 429) and p_resp.headers.get("x-ratelimit-remaining") == "0":
                logger.warning("GitHub rate limit reached while fetching PRs")
                break
            if p_resp.status_code != 200:
                logger.warning(f"Failed to fetch PRs page {page}: HTTP {p_resp.status_code}")
                break
            page_data = p_resp.json()
            if not page_data or not isinstance(page_data, list):
                break
            for pr in page_data:
                raw_prs.append(pr)
                if len(raw_prs) >= max_pulls:
                    break
            if len(page_data) < pr_per_page or len(raw_prs) >= max_pulls or page >= 10:
                break
            page += 1

        # 4. Fetch Issues (state=all, excluding PRs)
        raw_issues: List[Dict[str, Any]] = []
        page = 1
        issue_per_page = max(1, min(per_page, max_issues))
        while len(raw_issues) < max_issues:
            issues_url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=all&per_page={issue_per_page}&page={page}"
            i_resp = client.get(issues_url, headers=headers)
            if i_resp.status_code in (403, 429) and i_resp.headers.get("x-ratelimit-remaining") == "0":
                logger.warning("GitHub rate limit reached while fetching issues")
                break
            if i_resp.status_code != 200:
                logger.warning(f"Failed to fetch issues page {page}: HTTP {i_resp.status_code}")
                break
            page_data = i_resp.json()
            if not page_data or not isinstance(page_data, list):
                break
            for item in page_data:
                # In GitHub REST API, PRs also appear in /issues with a 'pull_request' key
                if "pull_request" in item:
                    continue
                raw_issues.append(item)
                if len(raw_issues) >= max_issues:
                    break
            if len(page_data) < issue_per_page or len(raw_issues) >= max_issues or page >= 10:
                break
            page += 1

        # 5. Fetch PR Files and Reviews (bounded)
        pr_files_map: Dict[int, List[Dict[str, Any]]] = {}
        pr_reviews_map: Dict[int, List[Dict[str, Any]]] = {}

        for pr in raw_prs:
            pr_num = pr.get("number")
            if not pr_num:
                continue

            if fetch_files:
                try:
                    f_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}/files?per_page=20"
                    f_resp = client.get(f_url, headers=headers)
                    if f_resp.status_code == 200:
                        pr_files_map[pr_num] = f_resp.json()
                except Exception as ex:
                    logger.debug(f"Could not fetch files for PR #{pr_num}: {ex}")

            if fetch_reviews:
                try:
                    r_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}/reviews?per_page=20"
                    r_resp = client.get(r_url, headers=headers)
                    if r_resp.status_code == 200:
                        pr_reviews_map[pr_num] = r_resp.json()
                except Exception as ex:
                    logger.debug(f"Could not fetch reviews for PR #{pr_num}: {ex}")

        # 6. Fetch Commit details / files (for a bounded subset of commits if not already in payload)
        commit_files_map: Dict[str, List[Dict[str, Any]]] = {}
        if fetch_files:
            # Inspect first 10 commits to extract touched files if available
            for c in raw_commits[:10]:
                sha = c.get("sha")
                if not sha:
                    continue
                if "files" in c and isinstance(c["files"], list):
                    commit_files_map[sha] = c["files"]
                else:
                    try:
                        detail_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
                        detail_resp = client.get(detail_url, headers=headers)
                        if detail_resp.status_code == 200:
                            data = detail_resp.json()
                            if "files" in data and isinstance(data["files"], list):
                                commit_files_map[sha] = data["files"]
                    except Exception as ex:
                        logger.debug(f"Could not fetch commit details for {sha}: {ex}")

    except Exception as e:
        logger.exception("Network exception during GitHub history import")
        return {
            "status": "INGESTION_FAILED",
            "error_code": "NETWORK_EXCEPTION",
            "error": f"Failed to connect to GitHub API: {str(e)}",
            "counts": {"commits": 0, "pull_requests": 0, "issues": 0, "people": 0, "files": 0, "resolves_relationships": 0}
        }
    finally:
        if owns_client:
            client.close()

    # 7. Store canonical graph entities and relationships in FalkorDB
    store_result = store_github_engineering_graph(
        workspace_id=workspace_id,
        owner=owner,
        repo=repo,
        repo_meta={
            "name": repo,
            "full_name": f"{owner}/{repo}",
            "owner": owner,
            "html_url": canonical_repo_url,
            "default_branch": default_branch,
            "description": description
        },
        commits=raw_commits,
        pull_requests=raw_prs,
        issues=raw_issues,
        pr_files_map=pr_files_map,
        pr_reviews_map=pr_reviews_map,
        commit_files_map=commit_files_map
    )

    return {
        "status": "INGESTED_SUCCESS",
        "repository": {
            "id": store_result["repo_id"],
            "owner": owner,
            "name": repo,
            "full_name": f"{owner}/{repo}",
            "html_url": canonical_repo_url,
            "default_branch": default_branch
        },
        "counts": store_result["counts"],
        "message": (
            f"Successfully imported {store_result['counts']['commits']} commits, "
            f"{store_result['counts']['pull_requests']} PRs, "
            f"{store_result['counts']['issues']} issues, "
            f"{store_result['counts']['people']} contributors, and "
            f"{store_result['counts']['resolves_relationships']} explicit resolution links into FalkorDB."
        )
    }


def store_github_engineering_graph(
    workspace_id: str,
    owner: str,
    repo: str,
    repo_meta: Dict[str, Any],
    commits: List[Dict[str, Any]],
    pull_requests: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    pr_files_map: Dict[int, List[Dict[str, Any]]],
    pr_reviews_map: Dict[int, List[Dict[str, Any]]],
    commit_files_map: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Persist repository, people, commits, pull requests, issues, files, and relationships into FalkorDB.
    All operations are strictly idempotent using MERGE.
    """
    now_ts = datetime.now(timezone.utc).isoformat()
    repo_slug = re.sub(r"[^a-zA-Z0-9_]", "_", f"{owner}_{repo}".lower())
    repo_id = f"repo_{repo_slug}"

    # 1. Upsert Repository Node
    db_client.query("""
    MERGE (r:Repository {workspace_id: $ws, id: $rid})
    ON CREATE SET r.name = $name,
                  r.full_name = $full_name,
                  r.owner = $owner,
                  r.html_url = $html_url,
                  r.default_branch = $default_branch,
                  r.description = $description,
                  r.created_at = $ts,
                  r.updated_at = $ts
    ON MATCH SET r.name = $name,
                 r.full_name = $full_name,
                 r.owner = $owner,
                 r.html_url = $html_url,
                 r.default_branch = $default_branch,
                 r.description = $description,
                 r.updated_at = $ts
    """, {
        "ws": workspace_id,
        "rid": repo_id,
        "name": repo_meta.get("name", repo),
        "full_name": repo_meta.get("full_name", f"{owner}/{repo}"),
        "owner": owner,
        "html_url": repo_meta.get("html_url", f"https://github.com/{owner}/{repo}"),
        "default_branch": repo_meta.get("default_branch", "main"),
        "description": repo_meta.get("description", ""),
        "ts": now_ts
    })

    # Also link Project entity for cross-compatibility with Company Brain workspace overview
    project_id = f"proj_gh_{repo_slug}"
    db_client.query("""
    MERGE (p:Project {workspace_id: $ws, id: $pid})
    ON CREATE SET p.name = $full_name,
                  p.description = $description,
                  p.status = 'ACTIVE',
                  p.repo_url = $html_url,
                  p.default_branch = $default_branch,
                  p.created_at = $ts,
                  p.updated_at = $ts
    ON MATCH SET p.name = $full_name,
                 p.repo_url = $html_url,
                 p.updated_at = $ts
    """, {
        "ws": workspace_id,
        "pid": project_id,
        "full_name": repo_meta.get("full_name", f"{owner}/{repo}"),
        "description": f"Repository {owner}/{repo}",
        "html_url": repo_meta.get("html_url", f"https://github.com/{owner}/{repo}"),
        "default_branch": repo_meta.get("default_branch", "main"),
        "ts": now_ts
    })

    db_client.query("""
    MATCH (p:Project {workspace_id: $ws, id: $pid})
    MATCH (r:Repository {workspace_id: $ws, id: $rid})
    MERGE (p)-[:HAS_REPOSITORY]->(r)
    """, {"ws": workspace_id, "pid": project_id, "rid": repo_id})

    people_seen: Set[str] = set()
    files_seen: Set[str] = set()
    labels_seen: Set[str] = set()
    explicit_resolves_count = 0

    def upsert_person(user_obj: Optional[Dict[str, Any]]) -> Optional[str]:
        if not user_obj or not isinstance(user_obj, dict):
            return None
        login = user_obj.get("login")
        if not login:
            return None
        login_clean = str(login).strip()
        person_id = f"person_gh_{login_clean.lower()}"

        db_client.query("""
        MERGE (p:Person {workspace_id: $ws, id: $pid})
        ON CREATE SET p.login = $login,
                      p.name = $name,
                      p.github_id = $github_id,
                      p.avatar_url = $avatar_url,
                      p.html_url = $html_url,
                      p.created_at = $ts,
                      p.updated_at = $ts
        ON MATCH SET p.login = $login,
                     p.name = coalesce($name, p.name),
                     p.avatar_url = coalesce($avatar_url, p.avatar_url),
                     p.html_url = coalesce($html_url, p.html_url),
                     p.updated_at = $ts
        """, {
            "ws": workspace_id,
            "pid": person_id,
            "login": login_clean,
            "name": user_obj.get("name") or login_clean,
            "github_id": user_obj.get("id"),
            "avatar_url": user_obj.get("avatar_url") or "",
            "html_url": user_obj.get("html_url") or f"https://github.com/{login_clean}",
            "ts": now_ts
        })

        db_client.query("""
        MATCH (r:Repository {workspace_id: $ws, id: $rid})
        MATCH (p:Person {workspace_id: $ws, id: $pid})
        MERGE (r)-[:HAS_CONTRIBUTOR]->(p)
        """, {"ws": workspace_id, "rid": repo_id, "pid": person_id})

        people_seen.add(person_id)
        return person_id

    def upsert_file(path: str) -> Optional[str]:
        if not path:
            return None
        clean_path = path.strip().replace("\\", "/")
        path_hash = hashlib.sha256(clean_path.encode()).hexdigest()[:12]
        file_id = f"file_{repo_slug}_{path_hash}"
        filename = os.path.basename(clean_path)
        _, ext = os.path.splitext(filename)

        file_url = f"https://github.com/{owner}/{repo}/blob/{repo_meta.get('default_branch', 'main')}/{clean_path}"

        db_client.query("""
        MERGE (f:File {workspace_id: $ws, id: $fid})
        ON CREATE SET f.path = $path,
                      f.filename = $filename,
                      f.extension = $ext,
                      f.html_url = $html_url,
                      f.created_at = $ts,
                      f.updated_at = $ts
        ON MATCH SET f.path = $path,
                     f.html_url = $html_url,
                     f.updated_at = $ts
        """, {
            "ws": workspace_id,
            "fid": file_id,
            "path": clean_path,
            "filename": filename,
            "ext": ext,
            "html_url": file_url,
            "ts": now_ts
        })

        db_client.query("""
        MATCH (r:Repository {workspace_id: $ws, id: $rid})
        MATCH (f:File {workspace_id: $ws, id: $fid})
        MERGE (r)-[:HAS_FILE]->(f)
        """, {"ws": workspace_id, "rid": repo_id, "fid": file_id})

        files_seen.add(file_id)
        return file_id

    # 2. Upsert Commits
    for c in commits:
        sha = c.get("sha")
        if not sha:
            continue
        commit_id = f"commit_{repo_slug}_{sha[:12]}"
        commit_details = c.get("commit", {})
        message = commit_details.get("message") or c.get("message") or ""
        author_info = commit_details.get("author") or {}
        committer_info = commit_details.get("committer") or {}

        authored_at = author_info.get("date")
        committed_at = committer_info.get("date") or authored_at or now_ts
        author_name = author_info.get("name")
        author_email = author_info.get("email")

        # GitHub user object (if linked)
        gh_author = c.get("author")
        author_login = gh_author.get("login") if isinstance(gh_author, dict) else None
        if gh_author:
            upsert_person(gh_author)
        elif author_login:
            upsert_person({"login": author_login, "name": author_name})

        # Stats if present
        stats = c.get("stats") or {}
        additions = stats.get("additions", 0)
        deletions = stats.get("deletions", 0)
        total_changes = stats.get("total", additions + deletions)
        commit_url = c.get("html_url") or f"https://github.com/{owner}/{repo}/commit/{sha}"

        db_client.query("""
        MERGE (cm:Commit {workspace_id: $ws, id: $cid})
        ON CREATE SET cm.sha = $sha,
                      cm.message = $msg,
                      cm.author_login = $author_login,
                      cm.author_name = $author_name,
                      cm.author_email = $author_email,
                      cm.authored_at = $authored_at,
                      cm.committed_at = $committed_at,
                      cm.html_url = $html_url,
                      cm.additions = $additions,
                      cm.deletions = $deletions,
                      cm.total_changes = $total_changes,
                      cm.created_at = $ts,
                      cm.updated_at = $ts
        ON MATCH SET cm.message = $msg,
                     cm.author_login = $author_login,
                     cm.html_url = $html_url,
                     cm.committed_at = $committed_at,
                     cm.updated_at = $ts
        """, {
            "ws": workspace_id,
            "cid": commit_id,
            "sha": sha,
            "msg": message,
            "author_login": author_login,
            "author_name": author_name,
            "author_email": author_email,
            "authored_at": authored_at,
            "committed_at": committed_at,
            "html_url": commit_url,
            "additions": additions,
            "deletions": deletions,
            "total_changes": total_changes,
            "ts": now_ts
        })

        # Link Repository -> Commit
        db_client.query("""
        MATCH (r:Repository {workspace_id: $ws, id: $rid})
        MATCH (cm:Commit {workspace_id: $ws, id: $cid})
        MERGE (r)-[:HAS_COMMIT]->(cm)
        """, {"ws": workspace_id, "rid": repo_id, "cid": commit_id})

        # Link Person -> AUTHORED_COMMIT -> Commit
        if author_login:
            pid = f"person_gh_{author_login.lower()}"
            db_client.query("""
            MATCH (p:Person {workspace_id: $ws, id: $pid})
            MATCH (cm:Commit {workspace_id: $ws, id: $cid})
            MERGE (p)-[:AUTHORED_COMMIT]->(cm)
            """, {"ws": workspace_id, "pid": pid, "cid": commit_id})

        # Touched files for this commit
        files_for_commit = commit_files_map.get(sha, [])
        for f_info in files_for_commit:
            f_path = f_info.get("filename")
            if not f_path:
                continue
            fid = upsert_file(f_path)
            if fid:
                f_status = f_info.get("status", "modified")
                f_adds = f_info.get("additions", 0)
                f_dels = f_info.get("deletions", 0)
                db_client.query("""
                MATCH (cm:Commit {workspace_id: $ws, id: $cid})
                MATCH (f:File {workspace_id: $ws, id: $fid})
                MERGE (cm)-[tf:TOUCHED_FILE]->(f)
                ON CREATE SET tf.status = $status, tf.additions = $adds, tf.deletions = $dels
                ON MATCH SET tf.status = $status, tf.additions = $adds, tf.deletions = $dels
                """, {
                    "ws": workspace_id,
                    "cid": commit_id,
                    "fid": fid,
                    "status": f_status,
                    "adds": f_adds,
                    "dels": f_dels
                })

        # Store Evidence node for Commit so agents can cite it
        ev_commit_id = f"ev_commit_{repo_slug}_{sha[:12]}"
        db_client.query("""
        MERGE (ev:Evidence {workspace_id: $ws, id: $eid})
        ON CREATE SET ev.locator = $loc, ev.excerpt = $excerpt, ev.source_id = $cid, ev.created_at = $ts
        ON MATCH SET ev.excerpt = $excerpt
        """, {
            "ws": workspace_id,
            "eid": ev_commit_id,
            "loc": f"GitHub Commit {sha[:8]}",
            "excerpt": f"Commit {sha[:8]} by {author_login or 'dev'}: {message[:250]}",
            "cid": commit_id,
            "ts": now_ts
        })
        db_client.query("""
        MATCH (cm:Commit {workspace_id: $ws, id: $cid})
        MATCH (ev:Evidence {workspace_id: $ws, id: $eid})
        MERGE (cm)-[:HAS_EVIDENCE]->(ev)
        """, {"ws": workspace_id, "cid": commit_id, "eid": ev_commit_id})

    # 3. Upsert Issues
    issue_number_to_id: Dict[int, str] = {}
    for issue in issues:
        num = issue.get("number")
        if not num:
            continue
        issue_id = f"issue_{repo_slug}_{num}"
        issue_number_to_id[num] = issue_id

        title = issue.get("title", "")
        body = issue.get("body") or ""
        state = issue.get("state", "open")
        state_reason = issue.get("state_reason")
        created_at = issue.get("created_at") or now_ts
        updated_at = issue.get("updated_at") or created_at
        closed_at = issue.get("closed_at")
        issue_url = issue.get("html_url") or f"https://github.com/{owner}/{repo}/issues/{num}"

        # Creator / author of issue
        user_obj = issue.get("user")
        author_login = user_obj.get("login") if isinstance(user_obj, dict) else None
        if user_obj:
            upsert_person(user_obj)

        # Assignee & Closer info (Preserved strictly as metadata properties, NOT as authors of fix)
        assignee_obj = issue.get("assignee")
        assignee_login = assignee_obj.get("login") if isinstance(assignee_obj, dict) else None
        if assignee_obj:
            upsert_person(assignee_obj)

        closed_by_obj = issue.get("closed_by")
        closed_by_login = closed_by_obj.get("login") if isinstance(closed_by_obj, dict) else None
        if closed_by_obj:
            upsert_person(closed_by_obj)

        db_client.query("""
        MERGE (i:Issue {workspace_id: $ws, id: $iid})
        ON CREATE SET i.number = $number,
                      i.title = $title,
                      i.body = $body,
                      i.state = $state,
                      i.state_reason = $state_reason,
                      i.author_login = $author_login,
                      i.assignee_login = $assignee_login,
                      i.closed_by_login = $closed_by_login,
                      i.created_at = $created_at,
                      i.updated_at = $updated_at,
                      i.closed_at = $closed_at,
                      i.html_url = $html_url
        ON MATCH SET i.title = $title,
                     i.body = $body,
                     i.state = $state,
                     i.state_reason = $state_reason,
                     i.assignee_login = $assignee_login,
                     i.closed_by_login = $closed_by_login,
                     i.updated_at = $updated_at,
                     i.closed_at = $closed_at,
                     i.html_url = $html_url
        """, {
            "ws": workspace_id,
            "iid": issue_id,
            "number": num,
            "title": title,
            "body": body[:5000],
            "state": state,
            "state_reason": state_reason or "",
            "author_login": author_login or "",
            "assignee_login": assignee_login or "",
            "closed_by_login": closed_by_login or "",
            "created_at": created_at,
            "updated_at": updated_at,
            "closed_at": closed_at or "",
            "html_url": issue_url
        })

        # Link Repository -> Issue
        db_client.query("""
        MATCH (r:Repository {workspace_id: $ws, id: $rid})
        MATCH (i:Issue {workspace_id: $ws, id: $iid})
        MERGE (r)-[:HAS_ISSUE]->(i)
        """, {"ws": workspace_id, "rid": repo_id, "iid": issue_id})

        # Link Person -> OPENED_ISSUE -> Issue
        if author_login:
            pid = f"person_gh_{author_login.lower()}"
            db_client.query("""
            MATCH (p:Person {workspace_id: $ws, id: $pid})
            MATCH (i:Issue {workspace_id: $ws, id: $iid})
            MERGE (p)-[:OPENED_ISSUE]->(i)
            """, {"ws": workspace_id, "pid": pid, "iid": issue_id})

        # Store Issue Labels
        for lbl in issue.get("labels", []):
            if isinstance(lbl, dict) and lbl.get("name"):
                lbl_name = lbl["name"]
                lbl_id = f"label_{repo_slug}_{re.sub(r'[^a-zA-Z0-9_]', '_', lbl_name.lower())}"
                db_client.query("""
                MERGE (l:Label {workspace_id: $ws, id: $lid})
                ON CREATE SET l.name = $name, l.color = $color, l.description = $desc
                ON MATCH SET l.color = $color
                """, {
                    "ws": workspace_id,
                    "lid": lbl_id,
                    "name": lbl_name,
                    "color": lbl.get("color") or "",
                    "desc": lbl.get("description") or ""
                })
                db_client.query("""
                MATCH (i:Issue {workspace_id: $ws, id: $iid})
                MATCH (l:Label {workspace_id: $ws, id: $lid})
                MERGE (i)-[:HAS_LABEL]->(l)
                """, {"ws": workspace_id, "iid": issue_id, "lid": lbl_id})
                labels_seen.add(lbl_id)

        # Store Evidence node for Issue so agents can cite it
        ev_issue_id = f"ev_issue_{repo_slug}_{num}"
        db_client.query("""
        MERGE (ev:Evidence {workspace_id: $ws, id: $eid})
        ON CREATE SET ev.locator = $loc, ev.excerpt = $excerpt, ev.source_id = $iid, ev.created_at = $ts
        ON MATCH SET ev.excerpt = $excerpt
        """, {
            "ws": workspace_id,
            "eid": ev_issue_id,
            "loc": f"GitHub Issue #{num}",
            "excerpt": f"Issue #{num}: {title}\n{body[:350]}",
            "iid": issue_id,
            "ts": now_ts
        })
        db_client.query("""
        MATCH (i:Issue {workspace_id: $ws, id: $iid})
        MATCH (ev:Evidence {workspace_id: $ws, id: $eid})
        MERGE (i)-[:HAS_EVIDENCE]->(ev)
        """, {"ws": workspace_id, "iid": issue_id, "eid": ev_issue_id})

    # 4. Upsert Pull Requests
    for pr in pull_requests:
        num = pr.get("number")
        if not num:
            continue
        pr_id = f"pr_{repo_slug}_{num}"
        title = pr.get("title", "")
        body = pr.get("body") or ""
        state = pr.get("state", "open")
        created_at = pr.get("created_at") or now_ts
        updated_at = pr.get("updated_at") or created_at
        closed_at = pr.get("closed_at")
        merged_at = pr.get("merged_at")
        is_merged = bool(merged_at or pr.get("is_merged", False))

        pr_url = pr.get("html_url") or f"https://github.com/{owner}/{repo}/pull/{num}"
        head_ref = pr.get("head", {}).get("ref")
        base_ref = pr.get("base", {}).get("ref")

        # PR author
        user_obj = pr.get("user")
        author_login = user_obj.get("login") if isinstance(user_obj, dict) else None
        if user_obj:
            upsert_person(user_obj)

        db_client.query("""
        MERGE (pr:PullRequest {workspace_id: $ws, id: $prid})
        ON CREATE SET pr.number = $number,
                      pr.title = $title,
                      pr.body = $body,
                      pr.state = $state,
                      pr.is_merged = $is_merged,
                      pr.author_login = $author_login,
                      pr.created_at = $created_at,
                      pr.updated_at = $updated_at,
                      pr.closed_at = $closed_at,
                      pr.merged_at = $merged_at,
                      pr.html_url = $html_url,
                      pr.head_ref = $head_ref,
                      pr.base_ref = $base_ref
        ON MATCH SET pr.title = $title,
                     pr.body = $body,
                     pr.state = $state,
                     pr.is_merged = $is_merged,
                     pr.author_login = $author_login,
                     pr.updated_at = $updated_at,
                     pr.closed_at = $closed_at,
                     pr.merged_at = $merged_at,
                     pr.html_url = $html_url,
                     pr.head_ref = $head_ref,
                     pr.base_ref = $base_ref
        """, {
            "ws": workspace_id,
            "prid": pr_id,
            "number": num,
            "title": title,
            "body": body[:5000],
            "state": state,
            "is_merged": is_merged,
            "author_login": author_login or "",
            "created_at": created_at,
            "updated_at": updated_at,
            "closed_at": closed_at or "",
            "merged_at": merged_at or "",
            "html_url": pr_url,
            "head_ref": head_ref or "",
            "base_ref": base_ref or ""
        })

        # Link Repository -> PullRequest
        db_client.query("""
        MATCH (r:Repository {workspace_id: $ws, id: $rid})
        MATCH (pr:PullRequest {workspace_id: $ws, id: $prid})
        MERGE (r)-[:HAS_PULL_REQUEST]->(pr)
        """, {"ws": workspace_id, "rid": repo_id, "prid": pr_id})

        # Link Person -> OPENED_PR -> PullRequest
        if author_login:
            pid = f"person_gh_{author_login.lower()}"
            db_client.query("""
            MATCH (p:Person {workspace_id: $ws, id: $pid})
            MATCH (pr:PullRequest {workspace_id: $ws, id: $prid})
            MERGE (p)-[:OPENED_PR]->(pr)
            """, {"ws": workspace_id, "pid": pid, "prid": pr_id})

        # Touched files for this PR
        files_for_pr = pr_files_map.get(num, [])
        for f_info in files_for_pr:
            f_path = f_info.get("filename")
            if not f_path:
                continue
            fid = upsert_file(f_path)
            if fid:
                f_status = f_info.get("status", "modified")
                f_adds = f_info.get("additions", 0)
                f_dels = f_info.get("deletions", 0)
                db_client.query("""
                MATCH (pr:PullRequest {workspace_id: $ws, id: $prid})
                MATCH (f:File {workspace_id: $ws, id: $fid})
                MERGE (pr)-[tf:TOUCHED_FILE]->(f)
                ON CREATE SET tf.status = $status, tf.additions = $adds, tf.deletions = $dels
                ON MATCH SET tf.status = $status, tf.additions = $adds, tf.deletions = $dels
                """, {
                    "ws": workspace_id,
                    "prid": pr_id,
                    "fid": fid,
                    "status": f_status,
                    "adds": f_adds,
                    "dels": f_dels
                })

        # Reviews for this PR
        reviews_for_pr = pr_reviews_map.get(num, [])
        for rev in reviews_for_pr:
            rev_user = rev.get("user")
            rev_login = rev_user.get("login") if isinstance(rev_user, dict) else None
            if rev_user and rev_login:
                rev_pid = upsert_person(rev_user)
                rev_state = rev.get("state", "COMMENTED")
                rev_submitted = rev.get("submitted_at") or now_ts
                rev_html_url = rev.get("html_url") or pr_url

                db_client.query("""
                MATCH (p:Person {workspace_id: $ws, id: $pid})
                MATCH (pr:PullRequest {workspace_id: $ws, id: $prid})
                MERGE (p)-[r:REVIEWED_PR]->(pr)
                ON CREATE SET r.state = $state, r.submitted_at = $sub, r.html_url = $hurl
                ON MATCH SET r.state = $state, r.submitted_at = $sub, r.html_url = $hurl
                """, {
                    "ws": workspace_id,
                    "pid": rev_pid,
                    "prid": pr_id,
                    "state": rev_state,
                    "sub": rev_submitted,
                    "hurl": rev_html_url
                })

        # Store PR Labels
        for lbl in pr.get("labels", []):
            if isinstance(lbl, dict) and lbl.get("name"):
                lbl_name = lbl["name"]
                lbl_id = f"label_{repo_slug}_{re.sub(r'[^a-zA-Z0-9_]', '_', lbl_name.lower())}"
                db_client.query("""
                MERGE (l:Label {workspace_id: $ws, id: $lid})
                ON CREATE SET l.name = $name, l.color = $color, l.description = $desc
                ON MATCH SET l.color = $color
                """, {
                    "ws": workspace_id,
                    "lid": lbl_id,
                    "name": lbl_name,
                    "color": lbl.get("color") or "",
                    "desc": lbl.get("description") or ""
                })
                db_client.query("""
                MATCH (pr:PullRequest {workspace_id: $ws, id: $prid})
                MATCH (l:Label {workspace_id: $ws, id: $lid})
                MERGE (pr)-[:HAS_LABEL]->(l)
                """, {"ws": workspace_id, "prid": pr_id, "lid": lbl_id})
                labels_seen.add(lbl_id)

        # Store Evidence node for PullRequest so agents can cite it
        ev_pr_id = f"ev_pr_{repo_slug}_{num}"
        db_client.query("""
        MERGE (ev:Evidence {workspace_id: $ws, id: $eid})
        ON CREATE SET ev.locator = $loc, ev.excerpt = $excerpt, ev.source_id = $prid, ev.created_at = $ts
        ON MATCH SET ev.excerpt = $excerpt
        """, {
            "ws": workspace_id,
            "eid": ev_pr_id,
            "loc": f"GitHub PR #{num}",
            "excerpt": f"PR #{num}: {title}\n{body[:350]}",
            "prid": pr_id,
            "ts": now_ts
        })
        db_client.query("""
        MATCH (pr:PullRequest {workspace_id: $ws, id: $prid})
        MATCH (ev:Evidence {workspace_id: $ws, id: $eid})
        MERGE (pr)-[:HAS_EVIDENCE]->(ev)
        """, {"ws": workspace_id, "prid": pr_id, "eid": ev_pr_id})

        # 5. Check Explicit Issue Resolution in PR Body
        # "Only create a 'resolves issue' relationship when the GitHub data explicitly supports it. Do not infer that an assignee or closer authored the fix."
        explicit_links = extract_explicit_resolved_issues(body)
        for kw, target_issue_num in explicit_links:
            target_issue_id = issue_number_to_id.get(target_issue_num)
            if target_issue_id:
                db_client.query("""
                MATCH (pr:PullRequest {workspace_id: $ws, id: $prid})
                MATCH (i:Issue {workspace_id: $ws, id: $iid})
                MERGE (pr)-[rel:RESOLVES_ISSUE]->(i)
                ON CREATE SET rel.keyword = $kw, rel.created_at = $ts
                ON MATCH SET rel.keyword = $kw
                """, {
                    "ws": workspace_id,
                    "prid": pr_id,
                    "iid": target_issue_id,
                    "kw": kw,
                    "ts": now_ts
                })
                explicit_resolves_count += 1

    # 6. Check Explicit Issue Resolution in Commit Messages
    for c in commits:
        sha = c.get("sha")
        if not sha:
            continue
        commit_id = f"commit_{repo_slug}_{sha[:12]}"
        commit_details = c.get("commit", {})
        message = commit_details.get("message") or c.get("message") or ""
        explicit_links = extract_explicit_resolved_issues(message)
        for kw, target_issue_num in explicit_links:
            target_issue_id = issue_number_to_id.get(target_issue_num)
            if target_issue_id:
                db_client.query("""
                MATCH (cm:Commit {workspace_id: $ws, id: $cid})
                MATCH (i:Issue {workspace_id: $ws, id: $iid})
                MERGE (cm)-[rel:RESOLVES_ISSUE]->(i)
                ON CREATE SET rel.keyword = $kw, rel.created_at = $ts
                ON MATCH SET rel.keyword = $kw
                """, {
                    "ws": workspace_id,
                    "cid": commit_id,
                    "iid": target_issue_id,
                    "kw": kw,
                    "ts": now_ts
                })
                explicit_resolves_count += 1

    return {
        "repo_id": repo_id,
        "counts": {
            "commits": len(commits),
            "pull_requests": len(pull_requests),
            "issues": len(issues),
            "people": len(people_seen),
            "files": len(files_seen),
            "labels": len(labels_seen),
            "resolves_relationships": explicit_resolves_count
        }
    }


def get_person_contributions(
    workspace_id: str,
    person_identifier: str
) -> Dict[str, Any]:
    """
    Read-only query that lists a person's commits, PRs, reviews if available, and explicitly linked issues.
    Matched by person ID, GitHub login, or name (case-insensitive).
    """
    clean_id = person_identifier.strip()

    # 1. Locate Person node
    person_cypher = """
    MATCH (p:Person {workspace_id: $ws})
    WHERE p.id = $id OR toLower(p.login) = toLower($id) OR toLower(p.name) = toLower($id)
    RETURN p.id, p.login, p.name, p.avatar_url, p.html_url
    LIMIT 1
    """
    p_rows = db_client.query(person_cypher, {"ws": workspace_id, "id": clean_id})
    if not p_rows:
        return {
            "found": False,
            "person": None,
            "commits": [],
            "pull_requests": [],
            "reviews": [],
            "explicitly_linked_issues": [],
            "message": f"Person '{person_identifier}' not found in graph."
        }

    p_row = p_rows[0]
    person_data = {
        "id": p_row[0],
        "login": p_row[1],
        "name": p_row[2],
        "avatar_url": p_row[3],
        "html_url": p_row[4]
    }
    pid = person_data["id"]

    # 2. Retrieve Commits authored by this person
    commits_cypher = """
    MATCH (p:Person {workspace_id: $ws, id: $pid})-[:AUTHORED_COMMIT]->(c:Commit {workspace_id: $ws})
    OPTIONAL MATCH (r:Repository {workspace_id: $ws})-[:HAS_COMMIT]->(c)
    OPTIONAL MATCH (c)-[tf:TOUCHED_FILE]->(f:File {workspace_id: $ws})
    RETURN c.sha, c.message, c.authored_at, c.committed_at, c.html_url, c.additions, c.deletions,
           r.full_name, collect(distinct {path: f.path, status: tf.status}) as files
    ORDER BY c.committed_at DESC
    """
    c_rows = db_client.query(commits_cypher, {"ws": workspace_id, "pid": pid})
    commits = []
    for r in c_rows:
        files = [f for f in (r[8] or []) if f.get("path")]
        commits.append({
            "sha": r[0],
            "message": r[1],
            "authored_at": r[2],
            "committed_at": r[3],
            "html_url": r[4],
            "additions": r[5],
            "deletions": r[6],
            "repository": r[7],
            "touched_files": files
        })

    # 3. Retrieve Pull Requests opened by this person
    prs_cypher = """
    MATCH (p:Person {workspace_id: $ws, id: $pid})-[:OPENED_PR]->(pr:PullRequest {workspace_id: $ws})
    OPTIONAL MATCH (r:Repository {workspace_id: $ws})-[:HAS_PULL_REQUEST]->(pr)
    RETURN pr.number, pr.title, pr.state, pr.is_merged, pr.created_at, pr.merged_at, pr.html_url, r.full_name
    ORDER BY pr.created_at DESC
    """
    pr_rows = db_client.query(prs_cypher, {"ws": workspace_id, "pid": pid})
    pull_requests = []
    for r in pr_rows:
        pull_requests.append({
            "number": r[0],
            "title": r[1],
            "state": r[2],
            "is_merged": bool(r[3]),
            "created_at": r[4],
            "merged_at": r[5],
            "html_url": r[6],
            "repository": r[7]
        })

    # 4. Retrieve Reviews submitted by this person
    reviews_cypher = """
    MATCH (p:Person {workspace_id: $ws, id: $pid})-[rev:REVIEWED_PR]->(pr:PullRequest {workspace_id: $ws})
    OPTIONAL MATCH (r:Repository {workspace_id: $ws})-[:HAS_PULL_REQUEST]->(pr)
    RETURN pr.number, pr.title, rev.state, rev.submitted_at, rev.html_url, r.full_name
    ORDER BY rev.submitted_at DESC
    """
    rev_rows = db_client.query(reviews_cypher, {"ws": workspace_id, "pid": pid})
    reviews = []
    for r in rev_rows:
        reviews.append({
            "pr_number": r[0],
            "pr_title": r[1],
            "state": r[2],
            "submitted_at": r[3],
            "html_url": r[4],
            "repository": r[5]
        })

    # 5. Retrieve Explicitly Linked Issues resolved by this person's PRs or Commits
    linked_issues_cypher = """
    MATCH (p:Person {workspace_id: $ws, id: $pid})-[:OPENED_PR]->(pr:PullRequest {workspace_id: $ws})-[rel:RESOLVES_ISSUE]->(i:Issue {workspace_id: $ws})
    RETURN distinct i.number, i.title, i.state, i.html_url, i.created_at, pr.number as pr_number, rel.keyword as keyword
    """
    iss_rows = db_client.query(linked_issues_cypher, {"ws": workspace_id, "pid": pid})
    linked_issues = []
    seen_issue_nums = set()
    for r in iss_rows:
        issue_num = r[0]
        if issue_num not in seen_issue_nums:
            seen_issue_nums.add(issue_num)
            linked_issues.append({
                "number": issue_num,
                "title": r[1],
                "state": r[2],
                "html_url": r[3],
                "created_at": r[4],
                "resolved_via_pr": r[5],
                "resolution_keyword": r[6]
            })

    commit_linked_issues_cypher = """
    MATCH (p:Person {workspace_id: $ws, id: $pid})-[:AUTHORED_COMMIT]->(cm:Commit {workspace_id: $ws})-[rel:RESOLVES_ISSUE]->(i:Issue {workspace_id: $ws})
    RETURN distinct i.number, i.title, i.state, i.html_url, i.created_at, cm.sha as commit_sha, rel.keyword as keyword
    """
    c_iss_rows = db_client.query(commit_linked_issues_cypher, {"ws": workspace_id, "pid": pid})
    for r in c_iss_rows:
        issue_num = r[0]
        if issue_num not in seen_issue_nums:
            seen_issue_nums.add(issue_num)
            linked_issues.append({
                "number": issue_num,
                "title": r[1],
                "state": r[2],
                "html_url": r[3],
                "created_at": r[4],
                "resolved_via_commit": r[5],
                "resolution_keyword": r[6]
            })

    return {
        "found": True,
        "person": person_data,
        "commits": commits,
        "pull_requests": pull_requests,
        "reviews": reviews,
        "explicitly_linked_issues": linked_issues,
        "summary": {
            "commits_count": len(commits),
            "prs_count": len(pull_requests),
            "reviews_count": len(reviews),
            "explicitly_linked_issues_count": len(linked_issues)
        }
    }
