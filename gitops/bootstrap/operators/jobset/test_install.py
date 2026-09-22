"""Offline checks for the shared-platform mutation boundaries."""
import copy
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("jobset_install", Path(__file__).with_name("install.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InstallationBoundaries(unittest.TestCase):
    def test_approval_rejects_an_unexpected_dependency(self):
        subscription = {"metadata": {"annotations": {MODULE.OWNER: "rhoai-showroom"}},
                        "status": {"installPlanRef": {"name": "reviewed-plan"}}}
        plan = {"spec": {"clusterServiceVersionNames": [MODULE.PIN["csv"], "unreviewed.v1"]}}
        with patch.object(MODULE, "get", side_effect=[subscription, plan]), patch.object(MODULE, "oc") as command:
            with self.assertRaisesRegex(SystemExit, "Unexpected CSVs"):
                MODULE.approve_plan("reviewed-plan", True)
            command.assert_not_called()

    def test_catalog_digest_change_stops_before_installation(self):
        package = {"status": {"catalogSource": MODULE.PIN["catalog"], "channels": [{
            "name": MODULE.PIN["channel"], "currentCSV": MODULE.PIN["csv"],
            "currentCSVDesc": {"relatedImages": ["changed-image"]}}]}}
        with patch.object(MODULE, "get", return_value=package), patch.object(MODULE, "oc") as command:
            with self.assertRaisesRegex(SystemExit, "images changed"):
                MODULE.verify_catalog()
            command.assert_not_called()

    def test_trainer_patch_preserves_other_components_and_private_backup(self):
        original = {"metadata": {"name": "test-dsc", "resourceVersion": "123"}, "spec": {"components": {
            "trainer": {"managementState": "Removed", "customConfig": "preserved"},
            "kueue": {"managementState": "Removed", "autoCreateQueues": False},
            "trainingoperator": {"managementState": "Removed"},
            "dashboard": {"managementState": "Managed"}}}}
        after = copy.deepcopy(original)
        after["spec"]["components"]["trainer"]["managementState"] = "Managed"
        ready = {"status": {"conditions": [{"type": "Available", "status": "True"},
                                            {"type": "Established", "status": "True"}]}}
        def get(kind, name, namespace=None):
            if kind in ("crd", "jobsetoperator"):
                return ready
            if kind == "csv":
                return {"status": {"phase": "Succeeded"}}
            return after
        calls = []
        def command(*args, payload=None):
            calls.append(args)
            return json.dumps({"items": [original]}) if args[0] == "get" else "patched"
        with tempfile.TemporaryDirectory() as directory, patch.object(MODULE, "get", side_effect=get), patch.object(MODULE, "oc", side_effect=command):
            backup = Path(directory) / "dsc.json"
            result = MODULE.enable_trainer(backup, True)
            self.assertTrue(result["kueue_preserved"])
            self.assertEqual(json.loads(backup.read_text()), original)
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
            mutation = [call for call in calls if call[0] == "patch"][0]
            operations = json.loads(mutation[-1])
            self.assertEqual(operations, [
                {"op": "test", "path": "/metadata/resourceVersion", "value": "123"},
                {"op": "replace", "path": "/spec/components/trainer/managementState", "value": "Managed"}])


if __name__ == "__main__":
    unittest.main()
