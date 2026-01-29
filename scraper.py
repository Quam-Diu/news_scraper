#!/usr/bin/env python3
"""
Automated News Scraper for Notion
"""

import os
import json
import requests
import feedparser
from datetime import datetime, timezone
from notion_client import Client
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import time

# Configuration
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not DATABASE_ID:
    raise ValueError("Missing NOTION_TOKEN or NOTION_DATABASE_ID")

# Initialize Notion client
notion = Client(auth=NOTION_TOKEN)

def load_sources():
    """Load RSS feed sources"""
    with open('sources.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['feeds']

def clean_html(html_text):
    """Remove HTML tags"""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    return text[:2000]

def parse_date(date_string):
    """Parse date to ISO format"""
    if not date_string:
        return None
    try:
        parsed = date_parser.parse(date_string)
        return parsed.isoformat()
    except:
        return None

def fetch_feed(feed_config):
    """Fetch RSS feed"""
    articles = []
    feed_url = feed_config['url']
    category = feed_config['category']
    source_name = feed_config['name']
    
    print(f"\n📡 Fetching: {source_name}")
    
    try:
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries[:10]:
            article = {
                'title': entry.get('title', 'Untitled')[:2000],
                'url': entry.get('link', ''),
                'category': category,
                'source': source_name,
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
    """Add article to Notion"""
    try:
        # Build properties
        properties = {
            "Title": {
                "title": [{"text": {"content": article['title']}}]
            },
            "URL": {
                "url": article['url']
            },
            "Source": {
                "select": {"name": article['category']}
            },
            "Scraped Date": {
                "date": {"start": datetime.now(timezone.utc).isoformat()}
            },
            "Status": {
                "select": {"name": "Unread"}
            }
        }
        
        # Add optional fields
        if article.get('published_date'):
            properties["Published Date"] = {
                "date": {"start": article['published_date']}
            }
        
        if article.get('summary'):
            properties["Summary"] = {
                "rich_text": [{"text": {"content": article['summary']}}]
            }
        
        # Create page - using parent with database_id
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
    """Main function"""
    print("=" * 70)
    print("🗞️  NOTION NEWS AGGREGATOR")
    print("=" * 70)
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load sources
    sources = load_sources()
    print(f"📚 Loaded {len(sources)} sources")
    
    # Fetch articles
    all_articles = []
    for source in sources:
        articles = fetch_feed(source)
        all_articles.extend(articles)
        time.sleep(1)
    
    print(f"\n📊 Total articles: {len(all_articles)}")
    print("\n💾 Adding to Notion...")
    
    # Add to Notion
    added = 0
    failed = 0
    
    for article in all_articles:
        if add_to_notion(article):
            added += 1
        else:
            failed += 1
        time.sleep(0.3)
    
    # Summary
    print("\n" + "=" * 70)
    print(f"✓ Added: {added}")
    print(f"✗ Failed: {failed}")
    print(f"⏰ Done: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
