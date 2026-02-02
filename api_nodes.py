"""
WattNode API - Node registration, job routing, payouts
v2.1.0
"""

from flask import Blueprint, request, jsonify
import os
import json
import time
import uuid
import requests
from datetime import datetime, timezone

nodes_bp = Blueprint('nodes', __name__)

# === Config ===
NODES_FILE = os.environ.get('NODES_FILE', '/app/data/nodes.json')
JOBS_FILE = os.environ.get('JOBS_FILE', '/app/data/node_jobs.json')
WATT_MINT = "Gpmbh4PoQnL1kNgpMYDED3iv4fczcr7d3qNBLf8rpump"
BOUNTY_WALLET = "7vvNkG3JF3JpxLEavqZSkc5T3n9hHR98Uw23fbWdXVSF"
TREASURY_WALLET = os.environ.get('TREASURY_WALLET', 'Atu5phbGGGFogbKhi259czz887dSdTfXwJxwbuE5aF5q')
SOLANA_RPC = "https://solana.publicnode.com"

STAKE_AMOUNT = 10000  # 10,000 WATT required
HEARTBEAT_TIMEOUT = 120  # seconds - node inactive if no heartbeat
JOB_TIMEOUT = 30  # seconds - job expires if not completed

# Payment split (out of 100)
NODE_SHARE = 70
TREASURY_SHARE = 20
BURN_SHARE = 10

# === Storage Helpers ===
def load_nodes():
    if os.path.exists(NODES_FILE):
        with open(NODES_FILE, 'r') as f:
            return json.load(f)
    return {"nodes": {}}

def save_nodes(data):
    os.makedirs(os.path.dirname(NODES_FILE), exist_ok=True)
    with open(NODES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_jobs():
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, 'r') as f:
            return json.load(f)
    return {"jobs": {}, "pending": [], "completed": []}

def save_jobs(data):
    os.makedirs(os.path.dirname(JOBS_FILE), exist_ok=True)
    with open(JOBS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# === Stake Verification ===
def verify_stake(wallet: str, tx_signature: str) -> dict:
    """Verify WATT stake transaction to treasury wallet"""
    try:
        # Get transaction details
        resp = requests.post(SOLANA_RPC, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [tx_signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
        }, timeout=15)
        
        data = resp.json()
        if "error" in data or not data.get("result"):
            return {"valid": False, "error": "Transaction not found"}
        
        tx = data["result"]
        
        # Check age (must be within last 24 hours for registration)
        block_time = tx.get("blockTime", 0)
        if time.time() - block_time > 86400:
            return {"valid": False, "error": "Transaction too old (>24h)"}
        
        # Check pre/post token balances for WATT transfer
        meta = tx.get("meta", {})
        pre_balances = meta.get("preTokenBalances", [])
        post_balances = meta.get("postTokenBalances", [])
        
        # Find treasury wallet balance change
        treasury_pre = 0
        treasury_post = 0
        sender_wallet = None
        
        for bal in pre_balances:
            if bal.get("mint") == WATT_MINT:
                owner = bal.get("owner", "")
                if owner == TREASURY_WALLET:
                    treasury_pre = int(bal.get("uiTokenAmount", {}).get("amount", 0))
                elif owner == wallet:
                    sender_wallet = owner
        
        for bal in post_balances:
            if bal.get("mint") == WATT_MINT:
                owner = bal.get("owner", "")
                if owner == TREASURY_WALLET:
                    treasury_post = int(bal.get("uiTokenAmount", {}).get("amount", 0))
        
        amount_received = (treasury_post - treasury_pre) / 1_000_000  # 6 decimals
        
        if amount_received < STAKE_AMOUNT:
            return {"valid": False, "error": f"Insufficient stake: {amount_received} < {STAKE_AMOUNT}"}
        
        return {"valid": True, "amount": amount_received}
        
    except Exception as e:
        return {"valid": False, "error": str(e)}

# === Node Helpers ===
def generate_node_id():
    return f"node_{uuid.uuid4().hex[:12]}"

def is_node_active(node: dict) -> bool:
    """Check if node has recent heartbeat"""
    last_hb = node.get("last_heartbeat")
    if not last_hb:
        return False
    try:
        hb_time = datetime.fromisoformat(last_hb.replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - hb_time).total_seconds()
        return age < HEARTBEAT_TIMEOUT
    except:
        return False

def get_active_nodes(capability: str = None) -> list:
    """Get list of active nodes, optionally filtered by capability"""
    data = load_nodes()
    active = []
    for node_id, node in data.get("nodes", {}).items():
        if node.get("status") != "active":
            continue
        if not is_node_active(node):
            continue
        if capability and capability not in node.get("capabilities", []):
            continue
        active.append({"node_id": node_id, **node})
    return active

# === API Endpoints ===

@nodes_bp.route('/api/v1/nodes/register', methods=['POST'])
def register_node():
    """Register a new WattNode"""
    body = request.get_json() or {}
    
    wallet = body.get('wallet')
    capabilities = body.get('capabilities', [])
    stake_tx = body.get('stake_tx')
    endpoint = body.get('endpoint')  # null for polling mode
    name = body.get('name', 'unnamed-node')
    
    # Validation
    if not wallet:
        return jsonify({"success": False, "error": "wallet required"}), 400
    if not stake_tx:
        return jsonify({"success": False, "error": "stake_tx required"}), 400
    if not capabilities:
        return jsonify({"success": False, "error": "capabilities required (scrape, inference)"}), 400
    
    valid_caps = ['scrape', 'inference']
    for cap in capabilities:
        if cap not in valid_caps:
            return jsonify({"success": False, "error": f"invalid capability: {cap}"}), 400
    
    # Check if already registered
    data = load_nodes()
    for node_id, node in data.get("nodes", {}).items():
        if node.get("wallet") == wallet:
            return jsonify({
                "success": False, 
                "error": "wallet already registered",
                "node_id": node_id
            }), 409
        if node.get("stake_tx") == stake_tx:
            return jsonify({"success": False, "error": "stake_tx already used"}), 409
    
    # Verify stake
    stake_result = verify_stake(wallet, stake_tx)
    if not stake_result.get("valid"):
        return jsonify({
            "success": False, 
            "error": f"stake verification failed: {stake_result.get('error')}"
        }), 400
    
    # Register node
    node_id = generate_node_id()
    now = datetime.now(timezone.utc).isoformat()
    
    data["nodes"][node_id] = {
        "wallet": wallet,
        "name": name,
        "capabilities": capabilities,
        "endpoint": endpoint,
        "stake_amount": stake_result.get("amount", STAKE_AMOUNT),
        "stake_tx": stake_tx,
        "registered_at": now,
        "last_heartbeat": now,
        "jobs_completed": 0,
        "jobs_failed": 0,
        "total_earned": 0,
        "status": "active"
    }
    
    save_nodes(data)
    
    return jsonify({
        "success": True,
        "node_id": node_id,
        "status": "active",
        "stake_verified": True,
        "stake_amount": stake_result.get("amount"),
        "message": f"Node registered! You will receive {NODE_SHARE}% of job payments."
    })

@nodes_bp.route('/api/v1/nodes/heartbeat', methods=['POST'])
def node_heartbeat():
    """Keep node alive"""
    body = request.get_json() or {}
    node_id = body.get('node_id')
    
    if not node_id:
        return jsonify({"success": False, "error": "node_id required"}), 400
    
    data = load_nodes()
    if node_id not in data.get("nodes", {}):
        return jsonify({"success": False, "error": "node not found"}), 404
    
    data["nodes"][node_id]["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
    save_nodes(data)
    
    return jsonify({
        "success": True,
        "node_id": node_id,
        "status": data["nodes"][node_id]["status"]
    })

@nodes_bp.route('/api/v1/nodes/jobs', methods=['GET'])
def get_node_jobs():
    """Poll for available jobs (for polling mode nodes)"""
    node_id = request.args.get('node_id')
    
    if not node_id:
        return jsonify({"success": False, "error": "node_id required"}), 400
    
    # Verify node exists and is active
    nodes_data = load_nodes()
    node = nodes_data.get("nodes", {}).get(node_id)
    if not node:
        return jsonify({"success": False, "error": "node not found"}), 404
    if node.get("status") != "active":
        return jsonify({"success": False, "error": "node not active"}), 403
    
    # Get pending jobs for this node's capabilities
    jobs_data = load_jobs()
    available = []
    now = datetime.now(timezone.utc)
    
    for job_id in list(jobs_data.get("pending", [])):
        job = jobs_data.get("jobs", {}).get(job_id)
        if not job:
            continue
        
        # Check if job type matches node capability
        if job.get("type") not in node.get("capabilities", []):
            continue
        
        # Check if job expired
        expires = datetime.fromisoformat(job.get("expires_at", "").replace('Z', '+00:00'))
        if now > expires:
            # Move to failed
            jobs_data["pending"].remove(job_id)
            job["status"] = "expired"
            continue
        
        # Check if already assigned to another node
        if job.get("assigned_to") and job.get("assigned_to") != node_id:
            continue
        
        available.append({
            "job_id": job_id,
            "type": job.get("type"),
            "payload": job.get("payload"),
            "reward": job.get("node_reward"),
            "expires_at": job.get("expires_at")
        })
    
    save_jobs(jobs_data)
    
    # Update heartbeat
    nodes_data["nodes"][node_id]["last_heartbeat"] = now.isoformat()
    save_nodes(nodes_data)
    
    return jsonify({
        "success": True,
        "jobs": available[:5]  # Max 5 jobs at a time
    })

@nodes_bp.route('/api/v1/nodes/jobs/<job_id>/claim', methods=['POST'])
def claim_job(job_id):
    """Node claims a job to work on"""
    body = request.get_json() or {}
    node_id = body.get('node_id')
    
    if not node_id:
        return jsonify({"success": False, "error": "node_id required"}), 400
    
    jobs_data = load_jobs()
    job = jobs_data.get("jobs", {}).get(job_id)
    
    if not job:
        return jsonify({"success": False, "error": "job not found"}), 404
    if job.get("status") != "pending":
        return jsonify({"success": False, "error": f"job status: {job.get('status')}"}), 409
    if job.get("assigned_to") and job.get("assigned_to") != node_id:
        return jsonify({"success": False, "error": "job assigned to another node"}), 409
    
    # Assign job
    job["assigned_to"] = node_id
    job["claimed_at"] = datetime.now(timezone.utc).isoformat()
    jobs_data["jobs"][job_id] = job
    save_jobs(jobs_data)
    
    return jsonify({
        "success": True,
        "job_id": job_id,
        "payload": job.get("payload"),
        "reward": job.get("node_reward")
    })

@nodes_bp.route('/api/v1/nodes/jobs/<job_id>/complete', methods=['POST'])
def complete_job(job_id):
    """Node submits completed job result"""
    body = request.get_json() or {}
    node_id = body.get('node_id')
    result = body.get('result')
    
    if not node_id:
        return jsonify({"success": False, "error": "node_id required"}), 400
    if result is None:
        return jsonify({"success": False, "error": "result required"}), 400
    
    jobs_data = load_jobs()
    job = jobs_data.get("jobs", {}).get(job_id)
    
    if not job:
        return jsonify({"success": False, "error": "job not found"}), 404
    if job.get("assigned_to") != node_id:
        return jsonify({"success": False, "error": "job not assigned to this node"}), 403
    if job.get("status") == "completed":
        return jsonify({"success": False, "error": "job already completed"}), 409
    
    # Update job
    now = datetime.now(timezone.utc).isoformat()
    job["status"] = "completed"
    job["completed_at"] = now
    job["result"] = result
    
    # Move from pending to completed
    if job_id in jobs_data.get("pending", []):
        jobs_data["pending"].remove(job_id)
    jobs_data["completed"].append(job_id)
    jobs_data["jobs"][job_id] = job
    save_jobs(jobs_data)
    
    # Update node stats
    nodes_data = load_nodes()
    node = nodes_data.get("nodes", {}).get(node_id)
    if node:
        node["jobs_completed"] = node.get("jobs_completed", 0) + 1
        node["total_earned"] = node.get("total_earned", 0) + job.get("node_reward", 0)
        node["last_heartbeat"] = now
        save_nodes(nodes_data)
    
    # TODO: Auto-payout to node wallet (same as task payout)
    # For now, mark as pending_payout
    
    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": "completed",
        "reward": job.get("node_reward"),
        "payout_status": "pending"  # Will be "paid" after payout implemented
    })

@nodes_bp.route('/api/v1/nodes', methods=['GET'])
def list_nodes():
    """Public: List active nodes"""
    data = load_nodes()
    nodes_list = []
    
    for node_id, node in data.get("nodes", {}).items():
        active = is_node_active(node)
        nodes_list.append({
            "node_id": node_id,
            "name": node.get("name"),
            "capabilities": node.get("capabilities"),
            "status": "active" if active else "inactive",
            "jobs_completed": node.get("jobs_completed", 0),
            "total_earned": node.get("total_earned", 0),
            "registered_at": node.get("registered_at")
        })
    
    # Sort by jobs completed
    nodes_list.sort(key=lambda x: x.get("jobs_completed", 0), reverse=True)
    
    return jsonify({
        "success": True,
        "count": len(nodes_list),
        "active": len([n for n in nodes_list if n["status"] == "active"]),
        "nodes": nodes_list
    })

@nodes_bp.route('/api/v1/nodes/<node_id>', methods=['GET'])
def get_node(node_id):
    """Public: Get node details"""
    data = load_nodes()
    node = data.get("nodes", {}).get(node_id)
    
    if not node:
        return jsonify({"success": False, "error": "node not found"}), 404
    
    return jsonify({
        "success": True,
        "node_id": node_id,
        "name": node.get("name"),
        "capabilities": node.get("capabilities"),
        "status": "active" if is_node_active(node) else "inactive",
        "jobs_completed": node.get("jobs_completed", 0),
        "jobs_failed": node.get("jobs_failed", 0),
        "total_earned": node.get("total_earned", 0),
        "registered_at": node.get("registered_at"),
        "stake_amount": node.get("stake_amount")
    })

# === Job Creation Helper (called by scraper/inference endpoints) ===
def create_job(job_type: str, payload: dict, total_payment: int, requester_wallet: str) -> dict:
    """
    Create a job for node routing.
    Returns job_id if nodes available, None if should fallback to centralized.
    """
    # Check for active nodes with this capability
    active = get_active_nodes(capability=job_type)
    if not active:
        return {"routed": False, "reason": "no_active_nodes"}
    
    # Calculate splits
    node_reward = int(total_payment * NODE_SHARE / 100)
    treasury_amount = int(total_payment * TREASURY_SHARE / 100)
    burn_amount = int(total_payment * BURN_SHARE / 100)
    
    # Create job
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    expires = now.replace(second=now.second + JOB_TIMEOUT)
    
    job = {
        "job_id": job_id,
        "type": job_type,
        "payload": payload,
        "total_payment": total_payment,
        "node_reward": node_reward,
        "treasury_amount": treasury_amount,
        "burn_amount": burn_amount,
        "requester_wallet": requester_wallet,
        "status": "pending",
        "assigned_to": None,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "result": None
    }
    
    jobs_data = load_jobs()
    jobs_data["jobs"][job_id] = job
    jobs_data["pending"].append(job_id)
    save_jobs(jobs_data)
    
    return {
        "routed": True,
        "job_id": job_id,
        "node_reward": node_reward,
        "active_nodes": len(active)
    }

def wait_for_job_result(job_id: str, timeout: int = 30) -> dict:
    """Wait for job to be completed by a node"""
    start = time.time()
    while time.time() - start < timeout:
        jobs_data = load_jobs()
        job = jobs_data.get("jobs", {}).get(job_id)
        if job and job.get("status") == "completed":
            return {
                "success": True,
                "result": job.get("result"),
                "node_id": job.get("assigned_to")
            }
        time.sleep(0.5)
    
    # Timeout - job not completed
    return {"success": False, "error": "timeout"}

def cancel_job(job_id: str):
    """Cancel a pending job (used when falling back to centralized)"""
    jobs_data = load_jobs()
    if job_id in jobs_data.get("pending", []):
        jobs_data["pending"].remove(job_id)
    if job_id in jobs_data.get("jobs", {}):
        jobs_data["jobs"][job_id]["status"] = "cancelled"
    save_jobs(jobs_data)


# === TEST ENDPOINT (Admin only) ===
@nodes_bp.route('/api/v1/nodes/test/create-job', methods=['POST'])
def test_create_job():
    """
    Admin endpoint to create a test job for debugging.
    Requires ADMIN_PASSWORD header.
    """
    admin_pass = os.environ.get('ADMIN_PASSWORD', '')
    auth_header = request.headers.get('Authorization', '')
    
    if not admin_pass or auth_header != f'Bearer {admin_pass}':
        return jsonify({"success": False, "error": "unauthorized"}), 401
    
    body = request.get_json() or {}
    job_type = body.get('type', 'scrape')
    url = body.get('url', 'https://example.com')
    payment = body.get('payment', 100)
    
    result = create_job(
        job_type=job_type,
        payload={'url': url, 'format': 'text'},
        total_payment=payment,
        requester_wallet='test_admin'
    )
    
    return jsonify({
        "success": True,
        "job": result
    })
