#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 CircuitPython contributors (https://github.com/adafruit/circuitpython/graphs/contributors)
#
# SPDX-License-Identifier: MIT

"""Query CircuitPython board config and frozen module info. Outputs JSON.

Usage:
  board_config_info.py --boards [PORT]   List all boards, optionally filtered by port
  board_config_info.py --board BOARD_ID  Dump CIRCUITPY_* settings and frozen modules for a board
  board_config_info.py --frozen          List available frozen/ module directories
"""

import argparse
import json
import re
import sys
from pathlib import Path

root = Path(__file__).parent.parent
docs_dir = root / "docs"
sys.path.insert(0, str(docs_dir))
from shared_bindings_matrix import get_board_mapping  # noqa: E402


def parse_mk_assignments(path):
    """Parse a .mk file for scalar assignments and FROZEN_MPY_DIRS entries.

    Returns (scalar_vars: dict, frozen_dirs: list[str]).
    scalar_vars contains KEY = VALUE and KEY ?= VALUE lines.
    frozen_dirs contains module dir names from FROZEN_MPY_DIRS += $(TOP)/frozen/<name> lines.
    Does not evaluate make variable expressions; returns raw strings.
    """
    scalar_vars = {}
    frozen_dirs = []
    if not path.exists():
        return scalar_vars, frozen_dirs

    frozen_prefix = "FROZEN_MPY_DIRS += $(TOP)/frozen/"
    assignment_re = re.compile(r"^([A-Z][A-Z0-9_]*)\s*\??=\s*(.*)$")

    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(frozen_prefix):
            remainder = stripped[len(frozen_prefix) :]
            frozen_dirs.append(remainder.split("/")[0])
            continue
        m = assignment_re.match(stripped)
        if m:
            key, value = m.group(1), m.group(2).strip()
            scalar_vars[key] = value

    return scalar_vars, frozen_dirs


def get_board_info(board_id):
    """Return merged CIRCUITPY_* settings and frozen modules for a board.

    Merges board > port > base config layers. For each CIRCUITPY_* key,
    records the effective value and which layer set it (board/port/base).
    """
    board_mapping = get_board_mapping()
    if board_id not in board_mapping:
        raise ValueError(f"Unknown board: {board_id}")

    info = board_mapping[board_id]
    port = info["port"]
    board_dir = info["directory"]

    board_vars, board_frozen = parse_mk_assignments(board_dir / "mpconfigboard.mk")
    port_vars, _ = parse_mk_assignments(root / "ports" / port / "mpconfigport.mk")
    base_vars, _ = parse_mk_assignments(root / "py" / "circuitpy_mpconfig.mk")

    all_keys = (
        {k for k in base_vars if k.startswith("CIRCUITPY_")}
        | {k for k in port_vars if k.startswith("CIRCUITPY_")}
        | {k for k in board_vars if k.startswith("CIRCUITPY_")}
    )

    merged = {}
    for key in sorted(all_keys):
        if key in board_vars:
            merged[key] = {"value": board_vars[key], "source": "board"}
        elif key in port_vars:
            merged[key] = {"value": port_vars[key], "source": "port"}
        else:
            merged[key] = {"value": base_vars[key], "source": "base"}

    return {
        "board": board_id,
        "port": port,
        "circuitpy_settings": merged,
        "frozen_modules": board_frozen,
    }


def list_boards(port_filter=None):
    """List all boards with their port. Skips alias entries."""
    board_mapping = get_board_mapping()
    results = []
    for board_id, info in sorted(board_mapping.items()):
        if info.get("alias"):
            continue
        if port_filter and info["port"] != port_filter:
            continue
        results.append({"board": board_id, "port": info["port"]})
    return results


def list_frozen_modules():
    """List available frozen module directories."""
    frozen_dir = root / "frozen"
    if not frozen_dir.is_dir():
        return []
    return sorted(
        entry.name for entry in frozen_dir.iterdir() if entry.is_dir() and not entry.name.startswith(".")
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--boards",
        nargs="?",
        const="",
        metavar="PORT",
        help="List all boards, optionally filtered to PORT (e.g. espressif)",
    )
    group.add_argument(
        "--board",
        metavar="BOARD_ID",
        help="Dump CIRCUITPY_* settings and frozen_modules for BOARD_ID",
    )
    group.add_argument(
        "--frozen",
        action="store_true",
        help="List all available frozen/ module directories",
    )
    args = parser.parse_args()

    if args.boards is not None:
        result = list_boards(args.boards if args.boards else None)
        print(json.dumps(result, indent=2))
    elif args.board:
        try:
            result = get_board_info(args.board)
            print(json.dumps(result, indent=2))
        except ValueError as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)
    elif args.frozen:
        result = list_frozen_modules()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
