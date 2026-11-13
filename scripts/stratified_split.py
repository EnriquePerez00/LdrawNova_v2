#!/usr/bin/env python3
"""
Stratified Train/Validation Split for Corpus Dataset
======================================================

Partitions the corpus into 70% train / 30% validation, stratified by tier,
to enable proper evaluation without data leakage (bundle synthesis on train,
KPI measurement on validation).

Usage:
    python3 scripts/stratified_split.py --corpus data/dataset_splits/corpus_all_pairs.json \
        --output outputs/corpus_splits --seed 42 --train-ratio 0.7
"""

from __future__ import annotations

import argparse
import json
import os
import random
from collections import defaultdict
from typing import Dict, List, Tuple, Any


def stratified_split(
    corpus: List[Dict[str, Any]],
    train_ratio: float = 0.7,
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Splits corpus into train/val stratified by tier.
    
    Args:
        corpus: List of MOC items (each with 'complexity_tier' key)
        train_ratio: Fraction for training (default 0.7)
        seed: Random seed for reproducibility
    
    Returns:
        (train_split, val_split)
    """
    random.seed(seed)
    
    # Group by tier
    by_tier: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in corpus:
        tier = item.get("complexity_tier", "UNKNOWN")
        by_tier[tier].append(item)
    
    train_split: List[Dict[str, Any]] = []
    val_split: List[Dict[str, Any]] = []
    
    # Split each tier independently
    for tier, items in by_tier.items():
        random.shuffle(items)
        split_idx = int(len(items) * train_ratio)
        train_split.extend(items[:split_idx])
        val_split.extend(items[split_idx:])
    
    return train_split, val_split


def main():
    parser = argparse.ArgumentParser(description="Stratified Train/Val split for corpus")
    parser.add_argument(
        "--corpus",
        type=str,
        default="data/dataset_splits/corpus_all_pairs.json",
        help="Path to corpus JSON file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs/corpus_splits",
        help="Output directory for split JSONs",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.7,
        help="Fraction of corpus for training (default 0.7 = 70 percent train, 30 percent val)",
    )
    args = parser.parse_args()
    
    if not os.path.exists(args.corpus):
        print(f"❌ Corpus file not found: {args.corpus}")
        return
    
    with open(args.corpus) as f:
        corpus = json.load(f)
    
    print(f"📊 Corpus: {len(corpus)} items")
    
    train, val = stratified_split(corpus, train_ratio=args.train_ratio, seed=args.seed)
    
    os.makedirs(args.output, exist_ok=True)
    
    train_path = os.path.join(args.output, "train_split.json")
    val_path = os.path.join(args.output, "val_split.json")
    
    with open(train_path, "w") as f:
        json.dump(train, f, indent=2)
    with open(val_path, "w") as f:
        json.dump(val, f, indent=2)
    
    # Print stratification report
    by_tier_train = defaultdict(int)
    by_tier_val = defaultdict(int)
    for item in train:
        by_tier_train[item.get("complexity_tier", "?")] += 1
    for item in val:
        by_tier_val[item.get("complexity_tier", "?")] += 1
    
    print(f"\n✅ Split completed:")
    print(f"  Train: {len(train)} items ({100*len(train)/len(corpus):.1f}%)")
    print(f"  Val:   {len(val)} items ({100*len(val)/len(corpus):.1f}%)")
    print(f"\n  Train by tier:")
    for tier in sorted(by_tier_train.keys()):
        print(f"    {tier}: {by_tier_train[tier]}")
    print(f"\n  Val by tier:")
    for tier in sorted(by_tier_val.keys()):
        print(f"    {tier}: {by_tier_val[tier]}")
    print(f"\n  Outputs:")
    print(f"    Train: {train_path}")
    print(f"    Val:   {val_path}")


if __name__ == "__main__":
    main()
