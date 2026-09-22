"""Build the transparent Aurora allocation policy graph (onnx==1.19.1).

This is a deterministic demonstration classifier, not a learned demand model.
It recommends expedited review when seven-day demand exceeds available stock.
Warehouse zone is recorded for monitoring but does not affect the decision.
"""
from pathlib import Path
import onnx
from onnx import TensorProto, helper

root = Path(__file__).resolve().parent
features = helper.make_tensor_value_info("inventory", TensorProto.DOUBLE, ["batch", 3])
output = helper.make_tensor_value_info("expedite", TensorProto.INT64, ["batch", 1])
weights = helper.make_tensor("weights", TensorProto.DOUBLE, [3, 1], [0, 1, -1])
zero = helper.make_tensor("zero", TensorProto.DOUBLE, [1], [0])
graph = helper.make_graph([
    helper.make_node("MatMul", ["inventory", "weights"], ["gap"]),
    helper.make_node("Greater", ["gap", "zero"], ["needs_review"]),
    helper.make_node("Cast", ["needs_review"], ["expedite"], to=TensorProto.INT64),
], "Aurora inventory expedited-review policy", [features], [output], [weights, zero])
model = helper.make_model(graph, producer_name="rhoai-showroom", opset_imports=[helper.make_opsetid("", 13)], ir_version=8)
model.doc_string = "Synthetic warehouse service-level monitoring. Inputs: warehouse_zone, demand_7d, available_units. Output: expedite review (1/0). No purchase authorization."
onnx.checker.check_model(model)
onnx.save(model, root / "allocation.onnx")
print(f"Wrote {root / 'allocation.onnx'} ({(root / 'allocation.onnx').stat().st_size} bytes)")
