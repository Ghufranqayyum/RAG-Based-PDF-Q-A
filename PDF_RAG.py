import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
LLM_MODEL = "openai/gpt-oss-120b" # check Groq's current model list if this fails
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY is missing. Add it to the .env file in the RAG folder.")

app = FastAPI(title="RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

embedder = SentenceTransformer(EMBED_MODEL)
collection = chromadb.PersistentClient(path=str(ROOT / "chroma_db")).get_or_create_collection("docs")
llm = Groq(api_key=api_key)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=4, ge=1, le=10)


@app.get("/health")
def health():
    return {"status": "ok", "chunks": collection.count()}


@app.post("/ask")
def ask(req: AskRequest):
    if collection.count() == 0:
        raise HTTPException(
            status_code=400,
            detail="No documents are indexed yet. Put PDFs in the data folder and run: python src/ingest.py",
        )

    query_vec = embedder.encode(QUERY_PREFIX + req.question).tolist()
    res = collection.query(query_embeddings=[query_vec], n_results=req.k)

    docs = res["documents"][0]
    metas = res["metadatas"][0]

    sources = [
        {"source": m["source"], "page": m["page"], "text": d}
        for d, m in zip(docs, metas)
    ]

    context = "\n\n".join(f"[{s['source']} p.{s['page']}] {s['text']}" for s in sources)
    prompt = (
        "Answer ONLY from the context below. Cite sources like [file p.X]. "
        "If the answer is not in the context, say 'I don't know.'\n\n"
        f"Context:\n{context}\n\nQuestion: {req.question}"
    )

    try:
        out = llm.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"The language model request failed: {e}")

    return {"answer": out.choices[0].message.content, "sources": sources}