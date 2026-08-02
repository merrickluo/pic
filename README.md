# pic — the pi coding agent inside a container

`pic` runs the pi coding agent in a container from any project directory.
`pic-shell` is the same, with `bash` as the inner command.

## Usage

```
pic [PIC-OPTIONS] [PROJECT-DIR] [-- INNER-ARGS...]
pic-shell [PIC-OPTIONS] [PROJECT-DIR] [-- INNER-ARGS...]
```

pic's own options go before a bare `--`; everything after it goes
verbatim to the inner command (default: `pi`).

```
pic --help            pic's own help
pic -- --model sonnet -- "fix the build"   pi's options after `--`
```

| Option | Meaning |
|---|---|
| `-h`, `--help` | pic's own help |
| `-V`, `--version` | version |
| `-b`, `--backend NAME` | `guix` \| `oci` \| `auto` (default `auto`) |
| `-s`, `--share PATH` | extra path shared into the container (repeatable) |
| `-e`, `--preserve REGEX` | extra env var regexp passed through (repeatable) |
| `--runtime VALUE` | profile path (guix) or image ref (oci) — overrides config |
| `--no-project` | ignore `pic.toml` and project env detection |
| `--list-backends` | list backends and exit |

## Configuration

Precedence, low to high:

```
builtin defaults < ~/.config/pic/pic.toml < <project>/pic.toml
                 < environment < command line
```

Environment: `PIC_BACKEND`, `PIC_SHARE` (colon-separated),
`PIC_PRESERVE` (whitespace-separated), `PIC_RUNTIME`, `PIC_NO_PROJECT`.

`pic.toml` schema (project overrides user):

```toml
[pic]
backend = "auto"            # guix | oci | auto

[shares]
add = ["/path/to/share"]    # extra paths shared into the container

[env]
preserve = ["^MYCORP_"]     # extra env var regexps passed through

[backend.guix]
profile = "~/.guix-extra-profiles/agent"   # profile-mode runtime
manifest = "/path/to/manifest.scm"         # default: example shipped with pic
channels = ["/path/to/channel"]            # -L args for the manifest
network = true

[backend.oci]
driver = "auto"             # podman | docker | auto
image = "registry.example/pi-agent:latest"
network = "host"
```

## Backends

- **guix** — `guix shell -C`. Profile mode runs a prebuilt agent profile;
  project-env mode combines the agent manifest with the project's
  `guix.scm` (loaded in development mode) or `manifest.scm` (as a
  manifest). The agent profile is never built on demand — pic errors
  with the exact build command instead.
- **oci** — podman or docker with a prebuilt agent image. Env preserve
  regexps are expanded against the host environment.
- **apple** — Apple's `container` on macOS: TBD.

New backends implement the `Backend` ABC in `pic/backends/base.py` and
register in `pic/backends/__init__.py`; the frontend never names a
backend directly.

## Layout

```
pic/
├── README.md                  this file
├── pyproject.toml             entry points: pic, pic-shell; wheel data
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
