"""Verify the engagement-rate filter in ga_report.get_article_async without
hitting GA4 or the Keystone GraphQL endpoint.

Run: python test_filter.py
"""

import asyncio
import io
import os
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

import ga_report

# Production order is screenPageViews, engagementRate. The test deliberately
# stores rows in a different physical order from the headers it advertises
# (engagementRate first, screenPageViews second) so that any reintroduction of
# hardcoded index access would surface as a test failure.
METRIC_HEADERS = [
    SimpleNamespace(name="engagementRate"),
    SimpleNamespace(name="screenPageViews"),
]


def make_row(title, path, views, engagement_rate):
    return SimpleNamespace(
        dimension_values=[
            SimpleNamespace(value=title),
            SimpleNamespace(value=path),
        ],
        metric_values=[
            SimpleNamespace(value=str(engagement_rate)),
            SimpleNamespace(value=str(views)),
        ],
    )


class FakeSession:
    def __init__(self, posts):
        self._posts = posts

    async def execute(self, query, variable_values=None):
        wanted = set(variable_values.get("slugs", []))
        return {"posts": [p for p in self._posts if p["slug"] in wanted]}


class FakeClient:
    def __init__(self, posts):
        self._posts = posts

    async def __aenter__(self):
        return FakeSession(self._posts)

    async def __aexit__(self, *_):
        return False


class FakeGraphQLClient:
    posts_in_db = []

    def __init__(self):
        pass

    async def get_authenticated_client(self):
        return FakeClient(self.posts_in_db)


def make_post(slug, source="tv"):
    return {
        "id": slug,
        "slug": slug,
        "name": f"Title {slug}",
        "publishTime": "2026-05-19T00:00:00.000Z",
        "source": source,
        "heroImage": {"resized": {"w480": "x.jpg", "w800": "y.jpg"}},
        "exclusive": None,
    }


def run_with_threshold(threshold, rows, posts):
    os.environ["MIN_ENGAGEMENT_RATE"] = str(threshold)
    FakeGraphQLClient.posts_in_db = posts
    response = SimpleNamespace(rows=rows, metric_headers=METRIC_HEADERS)

    captured = io.StringIO()
    with patch.object(ga_report, "GraphQLClient", FakeGraphQLClient), redirect_stdout(captured):
        result = asyncio.run(ga_report.get_article_async(response))
    return result, captured.getvalue()


def test_filters_low_engagement():
    rows = [
        # crawler-pattern: high views, near-zero engagement
        make_row("劉邦友血案", "/story/20220208sot12021", 250046, 0.016),
        make_row("台積電之歌", "/story/20250620sot18012", 250046, 0.009),
        # real reader behavior
        make_row("520育嬰假", "/story/20260519nm009", 51048, 0.55),
        make_row("淡江大橋", "/story/20260516nm010", 30000, 0.42),
    ]
    posts = [make_post(s) for s in (
        "20220208sot12021", "20250620sot18012", "20260519nm009", "20260516nm010",
    )]
    result, stdout = run_with_threshold(0.3, rows, posts)

    slugs_kept = {a["slug"] for a in result["articles"]}
    assert slugs_kept == {"20260519nm009", "20260516nm010"}, slugs_kept
    assert "[bot-filtered] slug=20220208sot12021" in stdout
    assert "[bot-filtered] slug=20250620sot18012" in stdout
    assert "engagement=1.6%" in stdout
    assert "engagement=0.9%" in stdout
    print("PASS test_filters_low_engagement")


def test_existing_filters_preserved():
    rows = [
        # mm- prefix: existing exclusion still applies
        make_row("mm article", "/story/mm-20260318edi033", 126740, 0.72),
        # slug blacklist
        make_row("about us", "/story/aboutus", 1000, 0.9),
        # not a /story/ URL
        make_row("category page", "/category/pol", 66261, 0.18),
        # duplicate slug from two rows (different titles)
        make_row("dup A", "/story/20260518nm010", 50000, 0.6),
        make_row("dup B", "/story/20260518nm010", 40000, 0.7),
        # one legitimate yt-source article that should pass
        make_row("yt one", "/story/20260518sot1729001", 30000, 0.5),
    ]
    posts = [
        make_post("20260518nm010", source="tv"),
        make_post("20260518sot1729001", source="yt"),
    ]
    result, stdout = run_with_threshold(0.3, rows, posts)

    slugs_kept = [a["slug"] for a in result["articles"]]
    assert slugs_kept == ["20260518nm010", "20260518sot1729001"], slugs_kept
    yt_slugs = [a["slug"] for a in result["yt"]]
    assert yt_slugs == ["20260518sot1729001"], yt_slugs
    assert "mm-" not in stdout  # mm- exclusion happens BEFORE engagement check, no log
    print("PASS test_existing_filters_preserved")


def test_threshold_zero_disables_filter():
    rows = [
        make_row("low engagement", "/story/20220208sot12021", 250046, 0.016),
    ]
    posts = [make_post("20220208sot12021")]
    result, stdout = run_with_threshold(0.0, rows, posts)

    slugs_kept = {a["slug"] for a in result["articles"]}
    assert slugs_kept == {"20220208sot12021"}, slugs_kept
    assert "[bot-filtered]" not in stdout
    print("PASS test_threshold_zero_disables_filter")


def test_heroimage_format():
    rows = [
        make_row("with image", "/story/abc001", 1000, 0.5),
    ]
    posts = [make_post("abc001")]
    result, _ = run_with_threshold(0.3, rows, posts)

    image = result["articles"][0]["heroImage"]
    assert image == {"w480": "x.jpg", "w800": "y.jpg"}, image
    print("PASS test_heroimage_format")


if __name__ == "__main__":
    test_filters_low_engagement()
    test_existing_filters_preserved()
    test_threshold_zero_disables_filter()
    test_heroimage_format()
    print("\nAll tests passed.")
