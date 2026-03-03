const express = require('express');
const axios = require('axios');
const { Octokit } = require("@octokit/rest");
const app = express();
const octokit = new Octokit();

app.use(express.json());
const PYTHON_URL = process.env.PYTHON_URL; // Ye Render se aayega

app.get('/', (req, res) => {
    res.send(`
        <html><body style="text-align:center; padding:50px; font-family:sans-serif; background:#f4f7f6">
            <h1>🚀 Public AI DevOps Agent</h1>
            <input id="repo" placeholder="owner/repo (e.g. facebook/react)" style="padding:10px; width:300px;">
            <button onclick="scan()">Scan Repo's</button>
            <div id="out" style="margin-top:20px; font-weight:bold"></div>
            <script>
                async function scan() {
                    const repo = document.getElementById('repo').value;
                    document.getElementById('out').innerText = "🔍 AI Scanning...";
                    const res = await fetch('/scan', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ repo })
                    });
                    const d = await res.json();
                    document.getElementById('out').innerHTML = "🤖 AI Fix: " + d.explanation;
                }
            </script>
        </body></html>
    `);
});

app.post('/scan', async (req, res) => {
    try {
        const [owner, name] = req.body.repo.split('/');
        const { data } = await octokit.repos.getContent({ owner, repo: name, path: '' });
        const files = data.map(f => f.name).join(', ');
        const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { command: "Scan", error_log: files });
        res.json(aiRes.data);
    } catch (e) { res.status(500).json({ explanation: "Repo not found!" }); }
});

app.listen(process.env.PORT || 3000);