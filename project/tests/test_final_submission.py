import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class FinalSubmissionChecks(unittest.TestCase):
    def test_lab_workspaces_include_1_to_18(self):
        expected = {f"lab{i:02d}" for i in range(1, 19)}
        actual = {p.name for p in (ROOT / "labs").glob("lab*") if p.is_dir()}
        self.assertEqual(actual, expected)

    def test_assistant_is_authenticated_and_streaming(self):
        source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
        stream = (ROOT / "backend" / "assistant_stream.py").read_text(encoding="utf-8")
        self.assertIn('def local_assistant(body: agent.AssistantRequest, user=Depends(current_user))', source)
        self.assertIn('stream_router', source)
        self.assertIn('app.include_router(r)', source)
        self.assertIn('StreamingResponse(gen(), media_type="text/event-stream"', stream)
        self.assertIn('keep_alive', stream)

    def test_assistant_frontend_streams_and_has_lab_context(self):
        source = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('function mountChat', source)
        self.assertIn('compact: true', source)
        self.assertIn("/api/assistant/stream", source)
        self.assertIn("LAB RUN QUEUED", source)

    def test_sync_interval_options_and_default_are_consistent(self):
        source = (ROOT / "backend" / "dashboard.py").read_text(encoding="utf-8")
        service = (ROOT / "backend" / "sync_service.py").read_text(encoding="utf-8")
        ui = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
        for value in (10, 30, 60, 300, 600, 1800):
            self.assertIn(str(value), source)
            self.assertIn(f'[{value},', ui)
        self.assertIn('doc.get("interval_seconds", 900)', source)
        self.assertIn('os.getenv("SYNC_INTERVAL_MINUTES", "15")', service)

    def test_registered_lab_run_is_admin_gated_and_backgrounded(self):
        source = (ROOT / "backend" / "dashboard.py").read_text(encoding="utf-8")
        jobs = (ROOT / "backend" / "lab_jobs.py").read_text(encoding="utf-8")
        self.assertIn('user=Depends(require_admin)', source)
        self.assertIn('if exp_id in RUN_WARNINGS and not confirmed', source)
        self.assertIn('start_job(exp_id, meta', source)
        self.assertIn('subprocess.Popen', jobs)
        self.assertIn('db.lab_jobs.update_one', jobs)

    def test_labs_5_and_6_are_registered_for_website_execution(self):
        source = (ROOT / "backend" / "dashboard.py").read_text(encoding="utf-8")
        api = (ROOT / "backend" / "labs_api.py").read_text(encoding="utf-8")
        ui = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
        for experiment in ("l5-aggregation", "l5-bucket", "l5-lookup", "l5-lookup-pipeline",
                           "l6-index-design", "l6-index-stats", "l6-write-benchmark", "l6-covered-query"):
            self.assertIn(f'"{experiment}"', source)
        self.assertIn("5, 6", api)
        self.assertIn("  5: [", ui)
        self.assertIn("  6: [", ui)


if __name__ == "__main__":
    unittest.main()
