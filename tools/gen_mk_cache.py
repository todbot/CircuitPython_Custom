#!/usr/bin/env python3
"""
gen_mk_cache.py — Generate docs/mk_cache.json for the web GUI.

Pre-bundles the CircuitPython .mk files the GUI needs on every page load
so it can operate without hitting the GitHub API for stable content:

  - py/circuitpy_mpconfig.mk      (base mk — all CIRCUITPY_* defaults)
  - ports/*/mpconfigport.mk       (all port mks)
  - frozen/ directory listing     (frozen module names)
  - ports/ directory listing      (port names)
  - mpconfigboard.mk for every quick-select board

Run this whenever CircuitPython is updated:

    python tools/gen_mk_cache.py --cp ~/path/to/circuitpython

The output is committed to the repo so the GitHub Pages GUI can load it
as a plain file fetch with no API quota cost.
"""

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT   = SCRIPT_DIR.parent
DEFAULT_OUT = REPO_ROOT / 'docs' / 'mk_cache.json'

CP_CANDIDATES = [
    REPO_ROOT.parent / 'circuitpython',
    Path.home() / 'projects' / 'adafruit' / 'circuitpython',
]

# Must stay in sync with QUICK_BOARDS in docs/index.html
QUICK_BOARDS = [
    ('raspberrypi', 'raspberry_pi_pico'),
    ('raspberrypi', 'raspberry_pi_pico2'),
    ('raspberrypi', 'adafruit_feather_rp2040'),
    ('raspberrypi', 'adafruit_qtpy_rp2040'),
    ('atmel-samd',  'feather_m4_express'),
    ('atmel-samd',  'qtpy_m0'),
    ('atmel-samd',  'circuitplayground_express'),
]


def find_cp_root():
    for p in CP_CANDIDATES:
        if (p / 'py' / 'circuitpy_mpconfig.mk').exists():
            return p
    return None


def git_sha(path: Path) -> str:
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=path, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return 'unknown'


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cp',  metavar='PATH', help='CircuitPython repo root')
    ap.add_argument('--out', metavar='PATH', default=str(DEFAULT_OUT),
                    help=f'Output JSON (default: {DEFAULT_OUT})')
    args = ap.parse_args()

    cp_root = Path(args.cp) if args.cp else find_cp_root()
    if not cp_root or not (cp_root / 'py' / 'circuitpy_mpconfig.mk').exists():
        print('ERROR: CircuitPython source not found. Use --cp PATH.', file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out)
    print(f'Source : {cp_root}  (sha: {git_sha(cp_root)})')
    print(f'Output : {out_path}')

    cache = {
        'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'cp_sha':    git_sha(cp_root),
        'base_mk':   '',
        'port_mks':  {},
        'ports':     [],
        'frozen_modules': [],
        'board_mks': {},
    }

    # Base mk
    p = cp_root / 'py' / 'circuitpy_mpconfig.mk'
    cache['base_mk'] = p.read_text(encoding='utf-8')
    print(f'  base mk              : {len(cache["base_mk"]):,} chars')

    # Port mks (all ports that have one)
    for port_dir in sorted((cp_root / 'ports').iterdir()):
        if not port_dir.is_dir():
            continue
        mk = port_dir / 'mpconfigport.mk'
        if mk.exists():
            cache['port_mks'][port_dir.name] = mk.read_text(encoding='utf-8')
    cache['ports'] = sorted(cache['port_mks'])
    print(f'  port mks             : {len(cache["port_mks"])} ports')

    # Frozen modules list
    frozen_dir = cp_root / 'frozen'
    if frozen_dir.exists():
        cache['frozen_modules'] = sorted(
            d.name for d in frozen_dir.iterdir()
            if not d.name.startswith('.')
        )
    print(f'  frozen modules       : {len(cache["frozen_modules"])}')

    # Quick-select board mks
    for port, board in QUICK_BOARDS:
        mk = cp_root / 'ports' / port / 'boards' / board / 'mpconfigboard.mk'
        if mk.exists():
            key = f'{port}/boards/{board}'
            cache['board_mks'][key] = mk.read_text(encoding='utf-8')
            print(f'  board mk             : {key}')
        else:
            print(f'  WARNING: not found   : {mk}', file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )
    size_kb = out_path.stat().st_size / 1024
    print(f'\nWrote {out_path}  ({size_kb:.1f} KB)')


if __name__ == '__main__':
    main()
