"""Verify candidate guards and the create-only registry workflow without a cluster."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("register_model", ROOT / "gitops/components/models/register_model.py")
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)
CANDIDATE = json.loads((ROOT / "gitops/components/models/registry/qwen-4b-candidate.json").read_text())


class FakeClient:
    def __init__(self):
        self.data = {}
        self.created = 0

    def items(self, path):
        return copy.deepcopy(self.data.get(path, []))

    def request(self, path, body):
        self.created += 1
        record = {"id": str(self.created), **copy.deepcopy(body)}
        self.data.setdefault(path, []).append(record)
        return copy.deepcopy(record)


class RegistrationTest(unittest.TestCase):
    def test_plan_creates_nothing(self):
        client = FakeClient()
        result = registry.onboard(client, registry.validate_candidate(CANDIDATE), False)
        self.assertEqual(client.created, 0)
        self.assertTrue(all(item["action"] == "would_create" for item in result.values()))

    def test_apply_then_repeat_preserves_all_ids(self):
        client = FakeClient()
        first = registry.onboard(client, CANDIDATE, True)
        second = registry.onboard(client, CANDIDATE, True)
        self.assertEqual(client.created, 3)
        self.assertEqual([x["id"] for x in first.values()], [x["id"] for x in second.values()])
        self.assertTrue(all(item["action"] == "preserved" for item in second.values()))

    def test_partial_registration_resumes(self):
        client = FakeClient()
        registry.onboard(client, CANDIDATE, True)
        client.data.pop(registry.API + "/model_versions/2/artifacts")
        result = registry.onboard(client, CANDIDATE, True)
        self.assertEqual(result["model_artifact"]["action"], "created")
        self.assertEqual(result["model_version"]["id"], "2")

    def test_unowned_name_collision_is_rejected(self):
        client = FakeClient()
        client.data[registry.API + "/registered_models"] = [{"id": "10", "name": CANDIDATE["registered_model_name"]}]
        with self.assertRaisesRegex(ValueError, "not owned"):
            registry.onboard(client, CANDIDATE, True)
        self.assertEqual(client.created, 0)

    def test_immutable_revision_drift_is_rejected(self):
        client = FakeClient()
        registry.onboard(client, CANDIDATE, True)
        version = client.data[registry.API + "/registered_models/1/versions"][0]
        version["customProperties"]["showroom.revision"]["string_value"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "provenance differs"):
            registry.onboard(client, CANDIDATE, True)

    def test_later_evaluation_is_never_reset(self):
        client = FakeClient()
        registry.onboard(client, CANDIDATE, True)
        version = client.data[registry.API + "/registered_models/1/versions"][0]
        version["customProperties"]["showroom.safety_evaluation"]["string_value"] = "FAILED"
        registry.onboard(client, CANDIDATE, True)
        self.assertEqual(version["customProperties"]["showroom.safety_evaluation"]["string_value"], "FAILED")

    def test_mutable_pin_and_premature_approval_are_rejected(self):
        for key, value in [("revision", "main"), ("runtime_image", "image:latest"),
                           ("uri", "hf://wrong/model:main"), ("lifecycle", "approved"),
                           ("safety_evaluation", "PASSED")]:
            candidate = {**CANDIDATE, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                registry.validate_candidate(candidate)

    def test_candidate_matches_lock_file(self):
        lock = json.loads((ROOT / "gitops/components/models/models.lock.json").read_text())
        model = next(x for x in lock["models"] if x["manifest"] == "qwen-4b")
        for key in ["model", "revision", "license", "source"]:
            self.assertEqual(CANDIDATE[key], model[key])
        self.assertEqual(CANDIDATE["runtime_image"], lock["runtime_image"])


if __name__ == "__main__":
    unittest.main()
