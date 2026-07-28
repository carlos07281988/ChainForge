"""ChainForge Enterprise: Agent Distillation Pipeline example.

Usage:
    python examples/enterprise/distill_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.distill import (
    TrainingDataCollector, TrainingDataset,
    DistillationPipeline, LoRAAdapter, LoRAConfig,
)

async def main():
    print("=== Agent Distillation Pipeline ===\n")

    # 1. LoRA Adapter configuration
    adapter = LoRAAdapter(base_model="qwen2.5-3b")
    print("1. LoRA Adapter Configuration:")
    print(f"   Base model: {adapter.base_model}")
    print(f"   Rank (r): {adapter.config.r}")
    print(f"   Alpha: {adapter.config.alpha}")
    print(f"   Target modules: {adapter.config.target_modules}")

    # Export for different frameworks
    unsloth_cfg = adapter.to_framework("unsloth")
    print(f"\n   Unsloth export: r={unsloth_cfg['r']}, alpha={unsloth_cfg['lora_alpha']}")
    tr_cfg = adapter.to_framework("transformers")
    print(f"   Transformers export: task_type={tr_cfg['task_type']}")
    vllm_cfg = adapter.to_framework("vllm")
    print(f"   vLLM export: max_lora_rank={vllm_cfg['max_lora_rank']}")

    # VRAM estimation
    vram = adapter.estimate_vram("bf16")
    print(f"\n2. VRAM Estimation (bf16):")
    print(f"   Base model: {vram['base_model_vram_gb']} GB")
    print(f"   LoRA overhead: {vram['lora_adapter_vram_gb']} GB")
    print(f"   Total: {vram['total_vram_gb']} GB")

    # 2. Training Data Collector
    collector = TrainingDataCollector()
    print(f"\n3. Training Data Collector:")
    print(f"   Pairs collected: {collector.pair_count}")
    print(f"   (In production: collector.middleware() records real agent I/O)")

    # 3. Distillation Pipeline
    pipeline = DistillationPipeline(
        teacher=None,  # In production: your gpt-4o agent
        student_model="qwen2.5-3b",
        framework="unsloth",
    )
    print(f"\n4. Distillation Pipeline:")
    print(f"   Teacher: gpt-4o agent")
    print(f"   Student: {pipeline._student_model}")
    print(f"   Framework: {pipeline._framework}")

    # Create a mock dataset
    dataset = TrainingDataset(
        name="customer-support-v1",
        format="alpaca",
        total_pairs=5000,
        total_tokens=2_500_000,
        total_cost=75.0,
    )
    print(f"\n5. Dataset: {dataset.name}")
    print(f"   Pairs: {dataset.total_pairs}")
    print(f"   Tokens: {dataset.total_tokens:,}")
    print(f"   Cost collected: ${dataset.total_cost:.2f}")

    # Distill
    result = await pipeline.distill(dataset, epochs=3, lora_r=16, lora_alpha=32)
    print(f"\n6. Distillation Result:")
    print(f"   Status: {result.status}")
    print(f"   Output model: {result.output_model}")
    print(f"   Recovery rate: {result.recovery_rate:.0%}")
    print(f"   Teacher score: {result.teacher_score:.2f}")
    print(f"   Student score: {result.student_score:.2f}")
    print(f"   Cost saved/month: ${result.cost_saved_per_month:.2f}")
    if result.lora_config:
        print(f"   LoRA config: r={result.lora_config.r}, alpha={result.lora_config.alpha}")

if __name__ == "__main__":
    asyncio.run(main())
