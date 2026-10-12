"""
构建RAG知识库：读取 data/knowledge/ 下的文档，切分、向量化、存入Chroma
运行：python build_knowledge.py
"""
import os
import glob
import chromadb
from dotenv import load_dotenv
from app.llm import embed

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "data", "knowledge")
CHROMA_DIR = os.path.join(BASE_DIR, "data", "chroma_db")
COLLECTION = "wenlv_knowledge"

CHUNK_SIZE = 500      # 每段字符数
CHUNK_OVERLAP = 50    # 重叠字符数


def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """简单按字符切分，带重叠"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks


def main():
    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # 重建collection
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.create_collection(COLLECTION)

    files = glob.glob(os.path.join(KNOWLEDGE_DIR, "*.md")) + \
            glob.glob(os.path.join(KNOWLEDGE_DIR, "*.txt"))
    if not files:
        print("未找到知识库文件，请把 .md/.txt 放入 data/knowledge/")
        return

    all_chunks = []
    all_metas = []
    all_ids = []
    idx = 0

    for fpath in files:
        fname = os.path.basename(fpath)
        print(f"读取：{fname}")
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = chunk_text(text)
        for ch in chunks:
            if len(ch.strip()) < 20:
                continue
            all_chunks.append(ch)
            all_metas.append({"source": fname})
            all_ids.append(f"chunk_{idx}")
            idx += 1

    print(f"共切分 {len(all_chunks)} 个段落，开始向量化...")

    # 分批embedding
    BATCH = 20
    for i in range(0, len(all_chunks), BATCH):
        batch = all_chunks[i:i+BATCH]
        batch_ids = all_ids[i:i+BATCH]
        batch_metas = all_metas[i:i+BATCH]
        vectors = embed(batch)
        col.add(
            ids=batch_ids,
            documents=batch,
            embeddings=vectors,
            metadatas=batch_metas,
        )
        print(f"  已写入 {min(i+BATCH, len(all_chunks))}/{len(all_chunks)}")

    print(f"\n知识库构建完成！共 {col.count()} 个段落。")


if __name__ == "__main__":
    main()
