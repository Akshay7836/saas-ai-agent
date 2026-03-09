const express = require('express');
const axios = require('axios');
const path = require('path');
const { Octokit } = require("@octokit/rest");
const { createAppAuth } = require("@octokit/auth-app");
require('dotenv').config();

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname)));

const APP_ID = process.env.GITHUB_APP_ID;
const PRIVATE_KEY = process.env.GITHUB_PRIVATE_KEY.replace(/\\n/g, '\n');
const PYTHON_URL = process.env.PYTHON_URL?.replace(/\/$/, "");

async function getOcto(installationId) {
    return new Octokit({
        authStrategy: createAppAuth,
        auth: { appId: APP_ID, privateKey: PRIVATE_KEY, installationId },
    });
}

app.post('/scan', async (req, res) => {
    try {
        const { repo, installation_id } = req.body;
        const [owner, repoName] = repo.split('/');
        const octo = await getOcto(installation_id);

        const { data: tree } = await octo.git.getTree({ 
            owner, repo: repoName, tree_sha: 'main', recursive: true 
        });

        const files = tree.tree.filter(f => f.type === 'blob').map(f => f.path).join(", ");
        const ai = await axios.post(`${PYTHON_URL}/analyze-repo`, { files_context: files });
        
        res.json({ ...ai.data, repo });
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: "Scan failed. Check Python URL and App Permissions." });
    }
});

app.post('/apply-fix', async (req, res) => {
    try {
        const { repo, installation_id, target_file } = req.body;
        const [owner, repoName] = repo.split('/');
        const octo = await getOcto(installation_id);

        let originalCode = "";
        let sha = null;
        try {
            const { data: file } = await octo.repos.getContent({ owner, repo: repoName, path: target_file });
            originalCode = Buffer.from(file.content, 'base64').toString();
            sha = file.sha;
        } catch (fErr) { console.log("New file mode"); }

        const aiFix = await axios.post(`${PYTHON_URL}/apply-fix`, { file_path: target_file, original_code: originalCode });
        
        const branch = `fix-${Date.now()}`;
        const { data: mainRes } = await octo.git.getRef({ owner, repo: repoName, ref: 'heads/main' });
        await octo.git.createRef({ owner, repo: repoName, ref: `refs/heads/${branch}`, sha: mainRes.object.sha });

        await octo.repos.createOrUpdateFileContents({
            owner, repo: repoName, path: target_file,
            message: `🤖 AI Fix for ${target_file}`,
            content: Buffer.from(aiFix.data.fixed_code).toString('base64'),
            branch, sha
        });

        const pr = await octo.pulls.create({
            owner, repo: repoName, title: `🛡️ Minion Heal: ${target_file}`,
            head: branch, base: 'main', body: "AI identified and fixed a logical issue."
        });

        res.json({ pr_url: pr.data.html_url });
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: e.message });
    }
});

app.listen(process.env.PORT || 3000, () => console.log("Server Live"));