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
"""RAG Pipeline — document loading, splitting, embedding, retrieval, QA."""

from chainforge.rag.documents import Document
from chainforge.rag.loaders import TextLoader, CSVLoader, JSONLoader, DirectoryLoader, HTMLLoader, PDFLoader, NotionLoader, GitHubLoader
from chainforge.rag.splitters import RecursiveCharacterTextSplitter, TokenTextSplitter
from chainforge.rag.vectorstores import InMemoryVectorStore, ChromaVectorStore, FAISSVectorStore, PineconeVectorStore, QdrantVectorStore
from chainforge.rag.retrievers import VectorStoreRetriever, MultiQueryRetriever
from chainforge.rag.chains import RetrievalQA, SelfRAG, CorrectiveRAG
from chainforge.rag.graphrag import GraphRAGPipeline

__all__ = [
    "Document",
    "TextLoader", "CSVLoader", "JSONLoader", "DirectoryLoader", "HTMLLoader",
    "RecursiveCharacterTextSplitter", "TokenTextSplitter",
    "InMemoryVectorStore", "ChromaVectorStore", "FAISSVectorStore",
    "VectorStoreRetriever", "MultiQueryRetriever",
    "PineconeVectorStore", "QdrantVectorStore",
    "PDFLoader", "NotionLoader", "GitHubLoader",
    "RetrievalQA", "SelfRAG", "CorrectiveRAG",
    "GraphRAGPipeline",
]
