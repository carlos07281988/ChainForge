# ChainForge Verification Examples

This directory contains 31 self-verifying Python scripts that test every module
in the ChainForge framework. Run `python3 run_all.py` to execute all examples.

## Quick Start

```bash
cd /path/to/chainforge
.venv/bin/python3 example/run_all.py
# Or run a single example
.venv/bin/python3 example/01_core_tool.py
```

**Current total: 391 tests, 0 failures.**

## Examples by Module

### Core Modules (01-15)

| # | File | Module | Tests | Description |
|---|------|--------|-------|-------------|
| 01 | `01_core_tool.py` | `core/tool.py` | 18 | @tool, ToolSpec, schema generation |
| 02 | `02_core_message.py` | `core/message.py` | 27 | Message, Role, ContentPart |
| 03 | `03_core_stream.py` | `core/stream.py` | 20 | StreamEvent, Stream utilities |
| 04 | `04_core_pipeline.py` | `core/pipeline.py` | 9 | Pipeline composition, >> operator |
| 05 | `05_core_dag.py` | `core/graph.py` | 18 | DAG graph execution |
| 06 | `06_core_state.py` | `core/state.py` | 29 | AgentState, StateTracker |
| 07 | `07_core_structured_output.py` | `core/structured_output.py` | 15 | Pydantic structured output |
| 08 | `08_core_middleware.py` | `core/middleware.py` | 6 | Middleware chain |
| 09 | `09_testing_mock.py` | `testing/mock_llm.py` | 20 | MockLLM for testing |
| 10 | `10_parsers.py` | `parsers/` | 11 | JSON + Pydantic parsers |
| 11 | `11_memory_buffer.py` | `memory/buffer.py` | 11 | BufferMemory |
| 12 | `12_reasoning.py` | `reasoning/` | 8 | Reasoning strategies |
| 13 | `13_guardrails.py` | `guardrails/` | 18 | Guardrail types |
| 14 | `14_orchestration_swarm.py` | `orchestration/` | 9 | Swarm patterns |
| 15 | `15_tracing.py` | `tracing/` | 10 | Tracing spans |

### Phase 11-13: Agent Frontier (16-24)

| # | File | Module | Tests | Description |
|---|------|--------|-------|-------------|
| 16 | `16_time_travel.py` | `core/time_travel.py` | 13 | TimeTravelDebugger |
| 17 | `17_consensus.py` | `orchestration/consensus.py` | 17 | ConsensusAgent (4 strategies) |
| 18 | `18_self_evolving.py` | `agents/self_evolving.py` | 16 | SelfEvolvingAgent |
| 19 | `19_tool_synthesis.py` | `tools/synthesis.py` | 10 | ToolSynthesizer |
| 20 | `20_liquid_memory.py` | `memory/liquid.py` | 11 | LiquidMemory |
| 21 | `21_guardrail_injection.py` | `guardrails/injection.py` | 9 | PromptInjectionGuardrail |
| 22 | `22_provenance_graph.py` | `core/time_travel.py` | 7 | Execution Provenance Graph |
| 23 | `23_workflow_dsl.py` | `core/graph_dsl.py` | 9 | Workflow DSL |
| 24 | `24_multimodal.py` | `core/multimodal.py` | 4 | Multi-Modal Pipeline |

### Phase 14-16: Self-Optimization & Debug (25-31)

| # | File | Module | Tests | Description |
|---|------|--------|-------|-------------|
| 25 | `25_dream_mode.py` | `evolution/dream.py` | 7 | Dream/Simulation Mode |
| 26 | `26_tech_tree.py` | `evolution/tech_tree.py` | 7 | Technology Tree |
| 27 | `27_population.py` | `evolution/population.py` | 9 | Population Evolution |
| 28 | `28_behavior_test.py` | `testing/behavior.py` | 7 | Behavioral Testing |
| 29 | `29_budget.py` | `middleware/budget.py` | 9 | Performance Budget |
| 30 | `30_deploy.py` | `deploy.py` | 6 | Agent-as-Microservice |
| 31 | `31_aldp.py` | `aldp/` | 15 | ALDP Debug Protocol |

## Structure

Each example file is self-contained and prints pass/fail for each test:
- `\u2705` — test passed
- `\u274c` — test failed
- `Results: N passed, 0 failed` — final summary
