"""
Agent configurations for the WorkArena-Abstract experiments.

AGENT_4o_MINI_DIAGNOSTIC is AgentLab's standard GenericAgent config (FLAGS_GPT_4o, as in the
AgentLab/WorkArena papers) with extra flags turned on that make the agent's interpretation of the
prompt and its reasoning visible in the logs (AgentXray), to diagnose failures on abstracted prompts.

IMPORTANT: use the same agent config for the original-prompt and abstracted-prompt runs, otherwise
the two are not comparable.
"""

from agentlab.agents.generic_agent.agent_configs import AGENT_4o_MINI, FLAGS_GPT_4o
from agentlab.agents.generic_agent.generic_agent import GenericAgentArgs
from agentlab.llm.llm_configs import CHAT_MODEL_ARGS_DICT

FLAGS_DIAGNOSTIC = FLAGS_GPT_4o.copy()  # deep copy

# Reasoning made visible
FLAGS_DIAGNOSTIC.use_thinking = True  # reasoning before every action (already on in FLAGS_GPT_4o)
FLAGS_DIAGNOSTIC.use_plan = True  # writes/updates a plan: shows how it interpreted the vague goal
FLAGS_DIAGNOSTIC.use_memory = True  # keeps notes: shows what it assumed about missing information

# History shown to the agent
FLAGS_DIAGNOSTIC.obs.use_think_history = True  # sees its own earlier reasoning
FLAGS_DIAGNOSTIC.obs.use_action_history = True  # sees its past actions (already on)
FLAGS_DIAGNOSTIC.obs.use_error_logs = True  # sees the error of its last action (already on)
FLAGS_DIAGNOSTIC.obs.use_past_error_logs = True  # sees all earlier errors

# Kept off on purpose: use_criticise (doubles output, noisy), use_screenshot/use_som (cost, weak
# vision in gpt-4o-mini), use_html (duplicates the accessibility tree), use_diff (experimental),
# enable_chat (send_msg_to_user already comes with WorkArena's action set).

AGENT_4o_MINI_DIAGNOSTIC = GenericAgentArgs(
    chat_model_args=CHAT_MODEL_ARGS_DICT["openai/gpt-4o-mini-2024-07-18"],
    flags=FLAGS_DIAGNOSTIC,
)
# distinct (and short: Windows 260-char path limit) name, not confused with the standard config
AGENT_4o_MINI_DIAGNOSTIC.agent_name = "GenericAgent-4omini-diag"

AGENTS = {
    "diagnostic": AGENT_4o_MINI_DIAGNOSTIC,
    "standard": AGENT_4o_MINI,
}
