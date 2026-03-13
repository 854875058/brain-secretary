from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QQ_BOT_ROOT = ROOT / "qq-bot"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(QQ_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(QQ_BOT_ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


daemon = load_module("project_auto_evolve_daemon_test", ROOT / "scripts" / "project_auto_evolve_daemon.py")


class StructuredReportTests(unittest.TestCase):
    def test_extract_structured_report_from_marked_block(self) -> None:
        reply = "\n".join(
            [
                "short summary",
                daemon.STRUCTURED_REPORT_BEGIN,
                '{"status":"ok","summary":"done"}',
                daemon.STRUCTURED_REPORT_END,
            ]
        )

        payload = daemon._extract_structured_report(reply)

        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["summary"], "done")

    def test_attention_reasons_require_review_evidence(self) -> None:
        project_cfg = {
            "review_required": True,
            "require_structured_report": True,
        }
        report = daemon._normalize_structured_report(
            {
                "status": "ok",
                "summary": "finished",
                "review": {"status": "approved"},
                "validation": {"pending": []},
                "user_attention": [],
                "exceptions": [],
            }
        )
        collaboration = {
            "review_invoked": False,
            "review_completed": False,
        }

        reasons = daemon._build_attention_reasons(project_cfg, report, collaboration)

        self.assertIn("review_agent_missing", {item["code"] for item in reasons})

    def test_exception_payload_only_returns_attention_items(self) -> None:
        projects = [{"name": "tower-eye", "notify_mode": "exceptions_only"}]
        state = {
            "projects": {
                "tower-eye": {
                    "last_requires_attention": True,
                    "last_status": "attention",
                    "last_outcome": "review missing",
                    "last_finished_at": "2026-03-13T10:00:00+08:00",
                    "last_attention_reasons": [
                        {"code": "review_agent_missing", "message": "missing review evidence"}
                    ],
                    "last_user_attention": ["need manual review"],
                    "last_pending_validation": ["pytest"],
                    "last_commit": "abc1234",
                    "last_session_id": "auto-evolve:tower-eye:1",
                }
            }
        }
        watchdog = {"status": "ok", "message": "watchdog ok"}

        payload = daemon._build_exception_payload(projects, state, watchdog)

        self.assertEqual(payload["status"], "attention")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["project"], "tower-eye")
        self.assertEqual(payload["items"][0]["reasons"][0]["code"], "review_agent_missing")


if __name__ == "__main__":
    unittest.main()
