#!/usr/bin/env python3
"""Print compact completion status for every phase-2 command."""

import json
from pathlib import Path


PHASE2 = Path(__file__).resolve().parents[1]


def main():
    rows = []
    for command in sorted((PHASE2 / "cases").glob("*/*/command.json")):
        arm_dir = command.parent
        pdb_id = arm_dir.parent.name.upper()
        arm = arm_dir.name
        status_path = arm_dir / "logs" / "execution_status.json"
        status = json.loads(status_path.read_text()) if status_path.is_file() else {}
        result = (
            arm_dir
            / "results"
            / "boltz_results_{}_{}".format(pdb_id.lower(), arm)
        )
        models = len(list(result.rglob("*_model_*.pdb"))) if result.exists() else 0
        if status.get("exit_code") == 0 and models == 10:
            state = "complete"
        elif status:
            state = "failed"
        elif result.exists():
            state = "running"
        else:
            state = "pending"
        rows.append((pdb_id, arm, state, models))
    for row in rows:
        print("{:<5} {:<22} {:<9} {:>2}/10".format(*row))
    counts = {
        state: sum(row[2] == state for row in rows)
        for state in ("complete", "running", "pending", "failed")
    }
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
