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

# 📂 RAG Engine Setup (Optimized for 512MB RAM)
# Using EphemeralClient instead of default Client to save background overhead
chroma_client = chromadb.EphemeralClient() 

collection = chroma_client.get_or_create_collection(name="repo_code")

# 🧠 CHANGE: Switched to an even lighter model 'paraphrase-albert-small-v2'
# This model is roughly 40MB vs 100MB+ for MiniLM, saving critical RAM.
# device='cpu' ensures it doesn't look for non-existent GPU resources.
embed_model = SentenceTransformer('paraphrase-albert-small-v2', device='cpu')

@app.get("/")
def home():
    return {"status": "AI Agent Brain is Online with Optimized Memory"}

# 🧠 API 1: Indexing Phase
@app.post("/index-repo")
async def index_repo(request: Request):
    try:
        data = await request.json()
        files_dict = data.get("files", {}) 
        
        # Batch processing to prevent memory spikes
        for path, content in files_dict.items():
            # Only index files that are small enough to process
            if len(content) > 20000: # Skip massive log/data files
                continue
                
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

        query = "Find HTML buttons, event listeners, and JS function definitions."
        query_embedding = embed_model.encode(query).tolist()
        
        # Reduced n_results from 5 to 3 to keep the Groq prompt size smaller
        results = collection.query(query_embeddings=[query_embedding], n_results=3)
        
        retrieved_context = "\n---\n".join(results['documents'][0])

        prompt = f"""
        Analyze this repository structure: {file_list}
        
        Additional Code Context:
        {retrieved_context}

        Task: Identify ALL critical issues. Specifically check if HTML buttons call non-existent functions.
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

        if "```" in fixed_code:
            parts = fixed_code.split("```")
            fixed_code = parts[1] if len(parts) > 1 else parts[0]
            if fixed_code.startswith(("javascript", "python", "html", "css", "json")):
                fixed_code = "\n".join(fixed_code.split("\n")[1:])

        return {"fixed_code": fixed_code.strip(), "summary": f"Successfully healed {file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)