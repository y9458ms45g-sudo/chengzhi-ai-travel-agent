"""
知识库 RAG 检索工具
- 本地 md 文件按段落切 chunk
- BM25 关键词检索（纯 Python，不依赖 embedding API，离线可跑）
- 生产环境可无缝换成 embedding + 向量库（接口不变）
"""
import os
import glob
import math
import re
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "data", "knowledge")

# 城市关键词映射（与 executor.CITY_DETECT_RULES 保持同步）
CITY_KEYWORDS = {
    "重庆": ["重庆", "渝中", "江北", "南岸", "九龙坡", "沙坪坝", "解放碑",
             "洪崖洞", "磁器口", "长江索道", "鹅岭", "南滨路"],
    "成都": ["成都", "宽窄巷子", "锦里", "春熙路", "熊猫基地", "都江堰", "青城山"],
    "乐山": ["乐山", "峨眉山", "乐山大佛", "跷脚牛肉", "甜皮鸭", "钵钵鸡"],
}

# ---------- BM25 轻量实现 ----------
class BM25:
    """
    极简 BM25：对中文按字切分（不依赖 jieba，零安装）。
    k1=1.5, b=0.75 是论文默认值。
    """
    def __init__(self, corpus: list[str], k1=1.5, b=0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.doc_tokens = [self._tokenize(d) for d in corpus]
        self.doc_len = [len(t) for t in self.doc_tokens]
        self.avgdl = sum(self.doc_len) / max(len(self.doc_len), 1)
        self.df = Counter()
        for tokens in self.doc_tokens:
            for term in set(tokens):
                self.df[term] += 1
        self.N = max(len(corpus), 1)
        self.idf = {t: math.log((self.N - n + 0.5) / (n + 0.5) + 1)
                    for t, n in self.df.items()}

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        # 中文按单字切，英文按词切；过滤标点空白
        text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", " ", text)
        tokens = []
        for chunk in text.split():
            if re.match(r"^[a-zA-Z0-9]+$", chunk):
                tokens.append(chunk.lower())
            else:
                tokens.extend(list(chunk))  # 中文按字
        return tokens

    def search(self, query: str, top_k: int = 3) -> list[tuple[int, float]]:
        q_tokens = self._tokenize(query)
        scores = []
        for i, tokens in enumerate(self.doc_tokens):
            if not tokens:
                continue
            tf = Counter(tokens)
            score = 0.0
            dl = self.doc_len[i]
            for q in q_tokens:
                if q not in tf:
                    continue
                f = tf[q]
                idf = self.idf.get(q, 0.0)
                denom = f + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1))
                score += idf * f * (self.k1 + 1) / denom
            scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ---------- chunk 切分 ----------
def _chunk_markdown(text: str, max_len: int = 300) -> list[str]:
    """按标题+空行切 chunk，过长再硬切。"""
    # 按 markdown 标题切
    parts = re.split(r"\n(?=#{1,3}\s)", text)
    chunks = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) <= max_len:
            chunks.append(p)
        else:
            # 硬切成 max_len 大小
            for i in range(0, len(p), max_len):
                chunks.append(p[i:i+max_len])
    return chunks


_cache = {}           # city -> list[chunk]
_bm25_index = None    # 全局 BM25（加载所有 chunk）


def _load_chunks_for_city(city: str) -> list[str]:
    if city in _cache:
        return _cache[city]
    candidates = [
        os.path.join(KNOWLEDGE_DIR, f"{city}文旅知识库.md"),
        os.path.join(KNOWLEDGE_DIR, f"{city}.md"),
    ]
    chunks = []
    for fpath in candidates:
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                chunks = _chunk_markdown(f.read())
            break
    _cache[city] = chunks
    return chunks


def _detect_city(query: str) -> list[str]:
    matched = []
    for city, keywords in CITY_KEYWORDS.items():
        for kw in keywords:
            if kw in query:
                matched.append(city)
                break
    return matched


def search_knowledge(query: str, n_results: int = 3) -> str:
    """
    RAG 检索：
    1. 识别 query 涉及的城市
    2. 加载该城市的 md 文件，切 chunk
    3. BM25 检索 top-k 相关 chunk
    4. 返回 chunk 给 LLM（而不是整文件）
    """
    cities = _detect_city(query)
    all_chunks = []
    if cities:
        for city in cities:
            all_chunks.extend(_load_chunks_for_city(city))
    if not all_chunks:
        # 兜底：加载所有 md 文件
        files = glob.glob(os.path.join(KNOWLEDGE_DIR, "*.md"))
        for fpath in files:
            with open(fpath, "r", encoding="utf-8") as f:
                all_chunks.extend(_chunk_markdown(f.read()))

    if not all_chunks:
        return "[知识库为空] 请在 data/knowledge/ 目录下放置 .md 文件。"

    bm25 = BM25(all_chunks)
    hits = bm25.search(query, top_k=n_results)
    if not hits:
        return f"[知识库未命中] 与'{query}'相关的段落不足，建议联网搜索补充。"

    parts = [f"以下是知识库中与'{query}'最相关的 {len(hits)} 个段落："]
    for rank, (idx, score) in enumerate(hits, 1):
        parts.append(f"\n--- 段落{rank}（相关度{score:.2f}）---\n{all_chunks[idx]}")
    return "\n".join(parts)
