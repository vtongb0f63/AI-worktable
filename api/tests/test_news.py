import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from app.planner import news
from app.planner.news_sources import listing_entries


def test_world_athletics_public_cards():
    articles = [
        {'title': 'Runner wins', 'urlSlug': 'runner-wins', 'liveFrom': '2026-10-21T12:00:00Z',
         'standFirst': 'A cross country victory.', 'body': 'Do not import full article.'},
        {'title': 'Private story', 'urlSlug': 'private', 'gatedContent': True},
    ]
    raw = ('<a href="/competitions/diamond-league/news/runner-wins">Read</a><script id="__NEXT_DATA__" type="application/json">'
           + json.dumps({'props': {'pageProps': {'carouselArticles': articles, 'articles': []}}}) + '</script>')
    entries = listing_entries(raw.encode(), 'worldathletics', 'https://worldathletics.org/news')
    assert len(entries) == 1
    assert entries[0]['link'] == 'https://worldathletics.org/competitions/diamond-league/news/runner-wins'
    assert entries[0]['summary'] == 'A cross country victory.'
    assert entries[0]['timestamp'].tzinfo == timezone.utc


def test_flotrack_state_uses_published_date_and_preview_only():
    article = {'title': "Runner's race", 'slug_uri': '/articles/123-runner', 'publish_start_date': '2026-10-20T18:00:00Z',
               'modified_at': '2026-10-21T18:00:00Z', 'seo_description': 'A marathon preview.',
               'aggregated_category_slugs': ['road', 'professional'], 'body': 'Paid body'}
    raw = json.dumps({'G.https://api.flotrack.org/api/experiences/web/legacy-core/articles?limit=10': {'body': {'data': [article]}}})
    for char, escaped in [('&', '&a;'), ('"', '&q;'), ("'", '&s;'), ('<', '&l;'), ('>', '&g;')]:
        raw = raw.replace(char, escaped)
    entries = listing_entries(('<script id="flo-app-state">' + raw + '</script>').encode(), 'flotrack', 'https://www.flotrack.org/articles')
    assert entries[0]['title'] == "Runner's race"
    assert entries[0]['published'] == article['publish_start_date']
    assert entries[0]['summary'] == 'A marathon preview.'
    assert entries[0]['topics'] == 'road professional'


def test_xai_official_dated_cards_and_external_links():
    raw = b'''<a href="/news/grok-test"><time datetime="2026-10-20">Oct 20</time>
    <h3>Grok <span>update</span></h3><p>Public preview only.</p></a>
    <a href="https://evil.example/news/test"><time datetime="2026-10-20"></time><h3>Ignore</h3></a>
    <a href="/news/undated"><h3>No date</h3></a>'''
    entries = listing_entries(raw, 'xai', 'https://x.ai/news')
    assert len(entries) == 1
    assert entries[0]['title'] == 'Grok update'
    assert entries[0]['link'] == 'https://x.ai/news/grok-test'
    assert entries[0]['summary'] == 'Public preview only.'


def test_xai_feature_and_archive_plain_dates():
    raw = b'''<a href="/news/voice"><p>Oct 14, 2026</p><h1>Voice update</h1><p>Voice preview.</p></a>
    <a href="/news/model"><h3>Model update</h3><p>Model preview.</p><div>Sep 21, 2026</div></a>'''
    entries = listing_entries(raw, 'xai', 'https://x.ai/news')
    assert [(e['title'], e['published'], e['summary']) for e in entries] == [
        ('Voice update', '2026-10-14', 'Voice preview.'), ('Model update', '2026-09-21', 'Model preview.')]


def test_date_only_listing_overlaps_freshness_window(monkeypatch):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=47)).date().isoformat()
    old = (now - timedelta(days=5)).date().isoformat()
    raw = f'<a href="/news/grok"><time datetime="{recent}"></time><h3>Grok update</h3></a><a href="/news/old"><time datetime="{old}"></time><h3>Old release</h3></a>'
    monkeypatch.setattr(news, 'SOURCES', [news.Source('ai', 'xAI 官方', 'https://x.ai/news', 'xai', False)])
    original = httpx.Client
    monkeypatch.setattr(news.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=raw)), **kw))
    items, errors = news.collect('2026-10-22')
    assert len(items) == 1 and items[0]['published_at'] == recent
    assert errors == []


@pytest.mark.parametrize('kind', ['xai', 'worldathletics', 'flotrack'])
def test_changed_listing_is_reported(kind):
    with pytest.raises((ValueError, KeyError)):
        listing_entries(b'<html>Unexpected layout</html>', kind, 'https://example.com/news')


def test_source_diversity_bounded_newest_and_deduplicated():
    candidates = []
    for publisher in range(7):
        for hour in range(12):
            candidates.append({'source': str(publisher), 'category': 'ai', 'published_at': f'2026-10-21T{hour:02}:00:00+00:00',
                               'title': f'News {publisher}-{hour}', 'url': f'https://example.com/{publisher}/{hour}'})
    candidates.append({**candidates[-1], 'source': 'duplicate', 'title': 'News 6 11!'})
    selected = news.diverse_selection(candidates)
    assert len(selected) == 8
    assert {c['source'] for c in selected} == set(map(str, range(7)))
    assert all(c['published_at'].startswith('2026-10-21T11:') for c in selected[:7])
    assert len({c['url'] for c in selected}) == 8


def test_collect_freshness_topics_and_source_failure(monkeypatch):
    now = datetime.now(timezone.utc)
    def item(title, age, link='https://example.com/story', description=''):
        when = '<pubDate>' + format_datetime(now - timedelta(hours=age)) + '</pubDate>' if age is not None else ''
        return f'<item><title>{title}</title><link>{link}</link>{when}<description>{description}</description></item>'
    rss = '<rss version="2.0"><channel><title>Test</title>'
    rss += item('他说AI会改变工作', 1) + item('Retail earnings', 1, 'https://example.com/retail')
    rss += item('New model', 60) + item('AI tomorrow', -2) + item('AI no date', None)
    rss += item('AI unsafe', 1, 'javascript:alert(1)') + '</channel></rss>'
    sources = [news.Source('ai', 'test', 'https://example.com/feed'), news.Source('ai', 'failed', 'https://failed.example/feed')]
    monkeypatch.setattr(news, 'SOURCES', sources)
    original = httpx.Client
    def respond(request):
        return httpx.Response(503) if request.url.host == 'failed.example' else httpx.Response(200, text=rss)
    monkeypatch.setattr(news.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    items, errors = news.collect('2026-10-22')
    assert [i['title'] for i in items] == ['他说AI会改变工作']
    assert items[0]['date'] == '2026-10-22'
    assert errors == ['failed 暂时无法获取']


def test_running_filter_uses_excerpt_for_athlete_headlines(monkeypatch):
    now = format_datetime(datetime.now(timezone.utc))
    rss = f'<rss version="2.0"><channel><item><title>Jane wins in London</title><link>https://example.com/jane</link><pubDate>{now}</pubDate><description>A 1500m breakthrough.</description></item><item><title>Sprinter wins 100m</title><link>https://example.com/sprint</link><pubDate>{now}</pubDate></item></channel></rss>'
    monkeypatch.setattr(news, 'SOURCES', [news.Source('running', 'track', 'https://example.com/feed')])
    original = httpx.Client
    monkeypatch.setattr(news.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=rss)), **kw))
    items, errors = news.collect('2026-10-22')
    assert len(items) == 1 and items[0]['title'] == 'Jane wins in London'
    assert errors == []


def test_fetch_rejects_redirects_and_oversize():
    visited = []
    def redirect(request):
        visited.append(str(request.url))
        return httpx.Response(302, headers={'Location': 'http://127.0.0.1/private'})
    with httpx.Client(transport=httpx.MockTransport(redirect), follow_redirects=False) as client:
        with pytest.raises(httpx.HTTPStatusError):
            news.read_entries(client, news.SOURCES[0])
    assert visited == [news.SOURCES[0].url]
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b'x' * 2_000_001))) as client:
        with pytest.raises(ValueError, match='too large'):
            news.read_entries(client, news.SOURCES[0])
