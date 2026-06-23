# Architecture — Crowdfunding Campaign Goal Simulator

## Overview

The simulator is split into 7 single-responsibility modules. Each module maps directly to one concept in concurrent systems engineering.

```
main.py  (orchestrator)
  │
  ├── campaign.py          shared mutable state (no locks)
  ├── pledge_engine.py     naive read→add→write update + append-only log
  ├── progress.py          reads live campaign state for display
  ├── deadline.py          background thread monitoring the campaign timer
  ├── load_simulator.py    spawns 50-100 concurrent threads
  └── verifier.py          compares corrupted counter vs true log total
```

---

## Module Descriptions

### Module 1 — `campaign.py`
Holds all campaign state as plain Python instance variables: `total_pledged`, `backer_count`, `status`. No `threading.Lock`, no `queue.Queue`, no `atomic` type — intentionally unprotected. This is the shared memory region that concurrent threads will race to update.

### Module 2 — `pledge_engine.py`
Implements the classic **read-modify-write** antipattern:
1. **READ** `campaign.total_pledged` into a local variable
2. Sleep briefly to widen the race window (simulates network latency)
3. **ADD** the pledge amount locally
4. **WRITE** the result back to `campaign.total_pledged`

Because step 4 is not atomic, two threads that both execute step 1 before either reaches step 4 will each overwrite the other's contribution — the later write wins and the earlier write is lost.

An independent `pledge_log` list records every accepted pledge. This is protected by a `threading.Lock` only to prevent list corruption (not to fix the counter race).

### Module 3 — `progress.py`
Reads the current campaign state and formats it as a human-readable string. Because it reads the (potentially corrupted) shared counter, the progress percentage during and after a load simulation may not reflect reality.

### Module 4 — `deadline.py`
Runs as a daemon thread. Computes the time remaining, sleeps until the deadline, then calls `close_campaign()`. `close_campaign()` reads `total_pledged` (the corrupted value) and sets `status` accordingly. This demonstrates how the race condition flows downstream: corrupted data leads to an incorrect final verdict.

### Module 5 — `load_simulator.py`
Uses `ThreadPoolExecutor` to spawn all threads as close together as possible. All threads share the same `Campaign` object — no copies. The tighter the thread launch window, the more likely threads will read the same stale total before any write completes, maximising observable data loss.

### Module 6 — `verifier.py`
After all threads complete, compares:
- `campaign.total_pledged` — the counter (raced, possibly corrupted)
- `sum(pledge_log["amount"])` — the true total (every pledge recorded atomically)

Reports the lost amount, lost percentage, and whether the campaign status was incorrectly assigned (verdict mismatch).

### Module 7 — `main.py`
Wires all modules together. Starts the deadline checker before the load simulation so the timer is running concurrently with pledges, matching real-world conditions.

---

## Data Flow

```
LoadSimulator.run()
  └── [Thread 1 ... Thread N]
          └── pledge_engine.pledge()
                  ├── campaign.total_pledged  ← WRITE (racy)
                  ├── campaign.backer_count   ← WRITE (racy)
                  └── pledge_log.append()     ← WRITE (safe, lock-protected)

deadline.run_deadline_checker()   (parallel background thread)
  └── close_campaign()
          └── campaign.status = "successful" | "failed"  (reads racy counter)

verifier.verify_results()
  └── compare campaign.total_pledged  vs  sum(pledge_log)
```

---

## Why No Fix Is Applied

The goal of this project is to **demonstrate** the failure mode, not to solve it. The fix would be to replace the read-modify-write with:
- `threading.Lock` around the update block, or
- An atomic add via `threading.Lock` on a wrapper class

This is left as a learning exercise.
