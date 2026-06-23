# =============================================================================
# MODULE 5: Load Simulator
# =============================================================================
# Spawns concurrent threads that simulate real backers making pledges.
# Configurable number of threads and pledge amounts to test various scenarios.
#
# The simulator deliberately creates a high-concurrency environment where
# all threads overlap as much as possible to maximize the likelihood of
# race condition collisions in the pledge engine.
# =============================================================================

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from campaign      import Campaign
from pledge_engine import pledge


class LoadSimulator:
    """
    Orchestrates concurrent pledge operations for load testing.

    Attributes
    ----------
    num_threads : int
        Number of concurrent threads to spawn.
    pledge_amount : float
        Amount each thread pledges (same for all threads in basic mode).
    """

    def __init__(self, num_threads: int = 100, pledge_amount: float = 100.0):
        """
        Initialize the load simulator.

        Args
        ----
        num_threads : int, optional
            Number of concurrent pledger threads. Default: 100.
        pledge_amount : float, optional
            Amount each backer pledges. Default: 100.0.
        """
        self.num_threads   = num_threads
        self.pledge_amount = pledge_amount

    def run(self, campaign: Campaign) -> dict:
        """
        Execute the load simulation by spawning concurrent pledge threads.

        Returns a summary of what was attempted.

        Args
        ----
        campaign : Campaign
            The campaign to pledge to.

        Returns
        -------
        dict
            Contains:
            - 'num_threads': int (threads spawned)
            - 'num_successful': int (pledges accepted)
            - 'num_failed': int (pledges rejected, e.g., campaign closed)
            - 'elapsed_time': float (seconds to run all threads)
            - 'expected_total': float (sum of all pledge amounts)
        """
        threads = []
        results = {"successful": 0, "failed": 0}
        results_lock = threading.Lock()

        def worker(thread_id: int):
            """
            Worker function for a single thread — makes one pledge.
            """
            backer_id = f"backer_{thread_id:04d}"
            success = pledge(campaign, backer_id, self.pledge_amount)

            with results_lock:
                if success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1

        print(f"\n[LOAD_SIMULATOR] Spawning {self.num_threads} concurrent threads...")
        print(f"                 Pledge amount: ${self.pledge_amount:.2f}")
        print(f"                 Expected total: ${self.num_threads * self.pledge_amount:,.2f}")

        start = time.time()

        # Use ThreadPoolExecutor for cleaner concurrency management
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = [
                executor.submit(worker, i)
                for i in range(self.num_threads)
            ]
            # Wait for all threads to complete
            for future in as_completed(futures):
                future.result()  # re-raise any exceptions

        elapsed = time.time() - start

        print(f"\n[LOAD_SIMULATOR] All {self.num_threads} threads finished in {elapsed:.3f}s")
        print(f"                 Successful pledges: {results['successful']}")
        print(f"                 Failed pledges: {results['failed']}")

        return {
            "num_threads": self.num_threads,
            "num_successful": results["successful"],
            "num_failed": results["failed"],
            "elapsed_time": elapsed,
            "expected_total": self.num_threads * self.pledge_amount,
        }

    def run_varied_amounts(self, campaign: Campaign, amounts: list[float]) -> dict:
        """
        Advanced: Run simulation with varied pledge amounts.

        Useful for testing realistic scenarios where backers pledge different amounts.

        Args
        ----
        campaign : Campaign
            The campaign to pledge to.
        amounts : list[float]
            List of pledge amounts. If fewer than num_threads, amounts cycle.
            Example: [50, 100, 250] with num_threads=5 →
                     [50, 100, 250, 50, 100]

        Returns
        -------
        dict
            Same as run(), but with accurate expected_total based on amounts.
        """
        if not amounts:
            raise ValueError("amounts list cannot be empty")

        threads = []
        results = {"successful": 0, "failed": 0}
        results_lock = threading.Lock()

        def worker(thread_id: int):
            backer_id = f"backer_{thread_id:04d}"
            amount = amounts[thread_id % len(amounts)]
            success = pledge(campaign, backer_id, amount)
            with results_lock:
                if success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1

        print(f"\n[LOAD_SIMULATOR] Spawning {self.num_threads} concurrent threads (varied amounts)...")
        print(f"                 Amounts pattern: {amounts}")
        expected = sum(amounts[i % len(amounts)] for i in range(self.num_threads))
        print(f"                 Expected total: ${expected:,.2f}")

        start = time.time()

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = [
                executor.submit(worker, i)
                for i in range(self.num_threads)
            ]
            for future in as_completed(futures):
                future.result()

        elapsed = time.time() - start

        print(f"\n[LOAD_SIMULATOR] All {self.num_threads} threads finished in {elapsed:.3f}s")
        print(f"                 Successful pledges: {results['successful']}")
        print(f"                 Failed pledges: {results['failed']}")

        return {
            "num_threads": self.num_threads,
            "num_successful": results["successful"],
            "num_failed": results["failed"],
            "elapsed_time": elapsed,
            "expected_total": expected,
        }
