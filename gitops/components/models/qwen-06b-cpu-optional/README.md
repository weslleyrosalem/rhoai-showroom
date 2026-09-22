# Qwen0.6B on CPU — blocked pending runtime validation

The model is public and Apache2: `Qwen/Qwen3-0.6B`, revision `c1899de289a04d12100db370d81485cdf75e47ca`.

The reference cluster has validated NVIDIA vLLM presets, not a validated CPU serving image for this model. This directory deliberately contains no deployable inference resource. A CUDA image with `nvidia.com/gpu` removed is not a CPU runtime.

Before adding a component, select a CPU-enabled image pinned by digest, verify its architecture/instruction set on the actual workers, load this revision without remote code, run a health and bounded inference test, and record latency/memory. Only then add the runtime and deployment to an optional Kustomize profile. Do not present this module as running today.
