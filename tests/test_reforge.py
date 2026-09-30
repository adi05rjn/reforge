import copy
import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from reforge.capture import capture
from reforge.cli import main
from reforge.core import ReforgeError, attach_source, baseline, load, validate_ai
from reforge.local_ai import endpoint_url, enrich

ROOT = Path(__file__).resolve().parents[1]


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.p = load(ROOT / "examples/preferences.json")
        self.t = load(ROOT / "examples/target.json")
        self.m = load(ROOT / "examples/memory.json")

    def plan(self):
        return baseline(self.p, self.t, self.m)

    def response(self):
        return {"summary": "Prioritise the embedded workflow.",
                "application_order": [a["application"] for a in self.plan()["actions"]][::-1],
                "diagnostic_ids": ["editor-font-example"], "questions": ["Which terminal font do you prefer?"]}

    def test_missing_packages_only(self):
        self.assertNotIn("git", [a["application"] for a in self.plan()["actions"]])
        self.assertIn("gcc-arm-none-eabi", [a["package"] for a in self.plan()["actions"]])

    def test_repeatable_plan(self):
        self.assertEqual(self.plan(), self.plan())

    def test_target_already_rebuilt(self):
        self.t["installed_applications"] = list(self.p["applications"])
        self.assertEqual(self.plan()["actions"], [])

    def test_hardware_mismatch(self):
        plan = self.plan()
        self.assertEqual([r["id"] for r in plan["diagnostics_for_review"]], ["editor-font-example"])
        self.assertEqual(plan["skipped_diagnostics"][0]["id"], "old-laptop-driver-example")

    def test_unknown_hardware_never_matches(self):
        self.t["machine_model"] = "unknown"
        self.m["records"][0]["conditions"] = {"machine_model": "unknown"}
        self.assertEqual(self.plan()["diagnostics_for_review"], [])

    def test_unverified_fix(self):
        self.m["records"][0]["verified"] = False
        self.assertEqual(self.plan()["diagnostics_for_review"], [])

    def test_conditions_required(self):
        self.m["records"][0]["conditions"] = {}
        with self.assertRaises(ReforgeError): self.plan()

    def test_unknown_app_rejected(self):
        self.p["applications"].append("curl | sh")
        with self.assertRaises(ReforgeError): self.plan()

    def test_unsupported_target(self):
        self.t["os_id"] = "arch"
        with self.assertRaises(ReforgeError): self.plan()

    def test_bad_architecture_type(self):
        self.t["architecture"] = []
        with self.assertRaises(ReforgeError): self.plan()

    def test_valid_ai_reorders_only_approved_actions(self):
        plan = validate_ai(self.response(), self.plan())
        self.assertEqual(plan["mode"], "local_ai")
        self.assertEqual(plan["actions"][0]["application"], "gdb")

    def test_model_unknown_operation_rejected(self):
        response = self.response()
        response["shell_command"] = "sudo rm -rf /"
        with self.assertRaises(ReforgeError): validate_ai(response, self.plan())

    def test_model_hardware_fix_rejected(self):
        response = self.response()
        response["diagnostic_ids"] = ["old-laptop-driver-example"]
        with self.assertRaises(ReforgeError): validate_ai(response, self.plan())

    def test_model_missing_and_duplicate_apps_rejected(self):
        for order in (["neovim"], ["neovim", "neovim"], [["bad"]]):
            response = self.response()
            response["application_order"] = order
            with self.assertRaises(ReforgeError): validate_ai(response, self.plan())

    def test_nonlocal_endpoints_rejected(self):
        for url in ("https://example.com", "http://example.com", "http://127.0.0.1.evil.test",
                    "http://user:secret@127.0.0.1", "http://127.0.0.1?token=x"):
            with self.assertRaises(ReforgeError): endpoint_url(url)

    def test_loopback_endpoints(self):
        for host in ("127.0.0.1", "localhost", "[::1]"):
            self.assertEqual(endpoint_url(f"http://{host}:8080/v1"), f"http://{host}:8080/v1/chat/completions")

    def test_http_integration(self):
        payload = self.response()
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                raw = json.dumps({"choices": [{"message": {"content": json.dumps(payload)}}]}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args): pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = enrich(self.plan(), self.p, f"http://127.0.0.1:{server.server_port}", "fixture")
            self.assertEqual(result["mode"], "local_ai")
            self.assertEqual(requests[0][0], "/v1/chat/completions")
            context = json.loads(requests[0][1]["messages"][1]["content"])
            self.assertNotIn("old-laptop-driver-example", json.dumps(context))
            payload.clear()
            with self.assertRaises(ReforgeError):
                enrich(self.plan(), self.p, f"http://127.0.0.1:{server.server_port}", "fixture")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_unavailable_endpoint(self):
        with patch("urllib.request.OpenerDirector.open", side_effect=OSError("unavailable")):
            with self.assertRaisesRegex(ReforgeError, "start your local server"):
                enrich(self.plan(), self.p, "http://127.0.0.1:8080", "fixture")

    def test_capture_no_config_contents_or_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / ".gitconfig").write_text("private-token-example")
            (home / ".config/nvim").mkdir(parents=True)
            (home / ".config/nvim/init.lua").symlink_to(home / ".gitconfig")
            with patch("platform.system", return_value="Linux"), patch("platform.freedesktop_os_release", return_value={"ID": "debian"}):
                snapshot = capture(home)
            self.assertNotIn("private-token-example", json.dumps(snapshot))
            self.assertNotIn("neovim", snapshot["config_fingerprints"])
            self.assertEqual(len(snapshot["config_fingerprints"]["git"]["sha256"]), 64)
            attach_source(self.plan(), snapshot)

    def test_capture_unsupported_os(self):
        with patch("platform.system", return_value="Darwin"):
            with self.assertRaises(ReforgeError): capture()

    def test_cli_end_to_end_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "plan"
            args = ["plan", "--preferences", str(ROOT / "examples/preferences.json"),
                    "--target", str(ROOT / "examples/target.json"), "--memory",
                    str(ROOT / "examples/memory.json"), "--offline", "--output", str(out)]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 0)
                before = (out / "plan.json").read_bytes()
                self.assertEqual(main(args), 2)
                self.assertEqual(before, (out / "plan.json").read_bytes())
            self.assertIn("no installation", (out / "plan.md").read_text())

    def test_failed_inference_leaves_no_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "failed"
            args = ["plan", "--preferences", str(ROOT / "examples/preferences.json"),
                    "--target", str(ROOT / "examples/target.json"), "--output", str(out)]
            with patch("reforge.cli.enrich", side_effect=ReforgeError("model failed")), redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 2)
            self.assertFalse(out.exists())

    def test_remember_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "memory.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["remember", "--output", str(out), "--issue", "Font missing",
                    "--fix", "Select font", "--outcome", "Glyphs verified", "--verified", "--os-id", "debian"]), 0)
            self.assertTrue(load(out)["records"][0]["verified"])


if __name__ == "__main__":
    unittest.main()
