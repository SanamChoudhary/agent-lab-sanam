# Web Agents and Underspecified Prompts on WorkArena

This research project studies how AI web agents perform when they are given vague, realistic instructions instead of highly detailed ones.

## What this research is about

**AI web agents** are programs that use a website the way a person would. They read the page, click buttons, fill in forms and send messages to complete a task. One common benchmark for testing them is **WorkArena**. It is a set of everyday office tasks in **ServiceNow**, a business software platform. The tasks include creating an incident report, filtering a list, ordering a laptop and reading a dashboard chart.

WorkArena's instructions are very detailed. For example, it lists every field name and the exact value to enter. Real office workers rarely write instructions like that. They type something short like *"Log an incident for System Administrator"* and expect the details to be worked out.

This project asks: **how well do web agents cope when the instructions are vague, the way real people write them?** The research has four steps:

1. **Rewrite the prompts.** Turn WorkArena's detailed task prompts into shorter, *abstracted* versions that sound like what a typical worker would actually type.
2. **Measure the drop.** Run a standard agent (AgentLab's GenericAgent) on the abstracted prompts and compare its success with the original prompts.
3. **Find out why it fails.** Read the agent's step-by-step reasoning and exactly what it saw on the page, to find recurring causes of failure.
4. **Try to fix it.** Design and test changes to the agent that help it succeed on vague prompts. The changes must work for web agents in general, not just for this one website.

### Key terms

| Term | Meaning |
|---|---|
| Original prompt | The task instruction exactly as WorkArena wrote it. |
| Abstracted prompt | Our shorter, less specific rewrite of the original. |
| Strict success | WorkArena's own check: every detail must match exactly. |
| Abstracted success | Our relaxed check: the agent did what the vague prompt reasonably asked. |
| Recoverable missing info | A detail left out of the prompt that the agent could still find on the website. |
| Unrecoverable missing info | A detail only the person asking knows. The agent can only guess or ask. |

## Repository structure

| Folder | What it is |
|---|---|
| `AgentLab/` | An open-source toolkit from ServiceNow for building and running web agents. We use it to run experiments and as the source of our baseline agent. |
| `BrowserGym/` | An open-source framework that connects an agent to a real web browser. It shows the agent the page, carries out its clicks and typing, and checks whether the task was completed. |
| `workarena_abstract/` | **Our own code.** It turns WorkArena's tasks into vague versions with relaxed success checks, configures the agents (including our improved agent), and saves each run's results in readable form. |
| `experiment_results/` | The results of our experiment runs. Each run has its own folder holding the agent's step-by-step reasoning and what it saw at every step, plus written reports that explain the results. |

`workarena_abstract_tasks.csv` lists every task with its original prompt next to its abstracted prompt.

## Acknowledgements

This research was carried out as part of the **Motorola Scholar Program**. Thank you to the program for supporting this work.

It builds on the open-source [WorkArena](https://github.com/ServiceNow/WorkArena), [BrowserGym](https://github.com/ServiceNow/BrowserGym) and [AgentLab](https://github.com/ServiceNow/AgentLab) projects from ServiceNow Research.
