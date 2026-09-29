import hashlib
import json
import os
from pathlib import Path

import pandas as pd
from langchain_community.document_loaders import PyPDFLoader, DataFrameLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Configure paths
BASE_DIR = Path(__file__).resolve().parent
PDF_FILES = [
    BASE_DIR / "4. Student Handbook Aug 2026.pdf",
    BASE_DIR / "SOP STUDENT 17082026 - Final.pdf",
]
CSV_FILES = {
    "courses": BASE_DIR / "cleaned" / "courses.csv",
    "minor_courses": BASE_DIR / "cleaned" / "minor_courses.csv",
    "basket_requirements": BASE_DIR / "cleaned" / "basket_requirements.csv",
}


def configured_path(env_name, default):
    path = Path(os.getenv(env_name, str(default)))
    return path if path.is_absolute() else BASE_DIR / path


DB_DIR = configured_path("CHROMA_DB_DIR", BASE_DIR / "chroma_db_gemini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))


def document_id(index, document):
    metadata = json.dumps(document.metadata, sort_keys=True, default=str)
    value = f"{index}\0{document.page_content}\0{metadata}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def build_index():
    if not 1 <= EMBEDDING_BATCH_SIZE <= 100:
        raise ValueError("EMBEDDING_BATCH_SIZE must be between 1 and 100.")

    docs = []
    
    # 1. Load PDFs
    for pdf_path in PDF_FILES:
        if os.path.exists(pdf_path):
            print(f"Loading {pdf_path}...")
            loader = PyPDFLoader(pdf_path)
            docs.extend(loader.load())
        else:
            print(f"Warning: {pdf_path} not found.")

    # 2. Load CSVs
    for name, csv_path in CSV_FILES.items():
        if os.path.exists(csv_path):
            print(f"Loading {csv_path}...")
            df = pd.read_csv(csv_path)
            # Create a combined string representation for each row to enhance text retrieval
            df['combined_text'] = df.apply(lambda row: ' | '.join([f"{col}: {val}" for col, val in row.items() if pd.notnull(val)]), axis=1)
            loader = DataFrameLoader(df, page_content_column="combined_text")
            csv_docs = loader.load()
            
            # Add metadata about the source file
            for doc in csv_docs:
                doc.metadata['source'] = str(csv_path.relative_to(BASE_DIR))
            docs.extend(csv_docs)
        else:
            print(f"Warning: {csv_path} not found.")

    print(f"\nTotal documents loaded: {len(docs)}")

    # 3. Split Text into manageable chunks
    print("Splitting text...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    print(f"Total chunks created: {len(splits)}")
    if not splits:
        raise RuntimeError("No source documents were loaded; index was not changed.")

    # 4. Create and persist Vector Store
    print(f"Building Vector Store with Gemini in {DB_DIR}...")
    
    try:
        embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            output_dimensionality=EMBEDDING_DIMENSION,
        )
        vectorstore = None
        for start in range(0, len(splits), EMBEDDING_BATCH_SIZE):
            batch = splits[start : start + EMBEDDING_BATCH_SIZE]
            ids = [
                document_id(index, document)
                for index, document in enumerate(batch, start=start)
            ]
            if vectorstore is None:
                vectorstore = Chroma.from_documents(
                    documents=batch,
                    embedding=embeddings,
                    ids=ids,
                    persist_directory=str(DB_DIR),
                )
            else:
                vectorstore.add_documents(batch, ids=ids)
            print(f"Indexed {min(start + len(batch), len(splits))}/{len(splits)} chunks.")

        desired_ids = {
            document_id(index, document)
            for index, document in enumerate(splits)
        }
        stored_ids = set(vectorstore.get(include=[])["ids"])
        stale_ids = stored_ids - desired_ids
        if stale_ids:
            vectorstore.delete(ids=list(stale_ids))
            print(f"Removed {len(stale_ids)} stale chunks.")

        print(f"Vector store built successfully and persisted to {DB_DIR}")
    except Exception as e:
        print(f"Error building vector store: {e}")
        raise

if __name__ == "__main__":
    build_index()
