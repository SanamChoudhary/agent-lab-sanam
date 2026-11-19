# workarena_abstract.filter-change-request-list (seed 214)

- Category: list-filter
- Agent: GenericAgent-4omini-diag
- Steps: 15
- Strict success: 0.0
- Abstracted success: 0.0

## Goal given to the agent

````
Show me only the change requests with Normal and Network and no assigned to.
````

## Original WorkArena goal

````
Create a filter for the list to extract all entries where:
    - "Type" is "Normal" and 
    - "Assignment group" is "Network" and 
    - "Assigned to" is ""
````

## Information removed from the prompt

- column for "Normal" is "Type" (recoverable)
- column for "Network" is "Assignment group" (recoverable)
- use the list filter with 'is' conditions (recoverable)

Raw AgentLab files: `C:\Users\sanam\OneDrive\Documents\AgentLab-3\experiment_results\2026-11-19_02-44_abstracted_diagnostic\2026-11-19_02-44-52_GenericAgent-4omini-diag_on_workarena_abstract.filter-change-request-list_214`
