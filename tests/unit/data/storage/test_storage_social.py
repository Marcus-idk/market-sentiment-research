"""Social discussion storage CRUD tests."""

from datetime import UTC, datetime

from data.storage import get_social_discussions_since, store_social_discussions
from data.storage.db_context import _cursor_context
from data.storage.storage_utils import _normalize_url
from tests.factories import make_social_discussion


class TestStoreSocialDiscussions:
    """Insert and upsert behavior for social_discussions."""

    def test_store_social_discussions_inserts(self, temp_db):
        """Unique (source, source_id) rows insert with normalized fields."""
        first = make_social_discussion(
            source="reddit",
            source_id="t3_1",
            symbol="aapl",
            title="First",
            url="https://Reddit.com/r/stocks/1?utm_source=abc",
            published=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            content="Body1",
        )
        second = make_social_discussion(
            source="reddit",
            source_id="t3_2",
            symbol="TSLA",
            title="Second",
            url="https://reddit.com/r/stocks/2",
            published=datetime(2024, 1, 1, 13, 0, tzinfo=UTC),
            content="Body2",
        )

        store_social_discussions(temp_db, [first, second])

        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM social_discussions")
            assert cursor.fetchone()[0] == 2

            cursor.execute(
                """
                SELECT source, source_id, symbol, community, title, url, content, published_iso
                FROM social_discussions
                ORDER BY source_id
                """
            )
            rows = cursor.fetchall()
            assert rows[0]["symbol"] == "AAPL"
            assert rows[0]["title"] == "First"
            assert rows[0]["url"] == _normalize_url(first.url)
            assert rows[0]["content"] == "Body1"
            assert rows[1]["symbol"] == "TSLA"
            assert rows[1]["title"] == "Second"

    def test_store_social_discussions_upserts_on_source_id(self, temp_db):
        """Upsert updates fields when source/source_id conflict."""
        original = make_social_discussion(
            title="Original",
            content="Old",
            url="https://reddit.com/r/stocks/1",
        )
        updated = make_social_discussion(
            title="Updated",
            content="New content",
            url="https://reddit.com/r/stocks/1?utm_campaign=ads",
        )

        store_social_discussions(temp_db, [original])
        store_social_discussions(temp_db, [updated])

        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("SELECT title, content, url FROM social_discussions")
            row = cursor.fetchone()
            assert row["title"] == "Updated"
            assert row["content"] == "New content"
            assert row["url"] == _normalize_url(updated.url)

    def test_store_social_discussions_empty_list_noop(self, temp_db):
        """Empty input performs no inserts."""
        store_social_discussions(temp_db, [])

        with _cursor_context(temp_db, commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM social_discussions")
            assert cursor.fetchone()[0] == 0


class TestGetSocialDiscussions:
    """Query helpers for social_discussions."""

    def test_get_social_discussions_since_filters_by_timestamp(self, temp_db):
        """Returns only rows after cutoff."""
        before = make_social_discussion(
            source_id="t3_old",
            published=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
        )
        after = make_social_discussion(
            source_id="t3_new",
            published=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
        )
        store_social_discussions(temp_db, [before, after])

        cutoff = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
        results = get_social_discussions_since(temp_db, cutoff)

        assert len(results) == 1
        assert results[0].source_id == "t3_new"

    def test_get_social_discussions_since_filters_by_symbol_case_insensitive(self, temp_db):
        """Symbol filter uppercases input before lookup."""
        aapl = make_social_discussion(symbol="AAPL", source_id="t3_aapl")
        tsla = make_social_discussion(symbol="TSLA", source_id="t3_tsla")
        store_social_discussions(temp_db, [aapl, tsla])

        results = get_social_discussions_since(
            temp_db,
            datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            symbol="aapl",
        )

        assert [item.source_id for item in results] == ["t3_aapl"]
        assert results[0].symbol == "AAPL"

    def test_get_social_discussions_since_sorted_ascending(self, temp_db):
        """Rows are ordered by published_iso ascending."""
        newer = make_social_discussion(
            source_id="t3_newer",
            published=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        )
        oldest = make_social_discussion(
            source_id="t3_oldest",
            published=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
        )
        middle = make_social_discussion(
            source_id="t3_middle",
            published=datetime(2024, 1, 1, 11, 0, tzinfo=UTC),
        )
        store_social_discussions(temp_db, [newer, oldest, middle])

        results = get_social_discussions_since(
            temp_db,
            datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
        )

        assert [item.source_id for item in results] == ["t3_oldest", "t3_middle", "t3_newer"]

    def test_store_and_get_preserves_content_and_url_normalization(self, temp_db):
        """Content round-trips; URLs are normalized on insert."""
        discussion = make_social_discussion(
            url="https://REDDIT.com/r/stocks/comments/1?utm_medium=ref",
            content="Line one",
            published=datetime(2024, 1, 2, 9, 0, tzinfo=UTC),
        )

        store_social_discussions(temp_db, [discussion])

        results = get_social_discussions_since(
            temp_db,
            datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        )

        assert len(results) == 1
        result = results[0]
        assert result.content == "Line one"
        assert result.url == _normalize_url(discussion.url)
