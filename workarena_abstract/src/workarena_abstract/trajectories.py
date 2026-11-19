"""
Export readable agent trajectories and per-step context from an AgentLab study.

AgentLab saves every step as a compressed pickle (`step_N.pkl.gz`) holding the exact prompt sent to
the model (`agent_info.chat_messages`), the model's raw reply, the observation, errors and the
validation info. This module turns those into plain files for failure analysis:

    <study_dir>/trajectories/
        index.csv                        one row per episode
        <task>__seed<N>/
            summary.md                   goals, removed info, outcome
            trajectory.md                per step: think / plan / memory / action / error / url
            trajectory.json              same, machine-readable
            context/step_XX_prompt.md    exact messages sent to the model at step XX
            context/step_XX_response.md  the model's full raw reply at step XX
"""

import csv
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

TAGS = ("think", "plan", "step", "memory", "action")


def _msg_text(msg) -> str:
    content = msg["content"] if isinstance(msg, dict) else getattr(msg, "content", msg)
    if isinstance(content, str):
        return content
    parts = []
    for elem in content:
        if elem.get("type") in ("text", "input_text"):
            parts.append(elem.get("text", ""))
        elif elem.get("type") == "image_url":
            parts.append("[image omitted]")
    return "\n".join(parts)


def _msg_role(msg) -> str:
    return msg["role"] if isinstance(msg, dict) else getattr(msg, "role", "?")


def _parse_tags(text: str) -> dict:
    out = {}
    for tag in TAGS:
        m = re.findall(rf"<{tag}>(.*?)</{tag}>", text, flags=re.DOTALL)
        if m:
            out[tag] = m[-1].strip()
    return out


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def _goal_from_prompt(steps) -> str:
    """GenericAgent prompts contain a '## Goal:' section; return its text."""
    for s in steps:
        chat = _get(s.agent_info or {}, "chat_messages") or []
        messages = list(chat.messages) if hasattr(chat, "messages") else list(chat)
        for m in messages:
            if _msg_role(m) == "assistant":
                continue
            match = re.search(r"#+ Goal:?\s*\n(.*?)(?:\n#+ |\Z)", _msg_text(m), flags=re.DOTALL)
            if match:
                return match.group(1).strip()
    return ""


def _fence(text: str) -> str:
    return "````\n" + (text or "").rstrip() + "\n````\n"


def export_episode(res, out_root: Path) -> dict:
    """Export one ExpResult. Returns the index row."""
    env_args = res.exp_args.env_args
    ep_dir = out_root / f"{_safe(env_args.task_name)}__seed{env_args.task_seed}"
    ctx_dir = ep_dir / "context"
    ctx_dir.mkdir(parents=True, exist_ok=True)

    steps = res.steps_info
    # goals / removed info: AgentLab does not save the reset info, so read them from the first
    # step whose task_info carries them (our tasks repeat them in every validate() info)
    setup_info = next(
        (s.task_info for s in steps if s.task_info and "original_goal" in s.task_info), {}
    )
    summary = res.summary_info or {}

    # last validation info (strict / abstracted success) if any
    final_validation = next(
        (s.task_info for s in reversed(steps) if s.task_info and "strict_success" in s.task_info),
        {},
    )

    records = []
    for s in steps:
        agent_info = s.agent_info or {}
        chat = _get(agent_info, "chat_messages") or []
        messages = list(chat.messages) if hasattr(chat, "messages") else list(chat)
        obs = s.obs if isinstance(s.obs, dict) else {}

        # messages = [system, user prompt, assistant reply, (retry user msg, assistant reply)...]
        prompt_msgs = [m for m in messages if _msg_role(m) != "assistant"]
        replies = [m for m in messages if _msg_role(m) == "assistant"]
        raw_reply = _msg_text(replies[-1]) if replies else ""
        tags = _parse_tags(raw_reply)

        if messages:
            with open(ctx_dir / f"step_{s.step:02d}_prompt.md", "w", encoding="utf-8") as f:
                f.write(f"# Step {s.step}: exact context sent to the model\n\n")
                for i, m in enumerate(messages):
                    if _msg_role(m) == "assistant":
                        f.write(f"## Message {i} (assistant, earlier attempt; see response file)\n\n")
                    else:
                        f.write(f"## Message {i} ({_msg_role(m)})\n\n")
                    f.write(_fence(_msg_text(m)) + "\n")
            with open(ctx_dir / f"step_{s.step:02d}_response.md", "w", encoding="utf-8") as f:
                f.write(f"# Step {s.step}: model response\n\n")
                for i, r in enumerate(replies):
                    label = "final" if i == len(replies) - 1 else f"attempt {i + 1} (rejected by parser)"
                    f.write(f"## Reply ({label})\n\n" + _fence(_msg_text(r)) + "\n")

        stats = _get(agent_info, "stats") or {}
        records.append(
            {
                "step": s.step,
                "url": obs.get("url"),
                "last_action_error": obs.get("last_action_error") or "",
                "think": _get(agent_info, "think") or tags.get("think"),
                "plan": tags.get("plan"),
                "plan_step": tags.get("step"),
                "memory": tags.get("memory"),
                "action": s.action,
                "reward": s.reward,
                "terminated": s.terminated,
                "truncated": s.truncated,
                "validation": {
                    k: v for k, v in (s.task_info or {}).items()
                    if k in ("strict_success", "abstracted_success", "strict_message", "abstracted_message", "message",
                             "sim_user_question", "sim_user_reply")
                },
                "n_retry": stats.get("n_retry"),
                "prompt_tokens": stats.get("input_tokens") or stats.get("n_token_prompt"),
                "n_prompt_messages": len(prompt_msgs),
            }
        )

    goal = setup_info.get("abstracted_goal") or setup_info.get("original_goal") or ""
    if not goal:  # e.g. original WorkArena tasks: read the goal from the first prompt
        goal = _goal_from_prompt(steps)
    category = setup_info.get("category")
    if not category:
        try:
            from browsergym.workarena import TASK_CATEGORY_MAP

            from . import ABSTRACT_TASKS_BY_ID

            name = env_args.task_name
            if name in ABSTRACT_TASKS_BY_ID:
                name = ABSTRACT_TASKS_BY_ID[name].original_task_cls.get_task_id()
            category = TASK_CATEGORY_MAP.get(name)
        except ImportError:
            pass
    meta = {
        "task_name": env_args.task_name,
        "seed": env_args.task_seed,
        "category": category,
        "original_task": setup_info.get("original_task"),
        "goal_given_to_agent": goal,
        "original_goal": setup_info.get("original_goal"),
        "abstracted_goal": setup_info.get("abstracted_goal"),
        "removed_info": setup_info.get("removed_info"),
        "agent": res.exp_args.agent_args.agent_name,
        "n_steps": summary.get("n_steps"),
        "cum_reward": summary.get("cum_reward"),
        "strict_success": final_validation.get("strict_success", summary.get("cum_reward")),
        "abstracted_success": final_validation.get("abstracted_success"),
        "err_msg": summary.get("err_msg"),
        "raw_exp_dir": str(res.exp_dir),
    }

    with open(ep_dir / "trajectory.json", "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "steps": records}, f, indent=2, default=str)

    with open(ep_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write(f"# {meta['task_name']} (seed {meta['seed']})\n\n")
        f.write(f"- Category: {meta['category']}\n- Agent: {meta['agent']}\n")
        f.write(f"- Steps: {meta['n_steps']}\n")
        f.write(f"- Strict success: {meta['strict_success']}\n")
        f.write(f"- Abstracted success: {meta['abstracted_success']}\n")
        if meta["err_msg"]:
            f.write(f"- Error: {meta['err_msg']}\n")
        f.write(f"\n## Goal given to the agent\n\n{_fence(goal)}\n")
        if meta["original_goal"] and meta["original_goal"] != goal:
            f.write(f"## Original WorkArena goal\n\n{_fence(meta['original_goal'])}\n")
        if meta["removed_info"]:
            f.write("## Information removed from the prompt\n\n")
            for r in meta["removed_info"]:
                kind = "recoverable" if r.get("recoverable") else "unrecoverable"
                f.write(f"- {r.get('info')} ({kind})\n")
        f.write(f"\nRaw AgentLab files: `{meta['raw_exp_dir']}`\n")

    with open(ep_dir / "trajectory.md", "w", encoding="utf-8") as f:
        f.write(f"# Trajectory: {meta['task_name']} (seed {meta['seed']})\n\n")
        f.write(f"**Goal given to the agent:** {goal}\n\n")
        f.write(
            f"**Outcome:** strict={meta['strict_success']} abstracted={meta['abstracted_success']} "
            f"steps={meta['n_steps']}\n\n"
        )
        for r in records:
            f.write(f"---\n\n## Step {r['step']}\n\n")
            f.write(f"- URL: {r['url']}\n")
            if r["last_action_error"]:
                f.write(f"- Error from previous action: `{r['last_action_error'].strip()[:500]}`\n")
            if r["validation"]:
                f.write(f"- Validation: {r['validation']}\n")
            for key in ("think", "plan", "memory"):
                if r[key]:
                    f.write(f"\n**{key.capitalize()}**\n\n{_fence(r[key])}")
            if r["action"]:
                f.write(f"\n**Action**\n\n{_fence(r['action'])}")
            if r["n_prompt_messages"]:
                f.write(
                    f"\nFull context: [prompt](context/step_{r['step']:02d}_prompt.md) · "
                    f"[response](context/step_{r['step']:02d}_response.md)\n\n"
                )
    return {**{k: v for k, v in meta.items() if k != "removed_info"}, "folder": ep_dir.name}


def export_study(study_dir, out_dir=None) -> Path:
    """Export every episode of a study. Returns the trajectories folder."""
    from agentlab.experiments.loop import yield_all_exp_results

    study_dir = Path(study_dir)
    out_root = Path(out_dir) if out_dir else study_dir / "trajectories"
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for res in yield_all_exp_results(study_dir, use_cache=False):
        try:
            rows.append(export_episode(res, out_root))
        except Exception as e:
            logger.exception(f"Could not export {res.exp_dir}")
            rows.append({"raw_exp_dir": str(res.exp_dir), "err_msg": f"export failed: {e}"})

    if rows:
        fields = sorted({k for r in rows for k in r}, key=lambda k: (k != "task_name", k))
        with open(out_root / "index.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return out_root
