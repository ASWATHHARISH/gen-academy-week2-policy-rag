"""Dependency-free Okapi BM25 and equal-weight reciprocal rank fusion.

BM25 uses positive Lucene-style IDF and the standard saturation/length formula:
https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables
RRF: Cormack, Clarke and Buettcher (SIGIR 2009), k=60:
https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf
Parameters and tokenization are fixed independently of evaluation questions.
"""
from collections import Counter, defaultdict
import math
import re
from typing import Any

STOPWORDS = frozenset("a an and are as at be by for from in is it of on or that the this to was were with".split())


def tokenize(text: str) -> list[str]:
    """Keep number/acronym tokens; no stemming, acronym expansion or query tuning."""
    return [word for word in re.findall(r"\b\w+\b", text.casefold()) if word not in STOPWORDS]


class BM25Index:
    def __init__(self, documents: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        if not math.isfinite(k1) or k1 <= 0 or not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("Invalid BM25 parameters")
        self.documents = documents
        self.by_id = {document["id"]: document for document in documents}
        if len(self.by_id) != len(documents):
            raise ValueError("Duplicate BM25 document IDs")
        self.k1, self.b = k1, b
        self.lengths: list[int] = []
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for index, document in enumerate(documents):
            counts = Counter(tokenize(document["text"]))
            self.lengths.append(sum(counts.values()))
            for word, frequency in counts.items():
                self.postings[word].append((index, frequency))
        self.avgdl = sum(self.lengths) / len(documents) if documents else 0.0
        self.idf = {
            word: math.log1p((len(documents) - len(posting) + 0.5) / (len(posting) + 0.5))
            for word, posting in self.postings.items()
        }

    def scores(self, query: str) -> dict[str, float]:
        values = [0.0] * len(self.documents)
        if self.avgdl:
            for word in set(tokenize(query)):
                for index, frequency in self.postings.get(word, []):
                    norm = self.k1 * (1 - self.b + self.b * self.lengths[index] / self.avgdl)
                    values[index] += self.idf[word] * frequency * (self.k1 + 1) / (frequency + norm)
        return {document["id"]: values[index] for index, document in enumerate(self.documents)}

    def ranked(self, scores: dict[str, float], limit: int = 10) -> list[dict[str, Any]]:
        ids = sorted((cid for cid, score in scores.items() if score > 0), key=lambda cid: (-scores[cid], cid))
        return [{**self.by_id[cid], "bm25_score": scores[cid]} for cid in ids[:max(0, limit)]]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.ranked(self.scores(query), limit)


def reciprocal_rank_fusion(dense_ids: list[str], sparse_ids: list[str], k: int = 60) -> list[dict[str, Any]]:
    """RRF sums 1/(k+rank) once per list; component scores are never mixed."""
    if k <= 0:
        raise ValueError("RRF k must be positive")
    results: dict[str, dict[str, Any]] = {}
    for label, ids in (("dense_rank", dense_ids), ("sparse_rank", sparse_ids)):
        for rank, cid in enumerate(dict.fromkeys(ids), start=1):
            row = results.setdefault(cid, {"id": cid, "rrf_score": 0.0, "dense_rank": None, "sparse_rank": None})
            row[label] = rank
            row["rrf_score"] += 1.0 / (k + rank)
    return sorted(results.values(), key=lambda row: (
        -row["rrf_score"], row["dense_rank"] or float("inf"), row["sparse_rank"] or float("inf"), row["id"]
    ))
