const express = require('express');
const axios = require('axios');
const path = require('path');
const { Octokit } = require("@octokit/rest");
const app = express();
const octokit = new Octokit();

app.use(express.json());
// Static files serve karne ke liye (index.html isi folder mein honi chahiye)
app.use(express.static(path.join(__dirname))); 

const PYTHON_URL = process.env.PYTHON_URL; // Render Environment Variable

// 1. Home Route: index.html file bhejega
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// 2. Scan Route (Purana Logic + File content fetch)
app.post('/scan', async (req, res) => {
    try {
        const [owner, name] = req.body.repo.split('/');
        // Saari files ki list lena
        const { data } = await octokit.repos.getContent({ owner, repo: name, path: '' });
        const files = data.map(f => f.name).join(', ');
        
        // AI se analysis mangna
        const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { 
            command: "Scan", 
            error_log: files 
        });
        
        // Response mein repo details bhi bhej rahe hain taaki frontend ise use kar sake
        res.json({ ...aiRes.data, repo: req.body.repo });
    } catch (e) { 
        res.status(500).json({ explanation: "Repo not found or API error!" }); 
    }
});

// 3. Apply Fix Route (Naya Logic - Python Engine ko call karega)
app.post('/apply-fix', async (req, res) => {
    try {
        // Frontend se aane wala saara data Python ko bhej do
        const aiRes = await axios.post(`${PYTHON_URL}/apply-fix`, req.body);
        res.json(aiRes.data);
    } catch (e) {
        res.status(500).json({ status: "error", message: "AI Engine connection failed!" });
    }
});

app.listen(process.env.PORT || 3000, () => {
    console.log("Orchestrator is running on port 3000");
});