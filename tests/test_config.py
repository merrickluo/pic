"""Tests for configuration loading and precedence (pic/config.py)."""

import pytest

import pic.cli as cli
import pic.config as config


def write_toml(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def load(project_dir=None, env=None, parsed=None):
    env = {"HOME": "/home/tester"} if env is None else env
    return config.load_config(project_dir, env=env, parsed=parsed)


# --- defaults -------------------------------------------------------

def test_builtin_defaults():
    cfg = load()
    assert cfg.backend == "auto"
    assert cfg.command == "pi"
    assert cfg.oci_image == "ghcr.io/merrickluo/pi-agent:latest"
    assert any("~/.agents" in s for s in cfg.shares)
    assert any("ANTHROPIC" in r for r in cfg.preserves)
    assert cfg.guix_manifest  # shipped default resolved


# --- pic.toml layers -------------------------------------------------

def test_project_toml_overrides_and_appends(tmp_path):
    write_toml(tmp_path / "pic.toml", """
[pic]
backend = "oci"
no_project = true

[shares]
add = ["~/.config/mytool"]

[env]
preserve = ["^MYCORP_"]

[backend.oci]
image = "registry.example/pi:1"
""")
    cfg = load(project_dir=str(tmp_path))
    assert cfg.backend == "oci"
    assert cfg.no_project
    assert cfg.extra_shares == ["~/.config/mytool"]
    assert cfg.extra_preserves == ["^MYCORP_"]
    assert cfg.oci_image == "registry.example/pi:1"


def test_user_toml_applied_without_project(tmp_path, monkeypatch):
    user = tmp_path / "user.toml"
    write_toml(user, """
[backend.guix]
channels = ["/home/tester/projs/meex"]
""")
    monkeypatch.setattr(config, "USER_CONFIG", user)
    cfg = load()
    assert cfg.guix_channels == ["/home/tester/projs/meex"]


def test_project_toml_wins_over_user(tmp_path, monkeypatch):
    user = tmp_path / "user.toml"
    write_toml(user, '[pic]\nbackend = "guix"\n')
    write_toml(tmp_path / "proj" / "pic.toml", '[pic]\nbackend = "oci"\n')
    monkeypatch.setattr(config, "USER_CONFIG", user)
    cfg = load(project_dir=str(tmp_path / "proj"))
    assert cfg.backend == "oci"


def test_bad_toml_dies(tmp_path, capsys):
    write_toml(tmp_path / "pic.toml", "[unclosed\n")
    with pytest.raises(SystemExit) as exc:
        load(project_dir=str(tmp_path))
    assert exc.value.code == 1
    assert "bad configuration file" in capsys.readouterr().err


# --- default command ------------------------------------------------

def test_toml_command(tmp_path):
    write_toml(tmp_path / "pic.toml", '[pic]\ncommand = "claude"\n')
    cfg = load(project_dir=str(tmp_path))
    assert cfg.command == "claude"


def test_env_command_overrides_toml(tmp_path):
    write_toml(tmp_path / "pic.toml", '[pic]\ncommand = "claude"\n')
    env = {"HOME": "/home/tester", "PIC_COMMAND": "fish"}
    cfg = load(project_dir=str(tmp_path), env=env)
    assert cfg.command == "fish"


def test_cli_command_wins_over_env():
    env = {"HOME": "/home/tester", "PIC_COMMAND": "fish"}
    parsed = cli.Parsed(command="aider")
    cfg = load(env=env, parsed=parsed)
    assert cfg.command == "aider"


# --- environment and flags ------------------------------------------

def test_env_overrides_project(tmp_path):
    write_toml(tmp_path / "pic.toml", '[pic]\nbackend = "guix"\n')
    env = {"HOME": "/home/tester", "PIC_BACKEND": "oci",
           "PIC_SHARE": "/a:/b", "PIC_PRESERVE": "^A_ ^B_",
           "PIC_RUNTIME": "img:1", "PIC_NO_PROJECT": "1"}
    cfg = load(project_dir=str(tmp_path), env=env)
    assert cfg.backend == "oci"
    assert cfg.extra_shares == ["/a", "/b"]
    assert cfg.extra_preserves == ["^A_", "^B_"]
    assert cfg.runtime == "img:1"
    assert cfg.no_project


def test_cli_wins_over_env():
    env = {"HOME": "/home/tester", "PIC_BACKEND": "oci"}
    parsed = cli.Parsed(backend="guix", shares=["/cli"], preserves=["^C_"],
                        runtime="prof", no_project=True)
    cfg = load(env=env, parsed=parsed)
    assert cfg.backend == "guix"
    assert cfg.extra_shares == ["/cli"]
    assert cfg.extra_preserves == ["^C_"]
    assert cfg.runtime == "prof"
    assert cfg.no_project


def test_accumulation_order(tmp_path):
    # shares/preserves accumulate: project first, then env, then flags
    write_toml(tmp_path / "pic.toml", """
[shares]
add = ["/proj"]

[env]
preserve = ["^PROJ_"]
""")
    env = {"HOME": "/home/tester", "PIC_SHARE": "/env",
           "PIC_PRESERVE": "^ENV_"}
    parsed = cli.Parsed(shares=["/cli"], preserves=["^CLI_"])
    cfg = load(project_dir=str(tmp_path), env=env, parsed=parsed)
    assert cfg.extra_shares == ["/proj", "/env", "/cli"]
    assert cfg.extra_preserves == ["^PROJ_", "^ENV_", "^CLI_"]
