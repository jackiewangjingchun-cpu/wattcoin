"""
WSI Training Data Storage — Phase B
Saves AI evaluation outputs as labeled training data for future WSI fine-tuning.

Signal types:
  - pr_reviews_public     (from call_ai_review on public repo)
  - pr_reviews_internal   (from call_ai_review on internal repo)
  - bounty_evaluations    (from evaluate_bounty_request)
  - security_audits       (from ai_security_scan_pr)
  - swarmsolve_audits     (from safety_scan_pr)
  - task_verifications    (from ai_verify_submission)

Storage: data/wsi_training/{signal_type}/{timestamp}_{identifier}.json

Version: 1.0.0
"""

import os
import json
import re
from datetime import datetime, timezone


DATA_DIR = os.getenv("DATA_DIR", "/app/data")
WSI_TRAINING_DIR = os.path.join(DATA_DIR, "wsi_training")

VALID_SIGNAL_TYPES = [
    "pr_reviews_public",
    "pr_reviews_internal",
    "bounty_evaluations",
    "security_audits",
    "swarmsolve_audits",
    "task_verifications",
]


def save_training_data(signal_type, identifier, metadata, ai_response):
    """
    Save an AI evaluation as WSI training data. Fire-and-forget — never raises.

    Args:
        signal_type: One of VALID_SIGNAL_TYPES
        identifier:  Short ID string (e.g., "PR_42", "issue_15", "task_abc")
        metadata:    Dict with context (contributor, repo, outcome, etc.)
        ai_response: Raw AI output string OR parsed dict
    """
    try:
        if signal_type not in VALID_SIGNAL_TYPES:
            print(f"[WSI-TRAIN] Invalid signal_type: {signal_type}", flush=True)
            return

        # Ensure directory exists
        signal_dir = os.path.join(WSI_TRAINING_DIR, signal_type)
        os.makedirs(signal_dir, exist_ok=True)

        # Build filename: 20260209T031500Z_PR_42.json
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(identifier))[:50]
        filename = f"{ts}_{safe_id}.json"
        filepath = os.path.join(signal_dir, filename)

        # Parse ai_response if it's a string (try JSON extraction)
        parsed_response = None
        raw_response = ai_response if isinstance(ai_response, str) else None

        if isinstance(ai_response, dict):
            parsed_response = ai_response
            raw_response = json.dumps(ai_response)
        elif isinstance(ai_response, str):
            try:
                json_text = ai_response.strip()
                if json_text.startswith("```"):
                    json_text = json_text.split("\n", 1)[1] if "\n" in json_text else json_text[3:]
                    if json_text.endswith("```"):
                        json_text = json_text[:-3]
                    json_text = json_text.strip()
                parsed_response = json.loads(json_text)
            except (json.JSONDecodeError, ValueError):
                pass  # Keep raw only

        # Build training record
        record = {
            "version": "1.0",
            "signal_type": signal_type,
            "identifier": str(identifier),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "raw_response": raw_response,
            "parsed_response": parsed_response,
        }

        # Write atomically (write to tmp, rename)
        tmp_path = filepath + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(record, f, indent=2, default=str)
        os.replace(tmp_path, filepath)

        print(f"[WSI-TRAIN] Saved {signal_type}/{filename} ({len(raw_response or '')} chars)", flush=True)

    except Exception as e:
        # Never break the calling flow
        print(f"[WSI-TRAIN] Error saving {signal_type}/{identifier}: {e}", flush=True)
