from pathlib import Path

import chromadb
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer

# Same folder as this file (put it next to PDF_RAG.py)
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_DIR = ROOT / "chroma_db"

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
CHUNK_WORDS = 400
OVERLAP_WORDS = 60
MIN_WORDS = 30


def chunk(text):
    words = text.split()
    step = CHUNK_WORDS - OVERLAP_WORDS
    for i in range(0, len(words), step):
        yield " ".join(words[i:i + CHUNK_WORDS])


def main():
    pdfs = sorted(DATA_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in: {DATA_DIR}")
        return

    print("Loading embedding model (downloads once on first run)...")
    model = SentenceTransformer(EMBED_MODEL)
    collection = chromadb.PersistentClient(path=str(DB_DIR)).get_or_create_collection("docs")

    for pdf in pdfs:
        ids, texts, metas = [], [], []
        doc = fitz.open(pdf)
        for page_no, page in enumerate(doc, start=1):
            for j, c in enumerate(chunk(page.get_text())):
                if len(c.split()) < MIN_WORDS:
                    continue
                ids.append(f"{pdf.stem}-{page_no}-{j}")
                texts.append(c)
                metas.append({"source": pdf.name, "page": page_no})

        if not texts:
            print(f"{pdf.name}: no readable text found (it may be a scanned PDF).")
            continue

        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False).tolist()
        collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metas)
        print(f"{pdf.name}: {len(texts)} chunks stored")

    print("Done. Total chunks in database:", collection.count())


if __name__ == "__main__":
    main()
