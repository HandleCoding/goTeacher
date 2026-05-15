# GoTeacher

KataGo-powered Go/Weiqi teaching CLI for agents. It turns SGF positions into stable JSON and teaching signals so an LLM agent can write explanations without pasting whole game records into context.

## Install for Development

```bash
uv run --extra dev pytest
uv run goteacher version
```

## KataGo Setup

GoTeacher uses KataGo as an external analysis engine:

```bash
katago analysis -config CONFIG_FILE -model ENGINE_MODEL.bin.gz
katago analysis -config CONFIG_FILE -model ENGINE_MODEL.bin.gz -human-model b18c384nbt-humanv0.bin.gz
```

The easiest setup path is:

```bash
uv run goteacher setup --engine-model /path/to/ENGINE_MODEL.bin.gz
```

`setup` can download the latest KataGo release asset for the current platform, install the default Human SL model `b18c384nbt-humanv0.bin.gz`, install an engine model from a URL or local path, run `katago genconfig`, and save the resolved config. If KataGo asset detection fails, pass `--katago-asset-url` explicitly.

For fully manual setup, generate a KataGo config from an engine model:

```bash
katago genconfig -model ENGINE_MODEL.bin.gz -output ~/.local/share/goteacher/katago-configs/default.cfg
```

Initialize GoTeacher with existing local files:

```bash
uv run goteacher init \
  --katago /path/to/katago \
  --engine-model /path/to/engine.bin.gz \
  --human-model /path/to/b18c384nbt-humanv0.bin.gz
```

The Human SL model can also be installed from the embedded catalog:

```bash
uv run goteacher models install --human human-b18c384nbt-v0
```

## Commands

```bash
uv run goteacher analyze --sgf game.sgf --turn 87 --profile rank_5k --format json
uv run goteacher prompt --sgf game.sgf --turn 87 --profile rank_5k
uv run goteacher scan --sgf game.sgf --profile rank_5k --max 8
uv run goteacher doctor
uv run goteacher models list
uv run goteacher cache stats
```

`analyze` requires a configured KataGo binary, config, and engine model. `scan` currently validates SGF replay and emits the stable scan envelope; deep batch selection is the next implementation milestone.
