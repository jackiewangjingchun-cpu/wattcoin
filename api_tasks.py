"""
WattCoin Agent Tasks API - Task Routing Marketplace
GET  /api/v1/tasks                    - List all agent tasks
GET  /api/v1/tasks/<id>               - Get single task
POST /api/v1/tasks/<id>/submit        - Submit task result
GET  /api/v1/tasks/<id>/submissions   - List submissions (admin)
POST /api/v1/tasks/<id>/approve       - Manual approve (admin)
POST /api/v1/tasks/<id>/reject        - Manual reject (admin)
"""

import os
import re
import json
import uuid
import time
import requests
import base58
from flask import Blueprint, jsonify, request
from datetime import datetime
from functools import wraps

tasks_bp = Blueprint('tasks', __name__)

# =============================================================================
# CONFIG
# =============================================================================

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = "WattCoin-Org/wattcoin"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/issues"

GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

BOUNTY_WALLET = "7vvNkG3JF3JpxLEavqZSkc5T3n9hHR98Uw23fbWdXVSF"
BOUNTY_WALLET_PRIVATE_KEY = os.getenv("BOUNTY_WALLET_PRIVATE_KEY", "")
WATT_MINT = "Gpmbh4PoQnL1kNgpMYDED3iv4fczcr7d3qNBLf8rpump"
SOLANA_RPC = "https://solana.publicnode.com"

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
SUBMISSIONS_FILE = "/app/data/task_submissions.json"
AUTO_APPROVE_CONFIDENCE = 0.8  # Auto-approve if Grok confidence >= this

# Cache
_tasks_cache = {"data": None, "expires": 0}
CACHE_TTL = 300  # 5 minutes

# =============================================================================
# STORAGE
# =============================================================================

def load_submissions():
    """Load submissions from JSON file."""
    try:
        with open(SUBMISSIONS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"submissions": []}

def save_submissions(data):
    """Save submissions to JSON file."""
    try:
        os.makedirs(os.path.dirname(SUBMISSIONS_FILE), exist_ok=True)
        with open(SUBMISSIONS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving submissions: {e}")
        return False

def generate_submission_id():
    """Generate unique submission ID."""
    return f"sub_{uuid.uuid4().hex[:12]}"

# =============================================================================
# AUTH
# =============================================================================

def require_admin(f):
    """Require admin authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if auth != f"Bearer {ADMIN_PASSWORD}":
            return jsonify({"success": False, "error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# =============================================================================
# HELPERS
# =============================================================================

def parse_task_amount(title):
    """Extract WATT amount from title like [AGENT TASK: 1,000 WATT]"""
    match = re.search(r'\[AGENT\s*TASK:\s*([\d,]+)\s*WATT\]', title, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(',', ''))
    return 0

def get_task_type(body):
    """Determine if task is recurring or one-time based on body content."""
    if not body:
        return "one-time"
    body_lower = body.lower()
    if any(word in body_lower for word in ['daily', 'weekly', 'monthly', 'recurring', 'every day', 'every week']):
        return "recurring"
    return "one-time"

def get_frequency(body):
    """Extract frequency from body for recurring tasks."""
    if not body:
        return None
    body_lower = body.lower()
    if 'daily' in body_lower or 'every day' in body_lower:
        return "daily"
    if 'weekly' in body_lower or 'every week' in body_lower:
        return "weekly"
    if 'monthly' in body_lower or 'every month' in body_lower:
        return "monthly"
    return None

def clean_title(title):
    """Remove [AGENT TASK: X WATT] prefix from title."""
    return re.sub(r'\[AGENT\s*TASK:\s*[\d,]+\s*WATT\]\s*', '', title, flags=re.IGNORECASE).strip()

def extract_section(body, header):
    """Extract content under a markdown header."""
    if not body:
        return None
    pattern = rf'#+\s*{header}\s*\n(.*?)(?=\n#+\s|\Z)'
    match = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

# =============================================================================
# FETCH TASKS
# =============================================================================

def fetch_tasks():
    """Fetch agent tasks from GitHub Issues."""
    # Check cache
    if _tasks_cache["data"] and time.time() < _tasks_cache["expires"]:
        return _tasks_cache["data"]
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    try:
        resp = requests.get(
            GITHUB_API,
            params={"labels": "agent-task", "state": "open", "per_page": 50},
            headers=headers,
            timeout=15
        )
        
        if resp.status_code != 200:
            return []
        
        issues = resp.json()
        tasks = []
        
        for issue in issues:
            amount = parse_task_amount(issue["title"])
            if amount == 0:
                continue
            
            body = issue.get("body", "") or ""
            task_type = get_task_type(body)
            
            task = {
                "id": issue["number"],
                "title": clean_title(issue["title"]),
                "amount": amount,
                "type": task_type,
                "frequency": get_frequency(body) if task_type == "recurring" else None,
                "description": extract_section(body, "Description") or body[:500] if body else None,
                "requirements": extract_section(body, "Requirements"),
                "submission_format": extract_section(body, "Submission") or extract_section(body, "How to Submit"),
                "url": issue["html_url"],
                "created_at": issue["created_at"],
                "labels": [l["name"] for l in issue.get("labels", []) if l["name"] != "agent-task"],
                "body": body  # Keep full body for verification
            }
            tasks.append(task)
        
        # Sort by amount descending
        tasks.sort(key=lambda x: x["amount"], reverse=True)
        
        # Update cache
        _tasks_cache["data"] = tasks
        _tasks_cache["expires"] = time.time() + CACHE_TTL
        
        return tasks
        
    except Exception as e:
        print(f"Error fetching tasks: {e}")
        return []

def get_task_by_id(task_id):
    """Get task by ID, bypassing cache if needed."""
    tasks = fetch_tasks()
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None

# =============================================================================
# GROK VERIFICATION
# =============================================================================

def verify_with_grok(task, submission_result):
    """
    Use Grok to verify if submission meets task requirements.
    Returns: {"pass": bool, "reason": str, "confidence": float}
    """
    if not GROK_API_KEY:
        return {"pass": False, "reason": "Grok API not configured", "confidence": 0}
    
    prompt = f"""You are verifying an AI agent's task submission.

TASK: {task['title']}

REQUIREMENTS:
{task.get('requirements') or task.get('description') or 'Complete the task as described.'}

SUBMISSION:
{json.dumps(submission_result, indent=2)}

Evaluate if this submission meets the task requirements.
Reply with ONLY valid JSON (no markdown):
{{"pass": true/false, "reason": "brief explanation", "confidence": 0.0-1.0}}

Be strict but fair. Confidence should reflect how certain you are about your evaluation."""

    try:
        resp = requests.post(
            GROK_API_URL,
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-3-fast",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1
            },
            timeout=30
        )
        
        if resp.status_code != 200:
            return {"pass": False, "reason": f"Grok API error: {resp.status_code}", "confidence": 0}
        
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Parse JSON response
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        result = json.loads(content)
        return {
            "pass": bool(result.get("pass", False)),
            "reason": str(result.get("reason", "No reason provided")),
            "confidence": float(result.get("confidence", 0))
        }
        
    except json.JSONDecodeError as e:
        return {"pass": False, "reason": f"Failed to parse Grok response: {e}", "confidence": 0}
    except Exception as e:
        return {"pass": False, "reason": f"Grok verification error: {e}", "confidence": 0}

# =============================================================================
# SOLANA PAYOUT
# =============================================================================

def send_watt_payout(to_wallet, amount):
    """
    Send WATT tokens from bounty wallet to recipient.
    Returns: (success, tx_signature or error_message)
    
    Currently queues for manual payout via dashboard.
    Auto-payout requires BOUNTY_WALLET_PRIVATE_KEY and additional testing.
    """
    if not BOUNTY_WALLET_PRIVATE_KEY:
        # Queue for manual payout - this is the expected flow for now
        return False, "Queued for manual payout via dashboard"
    
    try:
        from solders.keypair import Keypair
        from solders.pubkey import Pubkey
        from solders.instruction import Instruction, AccountMeta
        from solders.transaction import Transaction
        from solders.message import Message
        from solders.hash import Hash
        import struct
        
        # Token-2022 program ID (WATT uses Token-2022)
        TOKEN_2022_PROGRAM_ID = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
        ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
        
        # Load wallet from private key
        key_bytes = base58.b58decode(BOUNTY_WALLET_PRIVATE_KEY)
        wallet = Keypair.from_bytes(key_bytes)
        
        mint = Pubkey.from_string(WATT_MINT)
        from_pubkey = wallet.pubkey()
        to_pubkey = Pubkey.from_string(to_wallet)
        
        # Get ATAs via RPC (more reliable than calculating)
        def get_ata_for_owner(owner_str):
            resp = requests.post(SOLANA_RPC, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [owner_str, {"mint": WATT_MINT}, {"encoding": "jsonParsed"}]
            }, timeout=15)
            data = resp.json()
            accounts = data.get("result", {}).get("value", [])
            if accounts:
                return Pubkey.from_string(accounts[0]["pubkey"])
            return None
        
        from_ata = get_ata_for_owner(str(from_pubkey))
        to_ata = get_ata_for_owner(to_wallet)
        
        if not from_ata:
            return False, "Bounty wallet has no WATT token account"
        if not to_ata:
            return False, f"Recipient {to_wallet[:8]}... has no WATT token account. They need to receive WATT first."
        
        # Build transfer instruction (opcode 3 for SPL token transfer)
        amount_raw = amount * (10 ** 6)  # 6 decimals
        instruction_data = struct.pack('<BQ', 3, amount_raw)
        
        # Account metas for transfer: [source, dest, owner]
        accounts = [
            AccountMeta(from_ata, is_signer=False, is_writable=True),
            AccountMeta(to_ata, is_signer=False, is_writable=True),
            AccountMeta(from_pubkey, is_signer=True, is_writable=False),
        ]
        
        transfer_ix = Instruction(TOKEN_2022_PROGRAM_ID, instruction_data, accounts)
        
        # Get recent blockhash
        rpc_resp = requests.post(SOLANA_RPC, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getLatestBlockhash",
            "params": [{"commitment": "finalized"}]
        }, timeout=15)
        blockhash_data = rpc_resp.json()
        blockhash = Hash.from_string(blockhash_data["result"]["value"]["blockhash"])
        
        # Build and sign transaction
        msg = Message.new_with_blockhash([transfer_ix], from_pubkey, blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign([wallet], blockhash)
        
        # Serialize and send
        tx_bytes = bytes(tx)
        tx_base64 = base58.b58encode(tx_bytes).decode('utf-8')
        
        send_resp = requests.post(SOLANA_RPC, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [tx_base64, {"encoding": "base58", "skipPreflight": False}]
        }, timeout=30)
        
        send_result = send_resp.json()
        
        if "result" in send_result:
            return True, send_result["result"]
        elif "error" in send_result:
            return False, f"RPC error: {send_result['error'].get('message', str(send_result['error']))}"
        else:
            return False, "Unknown RPC response"
            
    except ImportError as e:
        return False, f"Solana libraries not installed: {e}"
    except Exception as e:
        return False, f"Payout error: {e}"

# =============================================================================
# GITHUB COMMENT
# =============================================================================

def post_github_comment(issue_number, comment):
    """Post a comment on a GitHub issue."""
    if not GITHUB_TOKEN:
        return False
    
    try:
        resp = requests.post(
            f"{GITHUB_API}/{issue_number}/comments",
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            },
            json={"body": comment},
            timeout=15
        )
        return resp.status_code == 201
    except:
        return False

def close_github_issue(issue_number):
    """Close a GitHub issue."""
    if not GITHUB_TOKEN:
        return False
    
    try:
        resp = requests.patch(
            f"{GITHUB_API}/{issue_number}",
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            },
            json={"state": "closed"},
            timeout=15
        )
        return resp.status_code == 200
    except:
        return False

# =============================================================================
# ENDPOINTS - PUBLIC
# =============================================================================

@tasks_bp.route('/api/v1/tasks', methods=['GET'])
def list_tasks():
    """List all agent tasks."""
    tasks = fetch_tasks()
    
    # Optional filters
    task_type = request.args.get('type')  # recurring, one-time
    min_amount = request.args.get('min_amount', type=int)
    
    if task_type:
        tasks = [t for t in tasks if t["type"] == task_type]
    
    if min_amount:
        tasks = [t for t in tasks if t["amount"] >= min_amount]
    
    # Remove body from public response
    tasks_public = [{k: v for k, v in t.items() if k != 'body'} for t in tasks]
    
    total_watt = sum(t["amount"] for t in tasks)
    
    return jsonify({
        "success": True,
        "count": len(tasks),
        "total_watt": total_watt,
        "tasks": tasks_public,
        "note": "Agent-only tasks. Not listed on website.",
        "submit_endpoint": "/api/v1/tasks/{id}/submit",
        "docs": f"https://github.com/{GITHUB_REPO}/blob/main/CONTRIBUTING.md"
    })

@tasks_bp.route('/api/v1/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get single task by ID."""
    task = get_task_by_id(task_id)
    
    if not task:
        return jsonify({
            "success": False,
            "error": "task_not_found",
            "message": f"Task #{task_id} not found or not open"
        }), 404
    
    # Remove body from public response
    task_public = {k: v for k, v in task.items() if k != 'body'}
    
    return jsonify({
        "success": True,
        "task": task_public
    })

@tasks_bp.route('/api/v1/tasks/<int:task_id>/submit', methods=['POST'])
def submit_task(task_id):
    """
    Submit task result for verification and payout.
    
    Request:
        {"result": {...}, "wallet": "AgentWalletAddress"}
    
    Response:
        {"success": true, "submission_id": "sub_xxx", "status": "pending_review|approved|paid"}
    """
    # Validate request
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "invalid_json"}), 400
    
    result = data.get("result")
    wallet = data.get("wallet")
    
    if not result:
        return jsonify({"success": False, "error": "missing_result", "message": "result field is required"}), 400
    if not wallet:
        return jsonify({"success": False, "error": "missing_wallet", "message": "wallet field is required"}), 400
    
    # Validate wallet format (basic check)
    if len(wallet) < 32 or len(wallet) > 50:
        return jsonify({"success": False, "error": "invalid_wallet", "message": "Invalid Solana wallet address"}), 400
    
    # Get task
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({"success": False, "error": "task_not_found", "message": f"Task #{task_id} not found or not open"}), 404
    
    # Create submission
    submission_id = generate_submission_id()
    submission = {
        "id": submission_id,
        "task_id": task_id,
        "task_title": task["title"],
        "amount": task["amount"],
        "wallet": wallet,
        "result": result,
        "submitted_at": datetime.utcnow().isoformat() + "Z",
        "status": "pending_review",
        "grok_review": None,
        "tx_signature": None,
        "paid_at": None,
        "reviewed_at": None
    }
    
    # Verify with Grok
    grok_review = verify_with_grok(task, result)
    submission["grok_review"] = grok_review
    submission["reviewed_at"] = datetime.utcnow().isoformat() + "Z"
    
    # Determine status based on Grok review
    if grok_review["pass"] and grok_review["confidence"] >= AUTO_APPROVE_CONFIDENCE:
        submission["status"] = "approved"
        
        # Auto-payout
        success, tx_or_error = send_watt_payout(wallet, task["amount"])
        
        if success:
            submission["status"] = "paid"
            submission["tx_signature"] = tx_or_error
            submission["paid_at"] = datetime.utcnow().isoformat() + "Z"
            
            # Post GitHub comment
            comment = f"""## ✅ Task Completed - Auto-Verified

**Submission ID:** `{submission_id}`
**Agent Wallet:** `{wallet}`
**Payout:** {task["amount"]:,} WATT
**TX:** [{tx_or_error[:16]}...](https://solscan.io/tx/{tx_or_error})

---
*Verified by Grok AI (confidence: {grok_review["confidence"]:.0%})*
"""
            post_github_comment(task_id, comment)
            
            # Close issue if one-time task
            if task["type"] == "one-time":
                close_github_issue(task_id)
        else:
            # Check if it's queued for manual payout (expected) vs actual failure
            if "manual payout" in tx_or_error.lower():
                submission["status"] = "approved"  # Verified, awaiting manual payout
                submission["payout_note"] = "Awaiting manual payout via dashboard"
            else:
                submission["status"] = "payout_failed"
                submission["payout_error"] = tx_or_error
    
    elif grok_review["pass"]:
        # Pass but low confidence - queue for manual review
        submission["status"] = "pending_review"
    
    else:
        # Failed verification
        submission["status"] = "rejected"
    
    # Save submission
    submissions_data = load_submissions()
    submissions_data["submissions"].append(submission)
    save_submissions(submissions_data)
    
    # Clear task cache so updated info is fetched
    _tasks_cache["data"] = None
    
    return jsonify({
        "success": True,
        "submission_id": submission_id,
        "task_id": task_id,
        "status": submission["status"],
        "grok_review": grok_review,
        "tx_signature": submission.get("tx_signature"),
        "message": {
            "paid": f"Task completed! {task['amount']:,} WATT sent to {wallet[:8]}...",
            "approved": f"Task verified by Grok! {task['amount']:,} WATT payout pending admin approval.",
            "pending_review": "Submitted for manual review (Grok confidence below threshold).",
            "rejected": f"Submission rejected: {grok_review['reason']}",
            "payout_failed": f"Verified but payout failed: {submission.get('payout_error', 'Unknown error')}"
        }.get(submission["status"], "Submitted.")
    })

# =============================================================================
# ENDPOINTS - ADMIN
# =============================================================================

@tasks_bp.route('/api/v1/tasks/<int:task_id>/submissions', methods=['GET'])
@require_admin
def list_submissions(task_id):
    """List all submissions for a task (admin only)."""
    submissions_data = load_submissions()
    task_submissions = [s for s in submissions_data["submissions"] if s["task_id"] == task_id]
    
    return jsonify({
        "success": True,
        "task_id": task_id,
        "count": len(task_submissions),
        "submissions": task_submissions
    })

@tasks_bp.route('/api/v1/tasks/submissions', methods=['GET'])
@require_admin
def list_all_submissions():
    """List all submissions (admin only)."""
    submissions_data = load_submissions()
    
    # Optional status filter
    status = request.args.get('status')
    submissions = submissions_data["submissions"]
    
    if status:
        submissions = [s for s in submissions if s["status"] == status]
    
    return jsonify({
        "success": True,
        "count": len(submissions),
        "submissions": submissions
    })

@tasks_bp.route('/api/v1/tasks/<int:task_id>/approve/<submission_id>', methods=['POST'])
@require_admin
def approve_submission(task_id, submission_id):
    """Manually approve a submission and trigger payout (admin only)."""
    submissions_data = load_submissions()
    
    for sub in submissions_data["submissions"]:
        if sub["id"] == submission_id and sub["task_id"] == task_id:
            if sub["status"] == "paid":
                return jsonify({"success": False, "error": "already_paid"}), 400
            
            # Get task for amount
            task = get_task_by_id(task_id)
            amount = task["amount"] if task else sub.get("amount", 0)
            
            # Send payout
            success, tx_or_error = send_watt_payout(sub["wallet"], amount)
            
            if success:
                sub["status"] = "paid"
                sub["tx_signature"] = tx_or_error
                sub["paid_at"] = datetime.utcnow().isoformat() + "Z"
                sub["approved_by"] = "admin"
                save_submissions(submissions_data)
                
                # Post GitHub comment
                comment = f"""## ✅ Task Completed - Admin Approved

**Submission ID:** `{submission_id}`
**Agent Wallet:** `{sub['wallet']}`
**Payout:** {amount:,} WATT
**TX:** [{tx_or_error[:16]}...](https://solscan.io/tx/{tx_or_error})

---
*Manually approved by admin*
"""
                post_github_comment(task_id, comment)
                
                return jsonify({
                    "success": True,
                    "status": "paid",
                    "tx_signature": tx_or_error
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "payout_failed",
                    "message": tx_or_error
                }), 500
    
    return jsonify({"success": False, "error": "submission_not_found"}), 404

@tasks_bp.route('/api/v1/tasks/<int:task_id>/reject/<submission_id>', methods=['POST'])
@require_admin
def reject_submission(task_id, submission_id):
    """Manually reject a submission (admin only)."""
    data = request.get_json() or {}
    reason = data.get("reason", "Rejected by admin")
    
    submissions_data = load_submissions()
    
    for sub in submissions_data["submissions"]:
        if sub["id"] == submission_id and sub["task_id"] == task_id:
            if sub["status"] == "paid":
                return jsonify({"success": False, "error": "already_paid"}), 400
            
            sub["status"] = "rejected"
            sub["reject_reason"] = reason
            sub["rejected_at"] = datetime.utcnow().isoformat() + "Z"
            save_submissions(submissions_data)
            
            return jsonify({
                "success": True,
                "status": "rejected",
                "reason": reason
            })
    
    return jsonify({"success": False, "error": "submission_not_found"}), 404
