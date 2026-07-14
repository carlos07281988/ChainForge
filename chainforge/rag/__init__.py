"""RAG Pipeline — document loading, splitting, embedding, retrieval, QA.

Usage:
    from chainforge.rag.loaders import TextLoader
    from chainforge.rag.splitters import RecursiveCharacterTextSplitter
    from chainforge.rag.vectorstores import InMemoryVectorStore, ChromaVectorStore, FAISSVectorStore
    from chainforge.rag.retrievers import VectorStoreRetriever
    from chainforge.rag.chains import RetrievalQA

    docs = TextLoader("data.txt").load()
    chunks = RecursiveCharacterTextSplitter().split_documents(docs)
    store = InMemoryVectorStore()
    await store.add_documents(chunks)
    qa = RetrievalQA(llm=llm, retriever=VectorStoreRetriever(store))
    answer = await qa.run("What does this document say?")
"""

from chainforge.rag.documents import Document
from chainforge.rag.loaders import TextLoader, CSVLoader, JSONLoader, DirectoryLoader, HTMLLoader
from chainforge.rag.splitters import RecursiveCharacterTextSplitter, TokenTextSplitter
from chainforge.rag.vectorstores import InMemoryVectorStore, ChromaVectorStore, FAISSVectorStore
from chainforge.rag.retrievers import VectorStoreRetriever, MultiQueryRetriever
from chainforge.rag.chains import RetrievalQA

__all__ = [
    "Document",
    "TextLoader",
    "CSVLoader",
    "JSONLoader",
    "DirectoryLoader",
    "HTMLLoader",
    "RecursiveCharacterTextSplitter",
    "TokenTextSplitter",
    "InMemoryVectorStore",
    "ChromaVectorStore",
    "FAISSVectorStore",
    "VectorStoreRetriever",
    "MultiQueryRetriever",
    "RetrievalQA",
]
