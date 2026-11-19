# WorkArena-Abstract

The 33 WorkArena L1 tasks, with **abstracted prompts**: shorter, less specific goals of the kind an office worker would actually type. Each episode reports two scores:

- **Strict success** is WorkArena's own validator, unchanged.
- **Abstracted success** is a relaxed, per-category check: did the agent achieve what the abstracted prompt asked for?

The benchmark uses the same (task, seed) pairs as BrowserGym's `workarena_l1` (meta-seed 42, 10 seeds per task, 330 episodes), so original and abstracted runs can be compared episode by episode.

## Install

```bash
pip install -e workarena_abstract --no-deps   # deps (browsergym-workarena, agentlab) are already installed
```

Importing `workarena_abstract` registers the gym ids `browsergym/workarena_abstract.<task>`, for example `workarena_abstract.create-incident`.

## Use with AgentLab

```python
from agentlab.agents.generic_agent import AGENT_4o_MINI
from agentlab.experiments.study import Study
from workarena_abstract.benchmark import make_benchmark

for variant in ["original", "abstracted"]:
    Study([AGENT_4o_MINI], make_benchmark(variant, n_repeats=10)).run(n_jobs=4, parallel_backend="ray")
```

`scripts/run_baseline.py` does the same and also aggregates results:

```bash
python scripts/run_baseline.py --n-repeats 1 --backend sequential --n-jobs 1
python scripts/run_baseline.py --summarize <study_dir>
```

AgentLab only imports task packages it knows by name, so the abstracted benchmark uses a small `EnvArgs` subclass (`agentlab_env_args.py`). It registers the tasks in every worker, which means AgentLab itself does not need to be patched.

## What the agent sees and what is recorded

- **Goal:** the abstracted prompt replaces the WorkArena goal.
- **Setup info** (step 0 `task_info`):
  - `original_goal` and `abstracted_goal`
  - `removed_info`: a list of `{info, recoverable}`
  - `category` and `abstraction_level` (always 1)
- **Validation info** (each step's `task_info`):
  - `strict_success` and `abstracted_success`
  - `*_done` and `*_message` for each of the two checks
  - `reward_mode`
- **Reward:** follows `reward_mode`. The default is `"abstracted"`; pass `task_kwargs={"reward_mode": "strict"}` to switch. Because both metrics are always recorded, one run gives both.

## Abstraction rules (level 1)

Removed information is tagged **R** (recoverable: the agent could find it in the environment) or **U** (unrecoverable: only the user knows it).

| Category | Example abstracted prompt | Removed | Abstracted success |
|---|---|---|---|
| form (5) | `Log an incident for Don Goodliffe: "Customer didn't receive eFax"` | Values of the non-key fields (U, except fields derivable from the model, R). Field names (R). | A record is created whose key fields match. Other fields are ignored, as is the guard against "protected field changed". |
| list-filter (6) | `Show me only the incidents with Hardware and no assigned to.` | Column names for non-empty values (R). Filter operators (R). | The agent's filter selects exactly the same set of records as the target filter. |
| list-sort (6) | `Sort the incidents by Number, then by Assignment group.` | Sort directions (U). | Same fields in the same order; directions are ignored. |
| knowledge (1) | `What is the designated phone number to reach the CEO?` | That the answer is in the knowledge base (R). Answer format sentence (U). | Same as strict: WorkArena already accepts many answer formats. |
| menu (1) | `Take me to All Assets.` | Application name and menu path (R). The application is kept only when the module name is ambiguous. | The agent reaches any module with that name. |
| impersonation (1) | `Impersonate Beth.` | Last name (R if the first name is unique, otherwise ambiguous). | The impersonated user has that first name. |
| service catalog (9) | `Please order 1 iPad mini for me.` | Configuration options (U). Catalog location (R). | One requested item, correct item, correct quantity; configuration is ignored. |
| dashboard (4) | `How many Microsoft are in the Computers by Manufacturer chart?` / `What has the highest number in the chart?` | Answer unit (count or percent) or answer format (U). | Value questions accept the count or the percent. Min/max questions need only the correct label. |

Key fields kept in form prompts:

| Table | Key fields |
|---|---|
| incident | caller and short description |
| problem | short description |
| user | first and last name |
| hardware asset | model and serial number |
| change request | the first non-empty field among short description, description, justification, and so on |

Every abstracted criterion is a relaxation of the strict one, so strict success implies abstracted success. The abstracted validator only runs when the strict one fails. If it raises an error, the episode records `abstracted_error` in its info instead of crashing.

Code: the templates are in `templates.py` and the validators in `validation.py`.

## Layout

```
src/workarena_abstract/
  templates.py          rule-based goal rewriting (pure functions)
  validation.py         abstracted success checks
  tasks.py              AbstractedTaskMixin + one subclass per WorkArena L1 task
  benchmark.py          make_benchmark("abstracted" | "original"), task metadata
  agentlab_env_args.py  self-registering EnvArgs for AgentLab workers
scripts/
  export_goals.py       CSV of original vs abstracted goal for every (task, seed)
  run_baseline.py       GenericAgent on both variants + summary
tests/
  test_templates.py     offline: every WorkArena config, registration, seed pairing
  test_instance.py      live instance: cheat() solvability, relaxation sanity
```

## Tests

```bash
pytest workarena_abstract/tests/test_templates.py                                   # offline
WORKARENA_ABSTRACT_INSTANCE_TESTS=1 pytest workarena_abstract/tests/test_instance.py # needs ServiceNow
```

## Known limitations

- **Filter tasks:** abstracted success compares record sets at validation time. Degenerate filters (for example, a target that selects no records) can be matched by an unrelated filter that also selects nothing.
- **Form tasks:** fields not named in the prompt must still be valid for the form to submit. Abstracted success does not check them.
- **Prompt wording:** the wording is deterministic and template-based. Review `scripts/export_goals.py` output before running large studies.
