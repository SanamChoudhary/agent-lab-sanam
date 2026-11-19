"""
AgentLab integration.

AgentLab resolves task names to gym ids with a hard-coded list of prefixes (`_get_env_name` in
agentlab/experiments/loop.py), which does not know about this package, so in parallel workers
(ray/joblib) our tasks would not be registered. Instead of patching AgentLab, the benchmark uses
this EnvArgs subclass: unpickling it in a worker imports this module (and thus registers the
tasks), and `make_env` imports the package explicitly before creating the environment.
"""

from agentlab.experiments.loop import EnvArgs


class WorkArenaAbstractEnvArgs(EnvArgs):
    def make_env(self, *args, **kwargs):
        import workarena_abstract  # noqa: F401  (registers the gym environments)

        return super().make_env(*args, **kwargs)
