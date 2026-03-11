from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
from groq import Groq
import chromadb
import os

app = FastAPI()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

chroma_client = chromadb.Client()
collection = chroma_client.create_collection("repo")


class RepoRequest(BaseModel):
    repo: str
    files: List[Dict]


@app.get("/")
def health():
    return {"status": "AI DevOps Engine running"}


def embed_code(file_name):

    return [float(ord(c) % 10) for c in file_name][:10]


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
            "reason":"No code files",
            "action":"Add documentation"
        }

    for i,file in enumerate(code_files):

        collection.add(
            documents=[file],
            embeddings=[embed_code(file)],
            ids=[str(i)]
        )

    query_embedding=embed_code("bug")

    result=collection.query(
        query_embeddings=[query_embedding],
        n_results=1
    )

    target=result["documents"][0][0]

    prompt=f"""
You are a DevOps AI agent.

Analyze file:

{target}

Return:

Reason
Action
"""

    response=client.chat.completions.create(

        model="llama-3.1-70b-versatile",

        messages=[
            {"role":"user","content":prompt}
        ]

    )

    text=response.choices[0].message.content

    reason="AI detected improvement"
    action="Refactor code"

    if "Reason" in text:
        reason=text.split("Reason")[1][:100]

    if "Action" in text:
        action=text.split("Action")[1][:100]

    return {
        "target_file":target,
        "reason":reason,
        "action":action
    }