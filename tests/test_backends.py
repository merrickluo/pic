"""Golden-argv and behavior tests for the backends (pic/backends/)."""

import pytest

from pic.backends import BACKENDS, select_backend
from pic.backends.apple import AppleBackend, inherit_env
from pic.backends.guix import GuixBackend
from pic.backends.oci import OciBackend, expand_env
from pic.config import Config
from pic.spec import ProjectEnv, RuntimeSpec
from pic.util import PicError
from pathlib import Path

ENV = {"HOME": "/home/tester", "PATH": "/bin"}


def spec(workspace="/w", shares=("/s1", "/s2"), preserves=("^A_",),
         runtime=None, project=None, command=("pi", "--continue")):
    return RuntimeSpec(
        workspace=Path(workspace),
        shares=[Path(p) for p in shares],
        preserves=list(preserves),
        runtime=runtime,
        project=project,
        command=list(command),
    )


# --- guix backend ---------------------------------------------------

def test_guix_manifest_mode_golden_argv():
    cfg = Config(guix_manifest="/m.scm", guix_channels=["/ch"])
    argv = GuixBackend().build_argv(spec(), cfg, ENV)
    assert argv[:3] == ["guix", "shell", "-C"]
    assert "--network" in argv
    assert "--share=/s1" in argv and "--share=/s2" in argv
    assert "--preserve=^A_" in argv
    assert "-L" in argv and "/ch" in argv
    assert argv[-5:] == ["-m", "/m.scm", "--", "pi", "--continue"]


def test_guix_workspace_not_shared_twice():
    cfg = Config()
    s = spec(workspace="/w", shares=("/w", "/s1"))
    argv = GuixBackend().build_argv(s, cfg, ENV)
    assert argv.count("--share=/w") == 0


def test_guix_channels_expand_tilde():
    cfg = Config(guix_manifest="/m.scm", guix_channels=["~/ch"])
    argv = GuixBackend().build_argv(spec(), cfg, ENV)
    assert "/home/tester/ch" in argv


def test_guix_project_env_golden_argv():
    cfg = Config(guix_channels=["/ch1", "/ch2"], guix_manifest="/m.scm")
    project = ProjectEnv(container_args=["-D", "-f", "/w/guix.scm"])
    argv = GuixBackend().build_argv(spec(project=project), cfg, ENV)
    assert "-L" in argv and "/ch1" in argv and "/ch2" in argv
    assert "-m" in argv and "/m.scm" in argv
    assert argv[-6:] == ["-D", "-f", "/w/guix.scm", "--", "pi", "--continue"]


def test_guix_network_off():
    cfg = Config(guix_network=False)
    argv = GuixBackend().build_argv(spec(), cfg, ENV)
    assert "--network" not in argv


def test_guix_validate_missing_manifest_raises():
    cfg = Config(guix_manifest="/does/not/exist/m.scm")
    with pytest.raises(PicError, match="manifest not found"):
        GuixBackend().validate(spec(), cfg, ENV)


def test_guix_validate_present_manifest_passes(tmp_path):
    manifest = tmp_path / "m.scm"
    manifest.write_text("(specifications->manifest '())\n")
    cfg = Config(guix_manifest=str(manifest))
    GuixBackend().validate(spec(), cfg, ENV)  # must not raise


def test_guix_validate_missing_channel_raises(tmp_path):
    manifest = tmp_path / "m.scm"
    manifest.write_text("(specifications->manifest '())\n")
    cfg = Config(guix_manifest=str(manifest),
                 guix_channels=["~/no/such/channel"])
    with pytest.raises(PicError, match="channel not found"):
        GuixBackend().validate(spec(), cfg, ENV)


def test_guix_project_env_guix_scm_dev_mode(tmp_path):
    (tmp_path / "guix.scm").write_text("(define-public x 1)\n")
    env = GuixBackend().project_env(tmp_path, Config())
    assert env.container_args == ["-D", "-f", str(tmp_path / "guix.scm")]


def test_guix_project_env_manifest_scm(tmp_path):
    (tmp_path / "manifest.scm").write_text("(specifications->manifest '())\n")
    env = GuixBackend().project_env(tmp_path, Config())
    assert env.container_args == ["-m", str(tmp_path / "manifest.scm")]


def test_guix_project_env_none(tmp_path):
    assert GuixBackend().project_env(tmp_path, Config()) is None


# --- oci backend ----------------------------------------------------

def test_oci_golden_argv():
    cfg = Config(oci_driver="podman")
    env = dict(ENV, ANTHROPIC_API_KEY="sk-123")
    argv = OciBackend().build_argv(
        spec(workspace="/w", preserves=("^ANTHROPIC_",)), cfg, env)
    assert argv[:6] == ["podman", "run", "--rm", "-it", "--network", "host"]
    assert "-v/s1:/s1" in argv and "-v/s2:/s2" in argv
    assert "-e" in argv and "ANTHROPIC_API_KEY=sk-123" in argv
    assert argv[-5:] == ["-w", "/w", "ghcr.io/merrickluo/pi-agent:latest",
                         "pi", "--continue"]


def test_oci_sets_home_env():
    """The container runs as the image user (root); point $HOME at the
    mounted host home so pi finds ~/.pi, ~/.ssh, ~/.gitconfig, ..."""
    cfg = Config(oci_driver="podman")
    argv = OciBackend().build_argv(spec(), cfg, ENV)
    assert "-e" in argv and "HOME=/home/tester" in argv


def test_oci_runtime_overrides_image():
    cfg = Config(oci_driver="docker", oci_image="default:1")
    argv = OciBackend().build_argv(spec(runtime="custom:2"), cfg, ENV)
    assert "custom:2" in argv and "default:1" not in argv


def test_oci_network_config():
    cfg = Config(oci_driver="podman", oci_network="bridge")
    argv = OciBackend().build_argv(spec(), cfg, ENV)
    assert "--network" in argv and "bridge" in argv


def test_oci_driver_autodetect_podman_first(monkeypatch):
    seen = []
    monkeypatch.setattr("pic.backends.oci.shutil.which",
                        lambda name: seen.append(name) or name)
    cfg = Config()
    assert OciBackend()._driver(cfg, ENV) == "podman"
    assert seen == ["podman"]  # short-circuits on the first driver found


def test_oci_no_driver_validate_raises(monkeypatch):
    monkeypatch.setattr("pic.backends.oci.shutil.which", lambda n: None)
    with pytest.raises(PicError, match="no OCI driver"):
        OciBackend().validate(spec(), Config(), ENV)


def test_oci_project_env_none(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    assert OciBackend().project_env(tmp_path, Config()) is None


def test_expand_env_matches_regexps():
    env = {"ANTHROPIC_API_KEY": "a", "OPENAI_KEY": "b",
           "MYVAR_1": "c", "HOME": "/h"}
    pairs = expand_env([r"^(ANTHROPIC|OPENAI)_", "^MYVAR_"], env)
    assert pairs == [("ANTHROPIC_API_KEY", "a"), ("OPENAI_KEY", "b"),
                     ("MYVAR_1", "c")]


# --- apple backend -------------------------------------------------

def test_apple_golden_argv():
    cfg = Config(apple_image="img:1")
    env = dict(ENV, ANTHROPIC_API_KEY="sk-123")
    argv = AppleBackend().build_argv(
        spec(workspace="/w", shares=("/s1",), preserves=("^ANTHROPIC_",),
             command=("pi",)), cfg, env)
    assert argv[:4] == ["container", "run", "--rm", "-it"]
    assert "--network" in argv and "default" in argv
    assert "--init" in argv and "--ssh" in argv
    assert "-v/s1:/s1" in argv
    assert "-e" in argv and "ANTHROPIC_API_KEY" in argv
    assert "sk-123" not in argv  # bare key; the tool inherits the value
    assert argv[-4:] == ["-w", "/w", "img:1", "pi"]


def test_apple_sets_home_env():
    """Same $HOME fix as oci: the Linux image runs as root, the mounted
    shares are host-home paths."""
    cfg = Config()
    argv = AppleBackend().build_argv(spec(command=("pi",)), cfg, ENV)
    assert "-e" in argv and "HOME=/home/tester" in argv


def test_apple_runtime_overrides_image():
    cfg = Config(apple_image="default:1")
    argv = AppleBackend().build_argv(spec(runtime="custom:2", command=("pi",)),
                                     cfg, ENV)
    assert "custom:2" in argv and "default:1" not in argv


def test_apple_init_ssh_toggle():
    cfg = Config(apple_init=False, apple_ssh=False)
    argv = AppleBackend().build_argv(spec(command=("pi",)), cfg, ENV)
    assert "--init" not in argv and "--ssh" not in argv


def test_apple_inherit_env_bare_keys():
    env = {"ANTHROPIC_API_KEY": "a", "OPENAI_KEY": "b", "MYVAR_1": "c",
           "HOME": "/h"}
    keys = inherit_env([r"^(ANTHROPIC|OPENAI)_", "^MYVAR_"], env)
    assert keys == ["ANTHROPIC_API_KEY", "OPENAI_KEY", "MYVAR_1"]


def test_apple_no_container_validate_raises(monkeypatch):
    monkeypatch.setattr("pic.backends.apple.shutil.which", lambda n: None)
    with pytest.raises(PicError, match="container"):
        AppleBackend().validate(spec(), Config(), ENV)


def test_apple_project_env_none(tmp_path):
    assert AppleBackend().project_env(tmp_path, Config()) is None


# --- registry -------------------------------------------------------

def test_backend_registry():
    assert set(BACKENDS) == {"guix", "oci", "apple"}


def test_select_backend_explicit(monkeypatch):
    assert select_backend(Config(backend="oci")) is BACKENDS["oci"]


def test_select_backend_auto_prefers_guix(monkeypatch):
    monkeypatch.setattr(BACKENDS["guix"], "available", lambda: True)
    monkeypatch.setattr(BACKENDS["oci"], "available", lambda: True)
    assert select_backend(Config()) is BACKENDS["guix"]


def test_select_backend_auto_falls_back_to_oci(monkeypatch):
    monkeypatch.setattr(BACKENDS["guix"], "available", lambda: False)
    monkeypatch.setattr(BACKENDS["oci"], "available", lambda: True)
    assert select_backend(Config()) is BACKENDS["oci"]


def test_select_backend_auto_falls_back_to_apple(monkeypatch):
    monkeypatch.setattr(BACKENDS["guix"], "available", lambda: False)
    monkeypatch.setattr(BACKENDS["oci"], "available", lambda: False)
    monkeypatch.setattr(BACKENDS["apple"], "available", lambda: True)
    assert select_backend(Config()) is BACKENDS["apple"]


def test_select_backend_unknown_dies(capsys):
    with pytest.raises(SystemExit) as exc:
        select_backend(Config(backend="nope"))
    assert exc.value.code == 1
    assert "unknown backend" in capsys.readouterr().err
