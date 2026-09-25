import os
import pandas as pd
from langchain_community.document_loaders import PyPDFLoader, DataFrameLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Configure paths
PDF_FILES = ["4. Student Handbook Aug 2026.pdf", "SOP STUDENT 17082026 - Final.pdf"]
CSV_FILES = {
    "courses": "clenaed/courses.csv",
    "minor_courses": "clenaed/minor_courses.csv",
    "basket_requirements": "clenaed/basket_requirements.csv"
}
DB_DIR = "./chroma_db"

def build_index():
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
                doc.metadata['source'] = csv_path
            docs.extend(csv_docs)
        else:
            print(f"Warning: {csv_path} not found.")

    print(f"\nTotal documents loaded: {len(docs)}")

    # 3. Split Text into manageable chunks
    print("Splitting text...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    print(f"Total chunks created: {len(splits)}")

    # 4. Create and persist Vector Store
    print("Building Vector Store with Ollama (this may take a minute)...")
    
    try:
        # Using Ollama's nomic-embed-text for embeddings
        embeddings = OllamaEmbeddings(model="nomic-embed-text") 
        vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings, persist_directory=DB_DIR)
        print(f"✅ Vector store built successfully and persisted to {DB_DIR}")
    except Exception as e:
        print(f"❌ Error building vector store: {e}")
        print("Did you forget to start Ollama or pull the nomic-embed-text model?")

if __name__ == "__main__":
    build_index()
