"""Deterministic router + isolated workflow specialists; no LLM calls."""
from dataclasses import dataclass, field
from typing import Any, Callable


class WorkflowError(Exception):
    pass


class TransientError(WorkflowError):
    pass


class ValidationError(WorkflowError):
    pass


@dataclass
class Task:
    task_id: str
    kind: str
    payload: dict[str, Any]


@dataclass
class Result:
    task_id: str
    status: str
    attempts: dict[str, int] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Store:
    """In-memory stand-in for a registry; idempotency by unique task id."""
    def __init__(self):
        self.completed: dict[str, Result] = {}
        self.registry: dict[str, dict[str, Any]] = {}


STEPS = {
    "onboard_column": ("schema", "populate", "validate"),
    "migrate_column": ("schema", "validate", "populate", "validate"),
}


def schema(context: dict[str, Any]) -> None:
    name = context["payload"].get("column")
    dtype = context["payload"].get("dtype")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValidationError("column must be a valid identifier")
    if dtype not in {"int", "float", "str"}:
        raise ValidationError("dtype must be one of int, float, str")
    context["spec"] = {"column": name, "dtype": dtype}


def populate(context: dict[str, Any]) -> None:
    spec = context.get("spec")
    if not spec:
        raise ValidationError("schema must run before population")
    context["generated"] = f"{spec['column']}:{spec['dtype']}"


def validate(context: dict[str, Any]) -> None:
    if "spec" not in context:
        raise ValidationError("missing spec")
    if "generated" in context and context["generated"] != f"{context['spec']['column']}:{context['spec']['dtype']}":
        raise ValidationError("generated output does not match schema")


WORKERS: dict[str, Callable[[dict[str, Any]], None]] = {
    "schema": schema, "populate": populate, "validate": validate
}


class Orchestrator:
    """Only routing, step sequencing, retries, dedupe and atomic commit."""
    def __init__(self, store: Store | None = None, max_retries: int = 2, injector=None):
        self.store = store if store is not None else Store()
        self.max_retries = max_retries
        self.injector = injector

    def run(self, task: Task) -> Result:
        if task.task_id in self.store.completed:
            prior = self.store.completed[task.task_id]
            return Result(task.task_id, "duplicate", dict(prior.attempts), list(prior.trace), dict(prior.output))
        if task.kind not in STEPS:
            return Result(task.task_id, "rejected", error=f"unsupported workflow: {task.kind}")
        # No partial registry commits: stage changes until all steps succeed.
        context: dict[str, Any] = {"payload": dict(task.payload)}
        result = Result(task.task_id, "failed")
        for step_index, step in enumerate(STEPS[task.kind]):
            invocation = f"{step_index}:{step}"
            for attempt in range(1, self.max_retries + 2):
                result.attempts[invocation] = attempt
                try:
                    if self.injector:
                        self.injector(task, step, attempt)
                    WORKERS[step](context)
                    result.trace.append(f"{step}:ok:{attempt}")
                    break
                except TransientError as exc:
                    result.trace.append(f"{step}:transient:{attempt}")
                    if attempt > self.max_retries:
                        result.error = str(exc)
                        return result
                except ValidationError as exc:
                    result.trace.append(f"{step}:invalid:{attempt}")
                    result.status = "rejected"
                    result.error = str(exc)
                    return result
        spec = context["spec"]
        result.output = {"spec": spec, "generated": context["generated"]}
        result.status = "completed"
        self.store.registry[task.task_id] = dict(result.output)
        self.store.completed[task.task_id] = result
        return result
