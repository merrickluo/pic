"""Profile-cache tests for the guix backend (pic/backends/guix.py).

The cache builds the agent profile once per cache key with
`guix shell --root=PROFILE ... -- true` and then launches containers
with `guix shell -C -p PROFILE`, skipping manifest/channel evaluation
on every launch.  A channel enters the key only by its HEAD commit:
uncommitted changes never invalidate the cache.
"""

import os
import subprocess
from pathlib import Path

import pytest

import pic.launch
from pic.backends.base import HOME_SHIM
from pic.backends.guix import GuixBackend
from pic.cli import Parsed
from pic.config import Config
from pic.spec import ProjectEnv, RuntimeSpec
from pic.util import PicError

ENV = {"HOME": "/home/tester", "PATH": "/bin"}


def spec(workspace="/w", shares=("/s1", "/s2"), preserves=("^A_",),
         project=None, command=("pi", "--continue")):
    return RuntimeSpec(
        workspace=Path(workspace),
        shares=[Path(p) for p in shares],
        preserves=list(preserves),
        runtime=None,
        project=project,
        command=list(command),
    )


def make_env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return dict(ENV, HOME=str(home))


def manifest(tmp_path, name="agent.scm", text="(specifications->manifest '())\n"):
    path = tmp_path / name
    path.write_text(text)
    return path


def git_repo(path):
    path.mkdir(parents=True)
    (path / "x.scm").write_text("(define-public x 1)\n")
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for key, value in (("user.email", "tester@example.com"),
                       ("user.name", "tester"),
                       ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(path), "config", key, value],
                       check=True)
    commit_all(path, "init")
    return path


def commit_all(path, message):
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q",
                    "--allow-empty", "-m", message], check=True)


def profile_arg(argv):
    return Path(argv[argv.index("-p") + 1])


def fake_run(calls):
    """subprocess.run stub: records `guix` invocations (the profile
    build), delegates everything else (git status) to the real one."""
    real = subprocess.run

    def run(argv, **kw):
        if argv[0] == "guix":
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0)
        return real(argv, **kw)

    return run


def cached_setup(tmp_path):
    env = make_env(tmp_path)
    cfg = Config(guix_manifest=str(manifest(tmp_path)),
                 guix_channels=[str(git_repo(tmp_path / "meex"))])
    return cfg, env


# --- cached argv ----------------------------------------------------

def test_cached_argv_uses_profile_not_manifest(tmp_path):
    cfg, env = cached_setup(tmp_path)
    argv = GuixBackend().build_argv(spec(), cfg, env)
    assert argv[:3] == ["guix", "shell", "-C"]
    assert "-m" not in argv and "-L" not in argv
    profile = profile_arg(argv)
    root = Path(env["HOME"]) / ".local/share/pic/profiles"
    assert profile.parent.parent == root  # root/<base-key>/<project-key>
    assert len(profile.parent.name) == 64 and len(profile.name) == 64
    assert argv[-7:] == ["--", "sh", "-c", HOME_SHIM, "sh", "pi",
                         "--continue"]


def test_cached_argv_keeps_shares_and_network(tmp_path):
    cfg, env = cached_setup(tmp_path)
    argv = GuixBackend().build_argv(spec(), cfg, env)
    assert "--network" in argv
    assert "--share=/s1" in argv and "--share=/s2" in argv
    assert "--preserve=^A_" in argv


def test_profile_cache_disabled_uses_direct_mode(tmp_path):
    cfg, env = cached_setup(tmp_path)
    cfg.guix_profile_cache = False
    argv = GuixBackend().build_argv(spec(), cfg, env)
    assert "-p" not in argv
    assert "-m" in argv and cfg.guix_manifest in argv
    assert "-L" in argv and cfg.guix_channels[0] in argv


# --- cache key ------------------------------------------------------

def test_key_changes_with_manifest_content(tmp_path):
    cfg, env = cached_setup(tmp_path)
    first = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    Path(cfg.guix_manifest).write_text("(specifications->manifest '(\"pi\"))\n")
    second = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    assert first != second


def test_key_changes_with_channel_commit(tmp_path):
    cfg, env = cached_setup(tmp_path)
    first = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    channel = Path(cfg.guix_channels[0])
    (channel / "y.scm").write_text("(define-public y 2)\n")
    commit_all(channel, "add y")
    second = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    assert first != second


def test_key_changes_with_project_env_content(tmp_path):
    cfg, env = cached_setup(tmp_path)
    project_manifest = manifest(tmp_path, "project.scm")
    project = ProjectEnv(container_args=["-m", str(project_manifest)])
    first = profile_arg(GuixBackend().build_argv(spec(project=project),
                                                 cfg, env))
    project_manifest.write_text("(specifications->manifest '(\"gcc\"))\n")
    second = profile_arg(GuixBackend().build_argv(spec(project=project),
                                                  cfg, env))
    assert first != second


def test_key_changes_with_project_env_mode(tmp_path):
    """`-D -f guix.scm` (dev environment) and `-m guix.scm` build
    different profiles from the same file."""
    cfg, env = cached_setup(tmp_path)
    guix_scm = manifest(tmp_path, "guix.scm", "(define-public p 1)\n")
    dev = ProjectEnv(container_args=["-D", "-f", str(guix_scm)])
    plain = ProjectEnv(container_args=["-m", str(guix_scm)])
    assert profile_arg(GuixBackend().build_argv(spec(project=dev), cfg, env)) \
        != profile_arg(GuixBackend().build_argv(spec(project=plain), cfg, env))


def test_project_env_changes_only_project_key(tmp_path):
    cfg, env = cached_setup(tmp_path)
    project = ProjectEnv(container_args=["-m", str(manifest(tmp_path, "p.scm"))])
    bare = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    with_project = profile_arg(
        GuixBackend().build_argv(spec(project=project), cfg, env))
    assert bare.parent == with_project.parent
    assert bare.name != with_project.name


def test_channel_commit_changes_base_key(tmp_path):
    cfg, env = cached_setup(tmp_path)
    first = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    commit_all(Path(cfg.guix_channels[0]), "bump")
    second = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    assert first.parent != second.parent


def test_key_stable_across_backends(tmp_path):
    cfg, env = cached_setup(tmp_path)
    assert profile_arg(GuixBackend().build_argv(spec(), cfg, env)) \
        == profile_arg(GuixBackend().build_argv(spec(), cfg, env))


def test_untracked_scm_file_keeps_key(tmp_path):
    cfg, env = cached_setup(tmp_path)
    first = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    (Path(cfg.guix_channels[0]) / "new.scm").write_text("(define n 1)\n")
    assert profile_arg(GuixBackend().build_argv(spec(), cfg, env)) == first


def test_tracked_modification_keeps_key(tmp_path):
    cfg, env = cached_setup(tmp_path)
    first = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    (Path(cfg.guix_channels[0]) / "x.scm").write_text("(define x 42)\n")
    assert profile_arg(GuixBackend().build_argv(spec(), cfg, env)) == first


def test_staged_change_keeps_key(tmp_path):
    cfg, env = cached_setup(tmp_path)
    first = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    x_scm = Path(cfg.guix_channels[0]) / "x.scm"
    x_scm.write_text("(define x 42)\n")
    subprocess.run(["git", "-C", str(x_scm.parent), "add", "x.scm"],
                   check=True)
    assert profile_arg(GuixBackend().build_argv(spec(), cfg, env)) == first


# --- prepare: building the profile -----------------------------------

def test_prepare_builds_missing_profile(tmp_path, monkeypatch):
    cfg, env = cached_setup(tmp_path)
    calls = []
    monkeypatch.setattr(subprocess, "run", fake_run(calls))
    backend = GuixBackend()
    backend.prepare(spec(), cfg, env)
    assert len(calls) == 1
    argv = calls[0]
    profile = profile_arg(backend.build_argv(spec(), cfg, env))
    assert argv[:2] == ["guix", "shell"]
    assert f"--root={profile}" in argv
    assert "-L" in argv and cfg.guix_channels[0] in argv
    assert "-m" in argv and cfg.guix_manifest in argv
    assert argv[-2:] == ["--", "true"]


def test_prepare_passes_project_env_args(tmp_path, monkeypatch):
    cfg, env = cached_setup(tmp_path)
    calls = []
    monkeypatch.setattr(subprocess, "run", fake_run(calls))
    guix_scm = manifest(tmp_path, "guix.scm", "(define-public p 1)\n")
    project = ProjectEnv(container_args=["-D", "-f", str(guix_scm)])
    GuixBackend().prepare(spec(project=project), cfg, env)
    assert "-D" in calls[0] and str(guix_scm) in calls[0]


def test_prepare_skips_existing_profile(tmp_path, monkeypatch):
    cfg, env = cached_setup(tmp_path)
    backend = GuixBackend()
    profile = profile_arg(backend.build_argv(spec(), cfg, env))
    profile.parent.mkdir(parents=True)
    profile.symlink_to("/gnu/store/fake-profile")
    calls = []
    monkeypatch.setattr(subprocess, "run", fake_run(calls))
    backend.prepare(spec(), cfg, env)
    assert calls == []


def test_prepare_build_failure_raises(tmp_path, monkeypatch):
    cfg, env = cached_setup(tmp_path)

    def fail(argv, **kw):
        raise subprocess.CalledProcessError(1, argv)

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(PicError, match="profile"):
        GuixBackend().prepare(spec(), cfg, env)


def test_prepare_builds_profile_on_dirty_channel(tmp_path, monkeypatch):
    cfg, env = cached_setup(tmp_path)
    (Path(cfg.guix_channels[0]) / "x.scm").write_text("(define x 2)\n")
    calls = []
    monkeypatch.setattr(subprocess, "run", fake_run(calls))
    GuixBackend().prepare(spec(), cfg, env)
    assert len(calls) == 1


# --- pruning stale profiles -----------------------------------------

def fake_profile(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to("/gnu/store/fake-profile")


def test_prepare_prunes_other_bases_after_build(tmp_path, monkeypatch):
    cfg, env = cached_setup(tmp_path)
    old = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    fake_profile(old)
    root = old.parent.parent
    legacy = root / ("0" * 64)  # flat layout from older pic
    legacy.symlink_to("/gnu/store/legacy-profile")
    commit_all(Path(cfg.guix_channels[0]), "bump")
    monkeypatch.setattr(subprocess, "run", fake_run([]))
    backend = GuixBackend()
    backend.prepare(spec(), cfg, env)
    current_base = profile_arg(backend.build_argv(spec(), cfg, env)).parent
    assert sorted(root.iterdir()) == [current_base]


def test_prepare_keeps_other_projects_of_current_base(tmp_path, monkeypatch):
    cfg, env = cached_setup(tmp_path)
    project = ProjectEnv(container_args=["-m", str(manifest(tmp_path, "p.scm"))])
    other = profile_arg(GuixBackend().build_argv(spec(project=project),
                                                 cfg, env))
    fake_profile(other)
    monkeypatch.setattr(subprocess, "run", fake_run([]))
    GuixBackend().prepare(spec(), cfg, env)
    assert os.path.lexists(other)


def test_prepare_failure_keeps_old_bases(tmp_path, monkeypatch):
    cfg, env = cached_setup(tmp_path)
    old = profile_arg(GuixBackend().build_argv(spec(), cfg, env))
    fake_profile(old)
    commit_all(Path(cfg.guix_channels[0]), "bump")

    def fail(argv, **kw):
        if argv[0] == "guix":
            raise subprocess.CalledProcessError(1, argv)
        return subprocess.CompletedProcess(argv, 0, stdout="x\n")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(PicError):
        GuixBackend().prepare(spec(), cfg, env)
    assert os.path.lexists(old)


# --- launch orchestration --------------------------------------------

def test_run_pic_prepares_before_exec(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    order = []
    monkeypatch.setattr(GuixBackend, "available", lambda self: True)
    monkeypatch.setattr(GuixBackend, "prepare",
                        lambda self, s, c, e: order.append("prepare"))
    monkeypatch.setattr(pic.launch.os, "execv",
                        lambda binary, argv: order.append("exec"))
    monkeypatch.setattr(pic.launch.shutil, "which",
                        lambda name, **kw: "/bin/guix")
    env = make_env(tmp_path)
    pic.launch.run_pic(Parsed(), env=env)
    assert order == ["prepare", "exec"]


def test_dry_run_does_not_prepare(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(GuixBackend, "available", lambda self: True)

    def boom(self, s, c, e):
        raise AssertionError("prepare must not run on --dry-run")

    monkeypatch.setattr(GuixBackend, "prepare", boom)
    env = make_env(tmp_path)
    assert pic.launch.run_pic(Parsed(dry_run=True), env=env) == 0
    assert "guix" in capsys.readouterr().out
