import os
import re
import base64
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import httpx

from backend.config import DEFAULT_WORKSPACE_ID
from backend.db.falkordb_client import db_client

logger = logging.getLogger("company_brain.external_importer")

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svg", ".bmp", ".tiff",
    ".pdf", ".zip", ".tar", ".gz", ".tgz", ".bz2", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".dmg",
    ".pyc", ".pyo", ".pyd", ".whl", ".class", ".jar", ".war",
    ".wasm", ".mp3", ".mp4", ".wav", ".mov", ".avi", ".mkv",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".db", ".sqlite", ".sqlite3", ".parquet", ".arrow"
}

IGNORED_DIR_PREFIXES = (
    ".git/", ".github/", "node_modules/", "__pycache__/",
    ".venv/", "venv/", "vendor/", "dist/", "build/"
)

MAX_FILE_SIZE_BYTES_DEFAULT = 60_000  # 60 KB limit per file


def parse_github_repo_url(url: str) -> Optional[Tuple[str, str]]:
    """
    Extract (owner, repo) from GitHub URL or owner/repo format.
    Preserves exact backward compatibility with existing tests.
    """
    clean = url.strip().rstrip("/")
    # Handle https://github.com/owner/repo or github.com/owner/repo
    m = re.search(r"github\.com/([^/]+)/([^/]+)", clean)
    if m:
        repo = m.group(2).removesuffix(".git")
        return (m.group(1), repo)
    # Handle owner/repo
    m = re.match(r"^([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)$", clean)
    if m:
        return (m.group(1), m.group(2).removesuffix(".git"))
    return None


def parse_github_url_details(url: str) -> Optional[Dict[str, Any]]:
    """
    Detailed parser extracting owner, repo, ref (branch/tag/sha), and canonical repo_url.
    Handles /tree/{ref} and /blob/{ref}/path URLs.
    """
    clean = url.strip().rstrip("/")
    m = re.search(r"github\.com/([^/]+)/([^/]+)(?:/(?:tree|blob)/([^/]+))?", clean)
    if m:
        owner = m.group(1)
        repo = m.group(2).removesuffix(".git")
        ref = m.group(3)
        return {
            "owner": owner,
            "repo": repo,
            "ref": ref,
            "repo_url": f"https://github.com/{owner}/{repo}"
        }
    m = re.match(r"^([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)$", clean)
    if m:
        owner = m.group(1)
        repo = m.group(2).removesuffix(".git")
        return {
            "owner": owner,
            "repo": repo,
            "ref": None,
            "repo_url": f"https://github.com/{owner}/{repo}"
        }
    return None


def chunk_text_into_evidence(content: str, max_chars: int = 400) -> List[Dict[str, Any]]:
    """Chunk document content into grounded evidence excerpts with precise line locators."""
    lines = content.splitlines()
    chunks = []
    current_lines = []
    start_line = 1

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            if current_lines:
                text = " ".join(current_lines).strip()
                if len(text) >= 5:
                    chunks.append({
                        "excerpt": text[:max_chars],
                        "start_line": start_line,
                        "end_line": idx - 1
                    })
                current_lines = []
            start_line = idx + 1
        else:
            if not current_lines:
                start_line = idx
            current_lines.append(stripped)
            # Break if chunk gets too long
            if sum(len(l) for l in current_lines) >= max_chars:
                text = " ".join(current_lines).strip()
                chunks.append({
                    "excerpt": text[:max_chars],
                    "start_line": start_line,
                    "end_line": idx
                })
                current_lines = []
                start_line = idx + 1

    if current_lines:
        text = " ".join(current_lines).strip()
        if len(text) >= 5:
            chunks.append({
                "excerpt": text[:max_chars],
                "start_line": start_line,
                "end_line": len(lines)
            })

    return chunks


def _get_file_priority(path: str) -> int:
    """Assign ingestion priority so prominent docs are loaded before deeply nested code."""
    p_lower = path.lower()
    filename = os.path.basename(p_lower)
    # Priority 0: Primary repository documentation
    if filename.startswith(("readme", "architecture", "prd", "design", "roadmap", "contributing", "security")):
        return 0
    # Priority 1: Markdown and text documentation
    if p_lower.endswith((".md", ".markdown", ".rst", ".txt")):
        return 1
    # Priority 2: Structured configs / specifications
    if p_lower.endswith((".json", ".yaml", ".yml", ".toml", ".sql", ".env.example")):
        return 2
    # Priority 3: Source code files
    if p_lower.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".sh", ".html", ".css")):
        return 3
    return 4


def import_github_repo(
    repo_url: str,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    max_files: int = 10,
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES_DEFAULT,
    ref: Optional[str] = None
) -> Dict[str, Any]:
    """
    Import public GitHub repository context without requiring OAuth.
    Fetches repo metadata and recursively lists nested files using the Git Trees API.
    Skips binaries, filters oversized files, and downloads bounded text files.
    Stores repository, source files, and evidence excerpts with stable IDs and idempotent upserts in FalkorDB.
    """
    parsed = parse_github_url_details(repo_url)
    if not parsed:
        return {
            "status": "INGESTION_FAILED",
            "error_code": "INVALID_URL",
            "error": f"Invalid GitHub URL format: '{repo_url}'. Expected format: https://github.com/owner/repo or owner/repo.",
            "files_imported": [],
            "files_failed": [],
            "skipped_files": []
        }

    owner = parsed["owner"]
    repo = parsed["repo"]
    target_ref = ref or parsed["ref"]

    headers = {
        "User-Agent": "CompanyBrain-Importer/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    # Optional server-side token (never leaked to client)
    gh_token = os.getenv("GITHUB_TOKEN")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    skipped_files: List[Dict[str, str]] = []
    files_failed: List[Dict[str, str]] = []

    try:
        with httpx.Client(timeout=20.0) as client:
            # 1. Fetch Repository Metadata
            repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
            repo_resp = client.get(repo_api_url, headers=headers)

            if repo_resp.status_code == 404:
                return {
                    "status": "INGESTION_FAILED",
                    "error_code": "REPO_NOT_FOUND",
                    "error": f"Repository '{owner}/{repo}' not found or is private. Only public repositories can be imported without OAuth.",
                    "files_imported": [],
                    "files_failed": [],
                    "skipped_files": []
                }
            elif repo_resp.status_code == 403 or repo_resp.status_code == 429:
                is_rate_limit = (
                    repo_resp.headers.get("x-ratelimit-remaining") == "0"
                    or "rate limit" in repo_resp.text.lower()
                )
                if is_rate_limit:
                    return {
                        "status": "INGESTION_FAILED",
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "error": f"GitHub API rate limit exceeded for '{owner}/{repo}'. Please try again later or configure GITHUB_TOKEN in server environment.",
                        "files_imported": [],
                        "files_failed": [],
                        "skipped_files": []
                    }
                return {
                    "status": "INGESTION_FAILED",
                    "error_code": "ACCESS_FORBIDDEN",
                    "error": f"Access forbidden to repository '{owner}/{repo}' (HTTP 403).",
                    "files_imported": [],
                    "files_failed": [],
                    "skipped_files": []
                }
            elif repo_resp.status_code != 200:
                return {
                    "status": "INGESTION_FAILED",
                    "error_code": f"HTTP_{repo_resp.status_code}",
                    "error": f"GitHub API returned HTTP {repo_resp.status_code}: {repo_resp.text[:200]}",
                    "files_imported": [],
                    "files_failed": [],
                    "skipped_files": []
                }

            repo_meta = repo_resp.json()
            default_branch = repo_meta.get("default_branch", "main")
            target_ref = target_ref or default_branch

            # 2. Fetch Recursive Git Tree
            tree_api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{target_ref}?recursive=1"
            tree_resp = client.get(tree_api_url, headers=headers)

            if tree_resp.status_code == 403 and tree_resp.headers.get("x-ratelimit-remaining") == "0":
                return {
                    "status": "INGESTION_FAILED",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "error": "GitHub API rate limit exceeded while retrieving repository tree.",
                    "files_imported": [],
                    "files_failed": [],
                    "skipped_files": []
                }
            elif tree_resp.status_code != 200:
                return {
                    "status": "INGESTION_FAILED",
                    "error_code": f"TREE_HTTP_{tree_resp.status_code}",
                    "error": f"Could not retrieve recursive tree for ref '{target_ref}': HTTP {tree_resp.status_code}",
                    "files_imported": [],
                    "files_failed": [],
                    "skipped_files": []
                }

            tree_data = tree_resp.json()
            tree_truncated = bool(tree_data.get("truncated", False))
            tree_items = tree_data.get("tree", [])

            # 3. Filter and Classify Blobs
            candidate_blobs = []
            for item in tree_items:
                if item.get("type") != "blob":
                    continue
                path = item.get("path", "")
                size = item.get("size", 0)

                # Skip ignored directory prefixes
                if any(path.startswith(prefix) or f"/{prefix}" in path for prefix in IGNORED_DIR_PREFIXES):
                    continue

                # Check binary file extension
                _, ext = os.path.splitext(path.lower())
                if ext in BINARY_EXTENSIONS:
                    skipped_files.append({"path": path, "reason": "BINARY_FILE"})
                    continue

                # Check file size limit
                if size > max_file_size_bytes:
                    skipped_files.append({
                        "path": path,
                        "reason": f"OVERSIZED ({size} bytes > {max_file_size_bytes} bytes limit)"
                    })
                    continue

                candidate_blobs.append(item)

            if not candidate_blobs:
                return {
                    "status": "INGESTION_FAILED",
                    "error_code": "NO_READABLE_FILES",
                    "error": f"No readable text or Markdown files found in '{owner}/{repo}' matching size constraints.",
                    "files_imported": [],
                    "files_failed": [],
                    "skipped_files": skipped_files
                }

            # Sort by priority, then path
            candidate_blobs.sort(key=lambda b: (_get_file_priority(b["path"]), b["path"]))

            # Bounded selection
            selected_blobs = candidate_blobs[:max_files]
            for unselected in candidate_blobs[max_files:]:
                skipped_files.append({
                    "path": unselected["path"],
                    "reason": f"BOUND_EXCEEDED (max_files limit: {max_files})"
                })

            # 4. Download file contents
            imported_docs: List[Dict[str, Any]] = []
            for blob in selected_blobs:
                path = blob["path"]
                # Fetch via GitHub raw contents endpoint
                content_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={target_ref}"
                raw_headers = dict(headers)
                raw_headers["Accept"] = "application/vnd.github.v3.raw"

                try:
                    f_resp = client.get(content_url, headers=raw_headers)
                    if f_resp.status_code == 200:
                        content_type = f_resp.headers.get("content-type", "")
                        # If returned as raw text
                        if "application/json" not in content_type:
                            text_content = f_resp.text
                        else:
                            # Standard JSON response fallback (e.g. from mock or API)
                            data = f_resp.json()
                            if isinstance(data, dict) and data.get("encoding") == "base64" and data.get("content"):
                                text_content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                            elif isinstance(data, dict) and data.get("download_url"):
                                dl_resp = client.get(data["download_url"], headers=headers)
                                if dl_resp.status_code == 200:
                                    text_content = dl_resp.text
                                else:
                                    files_failed.append({"path": path, "error": f"Download URL failed: HTTP {dl_resp.status_code}"})
                                    continue
                            else:
                                text_content = f_resp.text

                        imported_docs.append({
                            "title": path,
                            "path": path,
                            "content": text_content,
                            "source_uri": f"https://github.com/{owner}/{repo}/blob/{target_ref}/{path}",
                            "commit_sha": target_ref
                        })
                    else:
                        files_failed.append({"path": path, "error": f"HTTP {f_resp.status_code}"})
                except Exception as ex:
                    files_failed.append({"path": path, "error": f"Download exception: {str(ex)}"})

    except Exception as e:
        logger.exception("Failed to connect to GitHub")
        return {
            "status": "INGESTION_FAILED",
            "error_code": "NETWORK_EXCEPTION",
            "error": f"Network or connection error fetching repository: {str(e)}",
            "files_imported": [],
            "files_failed": files_failed,
            "skipped_files": skipped_files
        }

    # If all candidate files failed to download
    if not imported_docs:
        return {
            "status": "INGESTION_FAILED",
            "error_code": "ALL_DOWNLOADS_FAILED",
            "error": f"Failed to download content for any of the {len(selected_blobs)} candidate file(s) from '{owner}/{repo}'.",
            "files_imported": [],
            "files_failed": files_failed,
            "skipped_files": skipped_files
        }

    # 5. Persist into FalkorDB with Stable IDs and Idempotent Upserts
    safe_slug = re.sub(r"[^a-zA-Z0-9_]", "_", f"{owner}_{repo}".lower())
    project_id = f"proj_gh_{safe_slug}"

    ingest_result = store_imported_documents(
        documents=imported_docs,
        project_name=f"{owner}/{repo}",
        project_id=project_id,
        source_type="GITHUB_PUBLIC_REPO",
        workspace_id=workspace_id,
        repo_url=f"https://github.com/{owner}/{repo}",
        default_branch=default_branch,
        commit_ref=target_ref,
        tree_truncated=tree_truncated
    )

    # 6. Build Final Status (Distinguishing Partial vs Full Success)
    if files_failed:
        overall_status = "INGESTION_PARTIAL"
        message = (
            f"Partially imported {len(imported_docs)} file(s) and {ingest_result['evidence_created']} "
            f"evidence records from {owner}/{repo}; {len(files_failed)} file(s) failed."
        )
    else:
        overall_status = "INGESTED_SUCCESS"
        message = (
            f"Successfully imported {len(imported_docs)} file(s) and {ingest_result['evidence_created']} "
            f"grounded evidence records from {owner}/{repo}."
        )

    ingest_result["status"] = overall_status
    ingest_result["message"] = message
    ingest_result["files_failed"] = files_failed
    ingest_result["skipped_files"] = skipped_files
    ingest_result["tree_truncated"] = tree_truncated
    ingest_result["repo_metadata"] = {
        "owner": owner,
        "repo": repo,
        "repo_url": f"https://github.com/{owner}/{repo}",
        "default_branch": default_branch,
        "commit_ref": target_ref,
        "tree_truncated": tree_truncated
    }

    return ingest_result


def store_imported_documents(
    documents: List[Dict[str, Any]],
    project_name: str,
    project_id: str,
    source_type: str = "IMPORTED_DOCUMENT",
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    repo_url: Optional[str] = None,
    default_branch: Optional[str] = None,
    commit_ref: Optional[str] = None,
    tree_truncated: bool = False
) -> Dict[str, Any]:
    """
    Store parsed documents, evidence excerpts, locators, and project entities into FalkorDB.
    Guarantees stable IDs and idempotent upserts: re-running on identical content
    updates existing nodes in-place without duplicating nodes or relationships.
    """
    now_ts = datetime.now(timezone.utc).isoformat()
    files_imported = []
    total_evidence = 0
    total_sources = 0

    canonical_repo_url = repo_url or f"urn:company:project:{project_id}"
    canonical_commit = commit_ref or "HEAD"
    canonical_branch = default_branch or "main"

    # 1. Upsert Project Node (Idempotent MERGE)
    db_client.query("""
    MERGE (p:Project {workspace_id: $ws, id: $pid})
    ON CREATE SET p.name = $name,
                  p.description = $desc,
                  p.status = 'ACTIVE',
                  p.repo_url = $repo_url,
                  p.default_branch = $default_branch,
                  p.commit_sha = $commit_sha,
                  p.tree_truncated = $tree_truncated,
                  p.created_at = $ts,
                  p.updated_at = $ts
    ON MATCH SET p.name = $name,
                 p.repo_url = $repo_url,
                 p.default_branch = $default_branch,
                 p.commit_sha = $commit_sha,
                 p.tree_truncated = $tree_truncated,
                 p.status = 'ACTIVE',
                 p.updated_at = $ts
    """, {
        "ws": workspace_id,
        "pid": project_id,
        "name": project_name,
        "desc": f"External context from {project_name} ({source_type})",
        "repo_url": canonical_repo_url,
        "default_branch": canonical_branch,
        "commit_sha": canonical_commit,
        "tree_truncated": tree_truncated,
        "ts": now_ts
    })

    for doc in documents:
        title = doc.get("title", "Untitled Document")
        path = doc.get("path", title)
        content = str(doc.get("content", ""))
        file_commit = doc.get("commit_sha") or canonical_commit
        source_uri = doc.get("source_uri") or f"doc://imported/{path}"

        # Stable hash-based ID for Source (deterministic per workspace, project, and file path)
        path_hash = hashlib.sha256(f"{project_id}:{path}".encode()).hexdigest()[:12]
        source_id = f"src_{project_id}_{path_hash}"

        # 2. Upsert Source Node (Idempotent MERGE)
        db_client.query("""
        MERGE (s:Source {workspace_id: $ws, id: $sid})
        ON CREATE SET s.title = $title,
                      s.path = $path,
                      s.source_type = $stype,
                      s.source_uri = $uri,
                      s.repo_url = $repo_url,
                      s.commit_sha = $commit_sha,
                      s.content = $content,
                      s.created_at = $ts,
                      s.updated_at = $ts,
                      s.is_synthetic = false
        ON MATCH SET s.title = $title,
                     s.path = $path,
                     s.source_type = $stype,
                     s.source_uri = $uri,
                     s.repo_url = $repo_url,
                     s.commit_sha = $commit_sha,
                     s.content = $content,
                     s.updated_at = $ts,
                     s.is_synthetic = false
        """, {
            "ws": workspace_id,
            "sid": source_id,
            "title": title,
            "path": path,
            "stype": source_type,
            "uri": source_uri,
            "repo_url": canonical_repo_url,
            "commit_sha": file_commit,
            "content": content[:25000],  # Substantive text storage
            "ts": now_ts
        })

        # 3. Link Project -> Source
        db_client.query("""
        MATCH (p:Project {workspace_id: $ws, id: $pid})
        MATCH (s:Source {workspace_id: $ws, id: $sid})
        MERGE (p)-[:HAS_SOURCE]->(s)
        """, {"ws": workspace_id, "pid": project_id, "sid": source_id})

        total_sources += 1
        files_imported.append(path)

        # 4. Chunk into Evidence Records with Line Locators
        chunks = chunk_text_into_evidence(content)
        for chunk in chunks:
            excerpt = chunk["excerpt"]
            start_line = chunk["start_line"]
            end_line = chunk["end_line"]
            locator = f"{path}#L{start_line}-L{end_line}"
            ev_uri = f"{source_uri}#L{start_line}-L{end_line}"

            # Stable hash-based ID for Evidence (deterministic per source, start, and end line)
            ev_hash = hashlib.sha256(f"{source_id}:{start_line}:{end_line}".encode()).hexdigest()[:12]
            ev_id = f"ev_{source_id}_{start_line}_{end_line}_{ev_hash}"

            # Upsert Evidence Node
            db_client.query("""
            MERGE (ev:Evidence {workspace_id: $ws, id: $eid})
            ON CREATE SET ev.excerpt = $excerpt,
                          ev.locator = $locator,
                          ev.source_uri = $ev_uri,
                          ev.commit_sha = $commit_sha,
                          ev.created_at = $ts,
                          ev.updated_at = $ts,
                          ev.is_synthetic = false
            ON MATCH SET ev.excerpt = $excerpt,
                         ev.locator = $locator,
                         ev.source_uri = $ev_uri,
                         ev.commit_sha = $commit_sha,
                         ev.updated_at = $ts,
                         ev.is_synthetic = false
            """, {
                "ws": workspace_id,
                "eid": ev_id,
                "excerpt": excerpt,
                "locator": locator,
                "ev_uri": ev_uri,
                "commit_sha": file_commit,
                "ts": now_ts
            })

            # Link Evidence -> Source and Project -> Evidence
            db_client.query("""
            MATCH (ev:Evidence {workspace_id: $ws, id: $eid})
            MATCH (s:Source {workspace_id: $ws, id: $sid})
            MATCH (p:Project {workspace_id: $ws, id: $pid})
            MERGE (ev)-[:FROM_SOURCE]->(s)
            MERGE (ev)-[:SUPPORTED_BY]->(s)
            MERGE (p)-[:HAS_EVIDENCE]->(ev)
            """, {"ws": workspace_id, "eid": ev_id, "sid": source_id, "pid": project_id})

            total_evidence += 1

    return {
        "status": "INGESTED_SUCCESS",
        "project_id": project_id,
        "project_name": project_name,
        "source_type": source_type,
        "files_imported": files_imported,
        "sources_created": total_sources,
        "evidence_created": total_evidence,
        "timestamp": now_ts,
        "message": f"Successfully imported {total_sources} source file(s) and {total_evidence} grounded evidence records into FalkorDB."
    }
