# flow-basics

Dark-themed Graphviz flow diagrams with semantic classes. Write clean `.dot` files, get pretty SVG + PNG.

![example](example.png)

## Using with AI agents

Tell your agent:

> Generate a flow diagram for [your topic]. Read https://raw.githubusercontent.com/8ff/flow-basics/main/PROMPT.md for instructions.

The agent will write a `.dot` file, download `render.py`, and produce SVG + PNG automatically.

## Manual usage

Requires `graphviz` and `python3`:
```bash
brew install graphviz       # macOS
apt install graphviz        # Linux
pkg install graphviz        # FreeBSD
pkg_add graphviz            # OpenBSD
```

```bash
./gen.sh                    # renders example.dot -> example.svg + example.png
./gen.sh myflow.dot         # renders myflow.dot  -> myflow.svg  + myflow.png
./gen.sh a.dot output       # renders a.dot       -> output.svg  + output.png
```

See [PROMPT.md](PROMPT.md) for the full `.dot` file format, node/edge classes, and conventions.
