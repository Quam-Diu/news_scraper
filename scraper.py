#!/usr/bin/env python3
import os
import json
import feedparser
from datetime import datetime, timezone
from notion_client import Client
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import time

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

notion = Client(auth=NOTION_TOKEN)

def load_sources():
    with open('sources.json', 'r') as f:
        return json.load(f)['feeds']

def fetch_feed(feed_config):
    articles = []
    print(f"📡 {feed_config['name']}")
    
    try:
        feed = feedparser.parse(feed_config['url'])
        for entry in feed.entries[:10]:
            if entry.get('link'):
                articles.append({
                    'title': entry.get('title', 'Untitled')[:2000],
                    'url': entry.get('link'),
                    'category': feed_config['category'],
                    'summary': BeautifulSoup(entry.get('summary', ''), 'html.parser').get_text()[:2000] if entry.get('summary') else ''
                })
        print(f"  ✓ {len(articles)} articles")
    except Exception as e:
        print(f"  ✗ {e}")
    
    return articles

def add_to_notion(article):
    try:
        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties={
                "Title": {"title": [{"text": {"content": article['title']}}]},
                "URL": {"url": article['url']},
                "Source": {"select": {"name": article['category']}},
                "Status": {"select": {"name": "Unread"}},
                "Scraped Date": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
                "Summary": {"rich_text": [{"text": {"content": article['summary']}}]} if article['summary'] else {}
            }
        )
        print(f"  ✓ {article['title'][:40]}")
        return True
    except Exception as e:
        print(f"  ✗ {e}")
        return False

def main():
    print("🗞️ NEWS SCRAPER\n")
    sources = load_sources()
    
    all_articles = []
    for source in sources:
        all_articles.extend(fetch_feed(source))
        time.sleep(1)
    
    print(f"\n📊 Total: {len(all_articles)}\n")
    
    added = 0
    for article in all_articles:
        if add_to_notion(article):
            added += 1
        time.sleep(0.3)
    
    print(f"\n✓ Done! Added {added} articles")

if __name__ == "__main__":
    main()
