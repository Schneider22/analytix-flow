from app.domain.hashing import canonical_json, sha256_canonical


def test_canonical_hash_is_order_independent():
    left = {"b": 2, "a": [1, 2]}
    right = {"a": [1, 2], "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert sha256_canonical(left) == sha256_canonical(right)
