import re
import unicodedata
import datasketch

SHINGLE_SIZE = 3
NUM_PERM = 128  # higher than a default 64 to reduce MinHash's own estimation noise near the threshold
SIMILARITY_THRESHOLD = 0.8  # near-duplicate, with margin below 1.0 for MinHash approximation error

_WHITESPACE_PATTERN = re.compile(r"\s+")


def _is_punctuation_or_symbol(ch: str) -> bool:
    return unicodedata.category(ch)[0] in ("P", "S")


def normalize_for_dedup(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in text if not _is_punctuation_or_symbol(ch))
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return text


def get_shingles(text: str, k: int = SHINGLE_SIZE) -> set[str]:
    if len(text) < k:
        return {text} if text else set()
    return {text[i:i + k] for i in range(len(text) - k + 1)}


def compute_minhash(text: str, num_perm: int = NUM_PERM) -> datasketch.MinHash:
    normalized = normalize_for_dedup(text)
    shingles = get_shingles(normalized)
    m = datasketch.MinHash(num_perm=num_perm)
    for shingle in shingles:
        m.update(shingle.encode("utf-8"))
    return m


def find_near_duplicates(records: list[dict], threshold: float = SIMILARITY_THRESHOLD) -> dict:
    canonical_hashes = []  # list of (id, MinHash)
    dup_map = {}

    for record in records:
        m = compute_minhash(record["text"])
        matched_canonical_id = None

        for canonical_id, canonical_hash in canonical_hashes:
            if m.jaccard(canonical_hash) >= threshold:
                matched_canonical_id = canonical_id
                break

        if matched_canonical_id is not None:
            dup_map[record["id"]] = matched_canonical_id
        else:
            canonical_hashes.append((record["id"], m))

    return dup_map