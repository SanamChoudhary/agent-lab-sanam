"""
WorkArena-Abstract: WorkArena L1 tasks with abstracted (underspecified) prompts.

Importing this package registers one gym environment per WorkArena L1 task, with ids
`browsergym/workarena_abstract.<task-name>` (e.g. `workarena_abstract.create-incident`).
"""

from browsergym.core.registration import register_task

from .tasks import (
    ABSTRACT_TASKS,
    ABSTRACT_TASKS_BY_ID,
    ORIGINAL_TO_ABSTRACT_ID,
    TASK_ID_PREFIX,
    AbstractedTaskMixin,
)

__version__ = "0.1.0"

for _task in ABSTRACT_TASKS:
    register_task(_task.get_task_id(), _task)

workarena_abstract_tasks = [t.get_task_id() for t in ABSTRACT_TASKS]


def make_benchmark(*args, **kwargs):
    """See `workarena_abstract.benchmark.make_benchmark` (lazy import of browsergym.experiments)."""
    from .benchmark import make_benchmark as _make

    return _make(*args, **kwargs)
