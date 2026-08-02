"""Tests for the syntactic `--` routing contract (pic/cli.py)."""

import pytest

import pic.cli as cli
from pic.spec import inner_command


def parse(argv, prog="pic"):
    return cli.parse(list(argv), prog)


# --- the `--` boundary ----------------------------------------------

def test_split_double_dash():
    assert cli.split_double_dash(["-s", "/x", "--", "--model", "x"]) == (
        ["-s", "/x"], ["--model", "x"])
    assert cli.split_double_dash(["--"]) == ([], [])
    assert cli.split_double_dash(["a", "b"]) == (["a", "b"], [])


def test_after_dashdash_goes_verbatim_to_inner():
    p = parse(["--", "--help", "--model", "sonnet", "@f"])
    assert p.inner == ["--help", "--model", "sonnet", "@f"]


def test_help_after_dashdash_is_pis_help_not_pics():
    # pic must never intercept args after `--`
    p = parse(["--", "--help"])
    assert p.inner == ["--help"]


# --- pic's own options ----------------------------------------------

def test_defaults():
    p = parse([])
    assert p.project_dir is None
    assert p.inner == []
    assert p.backend is None
    assert p.shares == []
    assert p.preserves == []


def test_project_dir_positional():
    p = parse(["/tmp/proj", "--no-project"], "pic")
    assert p.project_dir == "/tmp/proj"
    assert p.no_project


def test_unknown_long_option_raises_with_hint():
    with pytest.raises(cli.UsageError, match="--model"):
        parse(["--model", "sonnet"])
    with pytest.raises(cli.UsageError, match="after a bare"):
        parse(["--continue"])


def test_unknown_short_option_raises():
    with pytest.raises(cli.UsageError):
        parse(["-x"])


def test_second_bare_word_raises():
    with pytest.raises(cli.UsageError, match="only one project"):
        parse(["/a", "/b"])


def test_value_options():
    p = parse(["--backend", "oci", "--share", "/x", "--share=/y",
               "--preserve", "^A_", "--preserve=^B_", "--runtime", "img"])
    assert p.backend == "oci"
    assert p.shares == ["/x", "/y"]
    assert p.preserves == ["^A_", "^B_"]
    assert p.runtime == "img"


def test_short_value_options():
    p = parse(["-b", "guix", "-s", "/x", "-e", "^A_"])
    assert p.backend == "guix"
    assert p.shares == ["/x"]
    assert p.preserves == ["^A_"]


def test_missing_value_raises():
    with pytest.raises(cli.UsageError, match="missing value"):
        parse(["--backend"])


def test_flags():
    p = parse(["--no-project", "--list-backends"])
    assert p.no_project
    assert p.list_backends


def test_help_exits_zero_and_prints_pic_help(capsys):
    with pytest.raises(SystemExit) as exc:
        parse(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "PIC_SHARE" in out
    assert "PIC_PRESERVE" in out
    assert "no table of pi's options" in out


def test_version_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        parse(["--version"])
    assert exc.value.code == 0
    assert "pic" in capsys.readouterr().out


# --- inner command resolution ---------------------------------------

def test_inner_command_pic_defaults_to_pi():
    assert inner_command("pic", []) == ["pi"]


def test_inner_command_pic_prefixes_pi():
    assert inner_command("pic", ["--continue", "hi"]) == [
        "pi", "--continue", "hi"]


def test_inner_command_shell_defaults_to_bash():
    assert inner_command("pic-shell", []) == ["bash"]


def test_inner_command_shell_uses_cmd_verbatim():
    assert inner_command("pic-shell", ["ls", "-la"]) == ["ls", "-la"]
