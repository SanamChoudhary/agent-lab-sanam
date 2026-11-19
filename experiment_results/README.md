# Experiment results

`workarena_abstract/scripts/run_baseline.py` saves every agent run here. Each run is called a study and gets its own folder.

## Results: abstracted-prompt pilot

Study folder: [`2026-11-19_02-44_abstracted_diagnostic/`](2026-11-19_02-44_abstracted_diagnostic/)

### Setup

| | |
|---|---|
| Benchmark | WorkArena-Abstract: the 33 WorkArena L1 tasks with abstracted prompts (abstraction level 1) |
| Episodes | 33, one per task, using the first seed of each task's `workarena_l1` seeds (meta-seed 42) |
| Agent | AgentLab GenericAgent, `GenericAgent-4omini-diag` |
| Model | `gpt-4o-mini-2024-07-18` |
| Agent flags | AgentLab's standard `FLAGS_GPT_4o`, plus `use_plan`, `use_memory`, `use_think_history` and `use_past_error_logs` (see `workarena_abstract/src/workarena_abstract/agent_config.py`) |
| Observation | Accessibility tree; no screenshot is given to the model |
| Max steps | 15 per episode |
| Success measure | Abstracted success: the agent did what the abstracted prompt asked (see `workarena_abstract/README.md`) |
| Run | 2026-11-19, 02:44–03:27 (43 min), 8 episodes in parallel |

### Overall

| | Abstracted success |
|---|---|
| **All 33 tasks** | **8 / 33 (24.2%)** |

### By category

| Category | Episodes | Abstracted success |
|---|---|---|
| Service catalog | 9 | 4 (44%) |
| Dashboard | 4 | 2 (50%) |
| Menu (navigation + impersonation) | 2 | 1 (50%) |
| Form | 5 | 1 (20%) |
| List filter | 6 | 0 (0%) |
| List sort | 6 | 0 (0%) |
| Knowledge base | 1 | 0 (0%) |

### By task

| Task | Seed | Prompt given to the agent | Success | Steps |
|---|---|---|---|---|
| all-menu | 769 | Take me to Software Models. | ✅ | 12 |
| impersonation | 343 | Impersonate Derek. | ❌ | 0* |
| create-change-request | 106 | Raise a change request: "Oracle FLX (Java App Dependency)" | ✅ | 6 |
| create-hardware-asset | 700 | Add a new Apple MacBook Pro 17" to our hardware assets, serial number SN-714f…e760. | ❌ | 15 |
| create-incident | 71 | Log an incident for System Administrator: "ATF : Test1" | ❌ | 15 |
| create-problem | 20 | Open a problem record: "Request for a Blackberry" | ❌ | 15 |
| create-user | 614 | Add Mckenzie-William Hubbard-Smith as a new user. | ❌ | 15 |
| filter-asset-list | 466 | Show me only the assets with no serial number and Gaston Cieloszyk and Shared and Consumed and Consumable. | ❌ | 15 |
| filter-change-request-list | 214 | Show me only the change requests with Normal and Network and no assigned to. | ❌ | 15 |
| filter-hardware-list | 330 | Show me only the hardware with no company and Pending transfer and no assigned to. | ❌ | 15 |
| filter-incident-list | 458 | Show me only the incidents with Software and Fred Luddy. | ❌ | 15 |
| filter-service-catalog-item-list | 87 | Show me only the catalog items with Report Outage and Report an outage of a service or an application.. | ❌ | 15 |
| filter-user-list | 372 | Show me only the users with no default perspective and system and Finance and password needs reset set to false. | ❌ | 15 |
| sort-asset-list | 99 | Sort the assets by Model category, then by Display name, then by Quantity. | ❌ | 15 |
| sort-change-request-list | 871 | Sort the change requests by Phase, then by Planned start date, then by Justification. | ❌ | 15 |
| sort-hardware-list | 663 | Sort the hardware by Purchased, then by Quantity. | ❌ | 15 |
| sort-incident-list | 130 | Sort the incidents by Description, then by Assigned to. | ❌ | 15 |
| sort-service-catalog-item-list | 661 | Sort the catalog items by Name, then by Fulfillment automation level, then by Class. | ❌ | 15 |
| sort-user-list | 308 | Sort the users by Country code, then by Manager. | ❌ | 15 |
| knowledge-base-search | 121 | Which firm is providing legal consultations to the company? | ❌ | 15 |
| order-apple-mac-book-pro15 | 276 | Please order 9 Apple MacBook Pro 15 for me. | ❌ | 15 |
| order-apple-watch | 955 | Please order 3 Apple Watch for me. | ✅ | 5 |
| order-developer-laptop | 491 | Please order 3 Developer Laptop (Mac) for me. | ✅ | 5 |
| order-development-laptop-p-c | 160 | Please order 1 Development Laptop (PC) for me. | ❌ | 15 |
| order-ipad-mini | 413 | Please order 3 iPad mini for me. | ❌ | 15 |
| order-ipad-pro | 805 | Please order 4 iPad pro for me. | ✅ | 6 |
| order-loaner-laptop | 459 | Please order 9 Loaner Laptop for me. | ✅ | 5 |
| order-sales-laptop | 385 | Please order 6 Sales Laptop for me. | ❌ | 15 |
| order-standard-laptop | 191 | Please order 8 Standard Laptop for me. | ❌ | 15 |
| multi-chart-min-max-retrieval | 435 | What has the highest number in the Open series of the Incidents per week chart? | ❌ | 15 |
| multi-chart-value-retrieval | 102 | How many Survey : Basic Platform Based Test are in the Total Metrics by Metric Type chart? | ❌ | 15 |
| single-chart-min-max-retrieval | 270 | What has the lowest number in the chart? | ✅ | 1 |
| single-chart-value-retrieval | 860 | How many 4 - Low are in the chart? | ✅ | 3 |

\* Ended at step 0: the model's reply was missing a closed `<action>` tag on all 4 retries, so no action could be read. It counts as a failure.

### Observations

- **Service catalog was the strongest category** (4 of 9). The successful orders were completed in 5–6 steps.
- **List filter, list sort and knowledge base failed on every episode (13 of 13).** All of these ran to the 15-step limit.
- **Successful episodes were short** (1–12 steps). **Most failures (24 of 25) used all 15 steps**: the agent kept acting without completing the task, rather than stopping with a wrong answer.
- **Example failure, create-incident (seed 71).**
  - **What the agent did:** it filled in the description but never set the mandatory *Caller* field to "System Administrator". The submission was rejected, and the agent then waited (`noop`) for the remaining steps without noticing the error.
  - **Where to look:** `trajectories/workarena_abstract.create-incident__seed71/trajectory.md`.
## Folder layout

```
experiment_results/
  <date>_<study name>/                   one study (one run of the script)
    <date>_<episode name>/               AgentLab's raw files for one episode
      step_N.pkl.gz                        everything about step N (compressed)
      summary_info.json                    outcome, number of steps, cost, errors
      exp_args.pkl, goal_object.pkl.gz, ...
    workarena_abstract_summary.csv       per-episode success
    trajectories/                        readable export, made after the run
      index.csv                          one row per episode: task, success, steps, folder
      <task>__seed<N>/
        summary.md                       goal given, original goal, removed info, outcome
        trajectory.md                    every step: thinking, plan, memory, action, error, URL
        trajectory.json                  the same as trajectory.md, for analysis scripts
        context/
          step_00_prompt.md              exact context (system + user prompt) sent at step 0
          step_00_response.md            the model's full raw reply at step 0
          ...
```

- **Trajectory:** the agent's reasoning step by step. Read `trajectory.md`, or load `trajectory.json` in a script.
- **Context:** exactly what the model saw at each step, in `context/step_XX_prompt.md`. This includes:
  - the goal
  - the page as an accessibility tree
  - the history of earlier actions, thoughts and errors
  - the instructions
- **Interactive viewer:** AgentXray, started with `agentlab-xray`, reads the raw folders.
- **Re-export a study:** `python workarena_abstract/scripts/run_baseline.py --export experiment_results/<study>`
- **Summarize a study:** `python workarena_abstract/scripts/run_baseline.py --summarize experiment_results/<study>`
