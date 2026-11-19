"""
GenericAgent plus general-purpose interventions against the failures seen in the first pilot
(experiment_results/error_analysis.md). Nothing here is specific to ServiceNow: every mechanism uses
only the goal, the accessibility tree, the URL, the action history and the chat.

1. Loop breaker: warns when the agent repeats an action or the page stops changing; only the last
   3 thoughts are shown in the history, so stuck reasoning stops copying itself forward.
2. Action-effect feedback: one line on what the last action changed on the page.
3. Page check and done check, 4a/b. goal slots and required fields: standing instructions.
4c. Asking the user: replies to the agent's questions (sent by the task's simulated user, see
   tasks.py) are shown in the prompt.
6. Hygiene: one automatic wait when the page tree suddenly collapses on the same URL; a missing
   </action> closing tag is added before parsing; instructions on chart "image" labels and ids.
"""

import re
from dataclasses import dataclass

from agentlab.agents.generic_agent.generic_agent import GenericAgent, GenericAgentArgs
from browsergym.experiments.agent import AgentInfo

KEPT_THOUGHTS = 3  # thoughts older than this are hidden from the history
STALL_LIMIT = 2  # steps without progress before the loop-breaker note appears
COLLAPSE_RATIO = 0.3  # tree shrank below this fraction of the previous one on the same URL
MIN_TREE_LINES = 40  # ignore collapse on pages that were already small

INSTRUCTIONS = """\
Work in this order at every step:
- Page check: in <think>, first name the page you are on (e.g. list, form, search results, item \
details, dashboard) and the evidence for it (its heading or the URL). Search results are not the \
item's own page: open the item first.
- Done check: list which parts of the goal are already done and what remains. If nothing remains, \
finish now: submit the form or send the answer with send_msg_to_user. Do not add extra steps.
- Goal slots: split the goal into the values it gives and the values it leaves out. Information \
that exists on the site (records, names, options) should be looked up. On a form, find the fields \
marked as required or mandatory and fill them, matching each value from the goal to the field it \
belongs to.
- Asking: if a value only the requester can know is missing and cannot be found on the site, ask \
one short question with send_msg_to_user("...?") (end it with a question mark). The reply will \
appear in the "Notes" below. Do not ask for things you can find on the site. If the goal is a \
question for you to answer, do not ask anything: your message is taken as the final answer.
- Progress: if an action did not change the page, do not repeat it; try a different element or \
approach.

Reading the page:
- Elements shown as image '...' with a text label carry their content in that label (for example \
chart data points): read the label directly, there is nothing else to inspect.
- Element ids can be plain ("45") or prefixed ("a45") for content inside embedded frames. Use the \
id exactly as written in the tree.
"""


def _tree_lines(obs) -> set:
    """Tree lines without their ids, so the same element compares equal across steps."""
    return {re.sub(r"\[[^\]]*\]", "", line).strip() for line in obs["axtree_txt"].splitlines()}


class _CloseActionTag:
    """Wraps the chat model and closes an unclosed <action> tag before AgentLab parses the reply."""

    def __init__(self, llm):
        self._llm = llm

    def __call__(self, *args, **kwargs):
        answer = self._llm(*args, **kwargs)
        text = answer["content"]
        if isinstance(text, str) and "<action>" in text and "</action>" not in text:
            answer["content"] = text.rstrip() + "\n</action>"
        return answer

    def __getattr__(self, name):
        return getattr(self._llm, name)


@dataclass
class InterventionAgentArgs(GenericAgentArgs):
    def make_agent(self):
        return InterventionAgent(
            chat_model_args=self.chat_model_args, flags=self.flags, max_retry=self.max_retry
        )


class InterventionAgent(GenericAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flags = self.flags.copy()  # extra_instructions changes per step: don't share flags
        self.chat_llm = _CloseActionTag(self.chat_llm)

    def reset(self, seed=None):
        super().reset(seed)
        self.stalled_steps = 0
        self.waited_for_collapse = False

    def get_action(self, obs):
        prev = self.obs_history[-1] if self.obs_history else None

        # 6a. the page tree collapsed on the same URL: wait once instead of asking the model
        if prev is not None and not self.waited_for_collapse and self._collapsed(prev, obs):
            self.waited_for_collapse = True
            return self._wait(obs)
        self.waited_for_collapse = False

        notes = self._notes(prev, obs)
        self.flags.extra_instructions = INSTRUCTIONS + (
            "\nNotes about your progress:\n" + "\n".join(f"- {n}" for n in notes) if notes else ""
        )

        # 1. show only the last few thoughts in the history
        thoughts = self.thoughts
        self.thoughts = [
            t if i >= len(thoughts) - KEPT_THOUGHTS else "(older thought hidden)"
            for i, t in enumerate(thoughts)
        ]
        try:
            action, agent_info = super().get_action(obs)
        finally:
            self.thoughts = thoughts + self.thoughts[len(thoughts):]
        agent_info.extra_info["intervention_notes"] = notes
        return action, agent_info

    def _notes(self, prev, obs) -> list[str]:
        notes = []
        if prev is not None:
            # 2. what the last action changed
            before, after = _tree_lines(prev), _tree_lines(obs)
            url_changed = prev["url"] != obs["url"]
            if url_changed:
                notes.append(f"Your last action {self.actions[-1]} opened a new URL: {obs['url']}")
            elif before == after:
                notes.append(f"Your last action {self.actions[-1]} did not change the page.")
            else:
                added = [line for line in after - before if line][:5]
                notes.append(
                    f"Your last action {self.actions[-1]} changed the page: "
                    f"{len(after - before)} elements appeared, {len(before - after)} disappeared."
                    + (f" New: {'; '.join(added)}" if added else "")
                )

            # 1. loop breaker
            repeated = len(self.actions) >= 2 and self.actions[-1] == self.actions[-2]
            if repeated or (not url_changed and before == after):
                self.stalled_steps += 1
            else:
                self.stalled_steps = 0
            if self.stalled_steps >= STALL_LIMIT:
                tried = list(dict.fromkeys(a for a in self.actions[-6:] if a))
                notes.append(
                    f"No progress in the last {self.stalled_steps} steps. Recently tried: "
                    f"{', '.join(tried)}. Do not repeat these: choose a different element or "
                    "approach (another control, link, menu or search)."
                )

        # 4c. replies from the user to the agent's questions
        # (the chat starts with BrowserGym's greeting and the goal, so skip those two)
        chat = (obs.get("chat_messages") or [])[2:]
        for question, reply in zip(chat, chat[1:]):
            if question["role"] == "assistant" and reply["role"] == "user":
                notes.append(f"You asked: {question['message']} The user replied: {reply['message']}")
        return notes

    def _collapsed(self, prev, obs) -> bool:
        n_prev, n_now = len(prev["axtree_txt"].splitlines()), len(obs["axtree_txt"].splitlines())
        return (
            prev["url"] == obs["url"]
            and n_prev >= MIN_TREE_LINES
            and n_now < COLLAPSE_RATIO * n_prev
        )

    def _wait(self, obs):
        action = "noop(2000)"
        self.obs_history.append(obs)
        self.actions.append(action)
        self.memories.append(None)
        self.thoughts.append("The page content collapsed; waiting for it to load (automatic).")
        return action, AgentInfo(
            think=self.thoughts[-1], extra_info={"intervention_notes": ["automatic wait"]}
        )
