# Crowdfunding Campaign Goal Simulator

A Python simulation of a Kickstarter-style crowdfunding platform that deliberately demonstrates **race conditions** in concurrent systems.

## What It Does

A campaign is created with a funding goal and a deadline. 100 simulated backers all pledge money **at the same time** using threads. Because no locks are used, threads read the same stale total, compute their addition locally, then overwrite each other's writes — silently losing pledges. The campaign can be declared **FAILED** even when the real pledges met the goal.

## Project Structure

```
├── src/                    # All source modules
│   ├── campaign.py         # Module 1 — Campaign model (shared mutable state)
│   ├── pledge_engine.py    # Module 2 — Naive pledge (race condition lives here)
│   ├── progress.py         # Module 3 — Progress reporter
│   ├── deadline.py         # Module 4 — Background deadline checker
│   ├── load_simulator.py   # Module 5 — Concurrent thread spawner
│   ├── verifier.py         # Module 6 — Race condition detector
│   └── main.py             # Module 7 — Entry point / runner
├── tests/
│   └── test_all.py         # Full unit test suite (pytest)
├── docs/
│   ├── architecture.md     # System design explanation
│   ├── failure-demo.md     # Race condition output walkthrough
│   └── ai-review-summary.md
├── screenshots/            # Screenshots of the running application
├── .github/workflows/
│   └── ci.yml              # GitHub Actions CI pipeline
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10 or higher
- pytest (for tests only)

## Installation

```bash
git clone https://github.com/its-hasaan/Crowdfunding-Campaign-Goal-Simulator.git
cd Crowdfunding-Campaign-Goal-Simulator
pip install -r requirements.txt
```

## Running the Simulator

```bash
python src/main.py
```

The program will:
1. Start a campaign with a $10,000 goal and 60-second deadline
2. Spawn 100 concurrent threads each pledging $100 (expected total: $10,000)
3. Print every pledge and the total the thread observed
4. After the deadline, print the race condition report showing lost pledges

**To see results faster**, reduce `CAMPAIGN_DURATION` in `src/main.py` to `5`.

## Running the Tests

```bash
pytest tests/ -v
```

## The Race Condition — Quick Explanation

```
Thread A reads total_pledged = $0
Thread B reads total_pledged = $0    ← same stale value
Thread A writes $0 + $100 = $100
Thread B writes $0 + $100 = $100    ← overwrites Thread A
Result: $100 instead of $200        ← $100 lost
```

With 100 threads all starting simultaneously, the counter can end up showing only $200–$400 out of the expected $10,000.

## Expected Output (Race Condition Report)

```
============================================================
  RACE CONDITION REPORT
============================================================
  Backers who pledged (log) : 100
  Expected total (log sum)  : $ 10,000.00
  Observed total (counter)  : $    300.00
  Lost to race conditions   : $  9,700.00
  Campaign status           : FAILED

  *** 97.0% of pledges were silently dropped! ***
  *** Campaign declared FAILED but TRUE total met the goal! ***
============================================================
```

## Key Concept

This project teaches:
- **Shared mutable state** without synchronization
- **Read-modify-write race conditions**
- **Lost updates** in concurrent systems
- How **append-only logs** serve as ground truth
- Why **locks / atomic operations** exist in real systems
