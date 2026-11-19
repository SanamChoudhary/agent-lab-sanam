"""
Abstracted (relaxed) success checks, one per WorkArena L1 category.

Each function has the signature of `validate`: (task, page, chat_messages) -> (reward, done, msg, info).
They are only called when the strict WorkArena validator did NOT succeed: every abstracted criterion
is a relaxation of the strict one, so strict success implies abstracted success.
"""

import logging
import re
from urllib import parse

import numpy as np
from browsergym.workarena.api.requests import get_request_by_id
from browsergym.workarena.api.utils import table_api_call
from browsergym.workarena.tasks.utils.utils import check_url_suffix_match

from .templates import EMPTY_FILTER_VALUES

logger = logging.getLogger(__name__)

def _fail(msg: str, done: bool = False):
    return 0.0, done, "", {"message": msg}


def _success(msg: str):
    return 1.0, True, "Nice work, thank you!", {"message": msg}


def _display(v) -> str:
    """Table API returns reference fields as {"display_value": ..., "link": ...}."""
    if isinstance(v, dict):
        v = v.get("display_value", "")
    return "" if v is None else str(v)


# ---------------------------------------------------------------------------------------------
# Form: a record exists in the right table and the key fields match. Other fields are ignored,
# including the "protected field changed" guard (the agent has to guess the values of fields
# that are not in the prompt).
# ---------------------------------------------------------------------------------------------


def validate_form(task, page, chat_messages):
    sys_id = page.evaluate("localStorage").get(task.session_sys_id_field, None)
    if sys_id is None:
        return _fail("The form has not been submitted.")

    record = table_api_call(
        instance=task.instance,
        table=task.table_name,
        params={"sysparm_query": f"sys_id={sys_id}", "sysparm_display_value": True},
        wait_for_record=True,
        max_retries=20,
        raise_on_wait_expired=False,
    )["result"]
    if len(record) == 0:
        return _fail("The record was not found in the database.")
    record = {f: _display(v) for f, v in record[0].items()}

    for f in task.abstract_key_fields:
        if record.get(f) != task.template_record[f]:
            return _fail(f'Key field "{f}" has the wrong value.', done=True)
    return _success("A record with the requested key fields was created.")


# ---------------------------------------------------------------------------------------------
# List filter: the records shown by the agent's filter are exactly the records the target filter
# selects (any query that selects the same records counts, regardless of columns/operators used).
# ---------------------------------------------------------------------------------------------


def _target_filter_sys_ids(task) -> set[str]:
    columns = list(task.filter_columns)
    rows = table_api_call(
        instance=task.instance,
        table=task.table_name,
        params={
            "sysparm_fields": ",".join(["sys_id"] + columns),
            "sysparm_display_value": True,
            "sysparm_limit": 100000,
        },
    )["result"]

    def cond(row, col, val):
        shown = _display(row.get(col))
        if val in EMPTY_FILTER_VALUES:
            return shown in EMPTY_FILTER_VALUES
        return shown == val

    combine = any if task.filter_kind == "OR" else all
    return {
        _display(row["sys_id"])
        for row in rows
        if combine(cond(row, c, v) for c, v in zip(columns, task.filter_values))
    }


def validate_filter(task, page, chat_messages):
    if not check_url_suffix_match(page, expected_url=task.start_url, task=task):
        return _fail("The page is not on the list to filter.")
    task._wait_for_ready(page)
    current_query = task._extract_list_info(page)["query"]
    if not current_query:
        return _fail("There are no filters yet.")

    shown = {
        _display(r["sys_id"])
        for r in table_api_call(
            instance=task.instance,
            table=task.table_name,
            params={
                "sysparm_query": current_query,
                "sysparm_fields": "sys_id",
                "sysparm_limit": 100000,
            },
        )["result"]
    }
    target = _target_filter_sys_ids(task)
    if shown == target:
        return _success(f"Filter selects the expected {len(target)} records: {current_query}.")
    return _fail(
        f"Filter selects {len(shown)} records, expected {len(target)} "
        f"({len(shown & target)} in common): {current_query}."
    )


# ---------------------------------------------------------------------------------------------
# List sort: same fields in the same order; sort directions are ignored.
# ---------------------------------------------------------------------------------------------

_ORDERBY = re.compile(r"ORDERBY(?:DESC)?([^\^]+)")


def validate_sort(task, page, chat_messages):
    if not check_url_suffix_match(
        page, expected_url=task.start_url[: task.start_url.find("%3F")], task=task
    ):
        return _fail("The page is not on the list to sort.")
    task._wait_for_ready(page)

    url = parse.unquote(page.evaluate("() => window.location.href"))
    qs = parse.parse_qs(parse.urlparse(url).query)
    order = _ORDERBY.findall(qs.get("sysparm_query", [""])[0])
    if not order:
        list_info = task._extract_list_info(page)
        order = _ORDERBY.findall(list_info["query"] or "")
        if not order and len(task.sort_fields) == 1:
            # sorting by clicking a column header does not always show up in the query
            order_by = page.evaluate(f'{list_info["js_selector"]}.getOrderBy()')
            order = [order_by] if order_by else []

    if [o.strip() for o in order] == list(task.sort_fields):
        return _success("Correct sort fields (direction not checked).")
    return _fail(f"Incorrect sort fields: {order}.")


# ---------------------------------------------------------------------------------------------
# Menu: any module whose short name matches the one in the prompt.
# ---------------------------------------------------------------------------------------------


def _norm_url(url: str) -> str:
    return parse.urlunparse(parse.urlparse(parse.unquote(url)))


def validate_menu(task, page, chat_messages):
    page.wait_for_load_state("domcontentloaded")
    current = _norm_url(page.evaluate("() => window.location.href"))
    accepted = {_norm_url(task.instance.snow_url + u) for u in task.abstract_accepted_urls}
    if current in accepted:
        return _success("Reached a module matching the requested name.")
    return _fail("Not at an expected URL.")


# ---------------------------------------------------------------------------------------------
# Impersonation: impersonating any user with the requested first name.
# ---------------------------------------------------------------------------------------------


def validate_impersonation(task, page, chat_messages):
    page.wait_for_function("window.NOW && window.NOW.user")
    user_info = page.evaluate("window.NOW")["user"]
    if not user_info["isImpersonating"]:
        return _fail("Not currently impersonating a user.")
    user = table_api_call(
        instance=task.instance,
        table="sys_user",
        params={
            "sysparm_query": f"sys_id={user_info['userID']}",
            "sysparm_fields": "name,first_name",
        },
    )["result"][0]
    target = task.abstract_first_name.lower()
    names = {(user.get("first_name") or "").strip().lower()}
    names.add(((user.get("name") or "").split() or [""])[0].lower())
    if target in names:
        return _success("Impersonating a user with the requested first name.")
    return _fail("Impersonating a user with a different first name.")


# ---------------------------------------------------------------------------------------------
# Service catalog: one item, right item, right quantity; configuration is ignored.
# ---------------------------------------------------------------------------------------------


def validate_order(task, page, chat_messages):
    # the strict validator (already run) extracts the request sys_id from the URL
    if getattr(task, "request_sysid", None) is None:
        return _fail("The request was not created.")
    r = get_request_by_id(instance=task.instance, sysid=task.request_sysid)
    if r is None or len(r["items"]) == 0:
        return _fail("No items were requested.")
    if len(r["items"]) > 1:
        return _fail("Multiple kinds of items were requested.", done=True)
    (item,) = r["items"]
    if item["short_description"].lower() != task.short_description.lower():
        return _fail("The requested item is incorrect.", done=True)
    if item["quantity"] != str(task.quantity):
        return _fail("The requested quantity is incorrect.", done=True)
    return _success("Right item and quantity ordered (configuration not checked).")


# ---------------------------------------------------------------------------------------------
# Dashboard: value questions accept the count OR the percent; min/max accept the right label
# (the count is not required).
# ---------------------------------------------------------------------------------------------


def validate_dashboard(task, page, chat_messages):
    if not check_url_suffix_match(page, expected_url=task.start_url, task=task):
        return _fail("The page is not on the chart's URL.")
    if not (chat_messages and chat_messages[-1]["role"] == "assistant"):
        return _fail("The assistant did not provide an answer.")
    response = str(chat_messages[-1]["message"])

    task._wait_for_ready(page)
    _, chart_data, _ = task._get_chart_by_title(page, task.config["chart_title"])
    if len(chart_data) == 1:
        chart_data = chart_data[0]["data"]
    else:
        chart_data = [s["data"] for s in chart_data if s["name"] == task.config["chart_series"]][0]

    question = task.config["question"]
    if question.startswith("value"):
        label = question.split(";")[2].strip()
        response_ = response
        for lbl in {p["label"] for p in chart_data}:
            response_ = response_.replace(lbl, "")
        numbers = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", response_.replace(",", ""))}
        if not numbers:
            return _fail("No number detected in the response.")
        if len(numbers) > 2:
            return _fail("Too many numbers in the response.", done=True)
        point = [p for p in chart_data if p["label"] == label][0]
        expected = [float(point[k]) for k in ("count", "percent") if point.get(k) is not None]
        if any(np.isclose(e, n) for e in expected for n in numbers):
            return _success("Correct value (count or percent).")
        return _fail("Incorrect answer.", done=True)

    if question in ("max", "min"):
        target_func = max if question == "max" else min
        target_count = float(target_func(chart_data, key=lambda x: x["count"])["count"])
        targets = [p for p in chart_data if float(p["count"]) == target_count]
        if any(p["label"].lower() in response.lower() for p in targets):
            return _success("Correct label (count not required).")
        return _fail("Incorrect answer.", done=True)

    raise NotImplementedError(f"Dashboard question type {question!r} is not in WorkArena L1.")


def validate_same_as_strict(task, page, chat_messages):
    """Knowledge base: the strict check (answer substring) is already format-tolerant."""
    return None
