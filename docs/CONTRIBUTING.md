# Contributing to WattCoin

Welcome! WattCoin uses an AI-powered automated bounty system where contributors earn WATT tokens for merged PRs. This guide explains how to submit PRs that pass review and get paid.

## Quick Start: Your First Bounty

### 1. Find a Bounty

Browse [open issues labeled `bounty`](https://github.com/WattCoin-Org/wattcoin/labels/bounty). The issue title shows the reward amount:

```
[BOUNTY: 5000 WATT] Fix: API endpoint error handling
```

**Bounty Tiers:**
- Simple (500-2,000 WATT): Bug fixes, small helpers, docs examples
- Medium (2,000-10,000 WATT): New endpoints, refactors, skill enhancements
- Complex (10,000-50,000 WATT): Architecture, new core features, security improvements

### 2. Fork and Branch

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/YOUR_USERNAME/wattcoin.git
cd wattcoin
git checkout -b fix/issue-123
```

### 3. Make Your Changes

- Read the issue description carefully
- Implement ONLY what the bounty requests
- Follow existing code patterns
- Test your changes locally

### 4. Submit Your PR

**Required: Include your payout wallet in the PR description.**

```markdown
## Changes
Brief description of what you changed and why.

## Testing
How you verified the changes work.

**Payout Wallet**: YourSolanaWalletAddressHere
```

The wallet line must use this exact format: `**Payout Wallet**: <address>`

Alternative formats also accepted:
- `Wallet: <address>`
- `` `<address>` ``

### 5. AI Review

Within minutes, an AI reviewer scores your PR on 7 dimensions. Score ≥9/10 triggers auto-merge and queued payment.

### 6. Get Paid

After your PR merges and the deployment confirms stability, you receive WATT tokens on-chain with a transaction memo linking to your PR.

---

## Understanding AI Review

Every PR is scored by an AI reviewer on these dimensions:

### 1. Breaking Change Detection (CRITICAL — 2x weight)

**What it checks:** Does your PR remove or downgrade existing functionality?

**Pass:**
- Adding new features without touching existing code
- Fixing bugs while preserving all existing behavior
- Extending functionality (old code still works)

**Fail:**
- Removing environment variable support
- Changing function signatures that other code depends on
- Deleting configuration options without replacement
- Silently changing default behavior

**Example failure:**
```python
# Before
def process_payment(amount, wallet, memo=None):
    ...

# Your PR (BREAKS EXISTING CODE)
def process_payment(amount, wallet):  # Removed memo parameter
    ...
```

Score if ANY breaking change: **≤5/10** (auto-reject)

### 2. Value Change Audit (CRITICAL — 2x weight)

**What it checks:** Did you change any hardcoded values (timeouts, limits, thresholds, versions)?

**Pass:**
- No value changes
- Value changes explicitly justified in PR description

**Fail:**
- Changing rate limits without explanation
- Adjusting timeouts arbitrarily
- Modifying version numbers
- Tweaking thresholds "because it felt better"

**Example failure:**
```python
# Before
RETRY_DELAY = 30

# Your PR (UNJUSTIFIED)
RETRY_DELAY = 60  # No explanation in PR description
```

Score if unjustified value change: **≤6/10**

### 3. Scope & Bounty Integrity (HIGH)

**What it checks:** Do your changes match the bounty description? Are you staying in scope?

**Pass:**
- Changes directly address the bounty task
- Only touched files necessary for the fix
- No unrelated modifications

**Fail:**
- Touching payment system files when fixing a docs typo
- Refactoring unrelated code "while you're at it"
- Fixing multiple unrelated issues in one PR
- Identical code across multiple PRs from same author

**Example failure:**
```
Bounty: "Fix typo in README.md"

Files changed:
  README.md          ✅ In scope
  api_webhooks.py    ❌ Unrelated
  payment_queue.py   ❌ Scope creep
```

Score if scope creep: **≤6/10**

### 4. Security (HIGH)

**What it checks:** Basic security hygiene (detailed security audit runs separately)

**Pass:**
- No obvious vulnerabilities
- No hardcoded secrets or API keys
- No suspicious patterns

**Fail:**
- Exposing sensitive information
- Adding external dependencies without review
- Removing existing security measures
- Suspicious code patterns

### 5. Code Quality (MEDIUM)

**What it checks:** Readability, maintainability, follows existing patterns

**Pass:**
- Clean, readable code
- Follows project conventions
- Proper error handling
- Consistent with existing codebase

**Fail:**
- Dead code or commented-out blocks
- Duplicate logic
- No error handling
- Inconsistent style

### 6. Test Validity (MEDIUM)

**What it checks:** If you included tests, do they actually work?

**Pass:**
- Tests use real methods and would execute
- Tests actually verify the fix
- No tests included (acceptable for simple changes)

**Fail:**
- Tests call nonexistent functions
- Tests that can't possibly run
- Fake tests that don't verify anything

### 7. Functionality (MEDIUM)

**What it checks:** Does your code solve the stated problem completely?

**Pass:**
- Solves the full problem, not just part of it
- Handles edge cases
- Would survive production traffic

**Fail:**
- Partial solution
- Ignores edge cases
- Obvious bugs

---

## The 9/10 Threshold

**Auto-merge requires ≥9/10.** Here's what each score means:

| Score | Meaning |
|-------|---------|
| 10 | Perfect — no issues whatsoever |
| 9 | Excellent — trivial suggestions only, safe to merge |
| 7-8 | Good but has concerns that need fixing |
| 4-6 | Significant problems, needs major revision |
| 1-3 | Reject — breaking changes, security issues, or bounty farming |

**Strict rule:** If the reviewer lists ANY concern, the score cannot be 9 or higher.

### What 9/10 Actually Means

A 9/10 PR has:
- Zero breaking changes
- All value changes justified in PR description
- Changes perfectly scoped to the bounty
- Clean, production-ready code
- No security concerns
- Full functionality

**One concern = instant drop below 9.** Even minor issues like "could add a docstring here" prevent 9/10.

---

## Common Failure Patterns

### Bounty Farming

**Pattern:** Low-effort PRs targeting easy bounties

**Red flags:**
- 2-day-old GitHub account
- Multiple PRs submitted simultaneously
- Identical code structure across PRs
- Changes that don't match stated bounty
- Copy-paste code without understanding

**Example:**
```python
# Three PRs from same author, identical structure
PR #1: Add endpoint /api/foo
PR #2: Add endpoint /api/bar  
PR #3: Add endpoint /api/baz

# All PRs use exact same boilerplate with only names changed
```

Score: **≤6/10** (flagged for review)

### Scope Creep

**Pattern:** Touching files unrelated to the bounty

**Example:**
```
Bounty: "Add logging to user registration endpoint"

Files changed:
  ✅ registration.py — Added logging (in scope)
  ❌ payment_processor.py — "Fixed typo while browsing code"
  ❌ database.py — "Improved query performance"
```

**Why this fails:** We can't verify unrelated changes are safe. Submit separate PRs for separate improvements.

Score: **≤6/10**

### Breaking Changes Without Replacement

**Pattern:** Removing functionality without providing alternatives

**Example:**
```python
# Before: Supports both database backends
def connect_db(backend='postgres'):
    if backend == 'postgres':
        return PostgresClient()
    elif backend == 'sqlite':
        return SQLiteClient()

# Your PR: Removes SQLite support
def connect_db():
    return PostgresClient()  # Now only Postgres works
```

**Why this fails:** Existing code may depend on SQLite support. This breaks backward compatibility.

Score: **≤5/10** (auto-reject)

### Unjustified Value Changes

**Pattern:** Changing numbers without explaining why

**Example:**
```python
# Before
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30

# Your PR
MAX_RETRIES = 5      # Why?
TIMEOUT_SECONDS = 60  # Why?

# PR description: "Improved retry logic"  ← Not specific enough
```

**Fix:** Explain in PR description: "Increased MAX_RETRIES from 3 to 5 because [specific reason]. Increased TIMEOUT_SECONDS from 30 to 60 to accommodate [specific case]."

Score without justification: **≤6/10**

### Missing Wallet

**Pattern:** No payout wallet in PR description

All PRs require a wallet address in this format:

```markdown
**Payout Wallet**: YourSolanaAddressHere
```

**Without a wallet, your PR is blocked immediately.** The AI review won't even run.

---

## Merit System

Contributors build reputation through consistent high-quality work.

### Tiers

| Tier | Requirements | Payout Bonus |
|------|-------------|--------------|
| 🥉 Bronze | Default starting tier | No bonus |
| 🥈 Silver | Avg score ≥8.5, completed ≥5 PRs | +10% |
| 🥇 Gold | Avg score ≥9.5, completed ≥10 PRs | +20% |

**Example:** 5,000 WATT bounty
- Bronze: 5,000 WATT
- Silver: 5,500 WATT (+10%)
- Gold: 6,000 WATT (+20%)

### Scoring

Your average score is calculated from all your merged PRs. Rejected PRs (score <9) lower your average.

**Quality floor:** All contributors need ≥9/10 for auto-merge, regardless of tier. Tier bonuses affect payout, not the quality threshold.

### Tier Promotion

Promotions happen automatically when you meet the requirements. You'll receive a notification when promoted.

**Note:** Low scores or rejected PRs can delay promotion or cause demotion.

---

## Tips for Passing Review

### 1. Review Your Own Code First

Before submitting, ask an LLM to review your PR:

```
I'm submitting a PR to fix [issue]. Review this code for:
- Breaking changes
- Scope creep (does it touch unrelated files?)
- Unjustified value changes
- Code quality issues

[paste your diff]
```

Fix any issues the LLM identifies before submitting.

### 2. Match Existing Patterns

Don't introduce new coding styles. If the project uses:
- Certain error handling patterns → use those
- Specific naming conventions → follow them
- Particular file organization → respect it

Consistency matters more than personal preference.

### 3. Test Locally

Run the code locally before submitting. Verify:
- No syntax errors
- No import errors
- The fix actually works
- No new bugs introduced

### 4. Stay in Scope

**Only change what the bounty requests.** If you notice other issues:
- ✅ Open separate issues for them
- ❌ Don't fix them in this PR

One bounty = one PR = one focused change.

### 5. Justify Value Changes

If you must change a hardcoded value, explain why in the PR description:

```markdown
## Changes
Changed RETRY_DELAY from 30 to 60 seconds.

**Justification:** Testing showed that 30 seconds is insufficient for 
the blockchain confirmation check to complete during high network 
congestion. 60 seconds provides adequate buffer while staying 
responsive.
```

### 6. Write Clear PR Descriptions

Template:

```markdown
## Problem
Brief description of what was broken.

## Solution
What you changed and why.

## Testing
How you verified it works.

**Payout Wallet**: YourAddressHere
```

---

## Security & Privacy

### What Not to Include

❌ **Never include:**
- API keys or secrets
- Private keys or wallet private keys
- Personal email addresses
- Personal names
- Internal system URLs

✅ **Safe to include:**
- Public wallet addresses (for payouts)
- Code implementation
- Architecture improvements
- Bug fixes

### Security Review

All PRs undergo both AI code review and a separate AI security audit. The security audit checks for:
- Malware and backdoors
- Credential theft attempts
- Cryptocurrency theft
- Data exfiltration
- Supply chain attacks
- Obfuscated payloads

**Fail-closed principle:** If the security audit service is unavailable, PRs are blocked (never auto-merged without verification).

---

## FAQ

### How long does review take?

AI review typically completes within 1-5 minutes after you submit.

### What if I get a score below 9?

The AI reviewer posts feedback explaining what needs to be fixed. Address the concerns and push new commits — the review runs again automatically.

### Can I claim multiple bounties?

Yes, but submit separate PRs for each bounty. Don't combine multiple fixes into one PR.

### What if the bounty is already claimed?

Check for existing PRs linked to the issue. If someone else is working on it, find a different bounty.

### I disagree with the AI score. What now?

The review is automated but not infallible. If you believe the score is incorrect:
1. Review the feedback carefully — often the issue is real
2. If still unclear, comment on your PR explaining why you think it should pass
3. The team monitors flagged cases and can override if needed

### How long until I get paid?

Payments are queued after merge and processed after the deployment confirms stability. Typically 5-30 minutes after merge. You'll receive an on-chain transaction with a memo linking to your PR.

### Where can I see my merit score?

Check the [leaderboard](https://wattcoin.org/leaderboard) for current scores and tier rankings.

---

## Getting Help

- **Bug reports:** Open an issue
- **Questions:** Comment on the relevant issue or PR
- **General discussion:** Join the community Discord

---

**Welcome to WattCoin. Write good code, earn WATT.** 🚀
