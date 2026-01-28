#!/usr/bin/env python3
"""
Automated News Scraper for Notion
Fetches articles from RSS feeds and websites, stores in Notion database
"""

import requests
import feedparser
from datetime import datetime, timezone
from notion_client import Client
from bs4 import BeautifulSoup
from dateutil import parser
import json
import config

# Initialize Notion
notion = Client(auth=config.NOTION_TOKEN)

class NotionNewsAggregator:
    def __init__(self):
        self.notion = notion
        self.db_id = config.DATABASE_ID
        self.articles_added = 0
        self.articles_skipped = 0
    
    def load_sources(self):
        """Load sources from JSON file"""
        with open('sources.json', 'r') as f:
            return json.load(f)
    
    def article_exists(self, url):
        """Check if article URL already exists in database"""
        try:
            response = self.notion.databases.query(
                database_id=self.db_id,
                filter={
                    "property": "URL",
                    "url": {"equals": url}
                }
            )
            return len(response["results"]) > 0
        except Exception as e:
            print(f"Error checking existence: {e}")
            return False
    
    def parse_rss_feed(self, feed_url, category):
        """Parse RSS feed and extract articles"""
        articles = []
        try:
            print(f"Fetching RSS: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:config.MAX_ARTICLES_PER_SOURCE]:
                # Parse date
                pub_date = None
                if hasattr(entry, 'published'):
                    try:
                        pub_date = parser.parse(entry.published)
                    except:
                        pass
                
                articles.append({
                    'title': entry.get('title', 'No Title')[:2000],
                    'url': entry.get('link', ''),
                    'category': category,
                    'published_date': pub_date,
                    'summary': BeautifulSoup(
                        entry.get('summary', ''), 'html.parser'
                    ).get_text()[:2000]
                })
        
        except Exception as e:
            print(f"Error parsing {feed_url}: {e}")
        
        return articles
    
    def create_notion_page(self, article):
        """Create a new page in Notion database"""
        if self.article_exists(article['url']):
            self.articles_skipped += 1
            return
        
        try:
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
                "Read Status": {
                    "select": {"name": "Unread"}
                }
            }
            
            # Add published date if available
            if article.get('published_date'):
                properties["Published Date"] = {
                    "date": {"start": article['published_date'].isoformat()}
                }
            
            # Add summary if available
            if article.get('summary'):
                properties["Summary"] = {
                    "rich_text": [{"text": {"content": article['summary']}}]
                }
            
            self.notion.pages.create(
                parent={"database_id": self.db_id},
                properties=properties
            )
            
            self.articles_added += 1
            print(f"✓ Added: {article['title'][:60]}...")
        
        except Exception as e:
            print(f"✗ Error adding article: {e}")
    
    def run(self):
        """Main execution function"""
        print("=" * 60)
        print("Starting News Aggregation")
        print("=" * 60)
        
        sources = self.load_sources()
        all_articles = []
        
        # Process each category
        for category, feed_urls in sources.items():
            print(f"\n📰 Processing category: {category}")
            for feed_url in feed_urls:
                articles = self.parse_rss_feed(feed_url, category)
                all_articles.extend(articles)
        
        print(f"\n📊 Found {len(all_articles)} total articles")
        print("Adding to Notion...")
        
        # Add to Notion
        for article in all_articles:
            self.create_notion_page(article)
        
        # Summary
        print("\n" + "=" * 60)
        print(f"✓ Articles added: {self.articles_added}")
        print(f"⊘ Articles skipped (duplicates): {self.articles_skipped}")
        print("=" * 60)

if __name__ == "__main__":
    aggregator = NotionNewsAggregator()
    aggregator.run()
