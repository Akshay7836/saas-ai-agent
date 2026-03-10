from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

def index_repo(files):

    documents = []

    for f in files:

        documents.append({
            "path": f["path"],
            "content": f["code"]
        })

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    texts = []
    metadatas = []

    for doc in documents:

        chunks = splitter.split_text(doc["content"])

        for chunk in chunks:

            texts.append(chunk)

            metadatas.append({
                "path": doc["path"]
            })

    vectordb = Chroma.from_texts(
        texts,
        embeddings,
        metadatas=metadatas
    )

    return vectordb


def search_code(vectordb, query):

    results = vectordb.similarity_search(query, k=5)

    context = []

    for r in results:

        context.append({
            "path": r.metadata["path"],
            "code": r.page_content
        })

    return context