// const express = require('express');
// const axios = require('axios');
// const path = require('path');
// const { Octokit } = require("@octokit/rest");
// const app = express();

// // 1. GitHub Token for Public Scans
// // Ensure GITHUB_TOKEN is added in Render Environment Variables
// const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });

// // 2. Python Engine URL Safety
// const PYTHON_URL = process.env.PYTHON_URL?.replace(/\/$/, ""); 

// app.use(express.json());

// // 3. Serving Static Files (CSS/JS)
// app.use(express.static(path.join(__dirname))); 

// // 4. Root Route: Load index.html directly
// app.get('/', (req, res) => {
//     res.sendFile(path.join(__dirname, 'index.html'));
// });

// // 🚀 API 1: Scan Repository
// app.post('/scan', async (req, res) => {
//     const { repo } = req.body;
//     if (!repo || !repo.includes('/')) {
//         return res.status(400).json({ explanation: "Invalid format. Use 'owner/repo'." });
//     }

//     try {
//         const [owner, name] = repo.split('/');
//         // Fetch repo contents via Octokit
//         const { data } = await octokit.repos.getContent({ owner, repo: name, path: '' });
//         const fileNames = data.map(f => f.name).join(', ');

//         // Send file list to Python AI Engine
//         const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { 
//             command: "Scan", 
//             error_log: `Files found: ${fileNames}. Suggest a README or improvements.` 
//         });

//         res.json({ ...aiRes.data, repo });
//     } catch (e) {
//         console.error("❌ Scan Error:", e.message);
//         res.status(500).json({ explanation: "Repo not accessible or GitHub API limit hit." });
//     }
// });

// // 🛠️ API 2: Apply Auto-Fix
// app.post('/apply-fix', async (req, res) => {
//     try {
//         console.log("Pushing fix to Python Engine...");
//         // Forwarding installation_id and code to Python
//         const aiRes = await axios.post(`${PYTHON_URL}/apply-fix`, req.body);
//         res.json(aiRes.data);
//     } catch (e) {
//         console.error("❌ Apply Fix Error:", e.response?.data || e.message);
//         const errMsg = e.response?.data?.detail || "AI Engine connection failed.";
//         res.status(500).json({ status: "error", message: errMsg });
//     }
// });

// // 5. Start Server
// const PORT = process.env.PORT || 3000;
// app.listen(PORT, () => {
//     console.log(`✅ SaaS Orchestrator Live on Port ${PORT}`);
//     console.log(`🔗 Python Engine connected at: ${PYTHON_URL}`);
// });


const express = require('express');
const axios = require('axios');
const path = require('path');
const { Octokit } = require("@octokit/rest");
const { createAppAuth } = require("@octokit/auth-app"); // Auth library

const app = express();

// 1. GitHub App Configuration (Fetching from your Render Env)
const GITHUB_APP_ID = process.env.GITHUB_APP_ID;
const GITHUB_PRIVATE_KEY = process.env.GITHUB_PRIVATE_KEY.replace(/\\n/g, '\n'); 
const PYTHON_URL = process.env.PYTHON_URL?.replace(/\/$/, ""); 

app.use(express.json());
app.use(express.static(path.join(__dirname)));

// 🛠️ Function: Create Auth for specific User Installation
async function getInstallationOctokit(installationId) {
    return new Octokit({
        authStrategy: createAppAuth,
        auth: {
            appId: GITHUB_APP_ID,
            privateKey: GITHUB_PRIVATE_KEY,
            installationId: installationId,
        },
    });
}

// 🚀 API 1: Scan (Public or App-based)
app.post('/scan', async (req, res) => {
    try {
        const { repo, installation_id } = req.body;
        const [owner, name] = repo.split('/');
        
        // Agar installation_id hai, toh authenticated octokit use karo
        const scanOctokit = installation_id ? await getInstallationOctokit(installation_id) : new Octokit();

        const { data } = await scanOctokit.repos.getContent({ owner, repo: name, path: '' });
        const fileNames = data.map(f => f.name).join(', ');

        const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { 
            command: "Scan", 
            error_log: `Files: ${fileNames}. Suggest README.` 
        });

        res.json({ ...aiRes.data, repo });
    } catch (e) {
        res.status(500).json({ explanation: "Access Denied. Is the App installed on this repo?" });
    }
});

// 🛠️ API 2: Apply Fix (Pure Production Logic)
app.post('/apply-fix', async (req, res) => {
    try {
        const { repo, file_path, installation_id } = req.body;
        const [owner, name] = repo.split('/');

        if (!installation_id) throw new Error("Installation ID missing!");

        // 🟢 AUTH: Dynamic Token for this specific User
        const userOctokit = await getInstallationOctokit(installation_id);

        // AI Generation
        const aiRes = await axios.post(`${PYTHON_URL}/apply-fix`, {
            repo_name: repo,
            file_path: file_path,
            installation_id: installation_id
        });
        
        const { fixed_code, summary } = aiRes.data; 
        const newBranch = `ai-fix-${Date.now()}`;

        // Git Workflow
        const { data: mainRef } = await userOctokit.git.getRef({ owner, repo: name, ref: 'heads/main' });
        await userOctokit.git.createRef({
            owner, repo: name,
            ref: `refs/heads/${newBranch}`,
            sha: mainRef.object.sha
        });

        let fileSha;
        try {
            const { data: fileData } = await userOctokit.repos.getContent({ owner, repo: name, path: file_path, ref: 'main' });
            fileSha = fileData.sha;
        } catch (e) { /* New file */ }

        await userOctokit.repos.createOrUpdateFileContents({
            owner, repo: name,
            path: file_path,
            message: `🤖 AI Fix: ${file_path}`,
            content: Buffer.from(fixed_code).toString('base64'),
            branch: newBranch,
            sha: fileSha
        });

        const pr = await userOctokit.pulls.create({
            owner, repo: name,
            title: `🛠️ AI Fix for ${file_path}`,
            head: newBranch,
            base: 'main',
            body: summary
        });

        res.json({ status: "success", pr_url: pr.data.html_url });

    } catch (e) {
        console.error("❌ Production Error:", e.message);
        res.status(500).json({ status: "error", message: "403 Forbidden: Check App Permissions in GitHub Settings." });
    }
});

app.listen(process.env.PORT || 3000);