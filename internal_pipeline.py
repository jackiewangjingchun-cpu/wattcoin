# Internal Development Pipeline v1.0.0
"""
Internal code submission interface for WattCoin core development.
Chat-style panel: upload files → AI review → auto-merge → promote to public.

Routes:
  GET  /admin/internal                     - Main page (chat-style submission panel)
  POST /admin/internal/api/submit          - Submit code (creates branch + PR on internal repo)
  GET  /admin/internal/api/prs             - List internal PRs with review status
  GET  /admin/internal/api/pr/<number>     - Single PR detail with full review data
  POST /admin/internal/api/promote/<number>- Promote merged internal PR to public repo
  GET  /admin/internal/api/review-status/<number> - Poll for review completion
"""

import os
import json
import re
import base64
import time
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template_string, request, jsonify, session, redirect, url_for

internal_bp = Blueprint('internal', __name__)

# =============================================================================
# CONFIG
# =============================================================================

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
INTERNAL_REPO = "WattCoin-Org/wattcoin-internal"
PUBLIC_REPO = "WattCoin-Org/wattcoin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Files that should NEVER be promoted to public repo
PROMOTE_IGNORE = {
    "tests/", "docs/internal/", ".env", "security_config.py",
    "INTERNAL_TASKS.md", "CHANGELOG_INTERNAL.md"
}

# Patterns to scan for before promotion (privacy check)
SANITIZE_PATTERNS = [
    (r'\bChris\b', "Personal name detected"),
    (r'@gmail\.com|@outlook\.com|@hotmail\.com', "Personal email detected"),
    (r'sk-ant-api|ghp_|xai-|moltbook_sk', "API key detected"),
]

# =============================================================================
# AUTH (reuse admin session)
# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated

def github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_internal_prs(state="all", per_page=20):
    """Fetch PRs from internal repo."""
    import requests as req
    try:
        resp = req.get(
            f"https://api.github.com/repos/{INTERNAL_REPO}/pulls?state={state}&per_page={per_page}&sort=created&direction=desc",
            headers=github_headers(), timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
        return []
    except:
        return []

def get_internal_pr_detail(pr_number):
    """Get full PR detail from internal repo."""
    import requests as req
    try:
        resp = req.get(
            f"https://api.github.com/repos/{INTERNAL_REPO}/pulls/{pr_number}",
            headers=github_headers(), timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except:
        return None

def get_internal_pr_review(pr_number):
    """Get AI review data for an internal PR from stored reviews."""
    from pr_security import load_json_data, DATA_DIR
    reviews_file = f"{DATA_DIR}/pr_reviews.json"
    reviews = load_json_data(reviews_file, default={"reviews": []})
    
    for review in reversed(reviews["reviews"]):
        if review.get("pr_number") == pr_number and review.get("repo") == INTERNAL_REPO:
            return review
    
    # Fallback: check without repo field (backward compat)
    for review in reversed(reviews["reviews"]):
        if review.get("pr_number") == pr_number:
            return review
    
    return None

def sanitize_check(content, filepath=""):
    """Check content for privacy violations before promotion."""
    issues = []
    for pattern, msg in SANITIZE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append({"file": filepath, "issue": msg, "pattern": pattern})
    return issues

def should_ignore_for_promotion(filepath):
    """Check if file should be excluded from promotion."""
    for ignore in PROMOTE_IGNORE:
        if filepath.startswith(ignore) or filepath == ignore.rstrip("/"):
            return True
    # Also ignore test files by pattern
    if filepath.endswith("_test.py") or filepath.endswith(".test.py"):
        return True
    return False


# =============================================================================
# API ROUTES
# =============================================================================

@internal_bp.route('/admin/internal')
@login_required
def internal_page():
    """Render the internal pipeline page."""
    return render_template_string(INTERNAL_TEMPLATE)


@internal_bp.route('/admin/internal/api/submit', methods=['POST'])
@login_required
def submit_code():
    """
    Submit code to internal repo. Creates branch + PR.
    
    Accepts multipart/form-data:
      - description: PR description / commit message
      - files: uploaded file(s)
      - paths: JSON array of target paths for each file
    
    Or JSON body:
      - description: PR description
      - files: [{filename, content, path}]
    """
    import requests as req
    
    try:
        # Parse input
        if request.content_type and 'multipart' in request.content_type:
            description = request.form.get('description', 'Internal submission')
            uploaded_files = request.files.getlist('files')
            paths_json = request.form.get('paths', '[]')
            try:
                target_paths = json.loads(paths_json)
            except:
                target_paths = []
            
            file_data = []
            for i, f in enumerate(uploaded_files):
                content = f.read()
                path = target_paths[i] if i < len(target_paths) else f.filename
                # Try to decode as text, fall back to base64
                try:
                    text_content = content.decode('utf-8')
                    file_data.append({
                        "filename": f.filename,
                        "content": text_content,
                        "path": path,
                        "encoding": "utf-8"
                    })
                except UnicodeDecodeError:
                    file_data.append({
                        "filename": f.filename,
                        "content": base64.b64encode(content).decode(),
                        "path": path,
                        "encoding": "base64"
                    })
        else:
            data = request.get_json()
            description = data.get('description', 'Internal submission')
            file_data = data.get('files', [])
        
        if not file_data:
            return jsonify({"error": "No files provided"}), 400
        
        # Generate branch name
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        branch_name = f"internal/{timestamp}"
        safe_desc = re.sub(r'[^a-zA-Z0-9-]', '-', description[:30].lower()).strip('-')
        if safe_desc:
            branch_name = f"internal/{safe_desc}-{timestamp}"
        
        # Get main branch SHA
        ref_resp = req.get(
            f"https://api.github.com/repos/{INTERNAL_REPO}/git/ref/heads/main",
            headers=github_headers(), timeout=10
        )
        if ref_resp.status_code != 200:
            return jsonify({"error": "Failed to get main branch"}), 500
        main_sha = ref_resp.json()["object"]["sha"]
        
        # Create branch
        branch_resp = req.post(
            f"https://api.github.com/repos/{INTERNAL_REPO}/git/refs",
            headers=github_headers(), timeout=10,
            json={"ref": f"refs/heads/{branch_name}", "sha": main_sha}
        )
        if branch_resp.status_code not in [200, 201]:
            return jsonify({"error": f"Failed to create branch: {branch_resp.json().get('message', '')}"}), 500
        
        # Get current tree
        tree_resp = req.get(
            f"https://api.github.com/repos/{INTERNAL_REPO}/git/trees/{main_sha}?recursive=1",
            headers=github_headers(), timeout=15
        )
        current_tree = tree_resp.json() if tree_resp.status_code == 200 else {"tree": []}
        
        # Create blobs for new files
        tree_items = []
        committed_files = []
        for fd in file_data:
            path = fd.get("path", fd.get("filename", "unnamed"))
            content = fd.get("content", "")
            encoding = fd.get("encoding", "utf-8")
            
            blob_data = {"encoding": encoding}
            if encoding == "base64":
                blob_data["content"] = content
            else:
                blob_data["content"] = content
                blob_data["encoding"] = "utf-8"
            
            blob_resp = req.post(
                f"https://api.github.com/repos/{INTERNAL_REPO}/git/blobs",
                headers=github_headers(), timeout=10,
                json=blob_data
            )
            if blob_resp.status_code != 201:
                return jsonify({"error": f"Failed to create blob for {path}"}), 500
            
            tree_items.append({
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_resp.json()["sha"]
            })
            committed_files.append(path)
        
        # Create new tree (base on current)
        new_tree_resp = req.post(
            f"https://api.github.com/repos/{INTERNAL_REPO}/git/trees",
            headers=github_headers(), timeout=15,
            json={"base_tree": current_tree.get("sha", main_sha), "tree": tree_items}
        )
        if new_tree_resp.status_code != 201:
            return jsonify({"error": "Failed to create tree"}), 500
        
        # Create commit
        commit_resp = req.post(
            f"https://api.github.com/repos/{INTERNAL_REPO}/git/commits",
            headers=github_headers(), timeout=10,
            json={
                "message": description,
                "tree": new_tree_resp.json()["sha"],
                "parents": [main_sha]
            }
        )
        if commit_resp.status_code != 201:
            return jsonify({"error": "Failed to create commit"}), 500
        
        # Update branch to point to new commit
        req.patch(
            f"https://api.github.com/repos/{INTERNAL_REPO}/git/refs/heads/{branch_name}",
            headers=github_headers(), timeout=10,
            json={"sha": commit_resp.json()["sha"]}
        )
        
        # Create PR
        pr_body = f"{description}\n\n**Files:** {', '.join(committed_files)}\n\n**Submitted via:** Internal Pipeline UI"
        pr_resp = req.post(
            f"https://api.github.com/repos/{INTERNAL_REPO}/pulls",
            headers=github_headers(), timeout=10,
            json={
                "title": description,
                "body": pr_body,
                "head": branch_name,
                "base": "main"
            }
        )
        if pr_resp.status_code not in [200, 201]:
            return jsonify({"error": f"Failed to create PR: {pr_resp.json().get('message', '')}"}), 500
        
        pr_data = pr_resp.json()
        
        return jsonify({
            "success": True,
            "pr_number": pr_data["number"],
            "pr_url": pr_data["html_url"],
            "branch": branch_name,
            "files": committed_files,
            "message": f"PR #{pr_data['number']} created — AI review will trigger via webhook"
        }), 201
        
    except Exception as e:
        print(f"[INTERNAL] Submit error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@internal_bp.route('/admin/internal/api/prs')
@login_required
def list_internal_prs():
    """List internal PRs with review status."""
    state = request.args.get('state', 'all')
    prs = get_internal_prs(state=state)
    
    result = []
    for pr in prs:
        review = get_internal_pr_review(pr["number"])
        result.append({
            "number": pr["number"],
            "title": pr["title"],
            "state": pr["state"],
            "merged": pr.get("merged", False) or (pr.get("merged_at") is not None),
            "author": pr["user"]["login"],
            "created_at": pr["created_at"],
            "updated_at": pr["updated_at"],
            "review_score": review.get("review", {}).get("score") if review else None,
            "review_passed": review.get("review", {}).get("pass") if review else None,
            "has_review": review is not None,
            "url": pr["html_url"]
        })
    
    return jsonify(result)


@internal_bp.route('/admin/internal/api/pr/<int:pr_number>')
@login_required
def get_pr_detail(pr_number):
    """Get full PR detail with review data."""
    pr = get_internal_pr_detail(pr_number)
    if not pr:
        return jsonify({"error": "PR not found"}), 404
    
    review = get_internal_pr_review(pr_number)
    
    # Get diff
    import requests as req
    try:
        diff_resp = req.get(
            f"https://api.github.com/repos/{INTERNAL_REPO}/pulls/{pr_number}",
            headers={**github_headers(), "Accept": "application/vnd.github.v3.diff"},
            timeout=15
        )
        diff = diff_resp.text if diff_resp.status_code == 200 else ""
    except:
        diff = ""
    
    return jsonify({
        "number": pr["number"],
        "title": pr["title"],
        "body": pr.get("body", ""),
        "state": pr["state"],
        "merged": pr.get("merged", False) or (pr.get("merged_at") is not None),
        "author": pr["user"]["login"],
        "created_at": pr["created_at"],
        "files_changed": pr.get("changed_files", 0),
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "diff": diff[:10000],  # Cap diff size
        "review": review.get("review") if review else None,
        "review_raw": review if review else None,
        "url": pr["html_url"]
    })


@internal_bp.route('/admin/internal/api/review-status/<int:pr_number>')
@login_required
def review_status(pr_number):
    """Poll for review completion. Returns current status."""
    pr = get_internal_pr_detail(pr_number)
    review = get_internal_pr_review(pr_number)
    
    if not pr:
        return jsonify({"status": "not_found"}), 404
    
    merged = pr.get("merged", False) or (pr.get("merged_at") is not None)
    
    if review:
        review_data = review.get("review", {})
        return jsonify({
            "status": "reviewed",
            "score": review_data.get("score", 0),
            "passed": review_data.get("pass", False),
            "confidence": review_data.get("confidence", ""),
            "summary": review_data.get("summary", review_data.get("feedback", "")),
            "dimensions": review_data.get("dimensions", {}),
            "concerns": review_data.get("concerns", []),
            "novel_patterns": review_data.get("novel_patterns", []),
            "suggested_changes": review_data.get("suggested_changes", []),
            "merged": merged,
            "pr_state": pr["state"]
        })
    else:
        return jsonify({
            "status": "pending",
            "merged": merged,
            "pr_state": pr["state"]
        })


@internal_bp.route('/admin/internal/api/promote/<int:pr_number>', methods=['POST'])
@login_required
def promote_to_public(pr_number):
    """
    Promote a merged internal PR to the public repo.
    Runs sanitization check, excludes ignored files, pushes to public.
    """
    import requests as req
    
    # Verify PR is merged
    pr = get_internal_pr_detail(pr_number)
    if not pr:
        return jsonify({"error": "PR not found"}), 404
    
    merged = pr.get("merged", False) or (pr.get("merged_at") is not None)
    if not merged:
        return jsonify({"error": "PR not merged yet"}), 400
    
    try:
        # Get files changed in the PR
        files_resp = req.get(
            f"https://api.github.com/repos/{INTERNAL_REPO}/pulls/{pr_number}/files",
            headers=github_headers(), timeout=10
        )
        if files_resp.status_code != 200:
            return jsonify({"error": "Failed to get PR files"}), 500
        
        pr_files = files_resp.json()
        
        # Filter and sanitize
        sanitize_issues = []
        files_to_promote = []
        files_skipped = []
        
        for f in pr_files:
            filepath = f["filename"]
            
            # Skip ignored files
            if should_ignore_for_promotion(filepath):
                files_skipped.append(filepath)
                continue
            
            # Skip deleted files (status == "removed")
            if f.get("status") == "removed":
                files_to_promote.append({"path": filepath, "action": "delete"})
                continue
            
            # Get file content from internal repo (current main, post-merge)
            content_resp = req.get(
                f"https://api.github.com/repos/{INTERNAL_REPO}/contents/{filepath}?ref=main",
                headers=github_headers(), timeout=10
            )
            if content_resp.status_code != 200:
                continue
            
            content_data = content_resp.json()
            content_raw = base64.b64decode(content_data["content"]).decode("utf-8", errors="replace")
            
            # Run sanitization check
            issues = sanitize_check(content_raw, filepath)
            if issues:
                sanitize_issues.extend(issues)
                continue
            
            files_to_promote.append({
                "path": filepath,
                "action": "update",
                "content": content_data["content"],  # Already base64
                "sha_internal": content_data["sha"]
            })
        
        if sanitize_issues:
            return jsonify({
                "error": "Sanitization check failed",
                "issues": sanitize_issues,
                "message": "Fix these issues in the internal repo before promoting"
            }), 400
        
        if not files_to_promote:
            return jsonify({"error": "No files to promote (all filtered by ignore rules)"}), 400
        
        # Push each file to public repo
        promoted = []
        errors = []
        
        for f in files_to_promote:
            if f["action"] == "delete":
                # Get current SHA in public repo
                pub_resp = req.get(
                    f"https://api.github.com/repos/{PUBLIC_REPO}/contents/{f['path']}",
                    headers=github_headers(), timeout=10
                )
                if pub_resp.status_code == 200:
                    pub_sha = pub_resp.json()["sha"]
                    del_resp = req.delete(
                        f"https://api.github.com/repos/{PUBLIC_REPO}/contents/{f['path']}",
                        headers=github_headers(), timeout=10,
                        json={
                            "message": f"Remove {f['path']} (promoted from internal PR #{pr_number})",
                            "sha": pub_sha
                        }
                    )
                    if del_resp.status_code in [200, 204]:
                        promoted.append(f["path"])
                    else:
                        errors.append(f"Delete {f['path']}: {del_resp.json().get('message', 'failed')}")
                continue
            
            # Check if file exists in public repo (need SHA for update)
            pub_resp = req.get(
                f"https://api.github.com/repos/{PUBLIC_REPO}/contents/{f['path']}",
                headers=github_headers(), timeout=10
            )
            
            push_data = {
                "message": f"Promote from internal PR #{pr_number}: {pr.get('title', 'update')[:60]}",
                "content": f["content"]
            }
            
            if pub_resp.status_code == 200:
                push_data["sha"] = pub_resp.json()["sha"]
            
            push_resp = req.put(
                f"https://api.github.com/repos/{PUBLIC_REPO}/contents/{f['path']}",
                headers=github_headers(), timeout=10,
                json=push_data
            )
            
            if push_resp.status_code in [200, 201]:
                promoted.append(f["path"])
            else:
                errors.append(f"{f['path']}: {push_resp.json().get('message', 'failed')}")
        
        return jsonify({
            "success": len(errors) == 0,
            "promoted": promoted,
            "skipped": files_skipped,
            "errors": errors,
            "pr_number": pr_number,
            "message": f"Promoted {len(promoted)} files to public repo" + (f" ({len(errors)} errors)" if errors else "")
        })
        
    except Exception as e:
        print(f"[INTERNAL] Promote error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@internal_bp.route('/admin/internal/api/trigger-review/<int:pr_number>', methods=['POST'])
@login_required
def trigger_manual_review(pr_number):
    """Manually trigger AI review for an internal PR (if webhook didn't fire)."""
    from api_webhooks import handle_internal_pr_review
    
    try:
        result = handle_internal_pr_review(pr_number, "manual")
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# TEMPLATE
# =============================================================================

INTERNAL_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Internal Pipeline - WattCoin Admin</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .chat-feed { max-height: calc(100vh - 340px); overflow-y: auto; }
        .msg-user { background: #1a2332; border-left: 3px solid #22c55e; }
        .msg-system { background: #1a1f2e; border-left: 3px solid #3b82f6; }
        .msg-error { background: #1a1f2e; border-left: 3px solid #ef4444; }
        .msg-success { background: #1a1f2e; border-left: 3px solid #22c55e; }
        .dim-score { display: inline-block; min-width: 24px; text-align: center; border-radius: 4px; padding: 1px 6px; font-size: 12px; font-weight: 600; }
        .dim-good { background: #166534; color: #86efac; }
        .dim-ok { background: #854d0e; color: #fde047; }
        .dim-bad { background: #991b1b; color: #fca5a5; }
        .file-chip { display: inline-flex; align-items: center; gap: 4px; background: #374151; border-radius: 12px; padding: 2px 10px; font-size: 12px; margin: 2px; }
        .file-chip .remove { cursor: pointer; opacity: 0.5; }
        .file-chip .remove:hover { opacity: 1; }
        .pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: #facc15; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .promote-btn { transition: all 0.2s; }
        .promote-btn:hover { transform: scale(1.02); }
        #file-input { display: none; }
        .pr-item { cursor: pointer; transition: background 0.15s; }
        .pr-item:hover { background: #1f2937; }
        .pr-item.active { background: #1e3a5f; border-left: 3px solid #3b82f6; }
    </style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
    <div class="max-w-7xl mx-auto p-4">
        <!-- Header -->
        <div class="flex justify-between items-center mb-3">
            <div>
                <h1 class="text-2xl font-bold text-green-400">⚡ WattCoin Admin</h1>
                <p class="text-gray-500 text-sm">Internal Development Pipeline v1.0.0</p>
            </div>
            <div class="flex items-center gap-3">
                <a href="{{ url_for('admin.dashboard') }}" class="text-gray-400 hover:text-gray-200 text-sm">← Back to Dashboard</a>
                <a href="{{ url_for('admin.logout') }}" class="text-gray-400 hover:text-red-400 text-sm">Logout</a>
            </div>
        </div>
        
        <!-- Nav Tabs -->
        <div class="flex gap-1 mb-4 border-b border-gray-700">
            <a href="{{ url_for('admin.dashboard') }}" 
               class="px-4 py-2 text-sm font-medium border-b-2 border-transparent text-gray-400 hover:text-gray-200">
                🎯 PR Bounties
            </a>
            <a href="{{ url_for('admin.submissions') }}" 
               class="px-4 py-2 text-sm font-medium border-b-2 border-transparent text-gray-400 hover:text-gray-200">
                📋 Agent Tasks
            </a>
            <a href="{{ url_for('internal.internal_page') }}" 
               class="px-4 py-2 text-sm font-medium border-b-2 border-green-400 text-green-400">
                🔧 Internal Pipeline
            </a>
            <a href="{{ url_for('admin.api_keys') }}" 
               class="px-4 py-2 text-sm font-medium border-b-2 border-transparent text-gray-400 hover:text-gray-200">
                🔑 Scraper Keys
            </a>
        </div>

        <!-- Main Layout: Sidebar + Chat -->
        <div class="flex gap-4" style="height: calc(100vh - 180px);">
            
            <!-- Left Sidebar: PR List -->
            <div class="w-72 flex-shrink-0 bg-gray-800 rounded-lg overflow-hidden flex flex-col">
                <div class="p-3 border-b border-gray-700 flex justify-between items-center">
                    <span class="text-sm font-semibold text-gray-300">Internal PRs</span>
                    <select id="pr-filter" class="bg-gray-700 text-xs text-gray-300 rounded px-2 py-1 border-0" onchange="loadPRs()">
                        <option value="all">All</option>
                        <option value="open">Open</option>
                        <option value="closed">Closed</option>
                    </select>
                </div>
                <div id="pr-list" class="flex-1 overflow-y-auto">
                    <div class="p-4 text-center text-gray-500 text-sm">Loading...</div>
                </div>
            </div>

            <!-- Main Chat Area -->
            <div class="flex-1 flex flex-col bg-gray-800 rounded-lg overflow-hidden">
                
                <!-- Chat Feed -->
                <div id="chat-feed" class="chat-feed flex-1 p-4 space-y-3">
                    <div class="msg-system rounded-lg p-4">
                        <div class="text-blue-400 text-sm font-semibold mb-1">🔧 Internal Pipeline</div>
                        <div class="text-gray-300 text-sm">
                            Submit code to the internal repo for AI review. Upload files, set their target paths, 
                            and describe your changes. The AI will review, and passing code auto-merges. 
                            Merged PRs can be promoted to the public repo.
                        </div>
                    </div>
                </div>
                
                <!-- Input Area -->
                <div class="border-t border-gray-700 p-3">
                    <!-- File chips -->
                    <div id="file-chips" class="flex flex-wrap gap-1 mb-2 min-h-[28px]"></div>
                    
                    <!-- Input row -->
                    <div class="flex gap-2">
                        <button onclick="document.getElementById('file-input').click()" 
                                class="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm text-gray-300 flex-shrink-0"
                                title="Attach files">
                            📎
                        </button>
                        <input type="file" id="file-input" multiple onchange="handleFiles(this.files)">
                        <input type="text" id="description-input" 
                               placeholder="Describe your changes... (commit message)"
                               class="flex-1 bg-gray-700 text-gray-100 rounded-lg px-4 py-2 text-sm border border-gray-600 focus:border-green-400 focus:outline-none"
                               onkeydown="if(event.key==='Enter' && !event.shiftKey) submitCode()">
                        <button onclick="submitCode()" id="submit-btn"
                                class="px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-semibold text-white flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed">
                            Submit →
                        </button>
                    </div>
                    <div class="text-gray-500 text-xs mt-1">
                        Files will be placed at their original paths. Edit paths by clicking the file chip.
                    </div>
                </div>
            </div>
        </div>
    </div>

<script>
// =============================================================================
// STATE
// =============================================================================
let pendingFiles = [];  // [{file: File, path: string}]
let pollingIntervals = {};  // {pr_number: intervalId}

// =============================================================================
// FILE HANDLING
// =============================================================================
function handleFiles(fileList) {
    for (const f of fileList) {
        pendingFiles.push({ file: f, path: f.name });
    }
    renderFileChips();
    document.getElementById('file-input').value = '';
}

function renderFileChips() {
    const container = document.getElementById('file-chips');
    container.innerHTML = pendingFiles.map((f, i) => `
        <div class="file-chip">
            <span class="text-gray-300" contenteditable="true" 
                  onblur="updatePath(${i}, this.textContent)"
                  title="Click to edit target path">${f.path}</span>
            <span class="remove text-red-400" onclick="removeFile(${i})">×</span>
        </div>
    `).join('');
}

function updatePath(index, newPath) {
    if (index < pendingFiles.length) {
        pendingFiles[index].path = newPath.trim();
    }
}

function removeFile(index) {
    pendingFiles.splice(index, 1);
    renderFileChips();
}

// =============================================================================
// SUBMISSION
// =============================================================================
async function submitCode() {
    const desc = document.getElementById('description-input').value.trim();
    if (!desc && pendingFiles.length === 0) return;
    
    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = 'Submitting...';
    
    // Add user message to chat
    const filesHtml = pendingFiles.map(f => `<code class="text-green-300">${f.path}</code>`).join(', ');
    addMessage('user', `
        <div class="font-semibold text-green-300 mb-1">${escapeHtml(desc || 'Code submission')}</div>
        ${pendingFiles.length > 0 ? `<div class="text-gray-400 text-xs">Files: ${filesHtml}</div>` : ''}
    `);
    
    try {
        const formData = new FormData();
        formData.append('description', desc || 'Internal submission');
        formData.append('paths', JSON.stringify(pendingFiles.map(f => f.path)));
        pendingFiles.forEach(f => formData.append('files', f.file));
        
        const resp = await fetch('/admin/internal/api/submit', {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();
        
        if (data.success) {
            addMessage('system', `
                <div class="text-blue-400 text-sm font-semibold mb-1">✅ PR #${data.pr_number} Created</div>
                <div class="text-gray-300 text-sm mb-2">
                    Branch: <code>${data.branch}</code><br>
                    <a href="${data.pr_url}" target="_blank" class="text-blue-400 hover:underline">${data.pr_url}</a>
                </div>
                <div class="flex items-center gap-2 text-yellow-400 text-xs">
                    <div class="pulse-dot"></div>
                    <span id="status-${data.pr_number}">Waiting for AI review...</span>
                </div>
            `);
            
            // Start polling for review
            startPolling(data.pr_number);
        } else {
            addMessage('error', `<div class="text-red-400 text-sm">❌ ${data.error}</div>`);
        }
    } catch (e) {
        addMessage('error', `<div class="text-red-400 text-sm">❌ Network error: ${e.message}</div>`);
    }
    
    // Reset
    pendingFiles = [];
    renderFileChips();
    document.getElementById('description-input').value = '';
    btn.disabled = false;
    btn.textContent = 'Submit →';
    loadPRs();
}

// =============================================================================
// POLLING
// =============================================================================
function startPolling(prNumber) {
    if (pollingIntervals[prNumber]) return;
    
    let attempts = 0;
    pollingIntervals[prNumber] = setInterval(async () => {
        attempts++;
        try {
            const resp = await fetch(`/admin/internal/api/review-status/${prNumber}`);
            const data = await resp.json();
            
            if (data.status === 'reviewed') {
                clearInterval(pollingIntervals[prNumber]);
                delete pollingIntervals[prNumber];
                showReviewResult(prNumber, data);
                loadPRs();
            } else if (attempts > 60) {  // 5 min timeout
                clearInterval(pollingIntervals[prNumber]);
                delete pollingIntervals[prNumber];
                const statusEl = document.getElementById(`status-${prNumber}`);
                if (statusEl) statusEl.innerHTML = '⏱️ Review timed out. <button onclick="triggerReview(' + prNumber + ')" class="text-blue-400 underline">Trigger manually</button>';
            }
        } catch (e) {
            // Silently retry
        }
    }, 5000);
}

function showReviewResult(prNumber, data) {
    const scoreColor = data.score >= 9 ? 'text-green-400' : data.score >= 7 ? 'text-yellow-400' : 'text-red-400';
    const icon = data.passed ? '✅' : '❌';
    
    // Build dimensions HTML
    let dimsHtml = '';
    if (data.dimensions && Object.keys(data.dimensions).length > 0) {
        dimsHtml = '<div class="mt-2 space-y-1">';
        for (const [name, dim] of Object.entries(data.dimensions)) {
            if (dim && typeof dim === 'object' && dim.score !== undefined) {
                const s = dim.score;
                const cls = s >= 8 ? 'dim-good' : s >= 5 ? 'dim-ok' : 'dim-bad';
                const label = name.replace(/_/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase());
                dimsHtml += `<div class="flex items-center gap-2 text-xs">
                    <span class="dim-score ${cls}">${s}</span>
                    <span class="text-gray-400">${label}</span>
                </div>`;
            }
        }
        dimsHtml += '</div>';
    }
    
    // Concerns
    let concernsHtml = '';
    if (data.concerns && data.concerns.length > 0) {
        concernsHtml = `<div class="mt-2 text-xs"><span class="text-red-400 font-semibold">Concerns:</span> ${data.concerns.map(c => escapeHtml(c)).join('; ')}</div>`;
    }
    
    // Promote button (only if merged)
    let promoteHtml = '';
    if (data.merged) {
        promoteHtml = `<button onclick="promotePR(${prNumber})" class="promote-btn mt-2 px-3 py-1 bg-purple-600 hover:bg-purple-500 rounded text-xs font-semibold text-white">🚀 Promote to Public</button>`;
    }
    
    addMessage(data.passed ? 'success' : 'error', `
        <div class="flex items-center gap-2 mb-1">
            <span class="text-sm font-semibold ${scoreColor}">${icon} PR #${prNumber} — Score: ${data.score}/10</span>
            ${data.confidence ? `<span class="text-xs text-gray-500">(${data.confidence})</span>` : ''}
        </div>
        <div class="text-gray-300 text-sm">${escapeHtml(data.summary || '')}</div>
        ${dimsHtml}
        ${concernsHtml}
        ${data.merged ? '<div class="text-green-400 text-xs mt-1">✅ Auto-merged</div>' : ''}
        ${promoteHtml}
    `);
    
    // Update status line
    const statusEl = document.getElementById(`status-${prNumber}`);
    if (statusEl) statusEl.textContent = data.passed ? 'Review complete — PASSED' : 'Review complete — FAILED';
}

// =============================================================================
// PROMOTION
// =============================================================================
async function promotePR(prNumber) {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '🔄 Promoting...';
    
    try {
        const resp = await fetch(`/admin/internal/api/promote/${prNumber}`, { method: 'POST' });
        const data = await resp.json();
        
        if (data.success) {
            addMessage('success', `
                <div class="text-green-400 text-sm font-semibold mb-1">🚀 Promoted to Public Repo!</div>
                <div class="text-gray-300 text-xs">
                    Files: ${data.promoted.map(f => `<code>${f}</code>`).join(', ')}<br>
                    ${data.skipped.length > 0 ? `Skipped (internal only): ${data.skipped.join(', ')}` : ''}
                </div>
            `);
            btn.textContent = '✅ Promoted';
            btn.classList.replace('bg-purple-600', 'bg-gray-600');
        } else {
            addMessage('error', `
                <div class="text-red-400 text-sm font-semibold mb-1">❌ Promotion Failed</div>
                <div class="text-gray-300 text-xs">${escapeHtml(data.error || data.message)}</div>
                ${data.issues ? data.issues.map(i => `<div class="text-yellow-400 text-xs">⚠️ ${escapeHtml(i.file)}: ${escapeHtml(i.issue)}</div>`).join('') : ''}
            `);
            btn.disabled = false;
            btn.textContent = '🚀 Promote to Public';
        }
    } catch (e) {
        addMessage('error', `<div class="text-red-400 text-sm">❌ ${e.message}</div>`);
        btn.disabled = false;
        btn.textContent = '🚀 Promote to Public';
    }
}

// =============================================================================
// MANUAL REVIEW TRIGGER
// =============================================================================
async function triggerReview(prNumber) {
    addMessage('system', `<div class="text-blue-400 text-sm">🔄 Triggering manual review for PR #${prNumber}...</div>`);
    try {
        const resp = await fetch(`/admin/internal/api/trigger-review/${prNumber}`, { method: 'POST' });
        startPolling(prNumber);
    } catch (e) {
        addMessage('error', `<div class="text-red-400 text-sm">❌ ${e.message}</div>`);
    }
}

// =============================================================================
// PR LIST
// =============================================================================
async function loadPRs() {
    const filter = document.getElementById('pr-filter').value;
    const container = document.getElementById('pr-list');
    
    try {
        const resp = await fetch(`/admin/internal/api/prs?state=${filter}`);
        const prs = await resp.json();
        
        if (prs.length === 0) {
            container.innerHTML = '<div class="p-4 text-center text-gray-500 text-sm">No internal PRs yet</div>';
            return;
        }
        
        container.innerHTML = prs.map(pr => {
            const scoreHtml = pr.has_review 
                ? `<span class="${pr.review_score >= 9 ? 'text-green-400' : pr.review_score >= 7 ? 'text-yellow-400' : 'text-red-400'}">${pr.review_score}/10</span>`
                : '<span class="text-gray-500">—</span>';
            
            const statusIcon = pr.merged ? '🟢' : pr.state === 'open' ? '🟡' : '⚪';
            const age = timeAgo(pr.created_at);
            
            return `
                <div class="pr-item px-3 py-2 border-b border-gray-700" onclick="viewPR(${pr.number})">
                    <div class="flex justify-between items-start">
                        <div class="text-sm text-gray-200 truncate flex-1">${statusIcon} #${pr.number}</div>
                        <div class="text-xs ml-2">${scoreHtml}</div>
                    </div>
                    <div class="text-xs text-gray-400 truncate">${escapeHtml(pr.title)}</div>
                    <div class="text-xs text-gray-600">${age}</div>
                </div>
            `;
        }).join('');
    } catch (e) {
        container.innerHTML = '<div class="p-4 text-center text-red-400 text-sm">Failed to load</div>';
    }
}

async function viewPR(prNumber) {
    try {
        const resp = await fetch(`/admin/internal/api/pr/${prNumber}`);
        const pr = await resp.json();
        
        if (pr.error) return;
        
        let reviewHtml = '';
        if (pr.review) {
            const s = pr.review;
            reviewHtml = `
                <div class="mt-2 p-2 bg-gray-900 rounded text-xs">
                    <div class="font-semibold ${s.score >= 9 ? 'text-green-400' : s.score >= 7 ? 'text-yellow-400' : 'text-red-400'}">
                        Score: ${s.score}/10 — ${s.pass ? 'PASS' : 'FAIL'}
                    </div>
                    <div class="text-gray-400 mt-1">${escapeHtml(s.summary || s.feedback || '')}</div>
                </div>
            `;
        }
        
        addMessage('system', `
            <div class="text-blue-400 text-sm font-semibold mb-1">📋 PR #${prNumber}: ${escapeHtml(pr.title)}</div>
            <div class="text-gray-400 text-xs mb-1">
                +${pr.additions} / -${pr.deletions} | ${pr.files_changed} files | 
                ${pr.merged ? '🟢 Merged' : pr.state === 'open' ? '🟡 Open' : '⚪ Closed'}
            </div>
            <div class="text-gray-300 text-sm">${escapeHtml(pr.body || '').substring(0, 300)}</div>
            ${reviewHtml}
            ${pr.merged ? `<button onclick="promotePR(${prNumber})" class="promote-btn mt-2 px-3 py-1 bg-purple-600 hover:bg-purple-500 rounded text-xs font-semibold text-white">🚀 Promote to Public</button>` : ''}
            ${pr.state === 'open' && !pr.review ? `<button onclick="triggerReview(${prNumber})" class="mt-2 px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-xs font-semibold text-white">🤖 Trigger Review</button>` : ''}
        `);
    } catch (e) {
        addMessage('error', `<div class="text-red-400 text-sm">❌ Failed to load PR: ${e.message}</div>`);
    }
}

// =============================================================================
// CHAT HELPERS
// =============================================================================
function addMessage(type, html) {
    const feed = document.getElementById('chat-feed');
    const cls = type === 'user' ? 'msg-user' : type === 'error' ? 'msg-error' : type === 'success' ? 'msg-success' : 'msg-system';
    const div = document.createElement('div');
    div.className = `${cls} rounded-lg p-3`;
    div.innerHTML = html;
    feed.appendChild(div);
    feed.scrollTop = feed.scrollHeight;
}

function escapeHtml(text) {
    if (!text) return '';
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

function timeAgo(dateStr) {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
}

// =============================================================================
// INIT
// =============================================================================
loadPRs();
</script>
</body>
</html>
"""
