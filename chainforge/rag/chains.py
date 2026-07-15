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
"""RAG chains — retrieve and generate with LLM.

Provides:
  - RetrievalQA: basic retrieve-then-generate
  - SelfRAG: agent decides when and what to retrieve
  - CorrectiveRAG: agent evaluates and fixes retrieval quality
"""

from __future__ import annotations

import json
from typing import Any

from chainforge.core.message import Message
from chainforge.logging import get_logger
from chainforge.rag.retrievers import Retriever

logger = get_logger("rag.chains")

SELF_RAG_PROMPT = """You are an intelligent assistant that decides when to retrieve information.

Given the user's question, decide if you need to retrieve external information to answer.
If yes, generate a search query. If no, answer directly.

Respond in JSON:
{"need_retrieval": true/false, "search_query": "<query>", "reasoning": "<why>"}"""

CORRECTIVE_RAG_PROMPT = """Review the retrieved context and the user's question.

Does the context contain enough relevant information to answer the question well?

Respond in JSON:
{"sufficient": true/false, "gaps": ["<what's missing>"], "better_query": "<improved search query or empty>"}"""


class RetrievalQA:
    """Question-answering chain with document retrieval.

    Retrieves relevant documents for a question, builds a prompt with context,
    and generates an answer using the LLM.
    """

    def __init__(
        self,
        llm: Any,
        retriever: Retriever,
        *,
        k: int = 4,
        return_source_documents: bool = False,
        custom_prompt: str | None = None,
    ):
        self._llm = llm
        self._retriever = retriever
        self.k = k
        self.return_source_documents = return_source_documents
        self._custom_prompt = custom_prompt

    @property
    def default_prompt(self) -> str:
        return (
            "You are a helpful assistant. Use the following context to answer the question.\n\n"
            "Context:\n{context}\n\n"
            "Question: {question}\n\n"
            "Answer:"
        )

    async def run(self, question: str) -> str | dict[str, Any]:
        docs = await self._retriever.get_relevant_documents(question)
        docs = docs[:self.k]
        if not docs:
            return "No relevant documents found."
        context_parts = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", f"doc_{i}")
            context_parts.append(f"[Source: {source}]\n{doc.page_content}")
        context = "\n\n".join(context_parts)
        prompt_template = self._custom_prompt or self.default_prompt
        prompt = prompt_template.replace("{context}", context).replace("{question}", question)
        response = await self._llm.generate([Message(role="user", content=prompt)])
        answer = response.content or "No answer generated."
        if self.return_source_documents:
            return {
                "answer": answer,
                "sources": [{"content": d.page_content[:200], "metadata": d.metadata} for d in docs],
            }
        return answer


class SelfRAG:
    """Self-RAG: agent decides when and what to retrieve.

    The agent first decides if retrieval is needed. If yes, it retrieves
    and generates. If no, it answers directly from knowledge.

    Usage:
        rag = SelfRAG(llm=llm, retriever=retriever)
        answer = await rag.run("What is Python?")
    """

    def __init__(self, llm: Any, retriever: Retriever, *, k: int = 3):
        self._llm = llm
        self._retriever = retriever
        self.k = k

    async def run(self, question: str) -> str:
        # Step 1: Decide if retrieval is needed
        decision_resp = await self._llm.generate([
            Message.system(SELF_RAG_PROMPT),
            Message.user(f"Question: {question}"),
        ])
        raw = decision_resp.content or ""

        try:
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            decision = json.loads(raw)
        except (json.JSONDecodeError, Exception):
            decision = {"need_retrieval": True, "search_query": question, "reasoning": "default"}

        if not decision.get("need_retrieval", True):
            # Answer directly
            resp = await self._llm.generate([
                Message.user(f"Answer this question from your knowledge: {question}"),
            ])
            return resp.content or ""

        # Step 2: Retrieve
        query = decision.get("search_query", question)
        docs = await self._retriever.get_relevant_documents(query)
        docs = docs[:self.k]

        if not docs:
            # Fall back to direct answer
            resp = await self._llm.generate([
                Message.user(f"No documents found. Answer from knowledge: {question}"),
            ])
            return resp.content or ""

        context = "\n\n".join(f"[{d.metadata.get('source', f'doc_{i}')}]\n{d.page_content}" for i, d in enumerate(docs))

        # Step 3: Generate with context
        resp = await self._llm.generate([
            Message.system(f"Context:\n{context}\n\nAnswer the question using the context above."),
            Message.user(question),
        ])
        return resp.content or ""


class CorrectiveRAG:
    """Corrective RAG: agent evaluates retrieval quality and fixes it.

    After retrieval, the agent checks if the context is sufficient.
    If not, it generates a better query and retrieves again.

    Usage:
        rag = CorrectiveRAG(llm=llm, retriever=retriever, max_retries=2)
        answer = await rag.run("Explain quantum computing")
    """

    def __init__(self, llm: Any, retriever: Retriever, *, k: int = 3, max_retries: int = 1):
        self._llm = llm
        self._retriever = retriever
        self.k = k
        self.max_retries = max_retries

    async def run(self, question: str) -> str:
        query = question

        for attempt in range(self.max_retries + 1):
            # Retrieve
            docs = await self._retriever.get_relevant_documents(query)
            docs = docs[:self.k]

            if not docs:
                logger.info(f"CorrectiveRAG: no docs for '{query}', retry={attempt}")
                resp = await self._llm.generate([
                    Message.user(f"Answer this question from your knowledge: {question}"),
                ])
                return resp.content or ""

            context = "\n\n".join(f"[{d.metadata.get('source', f'doc_{i}')}]\n{d.page_content[:500]}" for i, d in enumerate(docs))

            # Evaluate retrieval quality
            eval_resp = await self._llm.generate([
                Message.system(CORRECTIVE_RAG_PROMPT),
                Message.user(f"Question: {question}\n\nRetrieved context:\n{context}"),
            ])
            raw = eval_resp.content or ""

            try:
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
                evaluation = json.loads(raw)
            except (json.JSONDecodeError, Exception):
                evaluation = {"sufficient": True, "gaps": [], "better_query": ""}

            if evaluation.get("sufficient", True):
                # Generate final answer
                resp = await self._llm.generate([
                    Message.system(f"Context:\n{context}\n\nAnswer the question thoroughly."),
                    Message.user(question),
                ])
                return resp.content or ""

            # Not sufficient: try again with improved query
            better_query = evaluation.get("better_query", "")
            if better_query and attempt < self.max_retries:
                logger.info(f"CorrectiveRAG: retrying with better query: {better_query}")
                query = better_query
            else:
                # Fallback
                resp = await self._llm.generate([
                    Message.user(f"Answer as best you can (limited context available): {question}"),
                ])
                return resp.content or ""

        resp = await self._llm.generate([
            Message.user(f"Answer this question: {question}"),
        ])
        return resp.content or ""
