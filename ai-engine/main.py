import os, json, uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq

app = FastAPI()

# Key hum Render ke Dashboard mein dalenge, yahan nahi
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class ErrorRequest(BaseModel):
    command: str
    error_log: str

@app.post("/fix-error")
async def fix_error(request: ErrorRequest):
    prompt = f"Analyze these GitHub files: {request.error_log}. What is missing? Give a fix command in JSON with 'explanation' and 'fix_command' keys."
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)