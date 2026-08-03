"""RuntimeSpec: the pure data contract between frontend and backends."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .util import die, expand_path


def inner_command(command, inner):
    """Resolve the inner command: COMMAND plus any inner args."""
    return [command] + list(inner)


@dataclass
class ProjectEnv:
    """A project dev environment discovered by a backend."""

    container_args: list[str]   # argv fragment appended to the container cmd


@dataclass
class RuntimeSpec:
    """Everything a backend needs to build the container argv."""

    workspace: Path             # project dir; always shared read-write
    shares: list[Path]          # existing paths only, `~`/uid expanded
    preserves: list[str]        # env var regexps (backend decides how to apply)
    runtime: str | None         # image ref (oci/apple)
    project: ProjectEnv | None  # dev environment discovered by the backend
    command: list[str]          # inner command, defaults resolved by the CLI


def assemble(config, project_dir, inner, env=None):
    """Build the RuntimeSpec for the merged CONFIG and CLI INNER args."""
    env = env if env is not None else os.environ
    workspace = Path(project_dir or os.getcwd()).resolve()
    if not workspace.is_dir():
        die(f"pic: project directory not found: {workspace}")

    shares = []
    for raw in config.shares:
        path = expand_path(raw.format(uid=os.getuid()), env)
        if os.path.exists(path):
            shares.append(Path(path))
        else:
            print(f"pic: skipping share for missing path: {path}",
                  file=sys.stderr)
    if workspace not in shares:
        shares.append(workspace)  # the workspace is always shared

    return RuntimeSpec(
        workspace=workspace,
        shares=shares,
        preserves=list(config.preserves),
        runtime=config.runtime,
        project=None,             # filled by the backend after selection
        command=list(inner),
    )
