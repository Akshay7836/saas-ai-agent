import os
import json
import traceback
import uvicorn
import chromadb
from fastapi import FastAPI, HTTPException, Request
from groq import Groq
from sentence_transformers import SentenceTransformer

app = FastAPI()

# 🔑 AI Setup
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 📂 RAG Engine Setup - Memory Optimized
# Using EphemeralClient to prevent disk-write RAM spikes
chroma_client = chromadb.EphemeralClient() 
collection = chroma_client.get_or_create_collection(name="repo_code")

# 🧠 Smallest model available to fit in 512MB RAM
# Dimensions: 768
embed_model = SentenceTransformer('paraphrase-albert-small-v2', device='cpu')

@app.get("/")
def home():
    return {"status": "AI Agent Brain Online", "memory_mode": "low-ram-optimized"}

@app.post("/index-repo")
async def index_repo(request: Request):
    try:
        data = await request.json()
        files_dict = data.get("files", {}) 
        for path, content in files_dict.items():
            if len(content) > 15000: continue # Skip huge files to save RAM
            embedding = embed_model.encode(content).tolist()
            collection.add(
                embeddings=[embedding],
                documents=[content],
                metadatas=[{"path": path}],
                ids=[path]
            )
        return {"status": "success", "indexed_files": len(files_dict)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-repo")
async def analyze_repo(request: Request):
    try:
        data = await request.json()
        file_list = data.get("files_context", "")
        query = "Find HTML buttons and JS function definitions."
        query_embedding = embed_model.encode(query).tolist()
        # Query only 3 results to keep context window light
        results = collection.query(query_embeddings=[query_embedding], n_results=3)
        retrieved_context = "\n---\n".join(results['documents'][0])

        prompt = f"Context:\n{retrieved_context}\n\nFiles: {file_list}\nTask: Find bugs/missing connections. Return JSON issues array."
        
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(chat.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Analysis Failed")

@app.post("/apply-fix")
async def apply_fix(request: Request):
    try:
        data = await request.json()
        file_path = data.get("file_path")
        original_code = data.get("original_code", "")
        prompt = f"Fix {file_path}. Original: {original_code}. Return raw code only."
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile"
        )
        return {"fixed_code": chat.choices[0].message.content.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))