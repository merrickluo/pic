"""pic — run the pi coding agent inside a container.

pic owns the arguments before a bare `--`; everything after it goes
verbatim to the inner command, which defaults to `pi` (set with `-c` or
`[pic] command` in pic.toml, e.g. `pic -c bash` for a shell).  There is
deliberately no table of pi's options: the boundary is the `--` itself,
so pi releases can change their CLI freely.

Usage:
  pic [PIC-OPTIONS] [PROJECT-DIR] [-- INNER-ARGS...]

  pic --help                        pic's own help (this text)
  pic -- --model sonnet -- "fix the build"   pi's options after `--`
  pic -c bash                       a shell inside the container

PIC-OPTIONS:
  -h, --help            show this help
  -V, --version         show the version
  -b, --backend NAME    guix | oci | auto   (default: auto)
  -c, --command CMD     inner command (default: pi / [pic] command)
  -s, --share PATH      extra path to share into the container (repeatable)
  -e, --preserve REGEX  extra env var regexp to pass through (repeatable)
      --runtime VALUE   image ref (oci/apple) — overrides config
      --no-project      ignore pic.toml and project env detection
      --list-backends   list the backends and exit

Environment: PIC_BACKEND, PIC_COMMAND, PIC_SHARE (colon-separated),
PIC_PRESERVE (whitespace-separated), PIC_RUNTIME, PIC_NO_PROJECT.

Configuration (schema in README.md):
  ~/.config/pic/pic.toml     user defaults
  <project>/pic.toml         project overrides

Precedence (low to high):
  builtin defaults < user pic.toml < project pic.toml < environment < flags
"""

import os
import sys
from dataclasses import dataclass, field

from . import __version__
from .launch import run_pic


class UsageError(Exception):
    """Bad command line; the message is user-facing."""


@dataclass
class Parsed:
    backend: str | None = None
    command: str | None = None
    shares: list[str] = field(default_factory=list)
    preserves: list[str] = field(default_factory=list)
    runtime: str | None = None
    no_project: bool = False
    list_backends: bool = False
    project_dir: str | None = None
    inner: list[str] = field(default_factory=list)


def split_double_dash(argv):
    """Split ARGV into (BEFORE, AFTER) at the first bare `--`."""
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


def need_value(args, i, opt):
    if i + 1 < len(args):
        return args[i + 1]
    raise UsageError(f"missing value for {opt}")


def parse(argv, prog):
    """Parse pic's own options (the part before `--`).

    --help/--version exit with status 0; unknown options raise UsageError
    with a hint pointing at the `--` boundary.
    """
    before, inner = split_double_dash(argv)
    parsed = Parsed(inner=inner)
    i = 0
    while i < len(before):
        arg = before[i]
        if arg in ("--help", "-h"):
            print(help_text(prog))
            raise SystemExit(0)
        elif arg in ("--version", "-V"):
            print(f"{prog} {__version__}")
            raise SystemExit(0)
        elif arg == "--list-backends":
            parsed.list_backends = True
        elif arg == "--no-project":
            parsed.no_project = True
        elif arg in ("--command", "-c"):
            parsed.command = need_value(before, i, arg)
            i += 1
        elif arg.startswith("--command="):
            parsed.command = arg.split("=", 1)[1]
        elif arg in ("--backend", "-b"):
            parsed.backend = need_value(before, i, arg)
            i += 1
        elif arg.startswith("--backend="):
            parsed.backend = arg.split("=", 1)[1]
        elif arg in ("--share", "-s"):
            parsed.shares.append(need_value(before, i, arg))
            i += 1
        elif arg.startswith("--share="):
            parsed.shares.append(arg.split("=", 1)[1])
        elif arg in ("--preserve", "-e"):
            parsed.preserves.append(need_value(before, i, arg))
            i += 1
        elif arg.startswith("--preserve="):
            parsed.preserves.append(arg.split("=", 1)[1])
        elif arg == "--runtime":
            parsed.runtime = need_value(before, i, arg)
            i += 1
        elif arg.startswith("--runtime="):
            parsed.runtime = arg.split("=", 1)[1]
        elif arg.startswith("-"):
            raise UsageError(
                f"{prog}: unknown option: {arg}\n"
                f"hint: pi's options go after a bare `--`, "
                f"e.g. `{prog} -- --help`")
        elif parsed.project_dir is None:
            parsed.project_dir = arg
        else:
            raise UsageError(
                f"{prog}: unexpected argument: {arg}\n"
                f"hint: only one project directory is accepted; pass "
                f"everything else after `--`")
        i += 1
    return parsed


def help_text(prog):
    """pic's own help (both entry points share this text)."""
    return __doc__


def _run(argv, prog):
    try:
        parsed = parse(sys.argv[1:] if argv is None else argv, prog)
    except UsageError as e:
        print(str(e), file=sys.stderr)
        print(f"run `{prog} --help` for usage", file=sys.stderr)
        return 2
    if parsed.list_backends:
        from .backends import BACKENDS

        for name, backend in BACKENDS.items():
            state = "available" if backend.available() else "not available"
            print(f"{name:<8} {state:<14} platforms={','.join(backend.platforms)}")
        return 0
    return run_pic(parsed)


def main(argv=None):
    """Entry point for the `pic` command."""
    return _run(argv, "pic")


if __name__ == "__main__":
    sys.exit(main())
