# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Workflow templates — known patterns mapped to IntentSchemas.

Templates provide instant compilation for common agent workflows without
requiring an LLM. Each template has keywords, a description, and a factory
function that produces an IntentSchema.
"""

from __future__ import annotations

from chainforge.compiler.schema import EdgeDef, IntentSchema, NodeDef, NodeType


# ── Template registry ─────────────────────────────────────────────────────

class WorkflowTemplate:
    """A named template that maps a description + keywords to an IntentSchema."""

    def __init__(self, name: str, description: str, keywords: list[str],
                 build_fn):
        self.name = name
        self.description = description
        self.keywords = keywords
        self._build = build_fn

    def build(self, user_input: str | None = None) -> IntentSchema:
        return self._build(user_input or self.description)

    def matches(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.keywords)


# ── Template definitions ──────────────────────────────────────────────────

def _build_search_then_answer(user_input: str) -> IntentSchema:
    return IntentSchema(
        name="search_and_answer",
        description=user_input,
        nodes=[
            NodeDef(id="entry", type=NodeType.entry, description="Start"),
            NodeDef(id="search", type=NodeType.tool, tool="web_search",
                    description="Search the web"),
            NodeDef(id="check", type=NodeType.conditional,
                    description="Check if search returned results"),
            NodeDef(id="answer_with_search", type=NodeType.llm,
                    prompt="Answer based on search results.",
                    description="Answer with search context"),
            NodeDef(id="answer_direct", type=NodeType.llm,
                    prompt="Answer using your own knowledge.",
                    description="Answer from knowledge"),
            NodeDef(id="exit", type=NodeType.exit, description="End"),
        ],
        edges=[
            EdgeDef(source="entry", target="search"),
            EdgeDef(source="search", target="check"),
            EdgeDef(source="check", target="answer_with_search",
                    condition="has_results"),
            EdgeDef(source="check", target="answer_direct",
                    condition="no_results"),
            EdgeDef(source="answer_with_search", target="exit"),
            EdgeDef(source="answer_direct", target="exit"),
        ],
        tools=["web_search"],
    )


def _build_plan_and_execute(user_input: str) -> IntentSchema:
    return IntentSchema(
        name="plan_and_execute",
        description=user_input,
        nodes=[
            NodeDef(id="entry", type=NodeType.entry, description="Start"),
            NodeDef(id="planner", type=NodeType.llm,
                    prompt="Plan the steps needed to accomplish: {input}",
                    description="Generate execution plan"),
            NodeDef(id="executor", type=NodeType.step,
                    description="Execute each step sequentially"),
            NodeDef(id="synthesizer", type=NodeType.llm,
                    prompt="Synthesize results into final answer.",
                    description="Synthesize results"),
            NodeDef(id="exit", type=NodeType.exit, description="End"),
        ],
        edges=[
            EdgeDef(source="entry", target="planner"),
            EdgeDef(source="planner", target="executor"),
            EdgeDef(source="executor", target="synthesizer"),
            EdgeDef(source="synthesizer", target="exit"),
        ],
    )


def _build_reflect_and_improve(user_input: str) -> IntentSchema:
    return IntentSchema(
        name="reflect_and_improve",
        description=user_input,
        nodes=[
            NodeDef(id="entry", type=NodeType.entry, description="Start"),
            NodeDef(id="generate", type=NodeType.llm,
                    prompt="Generate a response to: {input}",
                    description="Generate initial response"),
            NodeDef(id="critique", type=NodeType.llm,
                    prompt="Critique the response. Identify flaws.",
                    description="Self-critique"),
            NodeDef(id="improve", type=NodeType.llm,
                    prompt="Improve the response based on critique.",
                    description="Improve based on critique"),
            NodeDef(id="check_quality", type=NodeType.conditional,
                    description="Check if quality is acceptable"),
            NodeDef(id="exit", type=NodeType.exit, description="End"),
        ],
        edges=[
            EdgeDef(source="entry", target="generate"),
            EdgeDef(source="generate", target="critique"),
            EdgeDef(source="critique", target="improve"),
            EdgeDef(source="improve", target="check_quality"),
            EdgeDef(source="check_quality", target="exit",
                    condition="acceptable"),
            EdgeDef(source="check_quality", target="critique",
                    condition="needs_improvement"),
        ],
    )


def _build_tool_chain(user_input: str) -> IntentSchema:
    return IntentSchema(
        name="tool_chain",
        description=user_input,
        nodes=[
            NodeDef(id="entry", type=NodeType.entry, description="Start"),
            NodeDef(id="tool1", type=NodeType.tool, tool="",
                    description="First tool (detect from input)"),
            NodeDef(id="tool2", type=NodeType.tool, tool="",
                    description="Second tool (detect from input)"),
            NodeDef(id="summarize", type=NodeType.llm,
                    prompt="Summarize the tool results.",
                    description="Summarize all results"),
            NodeDef(id="exit", type=NodeType.exit, description="End"),
        ],
        edges=[
            EdgeDef(source="entry", target="tool1"),
            EdgeDef(source="tool1", target="tool2"),
            EdgeDef(source="tool2", target="summarize"),
            EdgeDef(source="summarize", target="exit"),
        ],
    )


def _build_rag_pipeline(user_input: str) -> IntentSchema:
    return IntentSchema(
        name="rag_pipeline",
        description=user_input,
        nodes=[
            NodeDef(id="entry", type=NodeType.entry, description="Start"),
            NodeDef(id="retrieve", type=NodeType.tool, tool="retrieve",
                    description="Retrieve relevant documents"),
            NodeDef(id="augment", type=NodeType.step,
                    description="Augment prompt with retrieved context"),
            NodeDef(id="generate", type=NodeType.llm,
                    prompt="Answer based on retrieved context.",
                    description="Generate with context"),
            NodeDef(id="exit", type=NodeType.exit, description="End"),
        ],
        edges=[
            EdgeDef(source="entry", target="retrieve"),
            EdgeDef(source="retrieve", target="augment"),
            EdgeDef(source="augment", target="generate"),
            EdgeDef(source="generate", target="exit"),
        ],
        tools=["retrieve"],
    )


def _build_router(user_input: str) -> IntentSchema:
    return IntentSchema(
        name="intent_router",
        description=user_input,
        nodes=[
            NodeDef(id="entry", type=NodeType.entry, description="Start"),
            NodeDef(id="classifier", type=NodeType.llm,
                    prompt="Classify the intent of: {input}. "
                           "Route to the appropriate handler.",
                    description="Classify intent"),
            NodeDef(id="handler_a", type=NodeType.llm,
                    prompt="Handle category A request.",
                    description="Handler for category A"),
            NodeDef(id="handler_b", type=NodeType.llm,
                    prompt="Handle category B request.",
                    description="Handler for category B"),
            NodeDef(id="handler_default", type=NodeType.llm,
                    prompt="Handle general request.",
                    description="Default handler"),
            NodeDef(id="synthesize", type=NodeType.step,
                    description="Synthesize handler result"),
            NodeDef(id="exit", type=NodeType.exit, description="End"),
        ],
        edges=[
            EdgeDef(source="entry", target="classifier"),
            EdgeDef(source="classifier", target="handler_a",
                    condition="category_a"),
            EdgeDef(source="classifier", target="handler_b",
                    condition="category_b"),
            EdgeDef(source="classifier", target="handler_default",
                    condition="other"),
            EdgeDef(source="handler_a", target="synthesize"),
            EdgeDef(source="handler_b", target="synthesize"),
            EdgeDef(source="handler_default", target="synthesize"),
            EdgeDef(source="synthesize", target="exit"),
        ],
    )


# ── Template registry ─────────────────────────────────────────────────────

_AVAILABLE_TEMPLATES: list[WorkflowTemplate] = [
    WorkflowTemplate(
        "search_and_answer",
        "Search the web and answer questions",
        ["search", "find", "look up", "google", "web", "answer", "question"],
        _build_search_then_answer,
    ),
    WorkflowTemplate(
        "plan_and_execute",
        "Plan steps then execute them",
        ["plan", "execute", "step", "multi-step", "complex"],
        _build_plan_and_execute,
    ),
    WorkflowTemplate(
        "reflect_and_improve",
        "Generate, self-critique, then improve",
        ["reflect", "improve", "critique", "revise", "review", "refine"],
        _build_reflect_and_improve,
    ),
    WorkflowTemplate(
        "rag_pipeline",
        "Retrieve context, augment, then generate",
        ["retrieve", "rag", "context", "document", "knowledge base",
         "search and answer"],
        _build_rag_pipeline,
    ),
    WorkflowTemplate(
        "intent_router",
        "Classify intent and route to different handlers",
        ["route", "classify", "categorize", "different types", "conditional"],
        _build_router,
    ),
    WorkflowTemplate(
        "tool_chain",
        "Chain multiple tools together",
        ["chain", "tool chain", "sequential", "pipeline"],
        _build_tool_chain,
    ),
]


def get_templates() -> list[WorkflowTemplate]:
    """Return all available templates."""
    return list(_AVAILABLE_TEMPLATES)


def find_matching_templates(text: str) -> list[WorkflowTemplate]:
    """Find templates matching the given text."""
    return [t for t in _AVAILABLE_TEMPLATES if t.matches(text)]


def best_template(text: str) -> WorkflowTemplate | None:
    """Find the single best-matching template by keyword density."""
    text_lower = text.lower()
    best = None
    best_count = 0
    for t in _AVAILABLE_TEMPLATES:
        count = sum(1 for kw in t.keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best = t
    return best if best_count > 0 else None


def get_template(name: str) -> WorkflowTemplate | None:
    """Get a template by name."""
    for t in _AVAILABLE_TEMPLATES:
        if t.name == name:
            return t
    return None


def list_templates() -> list[dict[str, str]]:
    """List all templates with descriptions."""
    return [
        {"name": t.name, "description": t.description, "keywords": t.keywords}
        for t in _AVAILABLE_TEMPLATES
    ]
