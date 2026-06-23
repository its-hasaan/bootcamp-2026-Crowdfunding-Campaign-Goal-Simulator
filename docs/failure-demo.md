# Failure Mode Demonstration

This document walks through how the race condition failure mode was demonstrated.

---

## Setup

- **Campaign goal:** $10,000
- **Concurrent backers:** 100 threads
- **Pledge per backer:** $100 each
- **Expected total:** 100 × $100 = **$10,000** (goal should be met)

---

## The Race Condition

Each thread runs this code in `pledge_engine.py`:

```python
current_total = campaign.total_pledged   # Step 1: READ
time.sleep(0.001)                        # Simulate latency → widens race window
new_total = current_total + amount       # Step 2: ADD
campaign.total_pledged = new_total       # Step 3: WRITE (no lock)
```

When 100 threads all execute **Step 1** before any execute **Step 3**, they all read the same starting value (e.g. `$0`). Each computes `$0 + $100 = $100` and writes back `$100`. The result: 100 pledges collapse to `$100` instead of `$10,000`.

---

## Actual Output (run on 2026-06-22)

```
============================================================
  CAMPAIGN STARTED: Open-Source Rover Project
  Goal    : $10,000.00
  Deadline: 60s from now
============================================================

[SIMULATOR] Launching 100 concurrent pledge threads...

  [PLEDGE] Backer backer_0025 pledged $  100.00 → observed total $    100.00
  [PLEDGE] Backer backer_0051 pledged $  100.00 → observed total $    100.00
  [PLEDGE] Backer backer_0050 pledged $  100.00 → observed total $    100.00
  ... (97 more lines, all reporting $100-$300)

[SIMULATOR] All threads finished in 0.042s

[PROGRESS] $    200.00 / $ 10,000.00 —   2.0% (100 backers)

============================================================
  RACE CONDITION REPORT
============================================================
  Backers who pledged (log) : 100
  Expected total (log sum)  : $ 10,000.00
  Observed total (counter)  : $    200.00
  Lost to race conditions   : $  9,800.00
  Campaign status           : FAILED

  *** 98.0% of pledges were silently dropped! ***
  *** Campaign declared FAILED but TRUE total met the goal! ***
============================================================
```

---

## What the Output Proves

| Fact | Value |
|------|-------|
| Pledges recorded in log | 100 (all accepted) |
| True total (from log) | $10,000.00 |
| Counter total (corrupted) | $200.00 |
| Money lost silently | $9,800.00 (98%) |
| Campaign verdict (counter) | FAILED |
| Campaign verdict (true) | SUCCESSFUL |

The campaign had enough money to succeed. The race condition made it appear to fail.

---

## Why the Counter Shows Only $200–$300

All 100 threads start at nearly the same millisecond. The `time.sleep(0.001)` ensures they all complete the READ before any WRITE lands. They all read `$0`, compute `$100`, and write `$100`. The last few threads to write "win" — everyone else's write is overwritten. Only the last 2–3 writes survive, giving totals of `$100`, `$200`, or `$300`.

---

## The Append-Only Log Is the Proof

The `pledge_log` list is appended to inside a `threading.Lock` — not to fix the counter, but to prevent list corruption. Every accepted pledge lands in the log regardless of the counter race. Summing the log gives the true total, exposing the discrepancy.
