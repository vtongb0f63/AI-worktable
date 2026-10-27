"""Bounded public news ingestion from a source-controlled allowlist."""
import calendar
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import urlparse
import feedparser
import httpx
from .news_sources import listing_entries


@dataclass(frozen=True)
class Source:
    category: str
    name: str
    url: str
    kind: str = 'rss'
    topic_filter: bool = True


# User input cannot add fetch targets. Listings never trigger additional requests.
SOURCES = [
    Source('domestic', '中国新闻网', 'https://www.chinanews.com.cn/rss/scroll-news.xml'),
    Source('international', 'BBC World', 'https://feeds.bbci.co.uk/news/world/rss.xml'),
    Source('ai', 'OpenAI', 'https://openai.com/news/rss.xml', topic_filter=False),
    Source('ai', 'Google Research', 'https://research.google/blog/rss/'),
    Source('ai', 'TechCrunch AI', 'https://techcrunch.com/category/artificial-intelligence/feed/'),
    Source('ai', 'The Verge AI', 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml', topic_filter=False),
    Source('ai', 'xAI 官方', 'https://x.ai/news', 'xai', topic_filter=False),
    Source('ai', '量子位', 'https://www.qbitai.com/feed'),
    Source('ai', 'DEV.to（AI 社区）', 'https://dev.to/feed/tag/ai', topic_filter=False),
    Source('running', 'World Athletics', 'https://worldathletics.org/news', 'worldathletics'),
    Source('running', 'Athletics Weekly', 'https://athleticsweekly.com/feed/'),
    Source('running', 'LetsRun.com', 'https://www.letsrun.com/feed/'),
    Source('running', 'FloTrack', 'https://www.flotrack.org/articles', 'flotrack'),
]
RUNNING_TERMS = re.compile(r'\b(?:running|runner[s]?|800\s?m|1500\s?m|3000\s?m|5000\s?m|10,?000\s?m|[135]0?k|mile[s]?|marathon|cross.country|xc|steeplechase|distance|diamond.league)\b|中长跑|马拉松|越野跑', re.I)
AI_TERMS = re.compile(r'(?<![a-z0-9])(?:AI|AGI|GPT\w*|Gemini|Grok|Claude|LLM[s]?|DeepSeek|OpenAI|Anthropic|Minimax|artificial intelligence|machine learning|neural|agent[s]?)(?![a-z0-9])|人工智能|模型|智能体|推理|智驾|机器人|豆包|千问', re.I)
CATEGORIES = ('domestic', 'international', 'ai', 'running')


def clean(value):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()


def read_entries(client, source):
    with client.stream('GET', source.url) as response:
        response.raise_for_status()
        raw = bytearray()
        for block in response.iter_bytes():
            raw.extend(block)
            if len(raw) > 2_000_000:
                raise ValueError('feed too large')
    if source.kind != 'rss':
        return listing_entries(bytes(raw), source.kind, source.url)
    entries = feedparser.parse(bytes(raw)).entries
    if not entries:
        raise ValueError('empty feed')
    for entry in entries[:40]:
        published = entry.get('published_parsed') or entry.get('updated_parsed')
        entry['timestamp'] = datetime.fromtimestamp(calendar.timegm(published), timezone.utc) if published else None
        entry['topics'] = ' '.join(tag.get('term', '') for tag in entry.get('tags', []))
    return entries[:40]


def diverse_selection(candidates):
    """Round-robin across publishers, newest first within each, max eight/category."""
    selected, seen_titles, seen_urls = [], set(), set()
    for category in CATEGORIES:
        groups = {}
        for item in sorted(candidates, key=lambda c: c['published_at'], reverse=True):
            if item['category'] == category:
                groups.setdefault(item['source'], []).append(item)
        count = 0
        while groups and count < 8:
            for name in list(groups):
                rows = groups[name]
                while rows:
                    item = rows.pop(0)
                    normalized = re.sub(r'\W+', '', item['title'].casefold())
                    if normalized in seen_titles or item['url'] in seen_urls:
                        continue
                    seen_titles.add(normalized)
                    seen_urls.add(item['url'])
                    selected.append(item)
                    count += 1
                    break
                if not rows:
                    del groups[name]
                if count == 8:
                    break
    return selected


def collect(day):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=48)
    candidates, errors = [], []
    with httpx.Client(timeout=18, follow_redirects=False, headers={'User-Agent': 'PersonalStudyReader/1.0'}) as client:
        for source in SOURCES:
            try:
                entries = read_entries(client, source)
                for entry in entries[:40]:
                    try:
                        timestamp = entry.get('timestamp')
                        # Date-only listings overlap the window for their entire UTC day.
                        # Preserve that precision for display rather than inventing a time.
                        date_only = bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', entry.get('published') or ''))
                        oldest = timestamp + timedelta(days=1) if timestamp and date_only else timestamp
                        if not timestamp or oldest < cutoff or timestamp > now + timedelta(minutes=10):
                            continue
                        link, title = entry.get('link', ''), clean(entry.get('title', ''))[:250]
                        parsed = urlparse(link)
                        if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or not title:
                            continue
                        summary = clean(entry.get('summary', ''))[:1800]
                        searchable = title + ' ' + summary + ' ' + entry.get('topics', '')
                        pattern = RUNNING_TERMS if source.category == 'running' else AI_TERMS if source.category == 'ai' else None
                        if source.topic_filter and pattern and not pattern.search(searchable):
                            continue
                        candidates.append({'source_id': hashlib.sha256(link.encode()).hexdigest()[:20], 'title': title, 'url': link, 'source': source.name, 'published_at': entry['published'] if date_only else timestamp.astimezone(timezone.utc).isoformat(), 'category': source.category, 'excerpt': summary, 'date': day})
                    except (TypeError, ValueError, OverflowError):
                        continue  # One malformed item must not discard the publisher.
            except Exception:
                errors.append(source.name + ' 暂时无法获取')
    return diverse_selection(candidates), errors
