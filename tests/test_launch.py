"""Tests for launch orchestration (pic/launch.py)."""

import pic.cli as cli
from pic.config import load_config
from pic.launch import config_project_dir


def test_config_project_dir_defaults_to_cwd(tmp_path, monkeypatch):
    """A bare `pic` inside a project reads that project's pic.toml."""
    monkeypatch.chdir(tmp_path)
    assert config_project_dir(cli.Parsed(), {}) == str(tmp_path)


def test_config_project_dir_explicit_arg():
    assert config_project_dir(cli.Parsed(project_dir="/p"), {}) == "/p"


def test_config_project_dir_no_project_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert config_project_dir(cli.Parsed(no_project=True), {}) is None


def test_config_project_dir_no_project_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert config_project_dir(cli.Parsed(), {"PIC_NO_PROJECT": "1"}) is None


def test_bare_pic_reads_cwd_pic_toml(tmp_path, monkeypatch):
    (tmp_path / "pic.toml").write_text('[pic]\ncommand = "bash"\n')
    monkeypatch.chdir(tmp_path)
    project_dir = config_project_dir(cli.Parsed(), {"HOME": "/h"})
    cfg = load_config(project_dir, env={"HOME": "/h"})
    assert cfg.command == "bash"
