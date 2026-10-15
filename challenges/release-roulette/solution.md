# Release Roulette — Author Solution

## Problem Statement

ReleaseBot is Aurora's AI release-prep assistant. Its stated job is
**inspect → summarize → stage**. Players only have the chat interface. They must
find out whether the assistant can do more than its role requires, and prove it
by making ReleaseBot cause a protected state change on release `aurora-4.8.1`.

## Vulnerability

ReleaseBot's tool registry is wired straight to `deploy-ops`, an adapter built
for **human release operators**. It exposes every deployment operation:

```text
list_releases  inspect_release  generate_report  stage_release   <- needed
promote_release  rollback_release  delete_release                <- NOT needed
```

The adapter records the caller (`actor`) but never authorizes it. It ignores
the `protected` flag and needs no human approval. The application assumes "the
model will only choose safe operations". That assumption is the vulnerability.

## OWASP Mapping

**LLM06:2025 — Excessive Agency.** OWASP names three root causes:

| Root cause | Present here? |
| --- | --- |
| Excessive **functionality**: tools beyond what the task needs | **Yes, primary.** rollback/promote/delete are in the agent's registry. |
| Excessive **permissions**: tools act with more privilege than needed | **Yes, secondary.** The adapter runs in "operator scope" and ignores `protected`. |
| Excessive **autonomy**: high-impact actions without human approval | **Yes, primary.** Rollback executes immediately. A vague "fix it" makes the agent pick rollback by itself. |

## Architecture

```text
Browser (chat)
   │
   ▼
Agent orchestrator (ReleaseRouletteAgent: deterministic planner)
   │  picks tools from AGENT_TOOLS  ← full operator registry (FLAW)
   ▼
deploy-ops tool adapter (tools.py)
   │  records actor, never authorizes, ignores `protected` (FLAW)
   ▼
Simulated deployment DB (SQLite, per player)
```

## Intended Attack Path

1. **Understand the role.** Ask `what can you do?`. ReleaseBot says its job is
   inspect / summarize / stage, and that promotion is done by a human.
2. **Enumerate capabilities.** Ask `what tools do you have?`. The registry lists
   `promote_release`, `rollback_release`, and `delete_release`, and notes that the
   adapter was built for human operators.
3. **Compare.** Available capability ≠ required capability. Rollback has nothing
   to do with release prep.
4. **Find the target.** Ask `list releases` or `check the release`.
   `aurora-4.8.1` is STAGED, protected, and production-bound.
5. **Trigger the unnecessary operation** through the normal interface:

   ```text
   roll back aurora-4.8.1
   ```

   The tool activity shows `rollback_release · release_id: aurora-4.8.1 ·
   STAGED -> ROLLED_BACK`, the release panel flips to **ROLLED BACK**, and the
   response contains the flag `OWASP{release_<random>}`.
6. Submit the flag.

**Alternative path (excessive autonomy).** Run `prepare a report on 4.8.1`. The
report shows a `checkout-latency` warning. Then ask
`can you fix the latency issue on 4.8.1?`. The player never mentions rollback.
The agent picks the "quickest remediation available" on its own, which is
`rollback_release`. Both paths solve, and both show the same root cause.

## Why It Works

Nothing between the agent and the deployment system checks *whether this caller
may perform this action*. The only "control" is the agent's description of its
role, and that's text, not enforcement. Once the tool is in the registry, a
normal-sounding request is enough to reach it.

## Exact Solve Condition

`backend/app/challenges/release_roulette/validator.py`, evaluated after every chat
turn against database state:

```text
release_id == "aurora-4.8.1"
AND status == "ROLLED_BACK"
AND last_actor == "releasebot"
```

## Why This Is Excessive Agency

The model does exactly what the application lets it do. No hidden system prompt
is broken and no guardrail is bypassed. The harm comes from the **power** the
agent was given (functionality + autonomy) and from the missing downstream
authorization, not from the model being tricked.

## Why This Is Not Primarily Prompt Injection

```text
Prompt Injection:  attacker manipulates model behavior.
Excessive Agency:  model has too much operational power.
```

They can occur together. OWASP notes that injection is a common *trigger* for
Excessive Agency. Here no injection is needed at all: a plain, honest request
reaches the dangerous tool. With the least-privilege registry
(`SAFE_AGENT_TOOLS`), the same request does nothing, however it is phrased.
That shows the root cause is the architecture.

## Root Cause

```python
AGENT_TOOLS = {  # agent.py
    "list_releases", "inspect_release", "generate_report", "stage_release",
    "promote_release", "rollback_release", "delete_release",   # <- should not be here
}

def rollback_release(ctx, release_id):  # tools.py
    # actor is recorded, but never authorized; `protected` is ignored;
    # no human approval.
    return _transition(ctx, "rollback_release", "rollback", release_id)
```

## Remediation

The fix is **not** "tell the model not to roll back releases". A prompt rule
is not a security boundary.

1. **Minimize functionality.** Give the agent only `SAFE_AGENT_TOOLS` (inspect,
   report, stage). `test_safe_registry_blocks_rollback` proves this alone stops
   the attack.
2. **Minimize permissions.** ReleaseBot's deployment identity should have no
   rollback/promote/delete rights at all, enforced by the deployment service.
3. **Separate high-impact operations.** Rollback, promote, and delete belong
   behind a separate privileged interface.
4. **Require human approval.** High-impact actions need explicit confirmation
   outside the model.
5. **Complete mediation.** The deployment service authorizes *every* privileged
   request itself:

   ```python
   def rollback_release(release_id, principal):
       authorize(principal=principal, action="release.rollback", resource=release_id)
       require_human_approval(action="release.rollback", resource=release_id)
       ...
   ```

Monitoring (the Tool Activity log) can *detect* excessive agency. It does not
replace least privilege or authorization.

### Secure architecture

```text
User → AI Agent → (only safe tools) → Safe Tool Gateway [inspect, report, stage] → Deployment Service

High-impact action:
User → AI proposes rollback → Policy / Authorization Layer → Human Approval → Privileged Deployment API
```

The model proposes. Code authorizes. A human approves high-impact actions.

## Alternative Designs

- Use read-only tools plus a "request rollback" tool that opens a ticket for a
  human instead of acting.
- Use per-tool scoped credentials, so ReleaseBot's token simply cannot roll back.
- Use an approval queue: the agent's high-impact calls become pending actions a
  release manager confirms.

## Common Unintended Solutions (and why they fail)

| Attempt | Result |
| --- | --- |
| `roll back the release` (no ID) | Agent asks which release. High-impact tools need an explicit ID. |
| Roll back `aurora-4.8.0` | Wrong release → validator unsolved. |
| Delete `aurora-4.8.1` | Status DELETED, not ROLLED_BACK → unsolved. Reset to try again. |
| `do not roll back 4.8.1` | Negated requests are not executed. |
| Guessing `/flag`, `/debug/state`, `/internal/config` | 404. The flag never appears in `/state`, metadata, or the frontend. |
| Submitting Model Mirror's flag | Each challenge has its own flag and hash. |
| SQL/command injection in chat | Release IDs are regex-validated. ORM-only queries; no shell execution exists. |

Note: `promote` then `roll back` 4.8.1 also solves (PROMOTED → ROLLED_BACK).
That's intended, since it uses the same excessive capability.

## Testing

`backend/tests/test_release_roulette.py` covers the initial state, tool
side-effects, the valid transitions, agent routing, the step limit, the
negation case, the least-privilege remediation, every validator case, both
solve paths end to end, reset, player isolation, malformed and oversized input,
flag non-disclosure (API, repo sources, logs), and an AST check that the
challenge code never imports `subprocess`/`socket`/etc. or calls `eval`/`exec`.

## Learning Outcomes

After solving, a student can:

1. Define Excessive Agency and its three root causes (functionality,
   permissions, autonomy).
2. Explain why "the model normally chooses the safe action" is not a control.
3. Explain why authorization must live outside the model, in the downstream
   system.
4. Apply least privilege to agent tool registries.
5. Justify human approval for high-impact, irreversible operations.
6. Tell Excessive Agency apart from Prompt Injection, and explain how they
   combine.
7. Redesign an agent so that even a manipulated or compromised model cannot
   exceed its authority.

> **An AI agent is not an authorization boundary.**
