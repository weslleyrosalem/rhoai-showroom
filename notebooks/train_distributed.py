"""Train a CPU demand regressor with two real PyTorch DDP ranks.

This is a training demonstration, not a replacement for the accepted Ray forecast.
The last 28 calendar days are held out before fitting; no GPU or LLM is used.
"""
import csv
from datetime import date, timedelta
import json
import os
from pathlib import Path
import socket

import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel


def main():
    torch.set_num_threads(1)
    torch.manual_seed(42)
    dist.init_process_group("gloo")
    rank, world = dist.get_rank(), dist.get_world_size()
    if world != 2:
        raise RuntimeError("This example requires two distributed ranks")
    rows = list(csv.DictReader(Path(os.environ.get("AURORA_DEMAND_CSV", "/workspace/demand.csv")).open()))
    skus = sorted({r["sku"] for r in rows})
    end = max(date.fromisoformat(r["date"]) for r in rows)
    cutoff = end - timedelta(days=28)

    def encode(row):
        day = date.fromisoformat(row["date"])
        return ([float(row["sku"] == sku) for sku in skus]
                + [float(day.weekday() == d) for d in range(7)]
                + [day.timetuple().tm_yday / 365, float(row["promotion"])])

    train = [r for r in rows if date.fromisoformat(r["date"]) <= cutoff]
    test = [r for r in rows if date.fromisoformat(r["date"]) > cutoff]
    shard = train[rank::world]
    x = torch.tensor([encode(r) for r in shard], dtype=torch.float32)
    y = torch.tensor([[float(r["units"]) / 30] for r in shard])
    model = DistributedDataParallel(torch.nn.Sequential(torch.nn.Linear(len(encode(train[0])), 24),
                                                       torch.nn.ReLU(), torch.nn.Linear(24, 1)))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.015)
    print(json.dumps({"event": "rank_started", "rank": rank, "world_size": world,
                      "pod": socket.gethostname(), "training_rows": len(shard)}), flush=True)
    for _ in range(120):
        optimizer.zero_grad()
        loss = torch.nn.functional.mse_loss(model(x), y)
        loss.backward()
        optimizer.step()
    workers = [None] * world
    dist.all_gather_object(workers, socket.gethostname())
    if rank == 0:
        model.eval()
        with torch.no_grad():
            predictions = model.module(torch.tensor([encode(r) for r in test], dtype=torch.float32)).flatten() * 30
        mae = sum(abs(float(p) - float(r["units"])) for p, r in zip(predictions, test)) / len(test)
        last_week = {(r["sku"], date.fromisoformat(r["date"]).weekday()): float(r["units"])
                     for r in train if date.fromisoformat(r["date"]) > cutoff - timedelta(days=7)}
        baseline = sum(abs(last_week[(r["sku"], date.fromisoformat(r["date"]).weekday())] - float(r["units"]))
                       for r in test) / len(test)
        result = {"event": "training_completed", "framework": "pytorch-ddp-gloo", "world_size": world,
                  "workers": workers, "epochs": 120, "train_rows": len(train), "holdout_rows": len(test),
                  "train_end": cutoff.isoformat(), "holdout_end": end.isoformat(), "mae": mae,
                  "seasonal_naive_mae": baseline, "beats_baseline": mae <= baseline,
                  "promotion": "comparison only; accepted Ray forecast remains unchanged"}
        print(json.dumps(result), flush=True)
    dist.barrier()
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
