"""
Baseline: AgentLab GenericAgent on the original and abstracted WorkArena L1 prompts (paired seeds).

    python workarena_abstract/scripts/run_baseline.py --n-repeats 1 --backend sequential --n-jobs 1

Both success metrics are recorded per step in `task_info` (strict_success, abstracted_success);
aggregate them with `--summarize <study_dir>`.
"""

import argparse
import logging
from pathlib import Path

from agentlab.agents.generic_agent import AGENT_4o_MINI
from agentlab.experiments.study import Study

from workarena_abstract.benchmark import make_benchmark


def summarize_study(study_dir):
    """Per-episode strict / abstracted success, read from the last validated step's task_info."""
    import pandas as pd
    from agentlab.experiments.loop import yield_all_exp_results

    rows = []
    for res in yield_all_exp_results(Path(study_dir)):
        env_args = res.exp_args.env_args
        # step 0 holds the setup info (goals); later steps hold validate() info
        task_info = next(
            (s.task_info for s in reversed(res.steps_info) if s.task_info and "strict_success" in s.task_info),
            {},
        )
        reward = res.summary_info.get("cum_reward")
        rows.append(
            {
                "task_name": env_args.task_name,
                "seed": env_args.task_seed,
                "variant": "abstracted" if env_args.task_name.startswith("workarena_abstract") else "original",
                # original tasks only have WorkArena's strict validator
                "strict_success": task_info.get("strict_success", reward),
                "abstracted_success": task_info.get("abstracted_success"),
                "n_steps": res.summary_info.get("n_steps"),
                "err_msg": res.summary_info.get("err_msg"),
            }
        )
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-repeats", type=int, default=10)
    parser.add_argument("--variants", nargs="+", default=["original", "abstracted"])
    parser.add_argument("--backend", default="ray", choices=["ray", "joblib", "sequential"])
    parser.add_argument("--n-jobs", type=int, default=4)
    parser.add_argument("--summarize", type=str, default=None, help="study dir to summarize")
    args = parser.parse_args()

    if args.summarize:
        df = summarize_study(args.summarize)
        print(df.groupby("variant")[["strict_success", "abstracted_success"]].mean())
        return

    agent = AGENT_4o_MINI  # swap for the agent config of your choice
    for variant in args.variants:
        benchmark = make_benchmark(variant, n_repeats=args.n_repeats)
        study = Study([agent], benchmark, logging_level_stdout=logging.WARNING)
        study.run(
            n_jobs=args.n_jobs,
            parallel_backend=args.backend,
            strict_reproducibility=False,
            n_relaunch=3,
        )
        print(f"{variant}: results in {study.dir}")


if __name__ == "__main__":
    main()
