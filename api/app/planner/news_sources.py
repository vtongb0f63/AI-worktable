"""Adapters for public news listings; never execute scripts or fetch article bodies."""
import json
import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class Listing(HTMLParser):
    def __init__(self, raw):
        super().__init__()
        self.scripts, self.links, self.cards = {}, [], []
        self.script_id = self.card = self.field = None
        self.feed(raw)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self.script_id = attrs.get('id')
            if self.script_id:
                self.scripts[self.script_id] = ''
        elif tag == 'a':
            href = attrs.get('href', '')
            self.links.append(href)
            self.card = {'link': href, 'title': '', 'summary': '', 'published': ''}
        elif self.card is not None:
            if tag == 'time':
                self.card['published'] = attrs.get('datetime', '')
            elif tag in ('h1', 'h2', 'h3', 'h4'):
                self.field = 'title'
            elif tag == 'p':
                self.field = 'summary'

    def handle_data(self, data):
        if self.script_id:
            self.scripts[self.script_id] += data
        elif self.card is not None:
            text = data.strip()
            if re.fullmatch(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}, \d{4}', text):
                self.card['published'] = self.card['published'] or datetime.strptime(text, '%b %d, %Y').date().isoformat()
            elif self.field:
                self.card[self.field] += data

    def handle_endtag(self, tag):
        if tag == 'script':
            self.script_id = None
        elif tag == 'a':
            if self.card:
                self.cards.append(self.card)
            self.card = self.field = None
        elif tag in ('h1', 'h2', 'h3', 'h4', 'p'):
            self.field = None


def iso_date(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def public_link(base, href, prefix):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != urlparse(base).netloc or not parsed.path.startswith(prefix):
        return ''
    return url


def listing_entries(raw, kind, base):
    page = Listing(raw.decode('utf-8'))
    entries = []
    if kind == 'worldathletics':
        props = json.loads(page.scripts['__NEXT_DATA__'])['props']['pageProps']
        links = {urlparse(href).path.rsplit('/', 1)[-1]: public_link(base, href, '/') for href in page.links if '/news/' in href}
        for article in props['carouselArticles'] + props['articles']:
            if article.get('gatedContent'):
                continue
            entries.append({'title': article.get('title', ''), 'link': links.get(article.get('urlSlug'), ''),
                            'published': article.get('liveFrom'),
                            'summary': article.get('standFirst') or article.get('seoDescription') or '',
                            'topics': article.get('urlSlug', '')})
    elif kind == 'flotrack':
        # Angular TransferState escaping, decoded once; this is JSON, not JavaScript.
        state = page.scripts['flo-app-state']
        state = state.replace('&q;', '"').replace('&s;', "'").replace('&l;', '<').replace('&g;', '>').replace('&a;', '&')
        data = json.loads(state)
        response = next(value for key, value in data.items() if '/legacy-core/articles?' in key)
        for article in response['body']['data']:
            entries.append({'title': article.get('title', ''),
                            'link': public_link(base, article.get('slug_uri', ''), '/articles/'),
                            'published': article.get('publish_start_date'),
                            'summary': article.get('seo_description') or article.get('preview_text') or '',
                            'topics': ' '.join(article.get('aggregated_category_slugs', []))})
    elif kind == 'xai':
        for card in page.cards:
            link = public_link(base, card['link'], '/news/')
            if link and card['title'] and card['published']:
                entries.append({**card, 'link': link})
    else:
        raise ValueError('Unknown listing adapter')
    entries = [entry for entry in entries if entry.get('link')]
    if not entries:
        raise ValueError('Listing format changed')
    for entry in entries:
        entry['title'] = unescape(entry['title']).strip()
        try:
            entry['timestamp'] = iso_date(entry['published'])
        except (TypeError, ValueError):
            entry['timestamp'] = None
    return entries
