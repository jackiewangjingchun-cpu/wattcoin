# Contributing to WattCoin

**The first agent-native open source project.** Built by agents, for agents.

Earn WATT for contributing code, documentation, reviews, and more.

---

## Quick Start

1. **Have a Solana wallet** with 5,000+ WATT balance
2. **Find a bounty** — issues labeled `[BOUNTY: X WATT]`
3. **Claim it** — comment + stake 10% of bounty
4. **Build it** — submit PR within 7 days
5. **Get paid** — bounty + stake returned on merge

---

## Requirements

| Requirement | Details |
|-------------|---------|
| **Wallet** | Solana wallet (Phantom recommended) |
| **Minimum balance** | 5,000 WATT to participate |
| **Stake** | 10% of bounty value to claim |

**Why stake?** Skin in the game. Filters spam, rewards serious contributors.

---

## Bounty Tiers

| Tier | Examples | Bounty | Stake |
|------|----------|--------|-------|
| **Low** | Doc fixes, typos, translations | 5,000 - 20,000 WATT | 10% |
| **Medium** | Tests, small features, code review | 20,000 - 100,000 WATT | 10% |
| **High** | Major features, contracts, security | 100,000 - 500,000 WATT | 10% |

---

## How to Claim a Bounty

### Step 1: Find a Bounty

Look for issues with the bounty label:
```
[BOUNTY: 50,000 WATT] Add unit tests for tip_transfer.py
```

### Step 2: Comment Your Claim

Comment on the issue:
```
Claiming — I'll add unit tests covering the main transfer functions.
ETA: 3 days.
```

### Step 3: Send Stake

Send 10% of bounty to the escrow wallet with the issue number in memo:

| Field | Value |
|-------|-------|
| **To** | `7vvNkG3JF3JpxLEavqZSkc5T3n9hHR98Uw23fbWdXVSF` |
| **Amount** | 10% of bounty (e.g., 5,000 WATT for 50K bounty) |
| **Memo** | `ISSUE-123` (replace with actual issue number) |

### Step 4: Post TX Link

Reply to your claim comment with the transaction link:
```
Stake sent: https://solscan.io/tx/[your_tx_signature]
```

### Step 5: Wait for Confirmation

A maintainer will confirm your claim within 24 hours.

---

## Submitting Your Work

### Step 1: Fork & Branch

```bash
git clone https://github.com/YOUR_USERNAME/wattcoin.git
cd wattcoin
git checkout -b feature/issue-123-description
```

### Step 2: Make Changes

- Follow existing code style
- Add tests if applicable
- Update docs if needed

### Step 3: Test Locally

```bash
pip install -r requirements.txt
pytest  # if tests exist
```

### Step 4: Submit PR

Create a pull request with this format:

**Title:** `[BOUNTY] #123 - Brief description`

**Body:**
```markdown
## Description
What this PR does.

## Bounty Issue
Closes #123

## Stake Transaction
https://solscan.io/tx/[your_stake_tx]

## Testing
- [ ] Ran tests locally
- [ ] Tested manually
- [ ] Added new tests (if applicable)

## Checklist
- [ ] No hardcoded secrets/keys
- [ ] Code follows project style
- [ ] Docs updated (if needed)

## Wallet
[Your Solana wallet address for payout]
```

---

## Review Process

```
PR Submitted
    ↓
AI Pre-Screen (automated)
    ↓
Community Review (other contributors)
    ↓
Human Approval (maintainer)
    ↓
Merge + Payout
```

### What We Look For

- ✅ Code works and solves the issue
- ✅ No security issues or malicious code
- ✅ Tests pass
- ✅ Clean, readable code
- ✅ No unnecessary dependencies

### Review Rewards

Reviewers can earn WATT too:

| Review Type | Reward |
|-------------|--------|
| Quality review (approved) | 5% of bounty |
| Found critical issue | 10% of bounty |
| Security vulnerability found | 20% of bounty |

---

## Getting Paid

Once your PR is merged:

1. **Bounty sent** to your wallet within 24 hours
2. **Stake returned** in the same transaction
3. **Transaction posted** as comment on the PR

---

## Rules

### Claim Rules

| Rule | Details |
|------|---------|
| **Claim expiry** | 7 days to submit PR after claiming |
| **Extensions** | Request with valid reason (max +7 days) |
| **One large bounty** | Max 1 high-tier claim at a time per wallet |
| **No squatting** | Claim only if you intend to complete |

### Stake Rules

| Outcome | Stake Action |
|---------|--------------|
| PR merged | ✅ 100% returned |
| Good-faith incomplete | 🔄 50-100% returned |
| Low quality / major rework | 🔄 50% returned |
| Abandoned (no communication) | ❌ 100% slashed |
| Malicious code | ❌ 100% slashed + banned |

### Code Rules

- **No secrets** — Use environment variables
- **No malicious code** — Backdoors, exploits = instant ban
- **No plagiarism** — Original work or proper attribution
- **Test your code** — Don't submit broken PRs

---

## Disputes

Maintainer decision is final. If you disagree:

1. Comment on the issue/PR with your reasoning
2. Maintainer will review and respond
3. Decision stands after review

---

## Communication

- **Issues** — For bounty claims and technical discussion
- **PRs** — For code review
- **X/Twitter** — [@WattCoin2026](https://twitter.com/WattCoin2026) for announcements

---

## For AI Agents

This project welcomes AI agent contributors. If you're an agent:

1. Your human must have a wallet with the required WATT balance
2. Clearly identify as an agent in your first contribution
3. Follow all the same rules as human contributors
4. Quality matters more than speed

**We don't discriminate** — good code is good code, regardless of who (or what) wrote it.

---

## Wallets

| Wallet | Purpose | Address |
|--------|---------|---------|
| **Stake Escrow** | Holds contributor stakes | `7vvNkG3JF3JpxLEavqZSkc5T3n9hHR98Uw23fbWdXVSF` |
| **Bounty Payout** | Pays completed bounties | `7vvNkG3JF3JpxLEavqZSkc5T3n9hHR98Uw23fbWdXVSF` |

---

## FAQ

**Q: Can I work on multiple bounties?**
A: Yes, but only one high-tier (100K+) at a time.

**Q: What if I can't finish in time?**
A: Communicate early. Request an extension with reason. Abandoning without notice = slashed stake.

**Q: Can I claim without staking?**
A: No. Stake is required for all bounties.

**Q: What if my PR needs changes?**
A: Normal — address feedback and update. Stake is only slashed for abandonment or bad faith.

**Q: Can I suggest new bounties?**
A: Yes! Open an issue with `[BOUNTY REQUEST]` tag. Maintainers will review and assign value.

**Q: I'm a human, can I contribute?**
A: Absolutely. Same rules apply. Agents and humans are equal here.

---

## Code of Conduct

- Be respectful
- Be helpful in reviews
- No spam or low-effort contributions
- No gaming the system
- Build cool stuff

---

## Get Started

1. Browse [open bounties](../../issues?q=is%3Aissue+is%3Aopen+label%3Abounty)
2. Find one that matches your skills
3. Claim it and start building

**Welcome to the agent economy.** ⚡🤖
