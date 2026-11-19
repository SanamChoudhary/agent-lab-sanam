"""
Abstracted versions of the 33 WorkArena L1 tasks.

Each abstracted task subclasses the original WorkArena task: `setup_goal` runs the original (so all
attributes used for validation and `cheat` are set exactly as in WorkArena) and then replaces the
goal text; `validate` runs WorkArena's strict validator and our relaxed abstracted validator and
reports both.
"""

import logging

from browsergym.workarena import ATOMIC_TASKS, TASK_CATEGORY_MAP
from browsergym.workarena.tasks.dashboard import DashboardRetrievalTask
from browsergym.workarena.tasks.form import GenericNewRecordTask
from browsergym.workarena.tasks.knowledge import KnowledgeBaseSearchTask
from browsergym.workarena.tasks.list import FilterListTask, SortListTask
from browsergym.workarena.tasks.navigation import AllMenuTask, ImpersonationTask
from browsergym.workarena.tasks.service_catalog import OrderHardwareTask

from . import templates as T
from . import validation as V

logger = logging.getLogger(__name__)

TASK_ID_PREFIX = "workarena_abstract"
REWARD_MODES = ("abstracted", "strict")


class AbstractedTaskMixin:
    """Mixed in front of a WorkArena task class: (AbstractedTaskMixin, OriginalTask)."""

    original_task_cls = None  # set on each generated class

    def __init__(self, *args, reward_mode: str = "abstracted", **kwargs):
        if reward_mode not in REWARD_MODES:
            raise ValueError(f"reward_mode must be one of {REWARD_MODES}, got {reward_mode!r}")
        super().__init__(*args, **kwargs)
        self.reward_mode = reward_mode

    @classmethod
    def get_task_id(cls):
        original_id = cls.original_task_cls.get_task_id()  # workarena.servicenow.<name>
        return f"{TASK_ID_PREFIX}.{original_id.split('.', 2)[-1]}"

    @classmethod
    def category(cls) -> str:
        return TASK_CATEGORY_MAP[cls.original_task_cls.get_task_id()]

    # ---------------------------------------------------------------------------------------
    # Goal
    # ---------------------------------------------------------------------------------------

    def setup_goal(self, page):
        original_goal, info = super().setup_goal(page=page)
        self.original_goal = original_goal
        abstraction = self._abstract()
        self.abstracted_goal = abstraction.goal
        self.removed_info = abstraction.removed_as_dicts()
        info = dict(info or {})
        info.update(
            {
                "original_task": self.original_task_cls.get_task_id(),
                "category": self.category(),
                "abstraction_level": T.ABSTRACTION_LEVEL,
                "original_goal": original_goal,
                "abstracted_goal": abstraction.goal,
                "removed_info": self.removed_info,
                "reward_mode": self.reward_mode,
            }
        )
        return abstraction.goal, info

    def _abstract(self) -> T.Abstraction:
        if isinstance(self, GenericNewRecordTask):
            labels = {f: self._form_field_label(f) for f in self.task_fields}
            abstraction, keys = T.abstract_form(
                self.table_label, self.task_fields, labels, self.template_record
            )
            self.abstract_key_fields = keys
            return abstraction
        if isinstance(self, FilterListTask):
            cols = [self.list_info["columns"][c] for c in self.filter_columns]
            return T.abstract_filter(
                T.LIST_PLURALS.get(self.table_name, self.table_name),
                self.filter_kind,
                [c["label"] for c in cols],
                [c["type"] for c in cols],
                self.filter_values,
            )
        if isinstance(self, SortListTask):
            return T.abstract_sort(self.original_goal)
        if isinstance(self, KnowledgeBaseSearchTask):
            return T.abstract_kb(self.question)
        if isinstance(self, AllMenuTask):
            counts = T.menu_last_segment_counts(self.all_configs)
            phrase = T.menu_phrase(self.module, counts)
            self.abstract_accepted_urls = [
                m["url"]
                for m in self.all_configs
                if "url" in m and T.menu_phrase(m, counts) == phrase
            ]
            return T.abstract_menu(self.module, self.all_configs)
        if isinstance(self, ImpersonationTask):
            self.abstract_first_name = self.user_full_name.split()[0]
            return T.abstract_impersonation(self.user_full_name, self.all_configs)
        if isinstance(self, OrderHardwareTask):
            return T.abstract_order(
                self.requested_item, self.quantity, self.requested_configuration
            )
        if isinstance(self, DashboardRetrievalTask):
            return T.abstract_dashboard(
                self.config["question"], self.config["chart_title"], self.config["chart_series"]
            )
        raise NotImplementedError(f"No abstraction template for {type(self).__name__}")

    def _form_field_label(self, field: str) -> str:
        # WorkArena does not keep the sampled form config, but field labels are stored in every
        # config under config["fields"] (same labels for a given table)
        for c in [self.fixed_config or {}] + list(self.all_configs or []):
            if field in c.get("fields", {}):
                return c["fields"][field]
        return field.replace("_", " ")

    # ---------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------

    def _abstract_validator(self):
        if isinstance(self, GenericNewRecordTask):
            return V.validate_form
        if isinstance(self, FilterListTask):
            return V.validate_filter
        if isinstance(self, SortListTask):
            return V.validate_sort
        if isinstance(self, KnowledgeBaseSearchTask):
            return V.validate_same_as_strict
        if isinstance(self, AllMenuTask):
            return V.validate_menu
        if isinstance(self, ImpersonationTask):
            return V.validate_impersonation
        if isinstance(self, OrderHardwareTask):
            return V.validate_order
        if isinstance(self, DashboardRetrievalTask):
            return V.validate_dashboard
        raise NotImplementedError(f"No abstracted validator for {type(self).__name__}")

    def validate(self, page, chat_messages):
        strict = super().validate(page, chat_messages)
        s_reward = strict[0]

        error = None
        if s_reward >= 1:
            abstracted = strict  # every abstracted criterion is a relaxation of the strict one
        else:
            try:
                abstracted = self._abstract_validator()(self, page, chat_messages) or strict
            except Exception as e:  # never let our relaxed check break the episode
                logger.exception("Abstracted validation failed")
                error = f"{type(e).__name__}: {e}"
                abstracted = (0.0, False, "", {"message": "abstracted validation error"})

        chosen = abstracted if self.reward_mode == "abstracted" else strict
        reward, done, user_message, _ = chosen
        info = {
            "message": chosen[3].get("message", ""),
            "reward_mode": self.reward_mode,
            "strict_success": float(strict[0]),
            "strict_done": bool(strict[1]),
            "strict_message": strict[3].get("message", ""),
            "abstracted_success": float(abstracted[0]),
            "abstracted_done": bool(abstracted[1]),
            "abstracted_message": abstracted[3].get("message", ""),
        }
        if error:
            info["abstracted_error"] = error
        return reward, done, user_message, info


def _make_abstract_class(original_cls):
    return type(
        f"Abstract{original_cls.__name__}",
        (AbstractedTaskMixin, original_cls),
        {"original_task_cls": original_cls, "__module__": __name__},
    )


ABSTRACT_TASKS = [_make_abstract_class(cls) for cls in ATOMIC_TASKS]
ABSTRACT_TASKS_BY_ID = {cls.get_task_id(): cls for cls in ABSTRACT_TASKS}
ORIGINAL_TO_ABSTRACT_ID = {
    cls.original_task_cls.get_task_id(): cls.get_task_id() for cls in ABSTRACT_TASKS
}
