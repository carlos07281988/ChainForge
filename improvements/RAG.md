# RAG Pipeline — Document Loading, Splitting, Embedding, Retrieval

> 为 ChainForge 添加完整的 RAG 能力

## Design

### Pipeline

```
Document → Loader → Splitter → Embedder → VectorStore → Retriever → QA Chain
```

### Document

```python
from chainforge.rag import Document

doc = Document(
    page_content="Your text here...",
    metadata={"source": "file.pdf", "page": 1},
)
```

### Loaders

```python
from chainforge.rag.loaders import TextLoader, CSVLoader

loader = TextLoader("data.txt")
documents = loader.load()
```

### Splitters

```python
from chainforge.rag.splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(documents)
```

### RetrievalQA

```python
from chainforge.rag.chains import RetrievalQA

qa = RetrievalQA(llm=llm, retriever=retriever)
answer = await qa.run("What does the document say about X?")
```

## Files

| File | Description |
|------|-------------|
| `chainforge/rag/__init__.py` | Exports |
| `chainforge/rag/documents.py` | Document, DocumentLoader |
| `chainforge/rag/loaders.py` | TextLoader, CSVLoader, JSONLoader |
| `chainforge/rag/splitters.py` | Text splitters |
| `chainforge/rag/embeddings.py` | EmbeddingFunction + OpenAI provider |
| `chainforge/rag/vectorstores.py` | InMemoryVectorStore |
| `chainforge/rag/retrievers.py` | Retriever protocol |
| `chainforge/rag/chains.py` | RetrievalQA |
| `tests/test_rag.py` | Tests |
