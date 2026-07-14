# Copyright 2024 ChainForge Contributors
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
"""RAG chains — retrieve and generate with LLM."""

from __future__ import annotations

from typing import Any

from chainforge.logging import get_logger
from chainforge.rag.retrievers import Retriever

logger = get_logger("rag.chains")


class RetrievalQA:
    """Question-answering chain with document retrieval.

    Retrieves relevant documents for a question, builds a prompt with context,
    and generates an answer using the LLM.

    Usage:
        qa = RetrievalQA(llm=llm, retriever=retriever)
        answer = await qa.run("What does the document say about Python?")
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
        """Run the QA pipeline.

        Args:
            question: The user's question.

        Returns:
            Answer string, or dict with answer + sources if return_source_documents=True.
        """
        # Retrieve documents
        docs = await self._retriever.get_relevant_documents(question)
        docs = docs[:self.k]

        if not docs:
            return "No relevant documents found."

        # Build context
        context_parts = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", f"doc_{i}")
            context_parts.append(f"[Source: {source}]\n{doc.page_content}")
        context = "\n\n".join(context_parts)

        # Build prompt
        prompt_template = self._custom_prompt or self.default_prompt
        prompt = prompt_template.replace("{context}", context).replace("{question}", question)

        # Generate answer
        from chainforge.core.message import Message, Role
        response = await self._llm.generate([Message(role=Role.user, content=prompt)])
        answer = response.content or "No answer generated."

        if self.return_source_documents:
            return {
                "answer": answer,
                "sources": [
                    {
                        "content": d.page_content[:200],
                        "metadata": d.metadata,
                    }
                    for d in docs
                ],
            }
        return answer
