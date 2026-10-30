"""The served catalogue file: products and vocabulary together, under one version."""

from pathlib import Path

from catalog.storage import encode_catalog, read_catalog, read_vocabulary

SEARCH = {"phrases": {"noise cancelling": "anc"}, "synonyms": [["headphone", "earbud"]]}


def test_vocabulary_round_trips(tmp_path: Path) -> None:
    data, _ = encode_catalog([], "src", "dec", SEARCH)
    (tmp_path / "catalog.json").write_bytes(data)
    vocabulary = read_vocabulary(tmp_path / "catalog.json")
    assert vocabulary.terms("noise cancelling earbuds") == ["anc", "earbud"]
    assert vocabulary.group("earbud") == {"headphone", "earbud"}
    assert read_catalog(tmp_path / "catalog.json")[1] == []


def test_a_vocabulary_change_changes_the_served_version() -> None:
    _, with_vocabulary = encode_catalog([], "src", "dec", SEARCH)
    _, without = encode_catalog([], "src", "dec", {"phrases": {}, "synonyms": []})
    assert with_vocabulary["products_sha256"] == without["products_sha256"]
    assert with_vocabulary["served_sha256"] != without["served_sha256"]
