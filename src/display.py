# =============================================================================
# MODULE: Visual Display
# =============================================================================
# Provides a rich terminal UI for demonstrating the race condition.
# Uses the `rich` library for panels, tables, progress bars, and colour.
# =============================================================================

import time
import threading

from rich.console   import Console
from rich.panel     import Panel
from rich.table     import Table
from rich.progress  import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.text       import Text
from rich           import box

console = Console()


def print_campaign_header(campaign) -> None:
    """Print a styled campaign info panel at startup."""
    content = (
        f"[bold cyan]Campaign:[/]  {campaign.title}\n"
        f"[bold cyan]Goal:    [/]  [green]${campaign.goal_amount:,.2f}[/]\n"
        f"[bold cyan]Duration:[/]  {campaign.duration_sec}s\n"
        f"[bold cyan]Status:  [/]  [yellow]{campaign.status.upper()}[/]"
    )
    console.print(Panel(content, title="[bold white] CROWDFUNDING SIMULATOR [/]",
                        border_style="cyan", padding=(1, 4)))


def print_simulation_start(num_backers: int, pledge_amount: float) -> None:
    """Print simulation launch info."""
    console.print(
        f"\n[bold yellow]⚡ Launching {num_backers} concurrent threads[/] "
        f"— each pledging [green]${pledge_amount:,.2f}[/]\n"
        f"   Expected total if no race condition: "
        f"[green]${num_backers * pledge_amount:,.2f}[/]\n"
    )


def run_with_progress(campaign, num_backers: int, pledge_fn, pledge_amount: float) -> list:
    """
    Runs load simulation while showing a live progress bar.
    Spawns threads internally and tracks completion count.

    Returns list of thread results (True/False per pledge).
    """
    results = []
    results_lock = threading.Lock()
    completed = [0]  # mutable counter for threads to increment

    def tracked_pledge(backer_id, amount):
        result = pledge_fn(campaign, backer_id, amount)
        with results_lock:
            results.append(result)
            completed[0] += 1

    threads = [
        threading.Thread(
            target=tracked_pledge,
            args=(f"backer_{i:04d}", pledge_amount),
            daemon=True,
        )
        for i in range(num_backers)
    ]

    with Progress(
        TextColumn("[bold cyan]  Pledges[/]"),
        BarColumn(bar_width=40, style="green", complete_style="bright_green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TextColumn("[green]{task.completed}[/]/[white]{task.total}[/] backers"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("pledging", total=num_backers)

        for t in threads:
            t.start()

        # Poll until all threads complete, updating the bar
        while completed[0] < num_backers:
            progress.update(task, completed=completed[0])
            time.sleep(0.01)
        progress.update(task, completed=num_backers)

    for t in threads:
        t.join()

    return results


def print_progress_bar(campaign) -> None:
    """Print a single progress snapshot panel."""
    pct = min((campaign.total_pledged / campaign.goal_amount * 100), 100) if campaign.goal_amount else 0
    filled  = int(pct / 5)   # 20-block bar
    empty   = 20 - filled
    bar     = "[green]" + "█" * filled + "[/][dim]" + "░" * empty + "[/]"

    console.print(
        f"\n[bold]Live Progress:[/] {bar} "
        f"[green]${campaign.total_pledged:,.2f}[/] / "
        f"[white]${campaign.goal_amount:,.2f}[/]  "
        f"[cyan]{pct:.1f}%[/]  "
        f"({campaign.backer_count} backers)\n"
    )


def print_race_condition_report(campaign, true_total: float, true_count: int) -> None:
    """Print the final race condition analysis as a rich table."""
    lost    = true_total - campaign.total_pledged
    loss_pct = (lost / true_total * 100) if true_total else 0

    # ── Verdict colours ──
    true_ok     = true_total >= campaign.goal_amount
    observed_ok = campaign.total_pledged >= campaign.goal_amount
    true_col     = "green"  if true_ok     else "red"
    observed_col = "green"  if observed_ok else "red"
    mismatch     = true_ok != observed_ok

    # ── Totals table ──
    table = Table(box=box.ROUNDED, border_style="bright_black", show_header=True,
                  header_style="bold white")
    table.add_column("Metric",           style="cyan",  min_width=28)
    table.add_column("Value",            style="white", justify="right", min_width=18)

    table.add_row("Real pledges (log)",      f"[green]${true_total:>12,.2f}[/]")
    table.add_row("Observed (counter)",      f"[red]${campaign.total_pledged:>12,.2f}[/]")
    table.add_row("Lost to race conditions", f"[red]${lost:>12,.2f}[/]")
    table.add_row("Loss percentage",         f"[red]{loss_pct:.2f}%[/]")
    table.add_section()
    table.add_row("Real backers",            f"{true_count}")
    table.add_row("Observed backer count",   f"{campaign.backer_count}")
    table.add_section()
    table.add_row("Goal amount",             f"${campaign.goal_amount:>12,.2f}")
    table.add_row("True verdict",            f"[{true_col}]{'SUCCESSFUL' if true_ok else 'FAILED'}[/]")
    table.add_row("Observed verdict",        f"[{observed_col}]{campaign.status.upper()}[/]")

    console.print(Panel(table, title="[bold white] RACE CONDITION ANALYSIS REPORT [/]",
                        border_style="red" if mismatch else "green", padding=(1, 2)))

    # ── Warning banner ──
    if mismatch:
        console.print(Panel(
            f"[bold red]⚠  {loss_pct:.0f}% of pledges were silently lost!\n[/]"
            f"[white]Campaign declared [red]FAILED[/] but real total MET the goal.\n"
            f"{true_count} backers were betrayed by the read→add→write race.[/]",
            border_style="red", padding=(0, 2)
        ))
    else:
        console.print("[green]✓ No critical mismatch detected this run.[/]")
