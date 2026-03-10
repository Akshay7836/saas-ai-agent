const express=require("express")
const axios=require("axios")
const path=require("path")
const {Octokit}=require("@octokit/rest")
const {createAppAuth}=require("@octokit/auth-app")
require("dotenv").config()

const app=express()
app.use(express.json())
app.use(express.static(path.join(__dirname)))

const APP_ID=process.env.GITHUB_APP_ID
const PRIVATE_KEY=process.env.GITHUB_PRIVATE_KEY.replace(/\\n/g,"\n")
const PYTHON_URL=process.env.PYTHON_URL?.replace(/\/$/,"")

async function getOcto(installationId){

return new Octokit({
authStrategy:createAppAuth,
auth:{appId:APP_ID,privateKey:PRIVATE_KEY,installationId}
})

}

app.post("/scan",async(req,res)=>{

try{

const {repo,installation_id}=req.body
const [owner,repoName]=repo.split("/")

const octo=await getOcto(installation_id)

const repoInfo=await octo.repos.get({owner,repo:repoName})
const defaultBranch=repoInfo.data.default_branch

const tree=await octo.git.getTree({
owner,
repo:repoName,
tree_sha:defaultBranch,
recursive:true
})

const importantFiles=tree.data.tree.filter(f=>

f.path.endsWith(".js")||
f.path.endsWith(".ts")||
f.path.endsWith(".py")||
f.path==="package.json"

).slice(0,5)

let fileData=[]

for(let file of importantFiles){

const content=await octo.repos.getContent({
owner,
repo:repoName,
path:file.path
})

const code=Buffer.from(content.data.content,"base64").toString()

fileData.push({
path:file.path,
code:code.slice(0,2000)
})

}

const ai=await axios.post(`${PYTHON_URL}/analyze-repo`,{files:fileData})

res.json(ai.data)

}catch(e){

console.error(e)
res.status(500).json({error:"Scan failed"})

}

})

app.post("/apply-fix",async(req,res)=>{

try{

const {repo,installation_id,target_file}=req.body

const [owner,repoName]=repo.split("/")

const octo=await getOcto(installation_id)

const file=await octo.repos.getContent({
owner,
repo:repoName,
path:target_file
})

const originalCode=Buffer.from(file.data.content,"base64").toString()

const aiFix=await axios.post(`${PYTHON_URL}/apply-fix`,{
file_path:target_file,
original_code:originalCode
})

const codeString=typeof aiFix.data.fixed_code==="string"
?aiFix.data.fixed_code
:JSON.stringify(aiFix.data.fixed_code,null,2)

const branch=`ai-fix-${Date.now()}`

const mainRef=await octo.git.getRef({
owner,
repo:repoName,
ref:"heads/main"
})

await octo.git.createRef({
owner,
repo:repoName,
ref:`refs/heads/${branch}`,
sha:mainRef.data.object.sha
})

await octo.repos.createOrUpdateFileContents({

owner,
repo:repoName,
path:target_file,
message:`AI Fix for ${target_file}`,
content:Buffer.from(codeString).toString("base64"),
branch,
sha:file.data.sha

})

const pr=await octo.pulls.create({

owner,
repo:repoName,
title:`AI Fix: ${target_file}`,
head:branch,
base:"main",
body:`AI automatically fixed an issue in ${target_file}`

})

res.json({pr_url:pr.data.html_url})

}catch(e){

console.error(e)
res.status(500).json({error:"Fix failed"})

}

})

app.listen(process.env.PORT||3000,()=>console.log("Server running"))