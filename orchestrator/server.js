const express = require("express");
const path = require("path");
const { Octokit } = require("@octokit/rest"); // Better for production
const { createAppAuth } = require("@octokit/auth-app");
const axios = require("axios");
require("dotenv").config();

const app = express();
app.use(express.json());
app.use(express.static(__dirname));

const APP_ID = process.env.GITHUB_APP_ID;
const PRIVATE_KEY = process.env.GITHUB_PRIVATE_KEY?.replace(/\\n/g, '\n');
const AI_URL = process.env.AI_ENGINE_URL?.replace(/\/$/, "");

function getOctokit(installationId) {
    return new Octokit({
        authStrategy: createAppAuth,
        auth: { appId: APP_ID, privateKey: PRIVATE_KEY, installationId }
    });
}

app.get("/", (req, res) => res.sendFile(path.join(__dirname, "index.html")));

app.post("/scan", async (req, res) => {
    try {
        const { repo, installation_id } = req.body;
        const [owner, repoName] = repo.split("/");
        const octo = getOctokit(installation_id);

        // Recursive scan for all files in all folders
        const { data: tree } = await octo.git.getTree({
            owner, repo: repoName, tree_sha: 'main', recursive: true
        });

        const files = tree.tree
            .filter(f => f.type === 'blob')
            .map(f => f.path);

        const ai = await axios.post(`${AI_URL}/analyze`, { repo, files });
        res.json(ai.data);
    } catch (err) {
        console.error(err.response?.data || err.message);
        res.status(500).json({ error: "Scan failed. Check AI Engine URL." });
    }
});

app.post("/apply-fix", async (req, res) => {
    try {
        const { repo, installation_id, target_file } = req.body;
        const [owner, repoName] = repo.split("/");
        const octo = getOctokit(installation_id);

        // 1. Get current file content and SHA
        const { data: fileData } = await octo.repos.getContent({ owner, repo: repoName, path: target_file });
        const originalCode = Buffer.from(fileData.content, 'base64').toString();

        // 2. Get fixed code from AI
        const aiResponse = await axios.post(`${AI_URL}/get-fix`, { 
            file_path: target_file, 
            original_code: originalCode 
        });
        
        const fixedCode = typeof aiResponse.data.fixed_code === 'string' 
            ? aiResponse.data.fixed_code 
            : JSON.stringify(aiResponse.data.fixed_code);

        // 3. Create Branch
        const branch = `ai-fix-${Date.now()}`;
        const { data: mainRef } = await octo.git.getRef({ owner, repo: repoName, ref: 'heads/main' });
        await octo.git.createRef({ owner, repo: repoName, ref: `refs/heads/${branch}`, sha: mainRef.object.sha });

        // 4. Push Fix
        await octo.repos.createOrUpdateFileContents({
            owner, repo: repoName, path: target_file,
            message: `🤖 AI Fix: ${target_file}`,
            content: Buffer.from(fixedCode).toString("base64"),
            branch,
            sha: fileData.sha
        });

        // 5. Create PR
        const pr = await octo.pulls.create({
            owner, repo: repoName, title: `🛡️ Minion Fix: ${target_file}`,
            head: branch, base: 'main',
            body: "AI identified and resolved an issue in this file."
        });

        res.json({ pr_url: pr.data.html_url });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: "Failed to apply fix." });
    }
});

app.listen(process.env.PORT || 3000);