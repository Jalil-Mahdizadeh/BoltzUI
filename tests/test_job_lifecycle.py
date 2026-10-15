"""Exercise the HTTP job lifecycle using fake predictions in a temporary workspace."""

import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def wait_for(function, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = function()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for the controlled job")


@unittest.skipUnless(os.name == "posix" and shutil.which("node"), "Container integration test needs POSIX and Node")
class JobLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="boltz-job-test-")
        self.workspace = Path(self.temporary.name)
        inputs = self.workspace / "workspace/inputs"
        inputs.mkdir(parents=True)
        for name in ["slow", "fail", "success", "empty"]:
            (inputs / f"{name}.yaml").write_text((ROOT / "fixtures/atom_contact_example.yaml").read_text())
        self.pid_file = self.workspace / "pids.json"
        fake = self.workspace / "boltzui-predict"
        fake.write_text(f'''#!{sys.executable}
import json, os, subprocess, sys, time
from pathlib import Path
data = Path(sys.argv[2])
if data.stem == "empty":
    sys.exit(0)
if data.stem == "slow":
    child = subprocess.Popen([sys.executable, "-c", "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('runtime ready', flush=True); time.sleep(120)"], stdout=subprocess.PIPE)
    child.stdout.readline()
    Path({str(self.pid_file)!r}).write_text(json.dumps({{"wrapper": os.getpid(), "runtime": child.pid}}))
    child.wait()
else:
    directory = Path(sys.argv[sys.argv.index("--out_dir") + 1]) / ("boltz_results_" + data.stem)
    predictions = directory / "predictions" / data.stem
    predictions.mkdir(parents=True)
    (predictions / (data.stem + "_model_0.pdb")).write_text("ATOM      1  OG  SER A   1       0.000   0.000   0.000  1.00 80.00           O  \\nATOM      2  N   GLY B   1       3.000   0.000   0.000  1.00 80.00           N  \\nEND\\n")
    (predictions / ("confidence_" + data.stem + "_model_0.json")).write_text('{{"confidence_score":0.9}}')
    sys.exit(7 if data.stem == "fail" else 0)
''')
        fake.chmod(0o755)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self.base = f"http://127.0.0.1:{port}"
        env = dict(os.environ, HOST="127.0.0.1", PORT=str(port), PATH=f"{self.workspace}{os.pathsep}{os.environ['PATH']}")
        self.server = subprocess.Popen(["node", str(ROOT / "server.js")], cwd=self.workspace, env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def ready():
            try:
                self.api("/api/jobs")
                return True
            except (OSError, urllib.error.URLError):
                return False
        wait_for(ready)

    def tearDown(self):
        if self.pid_file.exists():
            pids = json.loads(self.pid_file.read_text())
            try:
                os.killpg(pids["wrapper"], signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.server.terminate()
        self.server.wait(timeout=10)
        self.temporary.cleanup()

    def api(self, route, payload=None):
        request = urllib.request.Request(self.base + route, data=None if payload is None else json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def start(self, name, **extra):
        return self.api("/api/jobs", {"data": f"workspace/inputs/{name}.yaml", "preset": "standard", **extra})["job"]

    def finalized(self, job):
        def read():
            value = self.api("/api/jobs/" + job["id"])["job"]
            return value if value.get("manifestPath") else None
        return wait_for(read)

    def seed_previous(self, name):
        directory = self.workspace / "workspace/results" / f"boltz_results_{name}"
        old = directory / "predictions" / name / f"{name}_model_9.pdb"
        old.parent.mkdir(parents=True)
        old.write_text("previous model bytes")
        (directory / "boltzui_run.json").write_text('{"job_id":"previous-run"}')
        (directory / "contact_restraints.json").write_text('{"previous":"audit"}')
        return directory

    def test_stop_kills_runtime_and_overlapping_run_is_rejected(self):
        first = self.start("slow")
        wait_for(self.pid_file.exists)
        pids = json.loads(self.pid_file.read_text())
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.start("slow")
        self.assertEqual(rejected.exception.code, 400)
        self.assertIn("already writing", rejected.exception.read().decode())
        self.api("/api/jobs/" + first["id"] + "/stop", {})
        self.assertEqual(self.finalized(first)["status"], "stopped")
        for pid in pids.values():
            state_file = Path(f"/proc/{pid}/stat")
            self.assertTrue(not state_file.exists() or state_file.read_text().split()[2] == "Z", f"process {pid} is still running")
        # The output reservation is released after finalization.
        again = self.start("slow")
        self.api("/api/jobs/" + again["id"] + "/stop", {})
        self.finalized(again)

    def test_failed_rerun_preserves_previous_models_manifest_and_audit(self):
        directory = self.seed_previous("fail")
        before = {str(file.relative_to(directory)): file.read_bytes() for file in directory.rglob("*") if file.is_file()}
        failed = self.finalized(self.start("fail"))
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["exitCode"], 7)
        after = {str(file.relative_to(directory)): file.read_bytes() for file in directory.rglob("*") if file.is_file()}
        self.assertEqual(after, before)
        self.assertIsNone(failed["restraintReportPath"])
        manifest = json.loads((self.workspace / failed["manifestPath"]).read_text())
        self.assertEqual(manifest["job_id"], failed["id"])
        self.assertIn(".boltzui-history", manifest["output_directory"])
        self.assertTrue((self.workspace / manifest["output_directory"] / "predictions/fail/fail_model_0.pdb").exists())

    def test_successful_rerun_audits_only_new_models_and_archives_previous(self):
        directory = self.seed_previous("success")
        job = self.finalized(self.start("success"))
        self.assertEqual(job["status"], "succeeded")
        report = json.loads((directory / "contact_restraints.json").read_text())
        self.assertEqual([entry["model"] for entry in report["structures_examined"]], ["model_0"])
        self.assertEqual(json.loads((directory / "boltzui_run.json").read_text())["job_id"], job["id"])
        history = directory.parent / ".boltzui-history" / directory.name / job["id"] / "previous"
        self.assertTrue((history / "predictions/success/success_model_9.pdb").exists())
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.start("success", preset="custom", options={"override": False})
        self.assertIn("Override existing", rejected.exception.read().decode())

    def test_zero_exit_without_structures_restores_the_previous_result(self):
        directory = self.seed_previous("empty")
        job = self.finalized(self.start("empty"))
        self.assertEqual(job["status"], "failed")
        self.assertIn("produced no structures", job["failureReason"])
        self.assertEqual(json.loads((directory / "boltzui_run.json").read_text())["job_id"], "previous-run")


if __name__ == "__main__":
    unittest.main()
