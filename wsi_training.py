"""
WSI Training Data Storage Module
Saves AI evaluation outputs for future WSI model fine-tuning
"""

import os
import json
from datetime import datetime

# Base directory for all WSI training data
WSI_TRAINING_DIR = "data/wsi_training"

# Category subdirectories
CATEGORIES = {
    "pr_reviews_public": "pr_reviews_public",
    "pr_reviews_internal": "pr_reviews_internal",
    "bounty_evaluations": "bounty_evaluations",
    "security_audits": "security_audits",
    "swarmsolve_audits": "swarmsolve_audits",
    "task_verifications": "task_verifications"
}


def save_training_data(category, identifier, metadata, ai_output):
    """
    Save AI evaluation output as WSI training data.
    
    Args:
        category: One of the CATEGORIES keys (e.g., "pr_reviews_public")
        identifier: Unique identifier for this evaluation (e.g., "PR_123", "issue_fix_bug")
        metadata: Dict with evaluation context (pr_number, decision, score, etc.)
        ai_output: Raw AI response text (string)
    
    Returns:
        filepath: Path where data was saved, or None if failed
    """
    try:
        # Validate category
        if category not in CATEGORIES:
            print(f"[WSI-TRAINING] Invalid category '{category}' — skipping save", flush=True)
            return None
        
        # Create category directory
        category_dir = os.path.join(WSI_TRAINING_DIR, CATEGORIES[category])
        os.makedirs(category_dir, exist_ok=True)
        
        # Generate timestamped filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        # Sanitize identifier (remove special chars)
        safe_identifier = "".join(c for c in identifier if c.isalnum() or c in "_-")[:50]
        filename = f"{timestamp}_{safe_identifier}.json"
        filepath = os.path.join(category_dir, filename)
        
        # Combine metadata + AI output
        training_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "category": category,
            "identifier": identifier,
            "metadata": metadata,
            "ai_output": ai_output
        }
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(training_record, f, indent=2)
        
        print(f"[WSI-TRAINING] Saved: {category}/{filename}", flush=True)
        return filepath
        
    except Exception as e:
        print(f"[WSI-TRAINING] Failed to save {category}/{identifier}: {e}", flush=True)
        return None


def load_training_data(category=None, limit=None):
    """
    Load training data for analysis or model training.
    
    Args:
        category: Optional category to filter (None = all categories)
        limit: Optional max number of files to load (None = all)
    
    Returns:
        list of training records
    """
    records = []
    
    try:
        if category:
            if category not in CATEGORIES:
                print(f"[WSI-TRAINING] Invalid category '{category}'", flush=True)
                return []
            categories = [category]
        else:
            categories = CATEGORIES.keys()
        
        for cat in categories:
            category_dir = os.path.join(WSI_TRAINING_DIR, CATEGORIES[cat])
            if not os.path.exists(category_dir):
                continue
            
            files = sorted(os.listdir(category_dir), reverse=True)  # Newest first
            if limit:
                files = files[:limit]
            
            for filename in files:
                if not filename.endswith('.json'):
                    continue
                
                filepath = os.path.join(category_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        record = json.load(f)
                        records.append(record)
                except Exception as e:
                    print(f"[WSI-TRAINING] Failed to load {filepath}: {e}", flush=True)
        
        return records
        
    except Exception as e:
        print(f"[WSI-TRAINING] Load error: {e}", flush=True)
        return []


def get_training_stats():
    """
    Get statistics about accumulated training data.
    
    Returns:
        dict with counts per category and total
    """
    stats = {"total": 0}
    
    try:
        for category, subdir in CATEGORIES.items():
            category_dir = os.path.join(WSI_TRAINING_DIR, subdir)
            if not os.path.exists(category_dir):
                stats[category] = 0
                continue
            
            count = len([f for f in os.listdir(category_dir) if f.endswith('.json')])
            stats[category] = count
            stats["total"] += count
        
        return stats
        
    except Exception as e:
        print(f"[WSI-TRAINING] Stats error: {e}", flush=True)
        return {"total": 0, "error": str(e)}
