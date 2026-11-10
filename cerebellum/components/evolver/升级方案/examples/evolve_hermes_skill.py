#!/usr/bin/env python3
"""Evolver v3.0 使用示例"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def example_1_basic_generation():
    print("
" + "="*60)
    print("示例1: 基本技能生成 (不进化)")
    print("="*60)
    print("  engine.generate(topic, output_dir)")
    print("  -> 一次性 LLM 合成，无迭代优化")


def example_2_gepa_evolution():
    print("
" + "="*60)
    print("示例2: GEPA 进化技能")
    print("="*60)
    from evolver.evolution_config import EvolutionConfig
    config = EvolutionConfig(
        optimizer_model="openai/gpt-4.1",
        eval_model="openai/gpt-4.1-mini",
        max_iterations=10,
    )
    print(f"  optimizer_model: {config.optimizer_model}")
    print(f"  eval_model: {config.eval_model}")
    print(f"  max_iterations: {config.max_iterations}")


def example_3_hermes_integration():
    print("
" + "="*60)
    print("示例3: Hermes Agent 集成")
    print("="*60)
    print("  integration.evolve_hermes_skill(skill_name, iterations)")
    print("  -> 自动备份、进化、验证、写入")


def example_4_validation():
    print("
" + "="*60)
    print("示例4: 技能约束验证")
    print("="*60)
    print("  validator.validate(skill_text)")
    print("  -> 结构+大小+语义保持 检查")


def example_5_batch_evolution():
    print("
" + "="*60)
    print("示例5: 批量进化")
    print("="*60)
    skills = ["novel-writer", "novel-review", "agent-orchestrator"]
    for skill in skills:
        print(f"  进化: {skill}...")
    print(f"  预估成本: ~${len(skills) * 5 * 0.3:.2f}")


if __name__ == "__main__":
    print("Evolver v3.0 使用示例")
    print("="*60)
    example_1_basic_generation()
    example_2_gepa_evolution()
    example_3_hermes_integration()
    example_4_validation()
    example_5_batch_evolution()
    print("
提示: 需要设置 OPENAI_API_KEY 环境变量")
