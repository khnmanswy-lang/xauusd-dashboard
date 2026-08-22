---
description: Enforces idempotency and reliability patterns for automation scripts - safe to re-run without duplicating side effects, retry with backoff on transient failures, and structured logging so unattended runs are debuggable after the fact. Use whenever writing or modifying an automation script, scheduled job, or anything that calls an external API/service.
---

# Idempotent Automation

## Why this exists
Automation runs unattended - nobody's watching it in real time, and it often gets re-run (manual retry, a scheduled job firing again after a partial failure, GitHub Actions re-triggering). A script that isn't safe to re-run turns a transient failure into duplicated actions (double-sent messages, duplicate records, double-charged something) - often worse than the original failure.

## 1. Design for safe re-runs
Before writing the logic, ask: what happens if this runs twice with the same input? It should either be a no-op the second time, or explicitly check "has this already been done" before acting (a processed-IDs log, a database uniqueness constraint, checking the target state before writing to it) - not assume it only ever runs once cleanly.

## 2. Checkpoint long-running or multi-step work
If a script processes a batch of items, track progress (which items are done) so a failure partway through can resume from where it left off, rather than restarting the whole batch and risking duplicate actions on the already-processed items.

## 3. Retry transient failures, don't retry everything
Network timeouts, rate limits (429s), and other transient errors should retry with backoff (e.g. wait 1s, retry once or twice, give up and log clearly if it keeps failing). Don't blindly retry on errors that won't resolve themselves (bad credentials, malformed input, 4xx errors other than rate limits) - that just wastes time and obscures the real problem.

## 4. Log what happened, not just that it ran
Since nobody's watching live, the log is the only record. For each run, log what was attempted, what succeeded, what failed and why, and any items skipped because they were already done. A log that just says "job completed" is useless when something goes wrong three runs later.

## 5. Secrets never get logged or hardcoded
Credentials come from `.env`/environment variables or GitHub Actions secrets, never hardcoded or printed in logs - even in debug output.
