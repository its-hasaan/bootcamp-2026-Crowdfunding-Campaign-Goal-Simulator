# AI Code Review Summary

## Tool Used
GitHub Copilot (inline code review via VS Code)

---

## Findings & Actions Taken

### Finding 1 — Intentional Race Condition (No Fix Applied)
**Finding:** `total_pledged` and `backer_count` are modified by multiple threads without synchronization. This is a data race.

**Action:** No fix applied. This is the **intentional demonstration** of the failure mode. The entire project exists to show what happens without locking.

---

### Finding 2 — `pledge_log` uses a Lock but the counter does not
**Finding:** `_log_lock` protects only the append-only log, not `total_pledged`. This is asymmetric and could be confusing.

**Action:** Added inline comments in `pledge_engine.py` clearly explaining that the lock is intentionally scoped to the log only. The counter is deliberately left unprotected.

---

### Finding 3 — `time.sleep(0.001)` inside a hot path
**Finding:** Sleeping inside `pledge()` artificially slows throughput and may not reflect real network latency accurately.

**Action:** Kept as-is. The sleep is intentional — it widens the race window so the failure mode is reliably observable. Without it, threads may not overlap enough to demonstrate the bug consistently.

---

### Finding 4 — No input validation on `amount`
**Finding:** Negative or zero pledge amounts are not rejected.

**Action:** Added a guard in `pledge()`: if `amount <= 0`, the pledge is rejected and logged as invalid. This is a boundary condition that should be handled at the system edge.

---

### Finding 5 — `deadline_thread.join()` blocks main thread indefinitely if checker crashes
**Finding:** If `run_deadline_checker()` raises an unhandled exception, `main.py` will hang at `deadline_thread.join()`.

**Action:** Wrapped the deadline checker body in a `try/except` to ensure the campaign is always closed and the thread always exits, even on error.

---

## Summary

| Finding | Severity | Action |
|---------|----------|--------|
| Unprotected shared counter | Intentional | No fix (demo purpose) |
| Asymmetric locking | Low | Comment clarification added |
| Sleep in hot path | Low | Kept intentionally |
| No amount validation | Medium | Guard added |
| Thread join hang risk | Medium | try/except added to checker |
