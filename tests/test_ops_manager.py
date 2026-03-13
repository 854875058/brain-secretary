from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ops_manager = load_module("ops_manager_test", ROOT / "scripts" / "ops_manager.py")


class OpsManagerWindowsGatewayTests(unittest.TestCase):
    def test_windows_gateway_cmd_uses_real_openclaw_entry_and_port(self) -> None:
        manager = ops_manager.OpsManager(dry_run=True)

        with mock.patch.object(ops_manager, "shutil") as mocked_shutil:
            mocked_shutil.which.side_effect = (
                lambda executable: (
                    r"C:\Users\Administrator\AppData\Roaming\npm\openclaw.cmd"
                    if executable in {"openclaw.cmd", "openclaw"}
                    else None
                )
            )
            command = manager._windows_gateway_cmd()

        self.assertEqual(command[0], r"C:\Users\Administrator\AppData\Roaming\npm\openclaw.cmd")
        self.assertEqual(command[1], "gateway")
        self.assertIn("--port", command)
        self.assertIn("18789", command)


if __name__ == "__main__":
    unittest.main()
