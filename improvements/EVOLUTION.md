# Evolution Module — Self-Optimizing Agents

> Three mechanisms for agent self-improvement: Dream Mode, Technology Tree, and Population Evolution.

## Overview

```
evolution/
├── dream.py        # Predict tool outcomes before executing
├── tech_tree.py    # Unlock capabilities through usage
└── population.py   # Multi-generational genetic algorithm
```

## Dream / Simulation Mode

Agents predict tool call results before executing them, compare with actual outcomes, and learn from discrepancies.

**Levels:**
- `off` — no prediction
- `light` — predict tool result only
- `medium` — predict + evaluate correctness
- `deep` — full reasoning trace simulation

**Key API:**
- `record_prediction(name, args, prediction, confidence)` — record before execution
- `record_actual(name, args, actual)` — record and compare with prediction
- `accuracy()` — overall prediction accuracy rate
- `low_confidence_patterns()` — tools/patterns where predictions consistently fail
- `summary()` — full statistics

## Technology Tree

Inspired by Civilization games: agents unlock new capabilities by using tools and accumulating experience.

**Key API:**
- `add_node(id, name, desc, requires, required_count)` — define a tech node
- `record_usage(tool_name)` — track tool usage
- `check_unlocks()` — evaluate conditions and unlock eligible nodes
- `on_unlock(listener)` — register callback for unlock events
- `plot()` — ASCII visualization of tree
- `default_tech_tree()` — pre-built tree with 7+ nodes

**Node Properties:**
- `requires` — parent node IDs that must be unlocked first
- `required_count` — number of tool uses required
- `required_tool` — specific tool to track (or all tools)

## Population Evolution

Genetic algorithm framework that evolves optimal agent configurations.

**Key API:**
- `initialize(base_config, size)` — create initial population
- `evolve(fitness_scores)` — tournament selection + crossover + mutation
- `best_individual` — highest-fitness individual
- `avg_fitness` — population average
- `fitness_history()` — evolution data for plotting
- `summary()` — formatted statistics

**Genome Parameters:**
- `temperature`, `max_iterations`, `reasoning_enabled`, `parallel_tool_calls`

**Evolution Operators:**
- Tournament selection (size=3)
- Uniform crossover (rate=0.5)
- Gaussian mutation (rate=0.2)
- Elite preservation (top 2)
