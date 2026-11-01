"""Shopper text and product text into comparable words: apostrophes, single letters, plurals."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from catalog.domain.catalog import Catalog
from catalog.domain.text import Vocabulary, query_terms, stem, words
from tests.domain.test_catalog import product


class TestApostrophes:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("chef's knife", ["chef", "knife"]),
            ("chef\u2019s knife", ["chef", "knife"]),  # the curly apostrophe phones type
            ("men's watch", ["men", "watch"]),
            ("kids' art case", ["kid", "art", "case"]),
            ("CHEF'S KNIFE", ["chef", "knife"]),
        ],
    )
    def test_a_possessive_is_one_word(self, query: str, expected: list[str]) -> None:
        assert query_terms(query) == expected

    def test_product_text_has_no_stray_s(self) -> None:
        assert words("Chef's Knife 20cm") == {"chef", "knife", "20cm"}
        assert words("Kids' Art Supply Case") == {"kid", "art", "supply", "case"}
        assert words("Risky unless you know the person\u2019s taste") == {
            "risky",
            "unless",
            "you",
            "know",
            "the",
            "person",
            "taste",
        }

    def test_a_contraction_stays_one_word(self) -> None:
        assert words("you don't know") == {"you", "dont", "know"}

    def test_the_vocabulary_reads_apostrophes_the_same_way(self) -> None:
        vocabulary = Vocabulary(phrases={"chef's knife": "gyuto"}, generic=["set"])
        assert vocabulary.terms("chef\u2019s knife set") == ["gyuto"]
        assert vocabulary.terms("men's watch") == ["men", "watch"]

    def test_search_reports_no_missing_s(self) -> None:
        catalog = Catalog(
            [
                product("KD-001", name="Chef's Knife 20cm", subcategory="Knives", tags=["knife", "chef"]),
                product("KD-002", name="Paring Knife 9cm", subcategory="Knives", tags=["knife", "paring"]),
            ]
        )
        result = catalog.search("chef's knife")
        assert [p.product_id for p in result.products] == ["KD-001", "KD-002"]
        assert result.missing_terms == {"KD-002": ["chef"]}
        assert result.unmatched_terms == []


class TestSingleCharacters:
    """Decided: single letters and digits are kept. In this catalogue they carry meaning: "Vitamin C
    Serum", "E-Reader", "Moka Pot 3-cup", "2-4players". Only the "s" an apostrophe used to split off
    was noise, and that is handled where it arises."""

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("vitamin c serum", ["vitamin", "c", "serum"]),
            ("e-reader", ["e", "reader"]),
            ("3-cup moka pot", ["3", "cup", "moka", "pot"]),
        ],
    )
    def test_meaningful_single_characters_are_kept(self, query: str, expected: list[str]) -> None:
        assert query_terms(query) == expected

    @given(
        st.lists(
            st.tuples(
                st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=2, max_size=8),
                st.sampled_from(["", "'s", "\u2019s", "'", "\u2019", "n't"]),
            ),
            min_size=1,
            max_size=5,
        ),
        st.sampled_from([" ", ", ", " - ", "; "]),
    )
    def test_no_single_letter_term_unless_the_shopper_typed_one(
        self, parts: list[tuple[str, str]], separator: str
    ) -> None:
        text = separator.join(word + suffix for word, suffix in parts)
        assert all(len(t) > 1 for t in query_terms(text))
        assert all(len(w) > 1 for w in words(text))

    @given(st.lists(st.from_regex(r"[a-z]{2,8}", fullmatch=True), min_size=1, max_size=5))
    def test_a_possessive_reads_as_its_word(self, plain: list[str]) -> None:
        possessive = " ".join(f"{w}'s" for w in plain)
        assert query_terms(possessive) == query_terms(" ".join(plain))


class TestStem:
    """Pins the crude plural-to-singular rule as it is; a change here moves search results."""

    @pytest.mark.parametrize(
        ("word", "expected"),
        [
            ("knives", "knife"),
            ("shelves", "shelf"),
            ("accessories", "accessory"),
            ("glasses", "glass"),
            ("boxes", "box"),
            ("watches", "watch"),
            ("brushes", "brush"),
            ("candles", "candle"),
            ("kids", "kid"),
            ("glass", "glass"),
            ("cactus", "cactus"),
            ("tennis", "tennis"),
            ("mugs", "mug"),
            ("men", "men"),
            ("gas", "gas"),  # three letters or fewer are left alone
            ("lens", "len"),  # crude: a final -s after a letter other than s, u or i goes
        ],
    )
    def test_plural_to_singular(self, word: str, expected: str) -> None:
        assert stem(word) == expected
