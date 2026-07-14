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
"""Tests for the RAG Pipeline module."""

import json
import tempfile
from pathlib import Path

import pytest

from chainforge.rag import (
    Document,
    TextLoader,
    CSVLoader,
    JSONLoader,
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    InMemoryVectorStore,
    VectorStoreRetriever,
)
from chainforge.memory.embedding import IdentityEmbedding


class TestDocument:
    def test_creation(self):
        doc = Document(page_content="Hello world", metadata={"source": "test"})
        assert doc.page_content == "Hello world"
        assert doc.metadata["source"] == "test"

    def test_len(self):
        doc = Document(page_content="Hello")
        assert len(doc) == 5

    def test_str(self):
        doc = Document(page_content="Hello world")
        assert "Hello" in str(doc)


class TestTextLoader:
    def test_load(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello from file!")
            path = f.name
        loader = TextLoader(path)
        docs = loader.load()
        assert len(docs) == 1
        assert "Hello" in docs[0].page_content
        assert docs[0].metadata["source"] == path
        Path(path).unlink()

    def test_file_not_found(self):
        loader = TextLoader("/nonexistent.txt")
        with pytest.raises(FileNotFoundError):
            loader.load()


class TestCSVLoader:
    def test_load(self):
        csv_content = "name,age,city\nAlice,30,Beijing\nBob,25,Shanghai"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            path = f.name
        loader = CSVLoader(path)
        docs = loader.load()
        assert len(docs) == 2
        assert "Alice" in docs[0].page_content
        assert docs[1].metadata["file_type"] == "csv"
        Path(path).unlink()


class TestJSONLoader:
    def test_load_single(self):
        data = {"title": "Test", "content": "Hello world"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        loader = JSONLoader(path, content_key="content")
        docs = loader.load()
        assert len(docs) == 1
        assert docs[0].page_content == "Hello world"
        Path(path).unlink()

    def test_load_array(self):
        data = [{"text": "Doc 1"}, {"text": "Doc 2"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        loader = JSONLoader(path, content_key="text")
        docs = loader.load()
        assert len(docs) == 2
        Path(path).unlink()


class TestRecursiveCharacterTextSplitter:
    def test_simple_split(self):
        splitter = RecursiveCharacterTextSplitter(chunk_size=10, chunk_overlap=2)
        chunks = splitter.split_text("hello world foo bar")
        assert len(chunks) >= 1

    def test_split_with_separator(self):
        splitter = RecursiveCharacterTextSplitter(chunk_size=50, chunk_overlap=10)
        chunks = splitter.split_text("Hello world. " * 20)
        assert len(chunks) >= 3
        assert all(isinstance(c, str) and len(c) > 0 for c in chunks)

    def test_split_text_no_separator(self):
        splitter = RecursiveCharacterTextSplitter(chunk_size=20, chunk_overlap=5)
        chunks = splitter.split_text("x" * 100)
        assert len(chunks) >= 4
        assert all(isinstance(c, str) for c in chunks)

    def test_split_documents_preserves_metadata(self):
        splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=20)
        from chainforge.rag import Document
        docs = [Document(page_content="hello world " * 50, metadata={"source": "test"})]
        chunks = splitter.split_documents(docs)
        assert len(chunks) > 1
        assert all(c.metadata.get("chunk") is not None for c in chunks)
        assert all(c.metadata.get("source") == "test" for c in chunks)

    def test_split_preserves_newlines(self):
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        text = "Line one\n\nLine two\n\nLine three\n\nLine four"
        chunks = splitter.split_text(text)
        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)

    def test_split_documents(self):
        splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=20)
        docs = [Document(page_content="hello world", metadata={"source": "test"})]
        chunks = splitter.split_documents(docs)
        assert len(chunks) >= 1


class TestInMemoryVectorStore:
    @pytest.mark.asyncio
    async def test_add_and_search(self):
        store = InMemoryVectorStore(embedding_fn=IdentityEmbedding(dim=32))
        docs = [
            Document(page_content="Python is a programming language"),
            Document(page_content="JavaScript runs in the browser"),
        ]
        ids = await store.add_documents(docs)
        assert len(ids) == 2
        assert store.count == 2

    @pytest.mark.asyncio
    async def test_similarity_search(self):
        store = InMemoryVectorStore(embedding_fn=IdentityEmbedding(dim=32))
        docs = [
            Document(page_content="Python is great for data science"),
            Document(page_content="I love ice cream"),
        ]
        await store.add_documents(docs)
        results = await store.similarity_search("programming", k=2)
        assert len(results) >= 1


class TestVectorStoreRetriever:
    @pytest.mark.asyncio
    async def test_retrieve(self):
        store = InMemoryVectorStore(embedding_fn=IdentityEmbedding(dim=32))
        docs = [
            Document(page_content="Python is a programming language"),
            Document(page_content="The capital of France is Paris"),
        ]
        await store.add_documents(docs)
        retriever = VectorStoreRetriever(store, k=1)
        results = await retriever.get_relevant_documents("programming")
        assert len(results) >= 1


class TestRetrievalQA:
    @pytest.mark.asyncio
    async def test_no_docs(self):
        from chainforge.testing import MockLLM, MockResponse

        store = InMemoryVectorStore(embedding_fn=IdentityEmbedding(dim=32))
        retriever = VectorStoreRetriever(store, k=4)
        llm = MockLLM(responses=[MockResponse(content="Answer")])

        from chainforge.rag.chains import RetrievalQA
        qa = RetrievalQA(llm=llm, retriever=retriever)
        result = await qa.run("Question")
        assert "No relevant" in result  # Empty store

    @pytest.mark.asyncio
    async def test_with_docs(self):
        from chainforge.testing import MockLLM, MockResponse

        store = InMemoryVectorStore(embedding_fn=IdentityEmbedding(dim=32))
        await store.add_documents([
            Document(page_content="Python is a programming language created by Guido van Rossum"),
        ])
        retriever = VectorStoreRetriever(store, k=4)
        llm = MockLLM(responses=[MockResponse(content="Python was created by Guido van Rossum.")])

        from chainforge.rag.chains import RetrievalQA
        qa = RetrievalQA(llm=llm, retriever=retriever)
        result = await qa.run("Who created Python?")
        assert result is not None
