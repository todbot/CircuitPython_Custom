# CircuitPython_Custom

Build customized [CircuitPython](https://circuitpython.org) firmware on demand using GitHub Actions — no local toolchain required.

Start from any supported board, then tune it: enable or disable `CIRCUITPY_*` features, add frozen Python modules, choose a specific release or branch, and download the resulting `.uf2` straight from GitHub Actions artifacts.

**[Open the web GUI →](https://todbot.github.io/CircuitPython_Custom/)**

---

## What it does

- Clones the official [adafruit/circuitpython](https://github.com/adafruit/circuitpython) source at the version you choose
- Applies your `CIRCUITPY_*` flag overrides as make variables
- Optionally writes a `user_pre_mpconfigport.mk` to add or replace frozen Python libraries
- Builds with the standard CircuitPython CI toolchain (Ubuntu 24.04)
- Uploads the firmware as a downloadable GitHub Actions artifact

## Using the web GUI

The easiest way. Open **[todbot.github.io/CircuitPython_Custom](https://todbot.github.io/CircuitPython_Custom/)** in your browser.

### First time setup

You need a GitHub Personal Access Token to trigger builds. The token is only used to call the GitHub Actions API and is stored only in your browser's `localStorage` — it is never sent anywhere else.

**Classic token (recommended):**
1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Click **Generate new token (classic)**, check the **`workflow`** scope

**Fine-grained token:**
1. Go to **Personal access tokens → Fine-grained tokens**
2. Set repository access to this repo
3. Under Repository permissions set **Actions: Read and write** — note this is *not* the "Workflows" permission, which only covers editing `.yml` files
4. Fine-grained tokens may still return 403 on some accounts due to GitHub API limitations; use a classic token if so

### Normal view

1. **Board** — click a quick-select button or search across all ~600 boards
2. **Build Options** — pick a version tag, language, and optionally enable a debug build
3. **CIRCUITPY_\* Features** — browse or search all flags; check any you want to override and set a value; amber labels show what the selected board already sets
4. **Frozen Modules** — bold blue entries are already baked into the selected board; check additional ones to add them, or enable "Clear all" to strip the board's defaults first
5. **Custom build name** — optional label used in the artifact and run name
6. Click **Trigger Build** — a link to the Actions run appears when it starts

### Advanced view

Exposes the raw workflow inputs: free-text version/branch, board selected by port+board dropdowns, and a table of only the flags the board explicitly sets in its `mpconfigboard.mk`.

---

## Triggering manually (GitHub Actions UI)

Go to **Actions → Build board (custom) → Run workflow** and fill in the inputs directly:

| Input | Description |
|---|---|
| `board` | Board ID, e.g. `raspberry_pi_pico` |
| `version` | Tag (`9.2.0`, `10.0.0`), commit SHA, or `latest` |
| `branch` | Branch to build from when `version=latest` (default: `main`) |
| `language` | Locale, e.g. `en_US`, `de_DE` (default: `en_US`) |
| `flags` | Space-separated `CIRCUITPY_*` overrides, e.g. `CIRCUITPY_WIFI=1 CIRCUITPY_DISPLAYIO=0` |
| `frozen_modules` | Space-separated `frozen/` submodule dir names to add |
| `clear_frozen` | If true, clears the board's default `FROZEN_MPY_DIRS` before adding the above |
| `custom_name` | Replaces the board ID in the artifact and run name |
| `debug` | Set to true for a debug build |

---

## Tools

### `tools/gen_flags_json.py`

Syncs `docs/circuitpy_flags.json` (the flag list used by the web GUI) against a local CircuitPython source tree. Run this after a CircuitPython upgrade to pick up new or removed flags.

```bash
# Auto-discovers a sibling circuitpython/ checkout:
python tools/gen_flags_json.py

# Or point at a specific checkout:
python tools/gen_flags_json.py --cp ~/projects/adafruit/circuitpython

# Preview changes without writing:
python tools/gen_flags_json.py --dry-run
```

Existing `cat` and `desc` entries are preserved. New flags are added with `cat: ""` and any comment from the `.mk` file as a draft description (prefixed `[auto]`). Flags no longer in the source are removed.

### `tools/board_config_info.py`

Query board configuration from a local CircuitPython checkout and print JSON.

```bash
# List all boards (optionally filter by port):
python tools/board_config_info.py --boards
python tools/board_config_info.py --boards raspberrypi

# Show CIRCUITPY_* settings and frozen modules for a board:
python tools/board_config_info.py --board raspberry_pi_pico

# List available frozen/ module directories:
python tools/board_config_info.py --frozen
```

---

## How the frozen module override works

CircuitPython's build system silently includes `ports/<port>/user_pre_mpconfigport.mk` if it exists (via `-include` in `py/circuitpy_mkenv.mk`). The workflow generates this file at build time:

```makefile
# Generated by custom build workflow
FROZEN_MPY_DIRS :=                          # (only if clear_frozen=true)
FROZEN_MPY_DIRS += $(TOP)/frozen/Adafruit_CircuitPython_NeoPixel
```

This lets frozen modules be customized without modifying any tracked file in the CircuitPython tree.

---

## License

MIT
