"""Lightweight hashed bag-of-words embedding (no dependencies). Good enough for small, domain-specific memory."""
import hashlib
import math
import re

STOP = {"the", "and", "for", "with", "that", "this", "was", "were", "are", "has", "have", "had", "not", "but",
        "from", "into", "its", "than", "then", "also", "when", "which", "their", "there", "been", "will"}


def words(text):
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2 and w not in STOP]


def embed(text, dims=64):
    vec = [0.0] * dims
    for w in words(text):
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        vec[h % dims] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a, b):
    return max(0.0, sum(x * y for x, y in zip(a, b)))
