# Thin Orchestrator Lab

An independent, reproducible Python prototype inspired by Meta Engineering's October 19, 2026 article: [The Thin Orchestrator](https://engineering.fb.com/2026/10/19/ml-applications/thin-orchestrator-ai-agent-architecture/).

**Not affiliated with Meta. Not an implementation of Meta's internal code.** This first version uses deterministic specialist workers instead of LLM agents, to isolate and test the orchestration and reliability mechanisms without API costs or nondeterministic model behavior.

## Research question

Can a router that never makes domain decisions safely coordinate independent workflow specialists, enforce validation, retry transient errors, and avoid partial writes?

## System

- **Orchestrator:** validates workflow type, sequences steps, retries transient failures, rejects invalid inputs, deduplicates task IDs.
- **Specialists:** schema, population, validation. Each is independently testable.
- **Workflows:** column onboarding (schema → populate → validate), migration (schema → validate → populate → validate).
- **State:** in-memory registry, with commit only after successful completion. State is not durable across restarts.
- **Fault injection:** seeded synthetic timeouts during population, to test retry behavior.

## Windows 11 quickstart

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python -m pytest -v
python -m thin_orchestrator.experiment --tasks 100 --seed 42 --failure-rate 0.15 --output results/local_seed42.json
```

For PowerShell activation policy issues, use `.\.venv\Scripts\python.exe` instead of `python`.

## Metrics and validity

The experiment produces a JSON report with workload size, completion counts, number of injected failures and worker attempts. `results/local_seed42.json` is a locally executed reference run; reproduce and compare it on your own machine before making public claims.

**Do not confuse injected failure rate (per population attempt) with task failure rate.** Retries can absorb transient failures.

## Limitations

This prototype does not make LLM calls, use Meta production systems, or test end-to-end ML data onboarding. Task state is in-memory and therefore not crash durable. The workload contains only valid inputs. It measures reliability of orchestration logic under synthetic faults, not LLM accuracy, hallucination rate, token usage, or a demonstrated advantage over monolithic AI agents. Those require a controlled comparison that we have not run.

## Next experiments

1. Add a persistent SQLite task registry and recovery after process termination.
2. Add non-retryable vs retryable worker errors, exponential backoff and timeout budgets.
3. Build a monolithic baseline, using identical inputs, then compare correctness, recovery, latency and cost.
4. Optionally plug real LLM-backed specialists behind the worker interface; capture traceable evaluation metrics.

## Citation

Meta Engineering, *The Thin Orchestrator: How We Made Our AI Agents More Reliable by Giving the Router Less to Do*, October 19, 2026.

## Reference experiment, seed 42

On the locally executed 100-task experiment with 15% synthetic timeout probability per `populate` attempt:

- 99 tasks completed and committed, 1 exhausted its retry allowance.
- 17 transient timeouts were injected across attempts.
- 365 worker attempts were counted, including retries.
- The failed task did not produce a partial registry entry.

These observations are specific to a seeded simulation. They do not establish model quality or real-world agent performance. A useful next question is how changing the retry budget affects completion rate, total worker calls, and tail latency.
