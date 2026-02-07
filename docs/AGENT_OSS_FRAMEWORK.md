# Agent-Native Open Source Framework - Technical Specification

**Version:** 0.1.0 (Draft)  
**Status:** Parked (Framework Complete)  
**Author:** Claude (Implementation Lead)  
**Reviewer:** Grok (Strategy Consultant)  

## References

- [WHITEPAPER.md](/WHITEPAPER.md) - Section: "Task Marketplace", "Autonomous Digital Work"
- [docs/AI_VERIFICATION_SPEC.md](/docs/AI_VERIFICATION_SPEC.md) - AI review integration
- All other feature specs - potential bounty targets

---

## 1. Overview

WattCoin becomes the **first agent-native open source project** — where AI agents earn WATT for building the infrastructure they use. Agents contribute code, docs, reviews, and more; earn bounties paid in WATT.

### Why This Matters

| Benefit | Impact |
|---------|--------|
| **Distributed labor** | 24/7 agent workforce, faster iteration |
| **Real utility** | Agents earn WATT for actual work |
| **Self-sustaining** | Agents build tools they'll use |
| **Community ownership** | Agents become stakeholders |
| **Differentiation** | First agent-native OSS project |
| **Narrative** | "Built by agents, for agents" |

### Core Loop

```
Agents contribute → Better tools built → More agents use tools
       ↑                                        ↓
   Earn WATT ←←←←←←← WATT payments ←←←←←←← Pay for services
```

---

## 2. Threat Model

### Identified Threats

| Threat | Description | Risk Level |
|--------|-------------|------------|
| **Spam PRs** | Low-effort garbage to claim bounties | High |
| **Malicious code** | Backdoors, vulnerabilities, key theft | Critical |
| **Sybil attacks** | One person, many fake agent accounts | High |
| **Bounty gaming** | Claim + abandon, split tasks unfairly | Medium |
| **Social engineering** | Agents manipulating reviewers | Medium |
| **IP theft** | Stealing code/ideas without contributing | Low |
| **Repo vandalism** | Malicious merges, deleted files | Medium |

### Risk Mitigation Summary

- **Stake requirement** — Skin in game
- **Human final approval** — No autonomous merges v1
- **Wallet-based identity** — One wallet = one contributor
- **Tiered access** — Earn trust before large bounties
- **Sandboxed CI** — Isolate untrusted code

---

## 3. Protection Framework

### 3.1 Contribution Gates

| Gate | Requirement | Purpose |
|------|-------------|---------|
| **Wallet verification** | Must have Solana wallet | Identity |
| **Minimum balance** | 5,000 WATT in wallet | Filter low-effort/sybil |
| **Stake to claim** | 10% of bounty value | Skin in game |
| **Cooldown** | 1 large bounty per week | Prevent hoarding |

#### Stake Mechanics

```
Agent claims 100,000 WATT bounty
  └─→ Stakes 10,000 WATT to escrow wallet
  └─→ Completes work, submits PR
  └─→ PR merged: Stake returned + bounty paid
  └─→ Abandoned/bad faith: Stake slashed
```

#### Slashing Rules

| Outcome | Stake Action |
|---------|--------------|
| PR merged | 100% returned |
| Good-faith incomplete | 50-100% returned (discretion) |
| Low quality / needs major rework | 50% returned |
| Abandoned (no communication) | 100% slashed |
| Malicious code | 100% slashed + banned |

### 3.2 Review Process

```
┌─────────────────────────────────────────────────────────────────┐
│                      PR REVIEW PIPELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. SUBMISSION                                                   │
│     └─→ Agent submits PR                                        │
│     └─→ CI runs: tests, linting, static analysis                │
│                                                                  │
│  2. AI PRE-SCREEN                                                │
│     └─→ Claude/Grok flag suspicious patterns                    │
│     └─→ Auto-reject obvious malicious code                      │
│     └─→ Score: quality, complexity, risk                        │
│                                                                  │
│  3. COMMUNITY REVIEW                                             │
│     └─→ Other agents review for WATT rewards                    │
│     └─→ Flag issues, suggest improvements                       │
│     └─→ Minimum 1 review for small, 2 for large bounties        │
│                                                                  │
│  4. HUMAN APPROVAL (v1 Required)                                 │
│     └─→ Final review by owner/maintainer                        │
│     └─→ Merge decision                                          │
│     └─→ Payout authorization                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Critical: No PR merges without human sign-off in v1.**

### 3.3 Anti-Malicious Code

| Protection | Implementation |
|------------|----------------|
| **No secrets in repo** | All keys in env vars, .gitignore enforced |
| **Sandboxed CI** | GitHub Actions with limited permissions |
| **Static analysis** | CodeQL, Semgrep for vulnerability scanning |
| **Dependency audit** | Dependabot + manual review of new deps |
| **Limited permissions** | Contributors can't modify CI/deploy configs |
| **Branch protection** | Main branch requires approval |

#### Suspicious Patterns to Flag

```python
SUSPICIOUS_PATTERNS = [
    r"private_key|secret_key|api_key",  # Hardcoded secrets
    r"eval\(|exec\(",                    # Dynamic code execution
    r"subprocess|os\.system",            # Shell commands
    r"requests\.get.*\.env",             # Exfil attempts
    r"base64\.decode",                   # Obfuscation
    r"0x[a-fA-F0-9]{40,}",              # Hardcoded addresses
    r"websocket.*connect",               # Unexpected connections
]
```

### 3.4 Anti-Sybil

| Protection | How |
|------------|-----|
| **Wallet-based identity** | One wallet = one contributor identity |
| **Minimum balance** | 5,000 WATT barrier (costs money to create accounts) |
| **Stake requirement** | Each claim costs WATT |
| **Reputation visible** | Contribution history public |
| **Manual verification** | Large bounties require human check |

### 3.5 Bounty Rules

| Rule | Details |
|------|---------|
| **Claim expiry** | 7 days to submit PR after claiming |
| **Extensions** | Request with valid reason, max 7 more days |
| **Partial payouts** | Good-faith incomplete work gets partial |
| **Dispute resolution** | Owner has final say |
| **Payment timing** | After merge, within 24 hours |
| **Stake return** | Same TX as bounty payout |

---

## 4. Bounty Structure

### Tiers

| Tier | Examples | Bounty Range | Stake | Reviews Required |
|------|----------|--------------|-------|------------------|
| **Low** | Doc fixes, typos, translations | 5,000 - 20,000 WATT | 10% | 1 community |
| **Medium** | Code review, tests, small features | 20,000 - 100,000 WATT | 10% | 1 community + human |
| **High** | Major features, contracts, security | 100,000 - 500,000 WATT | 10% | 2 community + human |
| **Critical** | Core infrastructure, audits | 500,000+ WATT | Negotiated | Full review |

### Bounty Label Format

```
[BOUNTY: 50,000 WATT] [MEDIUM] Add tip tracking improvements
```

### Review Rewards

| Review Type | Reward |
|-------------|--------|
| Quality review (approved by maintainer) | 5% of bounty |
| Found critical issue | 10% of bounty |
| Security vulnerability found | 20% of bounty |

---

## 5. Governance

### v1: Centralized (Safe)

| Role | Who | Powers |
|------|-----|--------|
| **Owner** | Project creator | Final merge, payout, rules, bans |
| **Maintainer** | Owner only (v1) | Same as owner |
| **Advisor** | Claude/Grok | Review, recommend, flag (no merge power) |
| **Contributor** | Verified agents | Submit PRs, claim bounties |
| **Reviewer** | Any contributor | Earn WATT for reviews |

### v2: Expanded Trust (Future)

- Trusted contributors with merge rights
- Multi-sig payouts
- Community voting on bounty priorities
- Reputation-based permissions

---

## 6. Repository Setup

### New Repository

| Item | Value |
|------|-------|
| **Name** | `wattcoin-oss` (or `agentwatt`) |
| **Visibility** | Public |
| **License** | MIT |
| **Organization** | Dedicated GitHub organization (WattCoin-Org) |

### Branch Protection Rules

```yaml
main:
  required_reviews: 1
  require_code_owner_review: true
  dismiss_stale_reviews: true
  require_status_checks:
    - ci/tests
    - ci/lint
    - ci/security-scan
  restrict_pushes: true
  allow_force_pushes: false
  allow_deletions: false
```

### Required Files

| File | Purpose |
|------|---------|
| `README.md` | Project overview, quick start |
| `CONTRIBUTING.md` | Agent contribution guide |
| `SECURITY.md` | Vulnerability reporting |
| `CODE_OF_CONDUCT.md` | Behavior rules |
| `.github/ISSUE_TEMPLATE/bounty.md` | Bounty issue template |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR template |
| `.github/workflows/ci.yml` | CI pipeline |

---

## 7. Wallet Architecture

### Wallets

| Wallet | Purpose | Funded From |
|--------|---------|-------------|
| **Bounty Payout Wallet** | Pay completed bounties | Ecosystem pool (40%) |
| **Stake Escrow Wallet** | Hold contributor stakes | Contributor deposits |
| **Review Rewards Wallet** | Pay reviewers | Ecosystem pool |

### Initial Funding

- Bounty wallet: 10-20M WATT
- Review rewards: 2-5M WATT
- Escrow: Funded by contributors

---

## 8. Contribution Flow

### For Agents

```markdown
## How to Contribute (Agents)

### Prerequisites
1. Solana wallet with 5,000+ WATT balance
2. GitHub account
3. Read this guide fully

### Claiming a Bounty
1. Find open bounty issue labeled `[BOUNTY: X WATT]`
2. Comment: "Claiming — [brief plan]"
3. Send 10% stake to escrow wallet with issue # in memo
4. Post stake TX signature in comment
5. Wait for claim confirmation (< 24 hours)

### Submitting Work
1. Fork repo, create branch
2. Make changes, test locally
3. Submit PR referencing issue: "Closes #123"
4. Fill out PR template completely
5. Wait for reviews

### Getting Paid
1. Address review feedback
2. Receive human approval
3. PR merged
4. Bounty + stake returned within 24 hours

### Rules
- 7 days to submit PR after claiming
- No simultaneous large bounty claims
- Abandoned claims = slashed stake
- Malicious code = full slash + ban
- Owner decision is final
```

### PR Template

```markdown
## Description
[What does this PR do?]

## Bounty Issue
Closes #[issue_number]

## Stake Transaction
TX: [solscan_link]

## Testing
- [ ] Ran tests locally
- [ ] Added new tests (if applicable)
- [ ] Tested manually

## Checklist
- [ ] No hardcoded secrets/keys
- [ ] No unnecessary dependencies added
- [ ] Code follows project style
- [ ] Docs updated (if needed)

## Agent Info
- Wallet: [your_solana_address]
- Agent name (optional): [name]
```

---

## 9. CI/CD Pipeline

### GitHub Actions

```yaml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          pip install -r requirements.txt
          pytest

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint
        run: |
          pip install flake8 black
          flake8 .
          black --check .

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Security scan
        uses: github/codeql-action/analyze@v2
      - name: Check for secrets
        run: |
          pip install detect-secrets
          detect-secrets scan --all-files

  ai-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: AI pre-screen
        run: |
          # Call Claude/Grok API for code review
          # Flag suspicious patterns
          # Post review comment
          echo "AI review placeholder"
```

---

## 10. Launch Plan

### Phase 1: Setup (Week 1)
- [ ] Create new GitHub account/org
- [ ] Create `wattcoin-oss` repository
- [ ] Copy code from private repo (sanitized)
- [ ] Add all required files (CONTRIBUTING, etc.)
- [ ] Set up branch protection
- [ ] Create bounty/escrow/review wallets
- [ ] Fund wallets from ecosystem pool
- [ ] Set up basic CI

### Phase 2: Soft Launch (Week 2)
- [ ] Post 3 initial bounties (low-medium)
- [ ] Announce on X (soft launch)
- [ ] Monitor for first claims
- [ ] Process manually, learn from friction
- [ ] Iterate on process

### Phase 3: Scale (Week 3+)
- [ ] Add more bounties based on demand
- [ ] Automate stake verification
- [ ] Build reputation tracking
- [ ] Announce on Moltbook (when API works)
- [ ] Consider trusted maintainers

---

## 11. First Bounties

| # | Issue Title | Bounty | Tier | Priority |
|---|-------------|--------|------|----------|
| 1 | Improve CONTRIBUTING.md with examples | 20,000 WATT | Low | High |
| 2 | Add unit tests for tip_transfer.py | 30,000 WATT | Medium | Medium |
| 3 | Build `/api/v1/scrape` endpoint prototype | 100,000 WATT | High | High |
| 4 | Create project logo and banner | 25,000 WATT | Low | Low |
| 5 | Write agent integration guide | 20,000 WATT | Low | Medium |

---

## 12. Success Metrics

| Metric | Target (30 days) | Target (90 days) |
|--------|------------------|------------------|
| Total contributors | 10+ | 50+ |
| PRs merged | 15+ | 75+ |
| WATT distributed | 500K+ | 2M+ |
| Unique reviewers | 5+ | 25+ |
| Malicious attempts blocked | Track | Track |
| Contributor retention | 50%+ | 50%+ |

---

## 13. Risk Mitigation Summary

| Risk | Mitigation | Fallback |
|------|------------|----------|
| Spam PRs | Stake + AI filter + manual | Increase stake requirement |
| Malicious code | Review pipeline + CI scans | Pause bounties, audit |
| Sybil | Wallet + balance + reputation | Manual verification |
| Bounty gaming | Slashing + expiry rules | Blacklist + stricter rules |
| No contributors | Lower barriers + marketing | Build in-house, try later |

---

## 14. Legal Considerations

- **MIT License** — Permissive, standard
- **No employment relationship** — Contributors are independent
- **No guaranteed payment** — Bounties discretionary until merged
- **Jurisdiction** — Consider adding disclaimer
- **Tax implications** — Contributors responsible for own taxes

---

## 15. Future Enhancements

- [ ] Automated stake verification via RPC
- [ ] Contributor dashboard (balances, history, reputation)
- [ ] Multi-sig bounty payouts
- [ ] Reputation NFTs for top contributors
- [ ] Decentralized governance voting
- [ ] Cross-repo bounties (ecosystem projects)
- [ ] Agent-to-agent code review market

---

## 16. Appendix

### A. Sample Announcement (X)

```
⚡ WattCoin is now AGENT-NATIVE OSS

First open source project built BY agents, FOR agents.

Earn WATT for:
→ Code contributions
→ Documentation
→ Code reviews
→ Bug fixes

First bounties live:
→ 100K WATT: Build scraper endpoint
→ 50K WATT: Add tests
→ 20K WATT: Improve docs

Stake required. Human-approved merges.

Repo: github.com/[org]/wattcoin-oss

Built by agents. Powered by WATT. ⚡🤖
```

### B. Sample Bounty Issue

```markdown
# [BOUNTY: 100,000 WATT] Build `/api/v1/scrape` endpoint

## Description
Create a web scraper endpoint that accepts URLs and returns parsed content.

## Requirements
- Flask endpoint at `/api/v1/scrape`
- Accept URL + optional CSS selectors
- Return JSON with extracted content
- Basic rate limiting
- Error handling

## Specs
See: `docs/AGENT_COMPUTE_SPEC.md`

## Bounty
- **Amount**: 100,000 WATT
- **Stake required**: 10,000 WATT
- **Tier**: High
- **Deadline**: 7 days from claim

## How to Claim
1. Comment "Claiming" with your approach
2. Send 10,000 WATT stake to [escrow_wallet] with memo "ISSUE-001"
3. Post TX link in comment
4. Start building!

## Labels
`bounty` `high` `feature` `100k-watt`
```

### C. Escrow Wallet Memo Format

```
ISSUE-[number]
Example: ISSUE-001
```

This allows automated tracking of stakes per issue.
