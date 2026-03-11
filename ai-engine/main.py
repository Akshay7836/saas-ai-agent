from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
from groq import Groq
import chromadb
import os

app = FastAPI()

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

chroma_client = chromadb.Client()

try:
    collection = chroma_client.get_collection("repo_index")
except:
    collection = chroma_client.create_collection("repo_index")


class RepoRequest(BaseModel):
    repo: str
    files: List[Dict]


@app.get("/")
def health():
    return {"status": "AI Engine running"}


def embed_text(text):

    return [float(ord(c) % 10) for c in text][:10]


@app.post("/analyze")
def analyze(req: RepoRequest):

    files=req.files

    code_files=[]

    for f in files:

        name=f.get("name","")

        if name.endswith((".py",".js",".ts",".java",".go",".cpp")):
            code_files.append(name)

    if not code_files:

        return {
            "target_file":"README.md",
            "reason":"No code files detected",
            "action":"Add documentation"
        }

    for i,file in enumerate(code_files):

        collection.add(
            documents=[file],
            embeddings=[embed_text(file)],
            ids=[f"{req.repo}_{i}"]
        )

    result=collection.query(
        query_embeddings=[embed_text("bug")],
        n_results=1
    )

    target=result["documents"][0][0]

    prompt=f"""
You are a DevOps AI assistant.

Analyze file:

{target}

Return:

Reason:
Action:
"""

    response=groq_client.chat.completions.create(

        model="llama-3.1-70b-versatile",

        messages=[{"role":"user","content":prompt}]

    )

    text=response.choices[0].message.content

    reason="AI detected possible improvement"
    action="Refactor code"

    if "Reason:" in text:
        reason=text.split("Reason:")[1].split("\n")[0].strip()

    if "Action:" in text:
        action=text.split("Action:")[1].strip()

    return {
        "target_file":target,
        "reason":reason,
        "action":action
    }