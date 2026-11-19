# Results: abstracted-prompt pilot with interventions

**Study:** `2026-11-19_06-44_abstracted_intervention`.

**Compared with:** the first pilot, `2026-11-19_02-44_abstracted_diagnostic` (failure analysis in [`error_analysis.md`](error_analysis.md)).

**What stayed the same:**
- the 33 abstracted tasks and their seeds
- the model (`gpt-4o-mini-2024-07-18`)
- the agent flags
- the 15-step limit

**What changed:** the agent got the interventions described below. Example file paths in this report are relative to `2026-11-19_06-44_abstracted_intervention/trajectories/`.

---

## 1. Summary

| | First pilot (no interventions) | With interventions |
|---|---|---|
| **Abstracted success** | 8 / 33 (24%) | **12 / 33 (36%)** |
| Steps where the agent repeated its previous action | 57% | **33%** |
| `noop` (wait) actions | 178 | **26** |
| Total agent steps | 403 | 367 |

**In short:**
- The interventions helped most where the agent knew what to do but got stuck or lost: service catalog, one form, knowledge base and impersonation.
- They did not help list filters and sorts, which are still 0 of 12. There the agent does not know how that screen's controls work, and general advice cannot teach it.
- The agent never used the new option to ask the user a question.
- Each task was run once, so a single task can flip between success and failure by chance. Read the 8 → 12 change as a promising signal, not a final result.

---

## 2. What the interventions were

All of them are general: they use only the goal, the page content, the URL, the action history and the chat. None of them mentions ServiceNow or a specific task. The code is in `workarena_abstract/src/workarena_abstract/intervention_agent.py` and `tasks.py`.

| # | Intervention | Simple explanation |
|---|---|---|
| 1 | Loop breaker | When the agent repeats an action, or the page hasn't changed for 2 steps, it is told: "No progress in the last N steps. Recently tried: … Do not repeat these." Only its last 3 thoughts are shown, so old stuck reasoning isn't copied forward. |
| 2 | Action-effect feedback | After every action, one line tells the agent what changed: a new URL, elements that appeared or disappeared, or "nothing changed". |
| 3 | Page check and done check | Standing instruction: first name the page you are on and how you know it. Then list what is done and what remains, and finish as soon as nothing remains. |
| 4a/b | Goal slots and required fields | Standing instruction: split the request into the details it gives and the details it leaves out. Look up what exists on the site, and fill the form's required fields. |
| 4c | Ask the user | The agent may ask a question in the chat. A second GPT-4o-mini plays the requester and answers using only the original, detailed WorkArena prompt. |
| 6 | Hygiene | One automatic wait if the page content suddenly disappears. A missing `</action>` tag is fixed automatically. Explanations of chart "image" labels and of the two ID formats (`45` vs `a45`). |

---

## 3. Results by task type

| Task type | First pilot | With interventions | Change |
|---|---|---|---|
| Service catalog (9) | 4 | **7** | +3 |
| Form (5) | 1 | **2** | +1 |
| Knowledge base (1) | 0 | **1** | +1 |
| Menu: navigation + impersonation (2) | 1 | 1 | 0 (one won, one lost) |
| Dashboard (4) | 2 | 1 | −1 |
| List filter (6) | 0 | 0 | 0 |
| List sort (6) | 0 | 0 | 0 |
| **Total (33)** | **8** | **12** | **+4** |

### Task by task

| Task | First pilot | With interventions | Steps (before → after) |
|---|---|---|---|
| create-incident | ❌ | ✅ | 15 → 7 |
| impersonation | ❌ | ✅ | 0 → 12 |
| knowledge-base-search | ❌ | ✅ | 15 → 4 |
| order-apple-mac-book-pro15 | ❌ | ✅ | 15 → 15 |
| order-development-laptop-p-c | ❌ | ✅ | 15 → 5 |
| order-ipad-mini | ❌ | ✅ | 15 → 9 |
| order-standard-laptop | ❌ | ✅ | 15 → 9 |
| all-menu | ✅ | ❌ | 12 → 15 |
| order-ipad-pro | ✅ | ❌ | 6 → 15 |
| single-chart-min-max-retrieval | ✅ | ❌ | 1 → 1 |
| 7 other tasks | ✅ | ✅ | unchanged |
| 16 other tasks | ❌ | ❌ | unchanged |

---

## 4. What improved, with examples

### 4.1 Less looping (loop breaker, effect feedback)

- **What changed:** the share of steps that repeat the previous action fell from 57% to 33%, and waiting (`noop`) fell from 178 actions to 26.
- **Why:** in the first pilot the agent often waited over and over to "verify" the page. Now it is told the page hasn't changed and that waiting was already tried.

### 4.2 Service catalog: the agent now reaches the item's page (page check)

- **The problem before:** all 5 catalog failures in the first pilot mistook the search-results page for the item's order page.
- **What happens now:** the agent picks the item from the search suggestions and then confirms where it is.
- **Example:** `order-standard-laptop__seed191`, step 3:
  > "I am currently on the item details page for the "Standard Laptop," as indicated by the heading and the visible elements related to the laptop. I need to find the quantity input field to specify that I want to order 8 units."
- **Result:** 7 of 9 catalog orders succeeded, up from 4.

### 4.3 Forms: the agent fills the required fields (required-field instruction)

- **The problem before:** in the first pilot, "Log an incident for System Administrator: "ATF : Test1"" failed because the mandatory **Caller** field was never filled.
- **What happens now:** `create-incident__seed71`:
  1. fill the description
  2. go to *Caller* and fill it with "System Administrator"
  3. submit

  It succeeded in 7 steps.

### 4.4 Knowledge base and impersonation

- **Knowledge base** (`knowledge-base-search__seed121`): search "legal consultations" → open the article → send the answer. It succeeded in 4 steps; before, it used all 15 and failed.
- **Impersonation** (`impersonation__seed343`): in the first pilot the episode ended at step 0 because the reply was missing its `</action>` tag. With the automatic fix the agent got to act: it found the *Impersonate user* option and chose Derek Parker, succeeding in 12 steps.

---

## 5. What still fails, with examples

21 episodes failed. 18 of them still used all 15 steps.

### 5.1 List filters (0 / 6): the agent doesn't know how to build a filter

- **Simple explanation:** the agent now opens the filter panel more often, but doesn't know how to add a condition: pick a field, then an operator, then a value. So it clicks the same buttons again and again.
- **Example:** `filter-asset-list__seed466`: it opens the filter, fills "Gaston Cieloszyk" into one box, then clicks the "add AND condition" button **8 times in a row**.
- **Example:** `filter-user-list__seed372`: it types `false` into the field-chooser box four times, once for each condition it wants.
- **The vague prompt still plays a part.** The agent can't tell which column a value belongs to. In `filter-change-request-list__seed214`, it read "Normal" as a *priority* and "Network" as a *risk*. Its replies at step 0 then used `click(a47)` without quotes, which can't be read, so the episode ended there.

### 5.2 List sorts (0 / 6): clicking headers can't sort by several fields

- **Simple explanation:** every sort task needs 2–3 sort fields. Clicking a column header sorts by one field only, and the agent never found the list's multi-sort option. Once header clicks didn't finish the job, it explored unrelated buttons instead (notifications, help, activity stream).
- **Example:** `sort-service-catalog-item-list__seed661`: it clicked the Name, Fulfillment automation level and Class headers. Then it sent "The catalog items are successfully sorted" **11 times**, but the list was not sorted.

### 5.3 Dashboards with several charts (0 / 2): the agent still pokes at the chart

- **Simple explanation:** the data was in the page content, but the agent kept clicking the chart or its refresh button instead of reading the labels. The instruction about "image" labels was not enough.
- **Example:** `multi-chart-min-max-retrieval__seed435`: it clicked the refresh button 6 times and the chart graphic 6 times, and never answered.

### 5.4 Forms still fail where only the user knows the answer (4c not used)

- **Simple explanation:** the agent was allowed to ask the requester, but **it never asked in any episode**. When information was missing, it made something up instead.
- **Examples:**
  - `create-hardware-asset__seed700`: `fill('a293', 'AssetTag123') # Assuming a placeholder`, then it clicked Submit 5 times while the form was still incomplete.
  - `create-user__seed614` ("Add Daniel-Amber Gonzalez-Simpson as a new user"):
    - It wrote "Daniel" as the first name instead of "Daniel-Amber".
    - It invented an email address: `daniel.gonzalez-simpson@example.com # Assuming a placeholder email format`.
    - It submitted with the wrong first name.
- **Why:** the instruction said to ask only for information that cannot be found on the site. A small model seems to prefer guessing over admitting something is missing. Making the question step more explicit, or required whenever the agent writes "assuming", may be needed.

### 5.5 Tasks that got worse

| Task | First pilot | Now | What happened |
|---|---|---|---|
| single-chart-min-max | ✅ | ❌ | Correct value but no label. It answered "The lowest number in the chart is 49." The original prompt asked for "both the label and the count". That detail was removed in the abstracted prompt, and this time the agent didn't give the label ("Available"). In the first pilot it happened to give both. |
| order-ipad-pro | ✅ | ❌ | It got to the item and set the quantity, then waited 8 times despite the loop warning. It clicked *Order Now* only at the last step, which was too late. |
| all-menu | ✅ | ❌ | It explored the menus (All, More menus, Workspaces, Favorites, History) without typing into the menu's search box, which is what worked in the first pilot. |

Two of these look like chance with a single attempt (order-ipad-pro and all-menu). The chart answer is a real effect of the abstraction: the prompt no longer says what format the answer should take.

---

## 6. Takeaways

1. **General interventions help with "getting stuck" and "getting lost".** They raised success from 8 to 12, mostly through less looping and better awareness of which page the agent is on.
2. **They don't teach the agent how a particular screen works.** Filters, multi-field sorts and charts need knowledge of the interface, which general hints can't provide. The next intervention to try is a general way to *learn* those skills, e.g. memory built from the agent's own successful attempts (the "experience memory" left out of this round).
3. **The agent guesses instead of asking.** Information only the user knows was invented, never asked for. This is central to our research question. The ask-the-user option needs a stronger trigger before we can measure its effect.
4. **Next runs needed:**
   - The same 33 tasks with the **original prompts** (diagnostic agent), to measure the baseline gap.
   - More than one seed per task, so the differences can be trusted.
