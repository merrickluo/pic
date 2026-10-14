# pic — the pi coding agent inside a container

`pic` runs the pi coding agent inside a container.
`pic -c bash` gives you a shell instead.

## Usage

```
pic [PIC-OPTIONS] [PROJECT-DIR] [-- INNER-ARGS...]
```

pic's own options go before a bare `--`; everything after it goes
verbatim to the inner command (default: `pi`, or the configured
`[pic] command`).

```
pic --help            pic's own help
pic -- --model sonnet -- "fix the build"   pi's options after `--`
pic -c bash           a shell inside the container
```

| Option | Meaning |
|---|---|
| `-h`, `--help` | pic's own help |
| `-V`, `--version` | version |
| `-b`, `--backend NAME` | `guix` \| `oci` \| `auto` (default `auto`) |
| `-c`, `--command CMD` | inner command (default: `[pic] command` or `pi`), e.g. `bash`, `claude` |
| `-n`, `--dry-run` | print the container command pic would run, then exit |
| `-s`, `--share PATH` | extra path shared into the container (repeatable) |
| `-e`, `--preserve REGEX` | extra env var regexp passed through (repeatable) |
| `--runtime VALUE` | image ref (oci/apple) — overrides config |
| `--no-project` | ignore `.pic/config.toml` and project env detection |
| `--list-backends` | list backends and exit |

## Configuration

Precedence, low to high:

```
builtin defaults < ~/.config/pic/config.toml < <project>/.pic/config.toml
                 < environment < command line
```

`<project>` is PROJECT-DIR, defaulting to the current directory;
`--no-project` skips the project config.toml and project env detection.

Environment: `PIC_BACKEND`, `PIC_COMMAND`, `PIC_SHARE` (colon-separated),
`PIC_PRESERVE` (whitespace-separated), `PIC_RUNTIME`, `PIC_NO_PROJECT`.

`config.toml` schema (same for user and project; project overrides user):

```toml
[pic]
backend = "auto"            # guix | oci | auto
command = "pi"              # default inner command, e.g. "claude"

[shares]
add = ["/path/to/share"]    # extra paths shared into the container

[env]
preserve = ["^MYCORP_"]     # extra env var regexps passed through

[backend.guix]
manifest = "/path/to/manifest.scm"         # default: ~/.config/pic/manifest.scm, else shipped example
channels = ["/path/to/your-channel"]        # -L args for the manifest
network = true
profile_cache = true        # build the profile once, launch with -p

[backend.oci]
driver = "auto"             # podman | docker | auto
image = "ghcr.io/merrickluo/pi-agent:latest"
network = "host"

[backend.apple]
image = "ghcr.io/merrickluo/pi-agent:latest"
network = "default"         # container network names, not "host"
init = true                 # init process forwards signals
ssh = true                  # forward the SSH agent socket
```

## Backends

- **guix** — `guix shell -C` with the agent manifest (`-m`); local
  channels that provide agent packages go in `[backend.guix] channels`
  (`-L`). When the project has a dev environment it is added on top:
  `guix.scm` in development mode (`-D -f`), `manifest.scm` as a
  manifest.

  Evaluating the manifest and channels takes seconds per launch, so
  with `profile_cache = true` (the default) the profile is built once
  per cache key (`guix shell --root=PROFILE ... -- true`, also a GC
  root) under `$XDG_DATA_HOME/pic/profiles/` and containers launch with
  `-p PROFILE`.  The key covers the guix store path (i.e. `guix pull`),
  the agent manifest, the project env file, and each channel's HEAD
  commit.  Uncommitted channel changes do not invalidate the cache:
  commit them (or set `profile_cache = false`) to pick them up.  Old
  profiles are left in place (they are GC roots); prune
  `$XDG_DATA_HOME/pic/profiles/` by hand if it grows.
- **oci** — podman or docker with a prebuilt agent image. Env preserve
  regexps are expanded against the host environment. The container runs
  as the host uid:gid (`--user`, plus `--userns=keep-id` for rootless
  podman) so files created inside keep host ownership, and `$HOME` is
  set to the host home so pi finds `~/.pi`, `~/.ssh`, `~/.gitconfig`,
  ... even though the image user is root.
- **apple** — Apple's `container` (macOS 26, Apple silicon), OCI-compatible.
  Same image as oci; `-e KEY` inherits values from the host, `--init`
  forwards signals, `--ssh` forwards the SSH agent socket. Runs as the
  host uid:gid and with the host `$HOME`, like oci.

New backends implement the `Backend` ABC in `pic/backends/base.py` and
register in `pic/backends/__init__.py`; the frontend never names a
backend directly.

## Layout

```
pic/
├── README.md                  this file
├── pyproject.toml             entry point: pic; wheel data
├── guix.scm                   package definition for pic itself
├── pic/
│   ├── cli.py                 arg parsing (the `--` boundary), help
│   ├── config.py              config.toml + env + flag merging
│   ├── spec.py                RuntimeSpec / ProjectEnv, share expansion
│   ├── launch.py              orchestration: config → backend → exec
│   ├── resources.py           paths to shipped resources
│   ├── util.py                PicError, die, expand_path
│   └── backends/
│       ├── base.py            the Backend ABC
│       ├── guix.py            guix shell -C (profile / project-env modes)
│       └── oci.py             podman/docker run (env expansion)
├── guix/manifest.scm              example agent manifest (guix)
└── tests/                     pytest, stdlib-only
```

## Testing

```
uv sync        # create .venv once
uv run pytest  # run the suite
```

Covered: the `--` routing contract, config precedence, share expansion,
golden-argv for both backends, env expansion, backend selection.
