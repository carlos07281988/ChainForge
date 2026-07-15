# ChainForge Verification Examples

This directory contains 30 self-verifying Python scripts that test every module
in the ChainForge framework. Run `python3 run_all.py` to execute all examples.

## Core Modules (01-15)

| # | File | Module | Tests |
|---|------|--------|-------|
| 01 | `01_core_tool.py` | Tool protocol, @tool, ToolSpec | 18 |
| 02 | `02_core_message.py` | Message, Role, ContentPart | 27 |
| 03 | `03_core_stream.py` | StreamEvent, Stream utilities | 20 |
| 04 | `04_core_pipeline.py` | Pipeline composition | 9 |
| 05 | `05_core_dag.py` | DAG graph execution | 18 |
| 06 | `06_core_state.py` | AgentState, StateTracker | 29 |
| 07 | `07_core_structured_output.py` | Pydantic structured output | 15 |
| 08 | `08_core_middleware.py` | Middleware chain | 6 |
| 09 | `09_testing_mock.py` | MockLLM for testing | 20 |
| 10 | `10_parsers.py` | JSON + Pydantic parsers | 11 |
| 11 | `11_memory_buffer.py` | BufferMemory | 11 |
| 12 | `12_reasoning.py` | Reasoning strategies | 8 |
| 13 | `13_guardrails.py` | GuardrailResult, actions | 18 |
| 14 | `14_orchestration_swarm.py` | Swarm patterns | 9 |
| 15 | `15_tracing.py` | Tracing spans | 10 |

## Phase 11-13: Agent Frontier (16-24)

| # | File | Module | Tests |
|---|------|--------|-------|
| 16 | `16_time_travel.py` | TimeTravelDebugger | 13 |
| 17 | `17_consensus.py` | ConsensusAgent | 17 |
| 18 | `18_self_evolving.py` | SelfEvolvingAgent | 16 |
| 19 | `19_tool_synthesis.py` | ToolSynthesizer | 10 |
| 20 | `20_liquid_memory.py` | LiquidMemory | 11 |
| 21 | `21_guardrail_injection.py` | PromptInjectionGuardrail | 9 |
| 22 | `22_provenance_graph.py` | Execution Provenance Graph | 7 |
| 23 | `23_workflow_dsl.py` | Declarative Workflow DSL | 9 |
| 24 | `24_multimodal.py` | Multi-Modal Pipeline | 4 |

## Phase 14-15: Self-Optimization & Quality (25-30)

| # | File | Module | Tests |
|---|------|--------|-------|
| 25 | `25_dream_mode.py` | Dream/Simulation Mode | 7 |
| 26 | `26_tech_tree.py` | Technology Tree | 7 |
| 27 | `27_population.py` | Population Evolution | 9 |
| 28 | `28_behavior_test.py` | Behavioral Testing | 7 |
| 29 | `29_budget.py` | Performance Budget | 9 |
| 30 | `30_deploy.py` | Agent-as-Microservice | 6 |

## Running

```bash
# Run all examples
cd /path/to/chainforge
.venv/bin/python3 example/run_all.py

# Run a single example
.venv/bin/python3 example/01_core_tool.py
```

**Current total: 376 tests, 0 failures.**
