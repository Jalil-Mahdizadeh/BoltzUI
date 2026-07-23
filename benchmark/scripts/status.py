#!/usr/bin/env python3
"""Summarize candidate queue and executed classifications."""

from __future__ import print_function

import glob
import json
import os


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_DIR = os.path.dirname(SCRIPT_DIR)
CANDIDATES_DIR = os.path.join(BENCHMARK_DIR, "candidates")
QUEUE_PATH = os.path.join(BENCHMARK_DIR, "screening", "candidate_queue.json")


def load_json(path):
    with open(path, "r") as handle:
        return json.load(handle)


def main():
    queue = load_json(QUEUE_PATH)
    executed = {}
    for path in sorted(glob.glob(os.path.join(CANDIDATES_DIR, "*-*"))):
        candidate_path = os.path.join(path, "candidate.json")
        if not os.path.isfile(candidate_path):
            continue
        candidate = load_json(candidate_path)
        executed[candidate["pdb_id"]] = {
            "directory": os.path.basename(path),
            "status": candidate.get("status", "unknown"),
            "reason": candidate.get("classification_reason")
        }
    passed = [value for value in executed.values() if value["status"] == "passed"]
    skipped = [value for value in executed.values() if value["status"] == "skipped"]
    running = [value for value in executed.values() if value["status"] == "running"]
    remaining = [
        item["pdb_id"] for item in queue if item["pdb_id"] not in executed
    ]
    print(json.dumps({
        "queue_total": len(queue),
        "passed": len(passed),
        "skipped": len(skipped),
        "running": len(running),
        "remaining": len(remaining),
        "executed": executed,
        "remaining_pdb_ids": remaining
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
