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
| `--no-project` | ignore `pic.toml` and project env detection |
| `--list-backends` | list backends and exit |

## Configuration

Precedence, low to high:

```
builtin defaults < ~/.config/pic/pic.toml < <project>/pic.toml
                 < environment < command line
```

Environment: `PIC_BACKEND`, `PIC_COMMAND`, `PIC_SHARE` (colon-separated),
`PIC_PRESERVE` (whitespace-separated), `PIC_RUNTIME`, `PIC_NO_PROJECT`.

`pic.toml` schema (project overrides user):

```toml
[pic]
backend = "auto"            # guix | oci | auto
command = "pi"              # default inner command, e.g. "claude"

[shares]
add = ["/path/to/share"]    # extra paths shared into the container

[env]
preserve = ["^MYCORP_"]     # extra env var regexps passed through

[backend.guix]
manifest = "/path/to/manifest.scm"         # default: example shipped with pic
channels = ["/path/to/your-channel"]        # -L args for the manifest
network = true

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
- **oci** — podman or docker with a prebuilt agent image. Env preserve
  regexps are expanded against the host environment. `$HOME` is set to
  the host home, so pi finds `~/.pi`, `~/.ssh`, `~/.gitconfig`, ...
  even though the image runs as root.
- **apple** — Apple's `container` (macOS 26, Apple silicon), OCI-compatible.
  Same image as oci; `-e KEY` inherits values from the host, `--init`
  forwards signals, `--ssh` forwards the SSH agent socket. `$HOME` is
  set to the host home, like oci.

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
│   ├── config.py              pic.toml + env + flag merging
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
