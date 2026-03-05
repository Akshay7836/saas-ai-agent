// const express = require('express');
// const axios = require('axios');
// const path = require('path');
// const { Octokit } = require("@octokit/rest");
// const { createAppAuth } = require("@octokit/auth-app"); // Auth library

// const app = express();

// // 1. GitHub App Configuration (Fetching from your Render Env)
// const GITHUB_APP_ID = process.env.GITHUB_APP_ID;
// const GITHUB_PRIVATE_KEY = process.env.GITHUB_PRIVATE_KEY.replace(/\\n/g, '\n'); 
// const PYTHON_URL = process.env.PYTHON_URL?.replace(/\/$/, ""); 

// app.use(express.json());
// app.use(express.static(path.join(__dirname)));

// // 🛠️ Function: Create Auth for specific User Installation
// async function getInstallationOctokit(installationId) {
//     return new Octokit({
//         authStrategy: createAppAuth,
//         auth: {
//             appId: GITHUB_APP_ID,
//             privateKey: GITHUB_PRIVATE_KEY,
//             installationId: installationId,
//         },
//     });
// }

// // 🚀 API 1: Scan (Public or App-based)
// app.post('/scan', async (req, res) => {
//     try {
//         const { repo, installation_id } = req.body;
//         const [owner, name] = repo.split('/');
        
//         // Agar installation_id hai, toh authenticated octokit use karo
//         const scanOctokit = installation_id ? await getInstallationOctokit(installation_id) : new Octokit();

//         const { data } = await scanOctokit.repos.getContent({ owner, repo: name, path: '' });
//         const fileNames = data.map(f => f.name).join(', ');

//         const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { 
//             command: "Scan", 
//             error_log: `Files: ${fileNames}. Suggest README.` 
//         });

//         res.json({ ...aiRes.data, repo });
//     } catch (e) {
//         res.status(500).json({ explanation: "Access Denied. Is the App installed on this repo?" });
//     }
// });

// // 🛠️ API 2: Apply Fix (Pure Production Logic)
// app.post('/apply-fix', async (req, res) => {
//     try {
//         const { repo, file_path, installation_id } = req.body;
//         const [owner, name] = repo.split('/');

//         if (!installation_id) throw new Error("Installation ID missing!");

//         // 🟢 AUTH: Dynamic Token for this specific User
//         const userOctokit = await getInstallationOctokit(installation_id);

//         // AI Generation
//         const aiRes = await axios.post(`${PYTHON_URL}/apply-fix`, {
//             repo_name: repo,
//             file_path: file_path,
//             installation_id: installation_id
//         });
        
//         const { fixed_code, summary } = aiRes.data; 
//         const newBranch = `ai-fix-${Date.now()}`;

//         // Git Workflow
//         const { data: mainRef } = await userOctokit.git.getRef({ owner, repo: name, ref: 'heads/main' });
//         await userOctokit.git.createRef({
//             owner, repo: name,
//             ref: `refs/heads/${newBranch}`,
//             sha: mainRef.object.sha
//         });

//         let fileSha;
//         try {
//             const { data: fileData } = await userOctokit.repos.getContent({ owner, repo: name, path: file_path, ref: 'main' });
//             fileSha = fileData.sha;
//         } catch (e) { /* New file */ }

//         await userOctokit.repos.createOrUpdateFileContents({
//             owner, repo: name,
//             path: file_path,
//             message: `🤖 AI Fix: ${file_path}`,
//             content: Buffer.from(fixed_code).toString('base64'),
//             branch: newBranch,
//             sha: fileSha
//         });

//         const pr = await userOctokit.pulls.create({
//             owner, repo: name,
//             title: `🛠️ AI Fix for ${file_path}`,
//             head: newBranch,
//             base: 'main',
//             body: summary
//         });

//         res.json({ status: "success", pr_url: pr.data.html_url });

//     } catch (e) {
//         console.error("❌ Production Error:", e.message);
//         res.status(500).json({ status: "error", message: "403 Forbidden: Check App Permissions in GitHub Settings." });
//     }
// });

// app.listen(process.env.PORT || 3000);

const express = require('express');
const axios = require('axios');
const path = require('path');
const { Octokit } = require("@octokit/rest");
const { createAppAuth } = require("@octokit/auth-app");

const app = express();

// Configuration
const GITHUB_APP_ID = process.env.GITHUB_APP_ID;
const GITHUB_PRIVATE_KEY = process.env.GITHUB_PRIVATE_KEY.replace(/\\n/g, '\n'); 
const PYTHON_URL = process.env.PYTHON_URL?.replace(/\/$/, ""); 

app.use(express.json());
app.use(express.static(path.join(__dirname)));

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

// 🚀 API 1: Scan (Ye basic scan ke liye hai)
app.post('/scan', async (req, res) => {
    try {
        const { repo, installation_id } = req.body;
        const [owner, name] = repo.split('/');
        const scanOctokit = installation_id ? await getInstallationOctokit(installation_id) : new Octokit();

        const { data } = await scanOctokit.repos.getContent({ owner, repo: name, path: '' });
        const fileNames = data.map(f => f.name).join(', ');

        const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { 
            command: "Scan", 
            error_log: `Files: ${fileNames}` 
        });

        res.json({ ...aiRes.data, repo });
    } catch (e) {
        res.status(500).json({ explanation: "Scan failed. Check app installation." });
    }
});

// 🛠️ API 2: Agent-Based Auto Fix (The Master Logic)
app.post('/apply-fix', async (req, res) => {
    try {
        const { repo, installation_id } = req.body;
        const [owner, name] = repo.split('/');

        if (!installation_id) throw new Error("Installation ID missing!");
        const userOctokit = await getInstallationOctokit(installation_id);

        // --- STEP 1: Get all files (Recursive Tree) ---
        console.log("🔍 Fetching repo tree...");
        const { data: treeData } = await userOctokit.git.getTree({
            owner, repo: name, tree_sha: 'main', recursive: true
        });

        const filePaths = treeData.tree
            .filter(f => f.type === 'blob' && !f.path.includes('node_modules'))
            .map(f => f.path)
            .join(', ');

        // --- STEP 2: Ask AI which file is problematic ---
        console.log("🧠 AI is analyzing which file to fix...");
        const analysis = await axios.post(`${PYTHON_URL}/analyze-repo`, { 
            files_context: filePaths 
        });
        
        const { target_file, reason, action } = analysis.data;
        console.log(`🎯 Target: ${target_file} | Reason: ${reason}`);

        // --- STEP 3: Get the content of THAT specific file ---
        const { data: fileContent } = await userOctokit.repos.getContent({
            owner, repo: name, path: target_file, ref: 'main'
        });
        const originalCode = Buffer.from(fileContent.content, 'base64').toString();

        // --- STEP 4: Get Fixed Code from AI ---
        console.log("🛠️ AI is fixing the code...");
        const fixRes = await axios.post(`${PYTHON_URL}/apply-fix`, {
            repo_name: repo,
            file_path: target_file,
            installation_id: parseInt(installation_id),
            original_code: originalCode
        });

        const { fixed_code, summary } = fixRes.data;
        const newBranch = `ai-agent-fix-${Date.now()}`;

        // --- STEP 5: Create Branch & Push ---
        const { data: mainRef } = await userOctokit.git.getRef({ owner, repo: name, ref: 'heads/main' });
        await userOctokit.git.createRef({
            owner, repo: name, ref: `refs/heads/${newBranch}`, sha: mainRef.object.sha
        });

        await userOctokit.repos.createOrUpdateFileContents({
            owner, repo: name,
            path: target_file,
            message: `🤖 AI Agent: ${action}`,
            content: Buffer.from(fixed_code).toString('base64'),
            branch: newBranch,
            sha: fileContent.sha
        });

        // --- STEP 6: Create PR ---
        const pr = await userOctokit.pulls.create({
            owner, repo: name,
            title: `🛠️ AI Auto-Fix: ${target_file}`,
            head: newBranch,
            base: 'main',
            body: `### 🤖 AI Agent Report\n\n**File:** \`${target_file}\`\n**Problem:** ${reason}\n**Action:** ${action}\n\n${summary}`
        });

        res.json({ 
            status: "success", 
            message: `Fixed ${target_file} successfully!`, 
            pr_url: pr.data.html_url 
        });

    } catch (e) {
        console.error("❌ Agent Workflow Error:", e.message);
        res.status(500).json({ status: "error", message: e.message });
    }
});

app.listen(process.env.PORT || 3000);