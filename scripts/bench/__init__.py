"""scripts/bench — F1 harness for the step-aware benchmark loop.

Reads BrickLink Studio 2.0 `.io` files (step-aware LDraw archives) from an
external corpus (defaults to LegoGPT's normalized_io/), classifies them by
step count, renders ground-truth views per step, and emits oracle specs.

Nothing in this package modifies the main pipeline (ImprovementLoopV2,
ModelRouter, agent_roles); it only *consumes* them as libraries in later
phases (F2-F6). F1 — this module set — only prepares the dataset.
"""
