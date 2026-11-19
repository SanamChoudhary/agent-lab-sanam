"""
Benchmark definitions for AgentLab / BrowserGym experiments.

`make_benchmark("abstracted")` and `make_benchmark("original")` contain exactly the same
(task, seed) pairs as BrowserGym's `workarena_l1` benchmark, so results can be paired episode by
episode. Pass the returned object directly to `agentlab.experiments.study.Study`.
"""

from dataclasses import asdict
from typing import Literal

import pandas as pd
from browsergym.experiments.benchmark.base import Benchmark
from browsergym.experiments.benchmark.configs import DEFAULT_HIGHLEVEL_ACTION_SET_ARGS
from browsergym.experiments.benchmark.utils import make_env_args_list_from_workarena_curriculum
from browsergym.workarena import TASK_CATEGORY_MAP

from .tasks import ABSTRACT_TASKS, ORIGINAL_TO_ABSTRACT_ID

# What each category's abstracted prompt leaves out (R = recoverable, U = unrecoverable)
CATEGORY_REMOVED_INFO = {
    "form": "non-key field values (U); field names (R)",
    "list-filter": "column names (R); filter operators (R)",
    "list-sort": "sort directions (U)",
    "knowledge": "knowledge base as source (R); answer format (U)",
    "menu": "application name and menu path (R) / user last name (R or ambiguous)",
    "service catalog": "item configuration (U); catalog location (R)",
    "dashboard": "answer unit or format (U)",
}


def _to_agentlab_env_args(env_args_list):
    """Use the self-registering EnvArgs subclass when AgentLab is installed (see agentlab_env_args)."""
    try:
        from .agentlab_env_args import WorkArenaAbstractEnvArgs
    except ImportError:
        return env_args_list
    return [WorkArenaAbstractEnvArgs(**asdict(e)) for e in env_args_list]


def task_metadata() -> pd.DataFrame:
    rows = []
    for cls in ABSTRACT_TASKS:
        original = cls.original_task_cls.get_task_id()
        category = TASK_CATEGORY_MAP[original]
        for variant, name in (("original", original), ("abstracted", cls.get_task_id())):
            rows.append(
                {
                    "task_name": name,
                    "variant": variant,
                    "original_task": original,
                    "level": "l1",
                    "category": category,
                    "removed_info": CATEGORY_REMOVED_INFO[category] if variant == "abstracted" else "",
                }
            )
    return pd.DataFrame(rows)


def make_benchmark(
    variant: Literal["abstracted", "original"] = "abstracted",
    n_repeats: int = 10,
    max_steps: int = 15,
    meta_seed: int = 42,
) -> Benchmark:
    if variant not in ("abstracted", "original"):
        raise ValueError(f"Unknown variant {variant!r}")

    env_args_list = make_env_args_list_from_workarena_curriculum(
        level="l1",
        task_category_filter=None,
        meta_seed=meta_seed,
        max_steps=max_steps,
        curriculum_type="agent",
        seeds_l1=n_repeats,
    )
    if variant == "abstracted":
        for env_args in env_args_list:
            env_args.task_name = ORIGINAL_TO_ABSTRACT_ID[env_args.task_name]
        env_args_list = _to_agentlab_env_args(env_args_list)

    metadata = task_metadata()
    metadata = metadata[metadata["variant"] == variant].reset_index(drop=True)

    return Benchmark(
        name=f"workarena_l1_{variant}",
        high_level_action_set_args=DEFAULT_HIGHLEVEL_ACTION_SET_ARGS["workarena"],
        is_multi_tab=False,
        supports_parallel_seeds=True,
        backends=["workarena"],
        env_args_list=env_args_list,
        task_metadata=metadata,
    )
