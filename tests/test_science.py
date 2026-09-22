import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
science = load("science", ROOT / "scripts/science.py")
rag = load("rag", ROOT / "apps/aurora-rag/rag.py")

class ScienceTest(unittest.TestCase):
    def test_synthetic_data_is_reproducible_and_products_join(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            first = science.generate(path / "first")
            second = science.generate(path / "second")
            self.assertEqual(first, second)
            self.assertEqual(len(first), 365 * 8)
            self.assertEqual({r["sku"] for r in first}, {p["sku"] for p in science.PRODUCTS})
            for row in first:
                self.assertGreaterEqual(row["units"], 0)
            recorded = json.loads((path / "first/provenance.json").read_text())
            self.assertEqual(recorded["sha256"], hashlib.sha256((path / "first/demand.csv").read_bytes()).hexdigest())

    def test_real_model_holdout_and_gate(self):
        rows = science.read_rows(ROOT / "data/demand.csv")
        models = [science.train_sku(rows, p["sku"]) for p in science.PRODUCTS]
        self.assertTrue(all(m["train_end"] < m["test_start"] for m in models))
        self.assertTrue(all(len(m["forecast"]) == 7 for m in models))
        self.assertTrue(all(m["mae"] <= m["baseline_mae"] for m in models))
        self.assertTrue(any(not m["candidate_passed_quality_gate"] for m in models))
        self.assertTrue(any(m["candidate_passed_quality_gate"] for m in models))
        # Corrupting held-out labels cannot change fitted regression weights.
        altered = [dict(row, units=999) if row["date"] >= "2025-12-04" else row for row in rows]
        old = science.train_sku(rows, "AS-001"); new = science.train_sku(altered, "AS-001")
        self.assertEqual(old["weights"], new["weights"])
        self.assertNotEqual(old["candidate_mae"], new["candidate_mae"])

    def test_retrieval_citations_are_existing_files(self):
        retriever = rag.Retriever(ROOT / "data/documents")
        cases = [("What is the return deadline after receiving a product?", "returns-policy.md"),
                 ("Approval of a purchase proposal above 5000", "purchasing-policy.md"),
                 ("target inventory coverage days", "inventory-playbook.md")]
        for question, expected in cases:
            found = retriever.retrieve(question)
            self.assertEqual(found[0]["document_id"], expected)
            self.assertTrue(all((ROOT / "data/documents" / x["document_id"]).exists() for x in found))
        self.assertEqual(retriever.retrieve("xyzunrelatedtoken"), [])

    def test_corpus_version_changes_when_policy_or_answers_change(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "data"
            shutil.copytree(ROOT / "data", copied)
            original = science.corpus_prefix(copied)
            self.assertEqual(original, science.corpus_prefix(ROOT / "data"))
            policy = copied / "documents/purchasing-policy.md"
            policy.write_text(policy.read_text() + "\nUpdated policy.\n")
            self.assertNotEqual(original, science.corpus_prefix(copied))

    def test_autorag_ground_truth_references_valid_documents(self):
        for case in json.loads((ROOT / "data/eval/autorag.json").read_text()):
            self.assertTrue(case["question"])
            self.assertTrue(case["correct_answers"])
            for doc in case["correct_answer_document_ids"]:
                self.assertTrue((ROOT / "data/documents" / doc).is_file())

if __name__ == "__main__":
    unittest.main()
