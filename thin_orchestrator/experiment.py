"""Seeded, reproducible experiment with fault injection. No real AI agents or Meta systems."""
import argparse
import json
import random
from collections import Counter
from .engine import Orchestrator, Store, Task, TransientError


def run(n: int = 100, seed: int = 42, failure_rate: float = 0.15) -> dict:
    if n < 1 or not 0 <= failure_rate <= 1:
        raise ValueError("n must be positive and failure-rate in [0,1]")
    rng = random.Random(seed)
    injections: list[str] = []
    def inject(task, step, attempt):
        # No injected failure during input schema checks, and never turn a validation error into an outage.
        if step == "populate" and rng.random() < failure_rate:
            injections.append(task.task_id)
            raise TransientError("synthetic worker timeout")
    store = Store()
    engine = Orchestrator(store, max_retries=2, injector=inject)
    statuses = Counter()
    total_attempts = 0
    rejected = 0
    for i in range(n):
        task = Task(f"task-{i}", "onboard_column" if i % 2 == 0 else "migrate_column", {
            "column": f"field_{i}", "dtype": ("int", "float", "str")[i % 3]
        })
        result = engine.run(task)
        statuses[result.status] += 1
        total_attempts += sum(result.attempts.values())
    return {
        "environment": "local deterministic workers, synthetic faults (NOT Meta or real LLMs)",
        "seed": seed, "tasks": n, "synthetic_failure_rate": failure_rate,
        "status_counts": dict(statuses), "injected_timeouts": len(injections),
        "total_worker_attempts": total_attempts,
        "registry_entries": len(store.registry),
        "all_completed": statuses["completed"] == n,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--failure-rate", type=float, default=0.15)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    result = run(args.tasks, args.seed, args.failure_rate)
    content = json.dumps(result, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(content)
    print(content, end="")


if __name__ == "__main__":
    main()
