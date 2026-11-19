"""
Export original vs abstracted goals for every (task, seed) of the benchmark, for manual review.

Needs a ServiceNow instance (some goals are built from instance data), but does not create users
or records: goals are generated with `setup(page, do_start=False)`.

Rows are appended to the CSV as they are produced; re-running the script skips (task, seed)
pairs already in the file.

    python workarena_abstract/scripts/export_goals.py --out goals.csv [--n-repeats 10]
"""

import argparse
import csv
import json
import logging
import os

from browsergym.workarena.instance import SNowInstance
from playwright.sync_api import sync_playwright

from workarena_abstract import ABSTRACT_TASKS_BY_ID
from workarena_abstract.benchmark import make_benchmark

COLUMNS = [
    "task_name",
    "original_task",
    "seed",
    "category",
    "original_goal",
    "abstracted_goal",
    "removed_info",
    "n_removed_recoverable",
    "n_removed_unrecoverable",
    "error",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="workarena_abstract_goals.csv")
    parser.add_argument("--n-repeats", type=int, default=10)
    args = parser.parse_args()

    bench = make_benchmark("abstracted", n_repeats=args.n_repeats)

    done = set()
    if os.path.exists(args.out):
        with open(args.out, newline="", encoding="utf-8") as f:
            done = {(r["task_name"], int(r["seed"])) for r in csv.DictReader(f) if not r["error"]}
    todo = [e for e in bench.env_args_list if (e.task_name, e.task_seed) not in done]
    print(f"{len(done)} rows already exported, {len(todo)} to go", flush=True)

    instance = SNowInstance()  # one instance for all tasks (avoids re-fetching the instance pool)
    write_header = not os.path.exists(args.out)
    with open(args.out, "a", newline="", encoding="utf-8") as f, sync_playwright() as p:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if write_header:
            writer.writeheader()
        browser = p.chromium.launch(headless=True)
        for i, env_args in enumerate(todo, 1):
            task_cls = ABSTRACT_TASKS_BY_ID[env_args.task_name]
            row = {
                "task_name": env_args.task_name,
                "original_task": task_cls.original_task_cls.get_task_id(),
                "seed": env_args.task_seed,
                "error": "",
            }
            context = browser.new_context()
            page = context.new_page()
            try:
                task = task_cls(seed=env_args.task_seed, instance=instance)
                # In a real episode, setup() first creates a temporary user, which draws one number
                # from the task's RNG (browsergym/workarena/api/user.py: random.randint(1000, 9999))
                # before the task config is sampled. Reproduce that draw so the exported goals are
                # the ones the agent actually gets for this seed.
                task.random.randint(1000, 9999)
                goal, info = task.setup(page=page, do_start=False)
                removed = info["removed_info"]
                row.update(
                    category=info["category"],
                    original_goal=info["original_goal"],
                    abstracted_goal=goal,
                    removed_info="; ".join(
                        f"{r['info']} ({'R' if r['recoverable'] else 'U'})" for r in removed
                    ),
                    n_removed_recoverable=sum(r["recoverable"] for r in removed),
                    n_removed_unrecoverable=sum(not r["recoverable"] for r in removed),
                )
            except Exception as e:
                logging.exception(f"Failed on {env_args.task_name} seed {env_args.task_seed}")
                row["error"] = f"{type(e).__name__}: {e}"
            finally:
                try:
                    context.close()
                except Exception:
                    pass
            writer.writerow(row)
            f.flush()
            print(f"[{i}/{len(todo)}] {row['task_name']} {row['seed']}: "
                  f"{row.get('abstracted_goal') or row['error']}", flush=True)
        browser.close()
    print(f"Done: {args.out}", flush=True)


if __name__ == "__main__":
    main()
