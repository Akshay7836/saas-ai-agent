const express = require('express');
const axios = require('axios');
const path = require('path');
const { Octokit } = require("@octokit/rest");
const app = express();

// Use GITHUB_TOKEN for Public Scans, AI Engine uses Private Key for Commits
const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });
const PYTHON_URL = process.env.PYTHON_URL?.replace(/\/$/, ""); 

app.use(express.json());
app.use(express.static(path.join(__dirname))); 

app.post('/scan', async (req, res) => {
    const { repo } = req.body;
    if (!repo || !repo.includes('/')) return res.status(400).json({ explanation: "Use 'owner/repo' format." });

    try {
        const [owner, name] = repo.split('/');
        const { data } = await octokit.repos.getContent({ owner, repo: name, path: '' });
        const fileNames = data.map(f => f.name).join(', ');

        const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { command: "Scan", error_log: fileNames });
        res.json({ ...aiRes.data, repo });
    } catch (e) {
        res.status(500).json({ explanation: "Repo not accessible. Is it public?" });
    }
});

app.post('/apply-fix', async (req, res) => {
    try {
        const aiRes = await axios.post(`${PYTHON_URL}/apply-fix`, req.body);
        res.json(aiRes.data);
    } catch (e) {
        const errMsg = e.response?.data?.detail || "AI Engine connection failed.";
        res.status(500).json({ status: "error", message: errMsg });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`✅ SaaS Orchestrator Live on Port ${PORT}`));