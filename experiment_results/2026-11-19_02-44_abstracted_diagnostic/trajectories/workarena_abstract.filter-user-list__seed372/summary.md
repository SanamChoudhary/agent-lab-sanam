# workarena_abstract.filter-user-list (seed 372)

- Category: list-filter
- Agent: GenericAgent-4omini-diag
- Steps: 15
- Strict success: 0.0
- Abstracted success: 0.0

## Goal given to the agent

````
Show me only the users with no default perspective and system and Finance and password needs reset set to false.
````

## Original WorkArena goal

````
Create a filter for the list to extract all entries where:
    - "Default perspective" is "" and 
    - "Updated by" is "system" and 
    - "Department" is "Finance" and 
    - "Password needs reset" is "false"
````

## Information removed from the prompt

- column for "system" is "Updated by" (recoverable)
- column for "Finance" is "Department" (recoverable)
- use the list filter with 'is' conditions (recoverable)

Raw AgentLab files: `C:\Users\sanam\OneDrive\Documents\AgentLab-3\experiment_results\2026-11-19_02-44_abstracted_diagnostic\2026-11-19_02-44-52_GenericAgent-4omini-diag_on_workarena_abstract.filter-user-list_372`
