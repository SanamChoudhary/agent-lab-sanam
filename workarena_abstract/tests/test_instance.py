"""
Instance-backed tests (need a ServiceNow instance: SNOW_INSTANCE_* env vars or a Hugging Face
login with access to the WorkArena instance pool). Enable with:

    WORKARENA_ABSTRACT_INSTANCE_TESTS=1 pytest workarena_abstract/tests/test_instance.py

1. Solvability: for every abstracted task, WorkArena's cheat() (which solves the full original
   task) must give strict_success = abstracted_success = 1.
2. Relaxation sanity: partial solutions that satisfy only the abstracted prompt must give
   strict_success = 0 and abstracted_success = 1.
"""

import os

import gymnasium as gym
import pytest

import workarena_abstract

pytestmark = pytest.mark.skipif(
    os.environ.get("WORKARENA_ABSTRACT_INSTANCE_TESTS") != "1",
    reason="set WORKARENA_ABSTRACT_INSTANCE_TESTS=1 to run tests against a ServiceNow instance",
)

SEED = 0


class Episode:
    def __init__(self, task_id, seed=SEED):
        self.env = gym.make(f"browsergym/{task_id}", headless=True)
        _, self.reset_info = self.env.reset(seed=seed)
        self.task = self.env.unwrapped.task
        self.page = self.env.unwrapped.page
        self.chat = self.env.unwrapped.chat.messages

    def cheat(self):
        self.task.cheat(self.page, self.chat)

    def validate(self):
        return self.task.validate(self.page, self.chat)

    def close(self):
        self.env.close()


@pytest.fixture
def episode():
    episodes = []

    def _make(task_id, seed=SEED):
        ep = Episode(task_id, seed)
        episodes.append(ep)
        return ep

    yield _make
    for ep in episodes:
        ep.close()


@pytest.mark.parametrize("task_id", workarena_abstract.workarena_abstract_tasks)
def test_cheat_solves_abstracted_task(task_id, episode):
    ep = episode(task_id)
    task_info = ep.reset_info["task_info"]
    assert task_info["abstracted_goal"] != task_info["original_goal"]
    assert ep.env.unwrapped.goal_object[0]["text"] == task_info["abstracted_goal"]

    ep.cheat()
    reward, done, _, info = ep.validate()
    assert info["strict_success"] == 1, info
    assert info["abstracted_success"] == 1, info
    assert reward == 1 and done


def test_form_key_fields_only(episode):
    """Fill only the key fields of an incident: abstracted success, strict failure."""
    ep = episode("workarena_abstract.create-incident")
    all_fields = ep.task.task_fields
    assert set(ep.task.abstract_key_fields) < set(all_fields)
    ep.task.task_fields = list(ep.task.abstract_key_fields)
    try:
        ep.cheat()
    finally:
        ep.task.task_fields = all_fields
    _, _, _, info = ep.validate()
    assert info["abstracted_success"] == 1, info
    assert info["strict_success"] == 0, info


def test_sort_wrong_directions(episode):
    ep = episode("workarena_abstract.sort-user-list")
    dirs = list(ep.task.sort_dirs)
    ep.task.sort_dirs = ["desc" if d == "asc" else "asc" for d in dirs]
    try:
        ep.cheat()
    finally:
        ep.task.sort_dirs = dirs
    _, _, _, info = ep.validate()
    assert info["abstracted_success"] == 1, info
    assert info["strict_success"] == 0, info


def test_order_default_configuration(episode):
    ep = episode("workarena_abstract.order-ipad-mini")
    config = ep.task.requested_configuration
    assert config, "expected an item with configuration options"
    ep.task.requested_configuration = {}
    try:
        ep.cheat()
    finally:
        ep.task.requested_configuration = config
    _, _, _, info = ep.validate()
    assert info["abstracted_success"] == 1, info
    # strict can only pass if the defaults happen to equal the requested configuration
    assert info["strict_success"] == 0 or info["strict_message"], info


def test_dashboard_label_without_count(episode):
    ep = episode("workarena_abstract.single-chart-min-max-retrieval")
    ep.cheat()
    label = ep.chat[-1]["message"].rsplit(",", 1)[0]
    ep.chat.append({"role": "assistant", "message": f"It's {label}."})
    _, _, _, info = ep.validate()
    assert info["abstracted_success"] == 1, info
    assert info["strict_success"] == 0, info
