# Error analysis: abstracted-prompt pilot

**Study:** `2026-11-19_02-44_abstracted_diagnostic`, with GPT-4o-mini running as AgentLab's GenericAgent. It has 33 episodes, one per WorkArena L1 task, and every prompt is the abstracted version. **Result:** 8 successes and 25 failures.

**How this was done:**
- Every episode's `trajectory.md` was read step by step: the agent's thinking, plan, memory, action and errors.
- It was cross-referenced with `context/step_XX_prompt.md`, the exact page content (AXTree) and history the model saw at that step.
- For each failure, we found the step where it went wrong and checked whether the information the agent needed was on the page.
- All file paths below are relative to `2026-11-19_02-44_abstracted_diagnostic/trajectories/`.

---

## 1. Summary

**What the agent does:**
- **It gets stuck, not wrong.** 24 of 25 failures used all 15 steps. The agent almost never gives a wrong answer. It stops making progress and repeats itself until it runs out of steps.
- **It gets lost in the interface.** Most failures happen before the missing information matters:
  - it misreads which page it is on
  - it uses the wrong control
  - it can't find what it needs on the page
- **It doesn't finish.** Several times it had done the work but did not submit.

**What the context does:**
- **The vague prompt played a role in 9 of 25 failures**, all in forms and list filters. That is where the agent has to work out which field a value belongs to. In none of them was the vague prompt the only problem.
- **Some failures come from the context, not the prompt.**
  - In 4 episodes the page content disappeared from what the agent saw.
  - In 1 episode the chart labels the agent needed were missing from the page content altogether.

### Error types at a glance

| # | Error type | Simple explanation | Failures affected |
|---|---|---|---|
| E1 | Stuck in a loop | Repeats a wait or the same click instead of trying something new | 22 of 25 |
| E2 | Wrong idea of where it is | Thinks it is on a page, or in a state, that it isn't | 7 |
| E3 | Wrong control | Uses a different button or box than the one that does the job | 11 |
| E4 | Vague value mapped to the wrong field | Can't tell which field or column a value in the prompt belongs to | 9 (all forms and filters) |
| E5 | Doesn't finish, or over-does it | Has done the work but invents more steps instead of submitting | 3 |
| E6 | Needed information not visible | The page content the agent receives is missing what it needs | 5 (plus hidden sort columns) |
| E7 | Output format errors | Writes an action the system can't read | 4 (1 fatal) |

Most failures have more than one error type, so the counts add up to more than 25.

### Results by task type

| Task type | Success | Main errors | Did the vague prompt contribute? |
|---|---|---|---|
| Service catalog (9) | 4 / 9 | E2 (all 5 failures), E1 | No |
| Dashboard (4) | 2 / 4 | E6, E3, E1 | No |
| Menu (2) | 1 / 2 | E7 (fatal) | No |
| Form (5) | 1 / 5 | E4, E5, E6, E1 | Partly, in 3 of 4 failures |
| List filter (6) | 0 / 6 | E3 (all 6), E4, E1 | Yes or partly, in 6 of 6 |
| List sort (6) | 0 / 6 | E1, E6 (hidden columns), E7 | No |
| Knowledge base (1) | 0 / 1 | E6, E1 | No |

---

## 2. Error types, with examples

### E1: Stuck in a loop (22 of 25 failures)

**What it is:** the agent stops making progress and repeats itself. It either waits (`noop`, `scroll`), which happened in 14 failures, or clicks the same element again and again, which happened in 8. Each step's reasoning is almost a copy of the previous one, so the agent never notices that nothing is changing.

**Example: create-incident (seed 71).** After filling one field, the agent decided to "verify" its work and then waited for 13 steps in a row.

> Plan (step 5 onward): "1. Verify that the "Short description" field contains "ATF : Test1"… 3. If both fields are filled correctly, click the "Submit" button"
> Action (steps 2–14): `noop(1000)  # Wait for a moment to ensure the fields are updated before verification`

(`workarena_abstract.create-incident__seed71/trajectory.md`)

**Why it matters:**
- **"Verify" has no action behind it.** The plan says to verify, but the agent has no action that verifies anything, so it waits.
- **History makes it worse.** With thinking history and memory turned on, each step copies the previous step's reasoning. That reinforces the loop instead of breaking it.
- **Successes broke out by changing action.** The two successes that fell into the same pattern escaped by trying something new: the change request clicked Submit, and the menu task used the menu's search box.

---

### E2: Wrong idea of where it is (7 failures)

**What it is:** the agent believes it is on a page, or that something has happened, when the page shows otherwise. It then acts on that false belief.

**Example: order-sales-laptop (seed 385).** Picking the item from the search suggestions opens a **search results** page, not the item's order page. The page says so plainly, and the link to the real item page is right there. The agent assumed it was already on the order page and spent the rest of the episode looking for a Quantity box that wasn't there.

> AXTree at step 5: `[a61] heading 'Catalog Search Results:'` … `[a146] link 'Sales Laptop', clickable, visible`
> Agent's thinking: "I will check if there is a visible input field or dropdown for quantity on the Sales Laptop details page" → `noop(1000)`

(`workarena_abstract.order-sales-laptop__seed385/context/step_05_prompt.md`)

**How often:**
- **All 5 service-catalog failures** made this mistake. **Every catalog success** clicked the item link (`a146`) on the very next step, including the two that also went through the search results page.
- **Other examples:**
  - **filter-hardware-list:** believed a filter was applied when the query was empty ("I have successfully set the filter for "Company"…").
  - **create-hardware-asset:** after the form reset, its memory still said "the serial number is already filled in".

---

### E3: Wrong control (11 failures)

**What it is:** the right button or field is on the page, but the agent uses a different one that looks related.

**Example: filter-asset-list (seed 466).** The filter panel was open, and the field selector for building a condition was visible. The agent clicked "Run filter" instead, believing it added a condition. It then repeated that click 7 times.

> AXTree at step 1: `[a1018] button 'Run filter'` and `[a1082] combobox 'All of these conditions must be met. -- choose field --'`
> Action: `click('a1018')  # Click on the button to add a new filter condition.`

(`workarena_abstract.filter-asset-list__seed466/context/step_01_prompt.md`)

**How often:**
- **List filter, 6 of 6 failures.** None of these episodes created a single filter condition. Instead the agent:
  - typed values into the keyword **search box** (incident, catalog items)
  - used the "Search a specific field" dropdown as if it were a filter (hardware, change request)
  - clicked "Run filter" or toggled the panel (asset, user)
- **Dashboard:** clicked the chart image 10 times, or the chart's "Save as PNG" menu 14 times, to "read" values.
- **Forms:** clicked search-as-you-type fields (Model category, Model) and waited for options instead of typing into them (create-hardware-asset, create-problem).

---

### E4: Vague value mapped to the wrong field (9 failures, all forms and filters)

**What it is:** the abstracted prompt gives a value without saying which field it belongs to. Examples: "for System Administrator" (which field?), or "with Normal and Network" (which columns?). The agent guesses wrong, or never connects the value to a field at all. **This is the error most directly caused by the abstraction.**

**Example 1: create-incident (seed 71).** "Log an incident for **System Administrator**" means *Caller = System Administrator*. At step 0 the agent noticed that Caller was mandatory, but it never put the name there. The form could not be submitted.

> Step 0 thinking: "The focused element is the "Caller" field, which is mandatory and needs to be filled before submitting the incident."
> AXTree at step 5: `[a182] searchbox 'Mandatory - must be populated before Submit Caller'` (still empty)

**Example 2: filter-change-request-list (seed 214).** "Show me only the change requests with **Normal** and **Network**…" means *Type = Normal, Assignment group = Network*. Those columns aren't visible in the list, so the agent picked visible ones that sounded plausible:

> Step 0 thinking: "filter the change requests to show only those with a "Normal" priority and "Network" risk"

**Other examples:**
- **create-hardware-asset:** typed the model name into "Display name" instead of "Model".
- **filter-user-list:** read the bare value "system" as "no system".
- **filter-incident-list and filter-service-catalog-item-list:** treated the bare values as keywords for the search box.

In every filter episode the agent also misused the controls (E3). So better field mapping alone would not have been enough.

---

### E5: Doesn't finish, or over-does it (3 failures)

**What it is:** the agent has done enough to succeed but doesn't submit. Instead it invents extra requirements, fills fields with made-up placeholder values, or keeps "double-checking".

**Example: create-problem (seed 20).** By step 4 the problem statement was filled, no field was marked mandatory, and Submit was visible. The agent invented a list of required fields and started working through them:

> Step 4 thinking: "The required fields include "First reported by," "Category," "Subcategory," "Service," "Service offering," "Configuration item," "Impact," "Urgency," and "Problem statement.""
> Later: `fill('a205', 'John Doe')`

(`workarena_abstract.create-problem__seed20/context/step_04_response.md`)

**Other examples:**
- **create-user:** filled made-up "User Title" and "Department Name" after all mandatory fields were done.
- **order-ipad-mini:** set the quantity, then spent its last 3 steps "verifying" with Order Now visible.

The vague prompt probably encourages this. Without a list of fields, the agent doesn't know when the form counts as "complete".

---

### E6: Needed information not visible (5 failures)

**What it is:** the page content the agent receives (the AXTree) does not contain what it needs, so it can't succeed by reading the page.

**Example 1: the page disappears (4 failures).** In create-hardware-asset, create-problem, create-user and knowledge-base-search, the form or article list suddenly vanished from the agent's view. Only about 15–20 page-header elements were left, nearly all marked `hidden`, while the browser was still on the same page. The agent then acted on element IDs it remembered, or simply waited.

> create-user, step 6 AXTree: 17 elements, 16 of them `hidden=True` (e.g. `[81] button 'All', clickable, visible, hidden=True`), URL still `…/sys_user.do`
> Action (steps 6–14): `noop(1000)  # Waiting to see if any validation messages or additional fields appear`

**Example 2: chart labels missing (multi-chart-value-retrieval).** The question asks about "Survey : Basic Platform Based Test". In the AXTree, every bar is labelled only with the series name ("1. Assessment, 46." … "12. Assessment, 2."), so the label never appears on the page. The task cannot be answered from the page content alone.

(`workarena_abstract.multi-chart-value-retrieval__seed102/context/step_05_prompt.md`, lines 129–140)

**Related: sort fields that aren't visible columns.**
- Quantity, Phase, Justification, Country code, Manager and Description aren't visible columns in their lists.
- Sorting by them needs the "Add Sort" option, which is hidden until the filter panel is opened.
- Instead, the agent invented headers ("Phase"), or used a similar-looking column (Short description for Description).

---

### E7: Output format errors (4 failures, 1 fatal)

**What it is:** the agent's reply can't be read by the system. Either a tag is missing, or an element ID is written wrong.

**Example: impersonation (seed 343), fatal.** All 4 attempts ended with an unclosed action tag, so no action could be read and the episode ended at step 0:

> Reply: `<action>\nclick('79')` (no closing `</action>`), and the system answered "Missing the key <action> in the answer."

**Other examples:**
- **sort-change-request-list:** wrote an ID with brackets, `click('[a220]')`, which gave "Could not find element with bid "[a220]"" 10 times.
- **sort-user-list:** wrote `'45'` instead of `'a45'` and clicked a page-header element instead of the list's Actions menu.

---

## 3. Context elements that cause errors

These are the parts of the context the model receives that most often led to errors.

1. **Thinking history and memory copy themselves forward (E1).**
   - **What we saw:** each step's reasoning and memory repeat the previous ones almost word for word. When the agent is stuck, this keeps it stuck: the context keeps telling it to "verify first".
   - **The flags involved:** `use_think_history` and `use_memory`. We turned these on to get diagnostic detail, and the same history appears to make looping worse.
2. **Pages that look like other pages (E2).** The catalog search results page shows a preview panel with the item's description and price, so it looks like a product page. The heading "Catalog Search Results" is there, but the agent ignores it.
3. **Similar-looking controls next to each other (E3).** On list pages, the keyword search box, the "Search a specific field" dropdown, "Run filter" and the condition builder all sit together. The AXTree labels don't make clear which one builds a filter.
4. **Chart data shown as "image" items (E3/E6).**
   - **Data present:** values do appear as text, e.g. `image '21. 2026-09-21, 9. Open.'`. But the agent read "image" as a picture it had to inspect. In multi-chart-min-max the answer was right there, and the agent clicked the chart 10 times instead.
   - **Labels missing:** on one dashboard the labels were missing altogether.
5. **The page content disappears mid-episode (E6).** In 4 episodes the page content dropped out of the AXTree while the browser stayed on the same page. This looks like a problem in how the page is captured (the form sits in an embedded frame), not something the agent caused. It should be investigated before the full run.
6. **Error messages are shown but don't change behaviour.** Action errors appear in the context, e.g. "Could not find element with bid…" and "Timeout 500ms exceeded". The agent usually repeats the same action anyway.
7. **Two ID formats on one page (E7).** Elements on the outer page have plain IDs (`45`), while elements inside the list frame have prefixed IDs (`a45`). This led to wrong-element clicks.

---

## 4. What succeeded, for contrast

- **Single-chart dashboards (2/2).** The values were listed in the AXTree, and the agent answered in 1–3 steps. Even without the answer-format instruction, it naturally gave both label and count.
- **Service-catalog successes (4/9).** Search, click the item link, set the quantity, click Order Now, all in 5–6 steps. Three of them kept the default configuration, which is fine for the abstracted check.
- **Change request (form).** The prompt's text mapped straight onto Short description, there were no unexpected mandatory fields, and the agent clicked Submit after a short "verify" loop.
- **Menu navigation.** It wasted 8 steps waiting, then switched to typing the module name into the menu's search box and found it.

**Common thread:** successes are short, take the direct route, and change approach when something isn't working.

---

## 5. Caveats

- **One episode per task.** Patterns are indicative, not statistically established.
- **No comparison with the original prompts yet.** Whether the original prompts produce the same failures, especially in filter, sort, catalog and dashboard tasks, can only be answered by running the same 33 episodes with the original prompts. This report only shows where the vague prompt *visibly* played a role (E4, E5).
- **Hand-labelled categories.** Error types were assigned by reading the logs. Some episodes fit several types, and the counts are approximate.
- **Sort validation detail.** For sort tasks with 2–3 fields, the validation message shows `[]` even when one column header was clicked, because a header-click sort is only detected for single-field tasks. This does not change any outcome, since no episode sorted a second field. WorkArena's original check behaves the same way.

---

## 6. Possible interventions (for the next stage)

Each one targets one of the errors above.

| Error | Intervention to try |
|---|---|
| E1 loops | Detect repeated actions or near-identical reasoning and tell the agent to try something different. Compare runs with think history and memory off and on. |
| E2 wrong page | Add a hint to check the page heading or URL before acting, and that search results must be clicked through. |
| E3 wrong control | Add short task-type hints, e.g. "to filter a list, open the filter panel and use '-- choose field --'". |
| E4 vague field mapping | Let the agent ask the user (a clarifying question), or tell it to look for empty mandatory fields and match prompt values to them. |
| E5 doesn't finish | Tell it to submit once the fields named in the request are filled. |
| E6 missing information | Fix how the page is captured when the content disappears. Consider adding screenshots for charts. |
| E7 format | Use a stronger model, or a more lenient way of reading its replies. |
