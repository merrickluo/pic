"""Configuration: builtin defaults, pic.toml (user + project), env, flags.

Precedence (low to high):

    builtin defaults
      < ~/.config/pic/pic.toml
      < <project>/pic.toml
      < environment (PIC_BACKEND, PIC_SHARE, PIC_PRESERVE, PIC_RUNTIME, ...)
      < command line flags
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import resources
from .util import die

USER_CONFIG = Path("~/.config/pic/pic.toml").expanduser()
PROJECT_CONFIG = "pic.toml"

#: Default paths shared into the container (existing ones only; `~`, $HOME
#: and {uid} are expanded later).  The workspace itself is always shared.
DEFAULT_SHARES = [
    "/tmp",
    "~/.agents",
    "~/.pi",
    "~/.ssh",
    "~/.gitconfig",
]

#: Default environment variable regexps passed into the container:
#: LLM provider API keys and similar secrets.
DEFAULT_PRESERVES = [
    r"^(ANTHROPIC|OPENAI|KIMI|MOONSHOT|DEEPSEEK|GEMINI|GOOGLE|OPENROUTER|"
    r"GROQ|MISTRAL|XAI|TOGETHER|AZURE_OPENAI|HF|HUGGING_FACE)_",
]


@dataclass
class Config:
    """Merged configuration; the single object backends read from."""

    backend: str = "auto"                      # guix | oci | auto
    extra_shares: list[str] = field(default_factory=list)
    extra_preserves: list[str] = field(default_factory=list)
    runtime: str | None = None                 # --runtime / PIC_RUNTIME
    no_project: bool = False

    guix_profile: str = "~/.guix-home/extra-profiles/agent"
    guix_manifest: str | None = None           # default: example shipped with pic
    guix_channels: list[str] = field(default_factory=list)
    guix_network: bool = True

    oci_driver: str = "auto"                   # podman | docker | auto
    oci_image: str = "ghcr.io/meex/pi-agent:latest"
    oci_network: str = "host"

    @property
    def shares(self):
        return DEFAULT_SHARES + self.extra_shares

    @property
    def preserves(self):
        return DEFAULT_PRESERVES + self.extra_preserves


def _read_toml(path):
    """Return the parsed TOML, or {} when the file does not exist."""
    if not path.is_file():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        die(f"pic: bad configuration file {path}: {e}")


def _apply_toml(cfg, data, source):
    pic = data.get("pic", {})
    if "backend" in pic:
        cfg.backend = str(pic["backend"])
    if "no_project" in pic:
        cfg.no_project = bool(pic["no_project"])
    shares = data.get("shares", {})
    if "add" in shares:
        cfg.extra_shares += [str(p) for p in shares["add"]]
    env = data.get("env", {})
    if "preserve" in env:
        cfg.extra_preserves += [str(r) for r in env["preserve"]]
    guix = data.get("backend", {}).get("guix", {})
    if "profile" in guix:
        cfg.guix_profile = str(guix["profile"])
    if "manifest" in guix:
        cfg.guix_manifest = str(guix["manifest"])
    if "channels" in guix:
        cfg.guix_channels = [str(c) for c in guix["channels"]]
    if "network" in guix:
        cfg.guix_network = bool(guix["network"])
    oci = data.get("backend", {}).get("oci", {})
    if "driver" in oci:
        cfg.oci_driver = str(oci["driver"])
    if "image" in oci:
        cfg.oci_image = str(oci["image"])
    if "network" in oci:
        cfg.oci_network = str(oci["network"])


def _apply_env(cfg, env):
    if env.get("PIC_BACKEND"):
        cfg.backend = env["PIC_BACKEND"]
    for entry in env.get("PIC_SHARE", "").split(":"):
        if entry:
            cfg.extra_shares.append(entry)
    for regexp in env.get("PIC_PRESERVE", "").split():
        cfg.extra_preserves.append(regexp)
    if env.get("PIC_RUNTIME"):
        cfg.runtime = env["PIC_RUNTIME"]
    if env.get("PIC_NO_PROJECT"):
        cfg.no_project = True


def _apply_cli(cfg, parsed):
    if parsed.backend:
        cfg.backend = parsed.backend
    cfg.extra_shares += parsed.shares
    cfg.extra_preserves += parsed.preserves
    if parsed.runtime:
        cfg.runtime = parsed.runtime
    if parsed.no_project:
        cfg.no_project = True


def load_config(project_dir=None, env=None, parsed=None):
    """Load and merge the configuration.  Parsed is the cli.Parsed result."""
    env = env if env is not None else os.environ
    cfg = Config()
    _apply_toml(cfg, _read_toml(USER_CONFIG), USER_CONFIG)
    if project_dir:
        _apply_toml(cfg, _read_toml(Path(project_dir) / PROJECT_CONFIG),
                    PROJECT_CONFIG)
    _apply_env(cfg, env)
    if parsed is not None:
        _apply_cli(cfg, parsed)
    if cfg.guix_manifest is None:
        cfg.guix_manifest = str(resources.default_manifest())
    return cfg
