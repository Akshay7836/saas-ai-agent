from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings


def index_repo(files):

    docs = []

    for file in files:
        docs.append({
            "content": file["code"],
            "metadata": {"path": file["path"]}
        })

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )

    chunks = []

    for doc in docs:
        parts = splitter.split_text(doc["content"])
        for p in parts:
            chunks.append({
                "content": p,
                "metadata": doc["metadata"]
            })

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vectordb = FAISS.from_texts(
        [c["content"] for c in chunks],
        embeddings,
        metadatas=[c["metadata"] for c in chunks]
    )

    return vectordb


def search_code(vectordb, query):

    results = vectordb.similarity_search(query, k=10)

    snippets = []

    for r in results:
        snippets.append({
            "file": r.metadata["path"],
            "code": r.page_content
        })

    return snippets