from thin_orchestrator.engine import Orchestrator, Store, Task, TransientError
from thin_orchestrator.experiment import run


def t(id="1", **kw):
    return Task(id, "onboard_column", {"column": "age", "dtype": "int", **kw})


def test_success():
    s = Store(); r = Orchestrator(s).run(t())
    assert r.status == "completed"
    assert s.registry["1"]["generated"] == "age:int"


def test_invalid_input_never_committed():
    s = Store(); r = Orchestrator(s).run(t(column="bad name"))
    assert r.status == "rejected" and not s.registry


def test_deduplication():
    s = Store(); engine = Orchestrator(s)
    assert engine.run(t()).status == "completed"
    assert engine.run(t()).status == "duplicate"
    assert len(s.registry) == 1


def test_retry_transient():
    state = {"calls": 0}
    def inject(task, step, attempt):
        if step == "populate" and attempt == 1:
            state["calls"] += 1
            raise TransientError("test timeout")
    r = Orchestrator(injector=inject).run(t())
    assert r.status == "completed" and state["calls"] == 1
    assert r.attempts["1:populate"] == 2


def test_retry_exhaustion_atomic():
    s = Store()
    def inject(task, step, attempt):
        if step == "populate":
            raise TransientError("unavailable")
    r = Orchestrator(s, max_retries=2, injector=inject).run(t())
    assert r.status == "failed" and not s.registry
    assert r.attempts["1:populate"] == 3


def test_unsupported_workflow():
    r = Orchestrator().run(Task("1", "arbitrary", {}))
    assert r.status == "rejected"


def test_migration_workflow():
    r = Orchestrator().run(Task("1", "migrate_column", {"column":"price", "dtype":"float"}))
    assert r.status == "completed" and len(r.trace) == 4


def test_seeded_reproducibility():
    assert run(n=40, seed=42) == run(n=40, seed=42)


def test_experiment_completes():
    r = run(n=100, seed=42, failure_rate=.15)
    assert sum(r["status_counts"].values()) == 100
    assert r["registry_entries"] == r["status_counts"].get("completed", 0)
