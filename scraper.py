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

def clean_html(html_text):
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, 'html.parser')
    return soup.get_text(separator=' ', strip=True)[:2000]

def parse_date(date_string):
    if not date_string:
        return None
    try:
        return date_parser.parse(date_string).isoformat()
    except:
        return None

def fetch_feed(feed_config):
    articles = []
    print(f"📡 Fetching: {feed_config['name']}")
    
    try:
        feed = feedparser.parse(feed_config['url'])
        for entry in feed.entries[:10]:
            article = {
                'title': entry.get('title', 'Untitled')[:2000],
                'url': entry.get('link', ''),
                'category': feed_config['category'],
                'published_date': parse_date(entry.get('published', '')),
                'summary': clean_html(entry.get('summary', entry.get('description', '')))
            }
            if article['url']:
                articles.append(article)
        print(f"  ✓ Found {len(articles)} articles")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    return articles

def add_to_notion(article):
    try:
        properties = {
            "Title": {"title": [{"text": {"content": article['title']}}]},
            "URL": {"url": article['url']},
            "Source": {"select": {"name": article['category']}},
            "Scraped Date": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
            "Status": {"select": {"name": "Unread"}}
        }
        
        if article.get('published_date'):
            properties["Published Date"] = {"date": {"start": article['published_date']}}
        
        if article.get('summary'):
            properties["Summary"] = {"rich_text": [{"text": {"content": article['summary']}}]}
        
        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=properties
        )
        print(f"  ✓ Added: {article['title'][:50]}...")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    print("=" * 70)
    print("🗞️  NOTION NEWS AGGREGATOR")
    print("=" * 70)
    
    sources = load_sources()
    print(f"📚 Loaded {len(sources)} sources\n")
    
    all_articles = []
    for source in sources:
        articles = fetch_feed(source)
        all_articles.extend(articles)
        time.sleep(1)
    
    print(f"\n📊 Total: {len(all_articles)} articles")
    print("💾 Adding to Notion...\n")
    
    added = 0
    for article in all_articles:
        if add_to_notion(article):
            added += 1
        time.sleep(0.3)
    
    print(f"\n✓ Added {added} articles!")

if __name__ == "__main__":
    main()
