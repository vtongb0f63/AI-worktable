"""Bounded RSS ingestion. Only configured public feeds are fetched, never user URLs."""
import calendar
import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import feedparser
import httpx

# Editors can change this allowlist in source control. User input cannot add fetch targets.
SOURCES = [
    ('domestic', '中国新闻网', 'https://www.chinanews.com.cn/rss/scroll-news.xml'),
    ('international', 'BBC World', 'https://feeds.bbci.co.uk/news/world/rss.xml'),
    ('ai', 'OpenAI', 'https://openai.com/news/rss.xml'),
    ('ai', 'Google Research', 'https://research.google/blog/rss/'),
    ('running', 'World Athletics', 'https://worldathletics.org/rss/news'),
    ('running', 'Athletics Weekly', 'https://athleticsweekly.com/feed/'),
]
RUNNING_TERMS = re.compile(r'run|800m|1500m|mile|3000m|5000m|10,?000m|marathon|cross.country|steeplechase|distance', re.I)
AI_TERMS = re.compile(r'model|AI|GPT|Gemini|intelligence|learning|reason|LLM', re.I)


def collect(day):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    candidates, errors, seen = [], [], set()
    with httpx.Client(timeout=18, follow_redirects=False, headers={'User-Agent': 'PersonalStudyReader/1.0'}) as client:
        for category, name, url in SOURCES:
            try:
                with client.stream('GET', url) as response:
                    response.raise_for_status()
                    raw = b''
                    for block in response.iter_bytes():
                        raw += block
                        if len(raw) > 2_000_000:
                            raise ValueError('feed too large')
                entries = feedparser.parse(raw).entries
                if not entries:
                    raise ValueError('empty feed')
                for entry in entries[:40]:
                    published = entry.get('published_parsed') or entry.get('updated_parsed')
                    if not published:
                        continue
                    timestamp = datetime.fromtimestamp(calendar.timegm(published), timezone.utc)
                    if timestamp < cutoff or timestamp > datetime.now(timezone.utc) + timedelta(minutes=10):
                        continue
                    link, title = entry.get('link', ''), entry.get('title', '')[:250]
                    if urlparse(link).scheme not in ('https', 'http') or not title:
                        continue
                    if category == 'running' and not RUNNING_TERMS.search(title):
                        continue
                    if category == 'ai' and not AI_TERMS.search(title):
                        continue
                    normalized = re.sub(r'\W+', '', title.casefold())
                    if normalized in seen:
                        continue
                    seen.add(normalized)
                    summary = re.sub(r'<[^>]+>', ' ', entry.get('summary', ''))
                    candidates.append({'source_id': hashlib.sha256(link.encode()).hexdigest()[:20], 'title': title, 'url': link, 'source': name, 'published_at': timestamp.isoformat(), 'category': category, 'excerpt': summary[:1800], 'date': day})
            except Exception:
                errors.append(name + ' 暂时无法获取')
    # A bounded candidate set keeps memory and inference consumption predictable.
    return sum(([c for c in candidates if c['category'] == category][:8] for category in ('domestic', 'international', 'ai', 'running')), []), errors
