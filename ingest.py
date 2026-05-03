import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

load_dotenv()

def setup_collection(client: QdrantClient, collection_name: str, vector_size: int=3072):
    collections = [c.name for c in client.get_collections().collections]

    if collection_name not in collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
        print(f"[INFO] Created collection: {collection_name}")
    else:
        print(f"[INFO] Collection already exists: {collection_name}")

def load_documents(source_path: str):
    path = Path(source_path)

    if not path.exists():
        raise FileNotFoundError(f"Source path not exits: {source_path}")
    
    loaders = []

    pdf_files = list(path.glob("**/*.pdf"))
    if pdf_files:
        for pdf in pdf_files:
            loaders.append(PyPDFLoader(str(pdf)))
        print(f"Found {len(pdf_files)} PDF files")

    txt_files = list(path.glob("**/*.txt"))
    if txt_files:
        for txt in txt_files:
            loaders.append(TextLoader(str(txt), encoding="utf-8"))
        print(f"Found {len(pdf_files)} txt files")

    if not loaders:
        raise ValueError(f"No documents found in the source directory: {source_path}")
    
    docs = []
    for loader in loaders:
        docs.extend(loader.load())
    return docs


def ingest(source_path: str, collection_name: str):
    print(f"\n[INFO] Starting ingestion from: {source_path}")

    docs = load_documents(source_path)
    print(f"[INFO] Loaded {len(docs)} documents")

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        model_name="gpt-4o",
        chunk_size=400,
        chunk_overlap=50,
        )
    chunks = splitter.split_documents(docs)
    print(f"[INFO]  Split into {len(chunks)} chunks")

    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=os.getenv("GEMINI_API_KEY"),
    )

    client = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )
    setup_collection(client, collection_name)

    print("[INFO] Indexing documents...")
    vector_store = QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
        collection_name=collection_name,
        force_recreate=True,
        batch_size=10
    )

    print(f"[INFO] Successfully indexed {len(chunks)} chunks into '{collection_name}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into Qdrant")
    parser.add_argument("--source", default="./docs", help="Path to documents directory")
    parser.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION", "rag_documents"))
    args = parser.parse_args()

    ingest(args.source, args.collection)