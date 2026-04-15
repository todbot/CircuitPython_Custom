#!/usr/bin/env python3
"""
gen_flags_json.py — Generate / refresh docs/circuitpy_flags.json from
a CircuitPython source tree.

Usage:
    python tools/gen_flags_json.py [--cp PATH] [--out PATH] [--dry-run]

Options:
    --cp PATH       Path to CircuitPython repo root (default: looks for
                    py/circuitpy_mpconfig.mk relative to this script's
                    grandparent, then falls back to ../circuitpython)
    --out PATH      Output JSON file (default: docs/circuitpy_flags.json
                    next to this script's parent)
    --dry-run       Print what would change without writing

Behaviour:
    - Parses py/circuitpy_mpconfig.mk to extract every CIRCUITPY_* flag
      defined with ?= (the public, overridable ones).
    - For each flag, captures the preceding comment block (if any) as a
      fallback description.
    - Merges with the existing JSON:
        * Existing cat/desc entries are preserved as-is.
        * New flags (not in existing JSON) are added with cat="" desc="".
          If there was a comment in the mk file, it is used as the initial
          desc (prefixed with "[auto] " so you know to review it).
        * Flags no longer in the mk file are removed (listed in output).
    - Maintains the existing category order from the JSON; new flags go
      at the end of the flags object.
    - Preserves pretty-formatting (aligned colons).

Output format matches the existing circuitpy_flags.json layout.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ── Locate default paths ─────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent          # tools/
REPO_ROOT   = SCRIPT_DIR.parent                       # CircuitPython_Custom-todbot/
DEFAULT_OUT = REPO_ROOT / 'docs' / 'circuitpy_flags.json'

# Candidates for the CircuitPython source tree, in preference order
CP_CANDIDATES = [
    REPO_ROOT.parent / 'circuitpython',               # sibling checkout
    Path.home() / 'projects' / 'adafruit' / 'circuitpython',
]


def find_cp_root():
    for p in CP_CANDIDATES:
        if (p / 'py' / 'circuitpy_mpconfig.mk').exists():
            return p
    return None


# ── mk parser ────────────────────────────────────────────────────────────────

# Matches:   CIRCUITPY_FOO ?= some_value
_FLAG_RE = re.compile(r'^(CIRCUITPY_[A-Z0-9_]+)\s*\?=\s*(.*)')

# Matches a comment line (strips leading #)
_COMMENT_RE = re.compile(r'^#\s?(.*)')


def parse_mk(mk_path: Path) -> dict:
    """
    Parse circuitpy_mpconfig.mk and return:
        { 'CIRCUITPY_FOO': {'default': '...', 'comment': '...'}, ... }

    Only the first ?= definition is recorded (subsequent ifdefs are skipped).
    'comment' is the immediately preceding comment block joined into one line,
    or '' if none.
    """
    results = {}
    lines = mk_path.read_text(encoding='utf-8').splitlines()

    pending_comment = []
    for line in lines:
        stripped = line.strip()

        cm = _COMMENT_RE.match(stripped)
        if cm:
            pending_comment.append(cm.group(1).strip())
            continue

        fm = _FLAG_RE.match(stripped)
        if fm:
            name, default = fm.group(1), fm.group(2).strip()
            if name not in results:   # keep first definition only
                comment = ' '.join(pending_comment).strip() if pending_comment else ''
                results[name] = {'default': default, 'comment': comment}
            pending_comment = []
            continue

        # Any non-comment, non-flag line resets the pending comment
        if stripped and not stripped.startswith('CFLAGS') and not stripped.startswith('ifndef'):
            pending_comment = []
        elif not stripped:
            # blank line also resets
            pending_comment = []

    return results


# ── JSON merge ───────────────────────────────────────────────────────────────

def merge(existing: dict, parsed: dict) -> tuple[dict, list, list, list]:
    """
    Returns (merged_flags, added_keys, removed_keys, unchanged_keys).

    existing: the 'flags' dict from circuitpy_flags.json
    parsed:   output of parse_mk()
    """
    added, removed, unchanged = [], [], []

    merged = {}
    # Keep existing entries that are still in the mk file
    for key, entry in existing.items():
        if key in parsed:
            merged[key] = entry
            unchanged.append(key)
        else:
            removed.append(key)

    # Add new flags not yet in the JSON
    for key in sorted(parsed):
        if key not in merged:
            comment = parsed[key]['comment']
            desc = f'[auto] {comment}' if comment else ''
            merged[key] = {'cat': '', 'desc': desc}
            added.append(key)

    return merged, added, removed, unchanged


# ── JSON serialiser (preserves aligned layout) ────────────────────────────────

def _quote(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def render_json(categories: list, flags: dict) -> str:
    cats_json = ', '.join(_quote(c) for c in categories)
    lines = ['{', f'  "categories": [{cats_json}],', '  "flags": {']

    # Determine alignment: longest key + some padding
    max_key = max((len(k) for k in flags), default=10)
    col = max_key + 4   # 2 indent + 2 quotes + some padding → align the {

    entries = list(flags.items())
    for i, (key, meta) in enumerate(entries):
        comma = '' if i == len(entries) - 1 else ','
        padded_key = f'"{key}"'
        padding = ' ' * (col - len(padded_key))
        cat_str  = _quote(meta.get('cat', ''))
        desc_str = _quote(meta.get('desc', ''))
        lines.append(f'    {padded_key}:{padding}{{ "cat": {cat_str}, "desc": {desc_str} }}{comma}')

    lines += ['  }', '}', '']
    return '\n'.join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cp',      metavar='PATH', help='CircuitPython repo root')
    ap.add_argument('--out',     metavar='PATH', default=str(DEFAULT_OUT),
                    help=f'Output JSON (default: {DEFAULT_OUT})')
    ap.add_argument('--dry-run', action='store_true',
                    help='Show changes without writing')
    args = ap.parse_args()

    # Resolve CircuitPython root
    if args.cp:
        cp_root = Path(args.cp)
    else:
        cp_root = find_cp_root()
        if cp_root is None:
            print('ERROR: Could not find a CircuitPython source tree. '
                  'Use --cp PATH to specify one.', file=sys.stderr)
            sys.exit(1)

    mk_path = cp_root / 'py' / 'circuitpy_mpconfig.mk'
    if not mk_path.exists():
        print(f'ERROR: {mk_path} not found.', file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out)

    print(f'Source : {mk_path}')
    print(f'Output : {out_path}')
    print()

    # Parse mk file
    parsed = parse_mk(mk_path)
    print(f'Found {len(parsed)} CIRCUITPY_* flags in mk file.')

    # Load existing JSON (or start fresh)
    if out_path.exists():
        with open(out_path, encoding='utf-8') as f:
            existing_json = json.load(f)
        categories    = existing_json.get('categories', [])
        existing_flags = existing_json.get('flags', {})
        print(f'Existing JSON has {len(existing_flags)} flags.')
    else:
        categories     = []
        existing_flags = {}
        print('No existing JSON — will create from scratch.')

    # Merge
    merged, added, removed, _ = merge(existing_flags, parsed)

    # Report
    if added:
        print(f'\nAdded ({len(added)}):')
        for k in added:
            auto_desc = parsed[k]['comment']
            print(f'  + {k}' + (f'  # {auto_desc[:70]}' if auto_desc else ''))
    if removed:
        print(f'\nRemoved ({len(removed)}):')
        for k in removed:
            print(f'  - {k}')
    if not added and not removed:
        print('No changes — JSON is already up to date.')
        return

    # Write
    output = render_json(categories, merged)

    if args.dry_run:
        print('\n--- dry run: would write ---')
        print(output[:2000], '...' if len(output) > 2000 else '')
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding='utf-8')
    print(f'\nWrote {out_path} ({len(merged)} flags).')
    if added:
        print(f'Review {len(added)} new entries (marked "[auto]") and fill in '
              '"cat" and update "desc" as needed.')


if __name__ == '__main__':
    main()
