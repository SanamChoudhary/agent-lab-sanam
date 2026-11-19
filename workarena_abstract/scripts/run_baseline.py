"""
Baseline: AgentLab GenericAgent on the original and abstracted WorkArena L1 prompts (paired seeds).

    # pilot: 33 abstracted episodes (1 seed per task)
    python workarena_abstract/scripts/run_baseline.py --variants abstracted --n-repeats 1

    # smoke test: a single episode, sequential
    python workarena_abstract/scripts/run_baseline.py --variants abstracted --n-repeats 1 \
        --task-glob "*create-incident*" --backend sequential --n-jobs 1

    # summary / readable trajectories of a finished study
    python workarena_abstract/scripts/run_baseline.py --summarize <study_dir>
    python workarena_abstract/scripts/run_baseline.py --export <study_dir>

Results go to AgentLab-3/experiment_results/<study>/ (override with --results-dir). After each run,
readable trajectories and per-step context are exported to <study>/trajectories/ (see
workarena_abstract/trajectories.py).

The agent defaults to AGENT_4o_MINI_DIAGNOSTIC (see workarena_abstract/agent_config.py). Use the
same --agent for the original and abstracted runs so they are comparable. Requires OPENAI_API_KEY.

Both success metrics are recorded per step in `task_info` (strict_success, abstracted_success).
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path

from agentlab.experiments.study import Study

from workarena_abstract.agent_config import AGENTS
from workarena_abstract.benchmark import make_benchmark
from workarena_abstract.trajectories import export_study

# AgentLab-3/experiment_results (this file is AgentLab-3/workarena_abstract/scripts/run_baseline.py)
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parents[2] / "experiment_results"


def summarize_study(study_dir):
    """Per-episode strict / abstracted success, read from the last validated step's task_info."""
    import pandas as pd
    from agentlab.experiments.loop import yield_all_exp_results
    from browsergym.workarena import TASK_CATEGORY_MAP

    from workarena_abstract import ABSTRACT_TASKS_BY_ID

    rows = []
    for res in yield_all_exp_results(Path(study_dir)):
        env_args = res.exp_args.env_args
        name = env_args.task_name
        abstracted = name in ABSTRACT_TASKS_BY_ID
        original = ABSTRACT_TASKS_BY_ID[name].original_task_cls.get_task_id() if abstracted else name
        # step 0 holds the setup info (goals); later steps hold validate() info
        task_info = next(
            (s.task_info for s in reversed(res.steps_info) if s.task_info and "strict_success" in s.task_info),
            {},
        )
        reward = res.summary_info.get("cum_reward")
        rows.append(
            {
                "task_name": name,
                "category": TASK_CATEGORY_MAP.get(original),
                "seed": env_args.task_seed,
                "variant": "abstracted" if abstracted else "original",
                # original tasks only have WorkArena's strict validator
                "strict_success": task_info.get("strict_success", reward),
                "abstracted_success": task_info.get("abstracted_success"),
                "n_steps": res.summary_info.get("n_steps"),
                "err_msg": res.summary_info.get("err_msg"),
            }
        )
    df = pd.DataFrame(rows)
    if len(df):
        # an episode that ended before any validation (e.g. the agent's reply could not be parsed)
        # is a failure on both metrics, not a missing value
        abst = df["variant"] == "abstracted"
        df.loc[abst, "abstracted_success"] = df.loc[abst, "abstracted_success"].fillna(0.0)
        df["strict_success"] = df["strict_success"].fillna(0.0)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-repeats", type=int, default=10)
    parser.add_argument("--variants", nargs="+", default=["original", "abstracted"])
    parser.add_argument("--agent", default="diagnostic", choices=sorted(AGENTS))
    parser.add_argument("--task-glob", default=None, help='only tasks matching, e.g. "*create-incident*"')
    parser.add_argument("--backend", default="ray", choices=["ray", "joblib", "sequential"])
    parser.add_argument("--n-jobs", type=int, default=4)
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--summarize", type=str, default=None, help="study dir to summarize")
    parser.add_argument("--export", type=str, default=None, help="study dir to export trajectories for")
    args = parser.parse_args()

    if args.export:
        print(f"Trajectories written to {export_study(args.export)}")
        return

    if args.summarize:
        df = summarize_study(args.summarize)
        cols = ["strict_success", "abstracted_success"]
        print(df.groupby("variant")[cols].mean(), "\n")
        print(df.groupby(["variant", "category"])[cols].mean(), "\n")
        errors = df[df["err_msg"].notna() & (df["err_msg"] != "")]
        print(f"{len(df)} episodes, {len(errors)} with errors")
        out = Path(args.summarize) / "workarena_abstract_summary.csv"
        df.to_csv(out, index=False)
        print(f"Per-episode table: {out}")
        return

    agent = AGENTS[args.agent]
    for variant in args.variants:
        benchmark = make_benchmark(variant, n_repeats=args.n_repeats)
        if args.task_glob:
            benchmark = benchmark.subset_from_glob("task_name", args.task_glob)
        if args.agent == "intervention" and variant == "abstracted":
            # the agent may ask questions; the task's simulated user answers from the original goal
            for env_args in benchmark.env_args_list:
                env_args.task_kwargs = {**(env_args.task_kwargs or {}), "simulated_user": True}
        study = Study([agent], benchmark, logging_level_stdout=logging.WARNING)
        # Short study folder name: AgentLab's default (agent + benchmark + filter) plus the
        # per-episode folders exceeds Windows' 260-character path limit under OneDrive.
        tag = f"_{args.task_glob.strip('*')}" if args.task_glob else ""
        study.dir = Path(args.results_dir) / (
            f"{datetime.now():%Y-%m-%d_%H-%M}_{variant}_{args.agent}{tag}"
        )
        study.run(
            n_jobs=args.n_jobs,
            parallel_backend=args.backend,
            strict_reproducibility=False,
            n_relaunch=3,
            exp_root=Path(args.results_dir),
        )
        print(f"{variant}: results in {study.dir}")
        print(f"{variant}: trajectories in {export_study(study.dir)}")


if __name__ == "__main__":
    main()
