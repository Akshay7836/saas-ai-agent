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

# 📂 RAG Engine Setup
# Using chromadb.Client() for in-memory (Standard Render setup)
# Note: For production, consider chromadb.PersistentClient(path="./chroma_db")
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection(name="repo_code")
# Lightweight model to convert code into vectors
embed_model = SentenceTransformer('all-MiniLM-L6-v2')

@app.get("/")
def home():
    return {"status": "AI Agent Brain is Online with RAG Memory"}

# 🧠 API 1: Indexing Phase
# This stores the repo content so the AI can "search" it later
@app.post("/index-repo")
async def index_repo(request: Request):
    try:
        data = await request.json()
        files_dict = data.get("files", {}) # Expecting {"path": "content"}
        
        for path, content in files_dict.items():
            embedding = embed_model.encode(content).tolist()
            collection.add(
                embeddings=[embedding],
                documents=[content],
                metadatas=[{"path": path}],
                ids=[path]
            )
        return {"status": "success", "indexed_files": len(files_dict)}
    except Exception as e:
        print(f"Indexing Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# 🚀 API 2: Deep Analysis (Multi-Issue)
@app.post("/analyze-repo")
async def analyze_repo(request: Request):
    try:
        data = await request.json()
        file_list = data.get("files_context", "")

        # 🔍 RAG Step: Find code related to structural/connection issues
        query = "Find HTML buttons, event listeners, and JS function definitions."
        query_embedding = embed_model.encode(query).tolist()
        results = collection.query(query_embeddings=[query_embedding], n_results=5)
        
        # Combine retrieved snippets for context
        retrieved_context = "\n---\n".join(results['documents'][0])

        prompt = f"""
        Analyze this repository structure: {file_list}
        
        Additional Code Context:
        {retrieved_context}

        Task: Act as a Lead Developer. Identify ALL critical issues (bugs, missing UI-to-Logic connections, or performance bottlenecks).
        Specifically, check if HTML buttons call functions that don't exist, or if functions are defined but never used.

        Return ONLY a JSON object:
        {{
            "issues": [
                {{
                    "target_file": "path/to/file",
                    "reason": "Why this is a problem",
                    "action": "How to fix it"
                }}
            ]
        }}
        """
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(chat.choices[0].message.content)
    except Exception as e:
        print(f"Analysis Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="AI Analysis Failed")

# 🛠️ API 3: Smart Reconstruction
@app.post("/apply-fix")
async def apply_fix(request: Request):
    try:
        data = await request.json()
        file_path = data.get("file_path")
        original_code = data.get("original_code", "")

        context = "File is EMPTY. Create it from scratch." if not original_code else f"Current Code:\n{original_code}"

        prompt = f"""
        Task: Reconstruct '{file_path}' to be production-ready and fix the identified issues.
        {context}
        Return ONLY the raw code. No explanation. No markdown blocks.
        """
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile"
        )
        fixed_code = chat.choices[0].message.content.strip()

        # Final cleanup for raw code delivery
        if "```" in fixed_code:
            fixed_code = fixed_code.split("```")[1]
            if "\n" in fixed_code:
                fixed_code = "\n".join(fixed_code.split("\n")[1:])

        return {"fixed_code": fixed_code, "summary": f"Successfully healed {file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)