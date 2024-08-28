from typing import Annotated, List
from fastapi import FastAPI, Query
from sentence_transformers import SentenceTransformer

app = FastAPI()
model = SentenceTransformer("all-roberta-large-v1", device="cuda")

@app.get("/query/")
async def read_items(sentences: Annotated[List[str], Query(...)]):
    embeddings = model.encode(sentences=sentences, device="cuda")    
    return {"embeddings": embeddings.tolist()}