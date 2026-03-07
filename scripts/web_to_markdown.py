#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = ROOT / 'archives' / 'web'


class SimpleHTMLToMarkdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.href_stack: list[str] = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag = tag.lower()
        if tag == 'script':
            self.in_script = True
            return
        if tag == 'style':
            self.in_style = True
            return
        if self.in_script or self.in_style:
            return
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            level = int(tag[1])
            self.parts.append('\n' + ('#' * level) + ' ')
        elif tag == 'p':
            self.parts.append('\n\n')
        elif tag == 'br':
            self.parts.append('  \n')
        elif tag in ('ul', 'ol'):
            self.parts.append('\n')
        elif tag == 'li':
            self.parts.append('\n- ')
        elif tag == 'a':
            self.href_stack.append(attrs_dict.get('href', '').strip())
        elif tag in ('strong', 'b'):
            self.parts.append('**')
        elif tag in ('em', 'i'):
            self.parts.append('*')
        elif tag == 'code':
            self.parts.append('`')
        elif tag == 'pre':
            self.parts.append('\n```\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'script':
            self.in_script = False
            return
        if tag == 'style':
            self.in_style = False
            return
        if self.in_script or self.in_style:
            return
        if tag == 'a':
            href = self.href_stack.pop() if self.href_stack else ''
            if href:
                self.parts.append(f' ({href})')
        elif tag in ('strong', 'b'):
            self.parts.append('**')
        elif tag in ('em', 'i'):
            self.parts.append('*')
        elif tag == 'code':
            self.parts.append('`')
        elif tag == 'pre':
            self.parts.append('\n```\n')

    def handle_data(self, data):
        if self.in_script or self.in_style:
            return
        text = re.sub(r'\s+', ' ', data)
        if text.strip():
            self.parts.append(text)

    def get_markdown(self) -> str:
        raw = ''.join(self.parts)
        raw = re.sub(r'\n{3,}', '\n\n', raw)
        return raw.strip() + '\n'


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or 'utf-8'
        data = resp.read()
    return data.decode(charset, errors='replace')


def build_output_path(url: str) -> Path:
    parsed = urlparse(url)
    slug = parsed.netloc + parsed.path
    slug = re.sub(r'[^a-zA-Z0-9._/-]+', '-', slug).strip('-/') or 'page'
    slug = slug.replace('/', '__')[:120]
    digest = hashlib.sha1(url.encode('utf-8')).hexdigest()[:8]
    return ARCHIVE_DIR / f'{slug}-{digest}.md'


def main() -> int:
    parser = argparse.ArgumentParser(description='Fetch a webpage and convert basic content to Markdown')
    parser.add_argument('url')
    args = parser.parse_args()

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    html = fetch(args.url)
    conv = SimpleHTMLToMarkdown()
    conv.feed(html)
    body = conv.get_markdown()
    output = build_output_path(args.url)
    content = f'# Web Archive\n\n- Source: {args.url}\n\n{body}'
    output.write_text(content, encoding='utf-8')
    print(output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
