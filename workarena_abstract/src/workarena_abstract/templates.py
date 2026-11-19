"""
Deterministic rewriting of WorkArena L1 goals into abstracted prompts (abstraction level 1).

Every function is pure: it takes the values a WorkArena task sets in `setup_goal` and returns an
`Abstraction` with the new goal text and a list of the information that was removed. Each removed
item is tagged as recoverable (the agent could find it in the environment) or unrecoverable (only
the user knows it; the agent can only guess or ask).
"""

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

ABSTRACTION_LEVEL = 1


@dataclass
class RemovedInfo:
    info: str
    recoverable: bool


@dataclass
class Abstraction:
    goal: str
    removed: list[RemovedInfo] = field(default_factory=list)

    def removed_as_dicts(self) -> list[dict]:
        return [asdict(r) for r in self.removed]


# ---------------------------------------------------------------------------------------------
# Forms (create a record)
# ---------------------------------------------------------------------------------------------

# Fields a worker would actually mention when asking for a new record, by table label.
# For "change request" no field is always present in the configs, so the first available field in
# priority order is used (a single one).
FORM_KEY_FIELDS = {
    "incident": ["caller_id", "short_description"],
    "problem": ["short_description"],
    "user": ["first_name", "last_name"],
    "hardware asset": ["model", "serial_number"],
}
CHANGE_REQUEST_KEY_PRIORITY = [
    "short_description",
    "description",
    "justification",
    "implementation_plan",
    "backout_plan",
    "test_plan",
    "risk_impact_analysis",
    "close_notes",
]
# Removed fields whose value can be derived from the environment given the key fields.
FORM_RECOVERABLE_FIELDS = {
    "hardware asset": {"model_category", "vendor"},  # both follow from the model
}


def form_key_fields(table_label: str, task_fields: list[str], template_record: dict) -> list[str]:
    """Pick the fields kept in the abstracted prompt (and checked by abstracted validation)."""

    def non_empty(f):
        return f in task_fields and str(template_record.get(f, "")).strip() != ""

    if table_label in FORM_KEY_FIELDS:
        keys = [f for f in FORM_KEY_FIELDS[table_label] if non_empty(f)]
        if keys:
            return keys
    else:
        for f in CHANGE_REQUEST_KEY_PRIORITY:
            if non_empty(f):
                return [f]
    # fallback: first non-empty task field
    for f in task_fields:
        if non_empty(f):
            return [f]
    return []


def abstract_form(
    table_label: str, task_fields: list[str], field_labels: dict, template_record: dict
) -> tuple[Abstraction, list[str]]:
    """Returns the abstraction and the list of key fields kept in the prompt."""
    keys = form_key_fields(table_label, task_fields, template_record)
    v = {f: template_record[f] for f in keys}

    if table_label == "incident" and keys == ["caller_id", "short_description"]:
        goal = f'Log an incident for {v["caller_id"]}: "{v["short_description"]}"'
    elif table_label == "problem" and keys == ["short_description"]:
        goal = f'Open a problem record: "{v["short_description"]}"'
    elif table_label == "user" and keys == ["first_name", "last_name"]:
        goal = f'Add {v["first_name"]} {v["last_name"]} as a new user.'
    elif table_label == "hardware asset" and keys == ["model", "serial_number"]:
        goal = f'Add a new {v["model"]} to our hardware assets, serial number {v["serial_number"]}.'
    elif table_label == "change request" and keys == ["short_description"]:
        goal = f'Raise a change request: "{v["short_description"]}"'
    elif keys:
        goal = f"Create a new {table_label} with " + " and ".join(
            f'{field_labels[f].lower()} "{v[f]}"' for f in keys
        )
        goal += "."
    else:
        goal = f"Create a new {table_label}."

    recoverable = FORM_RECOVERABLE_FIELDS.get(table_label, set())
    removed = [RemovedInfo("names of the form fields to fill", True)]
    for f in task_fields:
        if f in keys:
            continue
        value = str(template_record.get(f, ""))
        if value.strip() == "":
            continue  # expected empty; the default state of the form already satisfies it
        removed.append(RemovedInfo(f'{field_labels[f]} = "{value}"', f in recoverable))
    return Abstraction(goal, removed), keys


# ---------------------------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------------------------

# Plural display names of the lists, as used in WorkArena's sort goals.
LIST_PLURALS = {
    "alm_asset": "assets",
    "change_request": "change requests",
    "alm_hardware": "hardware",
    "incident": "incidents",
    "sc_cat_item": "catalog items",
    "sys_user": "users",
}

EMPTY_FILTER_VALUES = ("", "-- None --")


def abstract_filter(
    table_plural: str,
    filter_kind: str,
    column_labels: list[str],
    column_types: list[str],
    filter_values: list[str],
) -> Abstraction:
    """
    Column names are dropped wherever the value alone is meaningful (the agent must infer which
    column holds it). Empty-value and boolean conditions keep the column name since the value alone
    carries no meaning.
    """
    conds, removed = [], []
    for label, ctype, val in zip(column_labels, column_types, filter_values):
        if val in EMPTY_FILTER_VALUES:
            conds.append(f"no {label.lower()}")
        elif ctype == "boolean":
            conds.append(f"{label.lower()} set to {val}")
        else:
            conds.append(val)
            removed.append(RemovedInfo(f'column for "{val}" is "{label}"', True))
    joiner = " or " if filter_kind == "OR" else " and "
    goal = f"Show me only the {table_plural} with {joiner.join(conds)}."
    removed.append(RemovedInfo("use the list filter with 'is' conditions", True))
    return Abstraction(goal, removed)


_SORT_GOAL_TABLE = re.compile(r'Sort the "(.+?)" list')
_SORT_GOAL_FIELD = re.compile(r"-\s*(.+?)\s*\((ascending|descending)\)")


def abstract_sort(original_goal: str) -> Abstraction:
    table = _SORT_GOAL_TABLE.search(original_goal).group(1)
    fields = _SORT_GOAL_FIELD.findall(original_goal)
    labels = [label for label, _ in fields]
    goal = f"Sort the {table} by " + ", then by ".join(labels) + "."
    removed = [RemovedInfo(f"{label} direction: {d}", False) for label, d in fields]
    return Abstraction(goal, removed)


# ---------------------------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------------------------


def abstract_kb(question: str) -> Abstraction:
    """Ask the bare question: drop the 'using the knowledge base' pointer and format instructions."""
    i = question.find("?")
    removed = [RemovedInfo("the answer is in the knowledge base", True)]
    if i >= 0 and question[i + 1 :].strip():
        removed.append(RemovedInfo(f"answer format: {question[i + 1:].strip()}", False))
        question = question[: i + 1].strip()
    return Abstraction(question, removed)


# ---------------------------------------------------------------------------------------------
# Menu navigation / impersonation
# ---------------------------------------------------------------------------------------------


def menu_phrase(module: dict, last_segment_counts: Counter) -> str:
    """Short name a worker would use for a module; disambiguated with the app name if needed."""
    last = module["module"].split(">")[-1].strip()
    if last_segment_counts[last] > 1:
        return f"{module['application']} {last}"
    return last


def menu_last_segment_counts(all_configs: list[dict]) -> Counter:
    return Counter(m["module"].split(">")[-1].strip() for m in all_configs)


def abstract_menu(module: dict, all_configs: list[dict]) -> Abstraction:
    phrase = menu_phrase(module, menu_last_segment_counts(all_configs))
    goal = f"Take me to {phrase}."
    removed = [RemovedInfo(f'menu path "{module["module"]}"', True)]
    if module["application"] not in phrase:
        removed.append(RemovedInfo(f'application "{module["application"]}"', True))
    return Abstraction(goal, removed)


def abstract_impersonation(user_full_name: str, all_configs: list[str]) -> Abstraction:
    first = user_full_name.split()[0]
    rest = user_full_name[len(first) :].strip()
    unique = sum(n.split()[0] == first for n in all_configs) == 1
    goal = f"Impersonate {first}."
    removed = [RemovedInfo(f'last name "{rest}"', unique)] if rest else []
    return Abstraction(goal, removed)


# ---------------------------------------------------------------------------------------------
# Service catalog
# ---------------------------------------------------------------------------------------------


def abstract_order(item: str, quantity: int, configuration: dict) -> Abstraction:
    goal = f"Please order {quantity} {item} for me."
    removed = [RemovedInfo("item is in the Hardware category of the service catalog", True)]
    for name, (_, value) in configuration.items():
        removed.append(RemovedInfo(f'{name} = "{value}"', False))
    return Abstraction(goal, removed)


# ---------------------------------------------------------------------------------------------
# Dashboards / reports
# ---------------------------------------------------------------------------------------------


def _chart_locator(chart_title: str, chart_series: str) -> str:
    loc = f"the {chart_title} chart" if chart_title else "the chart"
    if chart_series:
        loc = f"the {chart_series} series of {loc}"
    return loc


def abstract_dashboard(question: str, chart_title: str, chart_series: str) -> Abstraction:
    loc = _chart_locator(chart_title, chart_series)
    if question.startswith("value"):
        _, unit, label = [x.strip() for x in question.split(";")]
        goal = f"How many {label} are in {loc}?"
        removed = [RemovedInfo(f"answer unit: {unit}", False)]
    elif question in ("max", "min"):
        word = "highest" if question == "max" else "lowest"
        goal = f"What has the {word} number in {loc}?"
        removed = [
            RemovedInfo("answer format: give both the label and the count", False),
            RemovedInfo("tie-breaking: if there are many, pick one", False),
        ]
    else:
        raise NotImplementedError(f"Dashboard question type {question!r} is not in WorkArena L1.")
    return Abstraction(goal, removed)
