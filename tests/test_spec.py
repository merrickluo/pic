"""Tests for spec assembly (pic/spec.py): workspace, share expansion."""

import pytest

from pic.config import Config
from pic.spec import RuntimeSpec, assemble


def test_workspace_always_shared(tmp_path):
    spec = assemble(Config(), str(tmp_path), ["pi"], env={"HOME": "/h"})
    assert spec.workspace == tmp_path.resolve()
    assert spec.workspace in spec.shares
    assert spec.command == ["pi"]
    assert spec.project is None


def test_missing_shares_skipped_with_warning(tmp_path, capsys):
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    cfg = Config(extra_shares=["/does/not/exist", "~/.ssh"])
    spec = assemble(cfg, str(tmp_path), ["pi"], env={"HOME": str(home)})
    paths = [str(p) for p in spec.shares]
    assert "/does/not/exist" not in paths
    assert str(home / ".ssh") in paths
    err = capsys.readouterr().err
    assert "skipping share" in err
    assert "/does/not/exist" in err


def test_uid_expansion(tmp_path, monkeypatch):
    cfg = Config(extra_shares=["/run/user/{uid}/gnupg"])
    import os
    real_exists = os.path.exists
    # hermetic: /run/user/<uid> may not exist on the build machine
    monkeypatch.setattr("pic.spec.os.path.exists",
                        lambda p: True if str(p).startswith("/run/user/")
                        else real_exists(p))
    spec = assemble(cfg, str(tmp_path), ["pi"], env={"HOME": "/h"})
    assert any(p.name == "gnupg" and str(p) == f"/run/user/{os.getuid()}/gnupg"
               for p in spec.shares)


def test_missing_project_dir_dies(capsys):
    with pytest.raises(SystemExit) as exc:
        assemble(Config(), "/does/not/exist/xyz", ["pi"],
                 env={"HOME": "/h"})
    assert exc.value.code == 1
    assert "project directory not found" in capsys.readouterr().err


def test_preserves_copied():
    cfg = Config(extra_preserves=["^MYVAR_"])
    spec = assemble(cfg, "/tmp", ["pi"], env={"HOME": "/h"})
    assert any("^MYVAR_" in r for r in spec.preserves)
    assert spec.preserves is not cfg.preserves  # copied, not aliased


def test_runtime_passthrough():
    spec = assemble(Config(runtime="img:1"), "/tmp", ["pi"],
                    env={"HOME": "/h"})
    assert spec.runtime == "img:1"


def test_spec_dataclass_fields():
    spec = RuntimeSpec(
        workspace=__import__("pathlib").Path("/w"),
        shares=[__import__("pathlib").Path("/s")],
        preserves=["^X_"],
        runtime="r",
        project=None,
        command=["pi"],
    )
    assert spec.workspace == __import__("pathlib").Path("/w")
    assert spec.shares == [__import__("pathlib").Path("/s")]
