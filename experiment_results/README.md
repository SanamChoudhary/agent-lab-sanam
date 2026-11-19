# Experiment results

`workarena_abstract/scripts/run_baseline.py` saves every agent run here. Each run is called a study and gets its own folder.

```
experiment_results/
  <date>_<study name>/                   one study (one run of the script)
    <date>_<episode name>/               AgentLab's raw files for one episode
      step_N.pkl.gz                        everything about step N (compressed)
      summary_info.json                    outcome, number of steps, cost, errors
      exp_args.pkl, goal_object.pkl.gz, ...
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
