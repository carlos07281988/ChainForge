# Output Parsers, Entity Memory, Toolkits, Document Loaders, Prompt Hub

## Output Parsers

```python
from chainforge.parsers import JSONOutputParser, PydanticOutputParser
from pydantic import BaseModel

parser = JSONOutputParser()
result = parser.parse('{"name": "Alice"}')
print(result.parsed)  # {"name": "Alice"}

class Person(BaseModel):
    name: str
    age: int

parser = PydanticOutputParser(pydantic_model=Person)
result = parser.parse('{"name": "Alice", "age": 30}')
print(result.parsed)  # Person(name='Alice', age=30)
```

## Entity Memory

```python
from chainforge.memory import EntityMemory

mem = EntityMemory()
mem.extract("Alice lives in Beijing and works at Google.")
entities = mem.get_entities()
print(entities["Alice"].mention_count)  # 1
context = mem.get_context()
```

## Toolkits

```python
from chainforge.tools import calculator_toolkit, file_toolkit

math_tools = calculator_toolkit()
file_tools = file_toolkit()
agent = Agent(llm=llm, tools=math_tools.tools + file_tools.tools)
```

## Document Loaders

```python
from chainforge.rag.loaders import DirectoryLoader, HTMLLoader

loader = DirectoryLoader("./docs", glob_pattern="*.txt")
docs = loader.load()

html = HTMLLoader("page.html")
doc = html.load()
```

## Vector Store Backends

```python
from chainforge.rag.vectorstores import ChromaVectorStore, FAISSVectorStore

# ChromaDB (requires chromadb)
store = ChromaVectorStore(persist_directory="./chroma_db")

# FAISS (requires faiss, numpy)
store = FAISSVectorStore()
```

## Embedding Providers

```python
from chainforge.rag.embeddings import OpenAIEmbedding, HuggingFaceEmbedding

# OpenAI (requires openai + OPENAI_API_KEY)
emb = OpenAIEmbedding()

# Local (requires sentence-transformers)
emb = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")
```

## Prompt Hub

```python
from chainforge.prompts import PromptTemplate, PromptHub

hub = PromptHub()
hub.register("greeting", PromptTemplate("Hello, {name}!"))
tmpl = hub.get("greeting")
print(tmpl.format(name="World"))  # Hello, World!
```
