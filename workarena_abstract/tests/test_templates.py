"""
Offline tests (no ServiceNow instance needed): run every abstraction template over every config
shipped with WorkArena, and check registration / benchmark pairing.
"""

import json
import os
import pytest
from browsergym.workarena import config as wa_config

from workarena_abstract import templates as T

CONFIG_DIR = os.path.dirname(wa_config.CREATE_INCIDENT_CONFIG_PATH)


def load(name):
    with open(os.path.join(CONFIG_DIR, name)) as f:
        return json.load(f)


def check(abstraction, original_goal=None):
    assert abstraction.goal.strip()
    assert "\n" not in abstraction.goal
    assert abstraction.removed, "every abstraction must remove something"
    if original_goal is not None:
        assert abstraction.goal != original_goal


FORM_FILES = {
    "change request": "create_change_request_task.json",
    "incident": "create_incident_task.json",
    "hardware asset": "create_hardware_asset_task.json",
    "problem": "create_problem_task.json",
    "user": "create_user_task.json",
}


@pytest.mark.parametrize("table_label", list(FORM_FILES))
def test_form_templates(table_label):
    for cfg in load(FORM_FILES[table_label]):
        a, keys = T.abstract_form(
            table_label, cfg["task_fields"], cfg["fields"], cfg["template_record"]
        )
        check(a)
        assert keys, "a key field must always be kept"
        assert all(k in cfg["task_fields"] for k in keys)
        for k in keys:
            assert str(cfg["template_record"][k]) in a.goal
        # removed values (long enough to be distinctive) must not leak into the prompt
        for f in cfg["task_fields"]:
            v = str(cfg["template_record"][f])
            if f not in keys and len(v) >= 6 and all(v not in str(cfg["template_record"][k]) for k in keys):
                assert v not in a.goal, (f, v, a.goal)


FILTER_FILES = {
    "alm_asset": "filter_asset_list_task.json",
    "change_request": "filter_change_request_list_task.json",
    "alm_hardware": "filter_hardware_list_task.json",
    "incident": "filter_incident_list_task.json",
    "sc_cat_item": "filter_service_catalog_item_list_task.json",
    "sys_user": "filter_user_list_task.json",
}


@pytest.mark.parametrize("table", list(FILTER_FILES))
def test_filter_templates(table):
    for cfg in load(FILTER_FILES[table]):
        cols = [cfg["list_info"]["columns"][c] for c in cfg["filter_columns"]]
        a = T.abstract_filter(
            T.LIST_PLURALS[table],
            cfg["filter_kind"],
            [c["label"] for c in cols],
            [c["type"] for c in cols],
            cfg["filter_values"],
        )
        check(a)
        assert a.goal.startswith(f"Show me only the {T.LIST_PLURALS[table]} with ")
        for v in cfg["filter_values"]:
            assert v in a.goal or v in T.EMPTY_FILTER_VALUES


@pytest.mark.parametrize(
    "fname",
    [
        "sort_asset_list_task.json",
        "sort_change_request_list_task.json",
        "sort_hardware_list_task.json",
        "sort_incident_list_task.json",
        "sort_service_catalog_item_list_task.json",
        "sort_user_list_task.json",
    ],
)
def test_sort_templates(fname):
    for cfg in load(fname):
        a = T.abstract_sort(cfg["goal"])
        check(a, cfg["goal"])
        assert "ascending" not in a.goal and "descending" not in a.goal
        assert len(a.removed) == len(cfg["sort_fields"])


def test_kb_templates():
    for cfg in load("knowledge_base_configs.json"):
        a = T.abstract_kb(cfg["question"])
        check(a)
        assert "knowledge base" not in a.goal.lower() or "knowledge base" in cfg["question"].lower()
        assert cfg["question"].startswith(a.goal)


def test_menu_templates():
    configs = load("all_menu.json")
    counts = T.menu_last_segment_counts(configs)
    for m in configs:
        a = T.abstract_menu(m, configs)
        check(a)
        assert ">" not in a.goal
        # the accepted set for the prompt always contains the true module
        phrase = T.menu_phrase(m, counts)
        assert any(o["url"] == m["url"] for o in configs if T.menu_phrase(o, counts) == phrase)


def test_impersonation_templates():
    users = load("impersonation_users.json")
    for u in users:
        a = T.abstract_impersonation(u, users)
        assert a.goal == f"Impersonate {u.split()[0]}."


@pytest.mark.parametrize(
    "fname",
    sorted(f for f in os.listdir(CONFIG_DIR) if f.startswith("order_")),
)
def test_order_templates(fname):
    for cfg in load(fname):
        a = T.abstract_order(cfg["item"], cfg["quantity"], cfg["configuration"])
        check(a)
        assert cfg["item"] in a.goal and str(cfg["quantity"]) in a.goal
        for _, value in cfg["configuration"].values():
            if isinstance(value, str) and len(value) >= 4:
                assert value not in a.goal


@pytest.mark.parametrize(
    "fname",
    [
        "dashboard_retrieval_value_task.json",
        "dashboard_retrieval_minmax_task.json",
        "report_retrieval_value_task.json",
        "report_retrieval_minmax_task.json",
    ],
)
def test_dashboard_templates(fname):
    for cfg in load(fname):
        a = T.abstract_dashboard(cfg["question"], cfg["chart_title"], cfg["chart_series"])
        check(a)
        assert "count" not in a.goal and "percent" not in a.goal


def test_registration_and_benchmark_pairing():
    import gymnasium as gym

    import workarena_abstract
    from workarena_abstract.benchmark import make_benchmark

    assert len(workarena_abstract.workarena_abstract_tasks) == 33
    for task_id in workarena_abstract.workarena_abstract_tasks:
        assert f"browsergym/{task_id}" in gym.registry

    orig = make_benchmark("original", n_repeats=10)
    abst = make_benchmark("abstracted", n_repeats=10)
    assert len(orig.env_args_list) == len(abst.env_args_list) == 330
    for o, a in zip(orig.env_args_list, abst.env_args_list):
        assert o.task_seed == a.task_seed
        assert workarena_abstract.ORIGINAL_TO_ABSTRACT_ID[o.task_name] == a.task_name

    # same episodes as BrowserGym's own workarena_l1
    from browsergym.experiments.benchmark.configs import DEFAULT_BENCHMARKS

    ref = DEFAULT_BENCHMARKS["workarena_l1"](n_repeats=10)
    assert [(e.task_name, e.task_seed) for e in ref.env_args_list] == [
        (e.task_name, e.task_seed) for e in orig.env_args_list
    ]


def test_env_args_register_tasks_in_fresh_process(tmp_path):
    """Simulates a ray/joblib worker: unpickling the env args must register our gym envs."""
    import pickle
    import subprocess
    import sys

    from workarena_abstract.benchmark import make_benchmark

    env_args = make_benchmark("abstracted", n_repeats=1).env_args_list[0]
    path = tmp_path / "env_args.pkl"
    path.write_bytes(pickle.dumps(env_args))
    code = (
        "import pickle, sys, gymnasium as gym\n"
        f"ea = pickle.loads(open(r'{path}', 'rb').read())\n"
        "assert 'workarena_abstract' in sys.modules\n"
        "assert f'browsergym/{ea.task_name}' in gym.registry, ea.task_name\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_trajectory_export_offline(tmp_path):
    """Exporter turns AgentLab step records into readable trajectory and context files."""
    import json
    from types import SimpleNamespace

    from agentlab.experiments.loop import StepInfo
    from agentlab.llm.llm_utils import AIMessage, Discussion, HumanMessage, SystemMessage

    from workarena_abstract.trajectories import export_episode

    reply = (
        "<think>The user wants an iPad mini; no colour given, I'll keep the default.</think>\n"
        "<plan>1. open catalog 2. pick iPad mini 3. order</plan><step>1</step>\n"
        "<memory>colour unspecified, using default</memory>\n<action>click('a12')</action>"
    )
    chat = Discussion([SystemMessage("You are an agent..."), HumanMessage("# Goal\nPlease order 1 iPad mini for me.\n# AXTree ..."), AIMessage(reply)])
    setup_info = {
        "category": "service catalog",
        "original_task": "workarena.servicenow.order-ipad-mini",
        "original_goal": 'Go to the hardware store and order 1 "iPad mini" with configuration {...}',
        "abstracted_goal": "Please order 1 iPad mini for me.",
        "removed_info": [{"info": 'Choose the colour = "Space Grey"', "recoverable": False}],
    }
    steps = [
        StepInfo(step=0, obs={"url": "https://x/catalog", "last_action_error": ""}, action="click('a12')",
                 agent_info={"think": "The user wants an iPad mini", "chat_messages": chat, "stats": {"n_retry": 0}},
                 task_info=setup_info),
        StepInfo(step=1, obs={"url": "https://x/checkout", "last_action_error": "TimeoutError: x"}, reward=1,
                 terminated=True, task_info={"strict_success": 0.0, "abstracted_success": 1.0}),
    ]
    res = SimpleNamespace(
        exp_args=SimpleNamespace(
            env_args=SimpleNamespace(task_name="workarena_abstract.order-ipad-mini", task_seed=7),
            agent_args=SimpleNamespace(agent_name="GenericAgent-test"),
        ),
        steps_info=steps,
        summary_info={"n_steps": 1, "cum_reward": 1, "err_msg": None},
        exp_dir=tmp_path / "raw",
    )
    row = export_episode(res, tmp_path / "trajectories")
    ep = tmp_path / "trajectories" / "workarena_abstract.order-ipad-mini__seed7"
    assert row["strict_success"] == 0.0 and row["abstracted_success"] == 1.0
    traj = (ep / "trajectory.md").read_text(encoding="utf-8")
    assert "colour unspecified, using default" in traj and "click('a12')" in traj and "TimeoutError" in traj
    prompt = (ep / "context" / "step_00_prompt.md").read_text(encoding="utf-8")
    assert "Please order 1 iPad mini" in prompt and "You are an agent" in prompt
    assert "<memory>" in (ep / "context" / "step_00_response.md").read_text(encoding="utf-8")
    data = json.loads((ep / "trajectory.json").read_text(encoding="utf-8"))
    assert data["steps"][0]["plan"].startswith("1. open catalog")
    assert "unrecoverable" in (ep / "summary.md").read_text(encoding="utf-8")
