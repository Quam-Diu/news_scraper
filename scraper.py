import os
import json
import requests
import feedparser
from datetime import datetime
from notion_client import Client
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# Initialize Notion client
notion = Client(auth=os.environ["NOTION_TOKEN"])
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

def fetch_rss_feeds(sources):
    """Fetch articles from RSS feeds"""
    articles = []
    
    for source in sources.get("rss_feeds", []):
        print(f"Fetching RSS: {source['name']}")
        feed = feedparser.parse(source["url"])
        
        for entry in feed.entries[:5]:  # Limit to 5 most recent
            articles.append({
                "title": entry.get("title", "No Title"),
                "url": entry.get("link", ""),
                "source": source["name"],
                "category": source["category"],
                "published": entry.get("published", ""),
                "summary": entry.get("summary", "")[:500]  # Limit length
            })
    
    return articles

def scrape_websites(sources):
    """Scrape articles from websites"""
    articles = []
    
    for source in sources.get("web_scrape", []):
        print(f"Scraping: {source['name']}")
        try:
            response = requests.get(source["url"], timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Customize this based on your target sites
            items = soup.select(source["selector"])
            
            for item in items[:5]:
                title_tag = item.find(['h1', 'h2', 'h3', 'a'])
                link_tag = item.find('a')
                
                if title_tag and link_tag:
                    articles.append({
                        "title": title_tag.get_text(strip=True),
                        "url": link_tag.get('href', ''),
                        "source": source["name"],
                        "category": source["category"],
                        "published": "",
                        "summary": item.get_text(strip=True)[:500]
                    })
        except Exception as e:
            print(f"Error scraping {source['name']}: {e}")
    
    return articles

def check_if_exists(url):
    """Check if article already exists in Notion"""
    try:
        results = notion.databases.query(
            database_id=DATABASE_ID,
            filter={
                "property": "URL",
                "url": {"equals": url}
            }
        )
        return len(results.get("results", [])) > 0
    except:
        return False

def add_to_notion(article):
    """Add article to Notion database"""
    if check_if_exists(article["url"]):
        print(f"Skipping duplicate: {article['title']}")
        return
    
    try:
        # Parse published date
        published_date = None
        if article["published"]:
            try:
                parsed = date_parser.parse(article["published"])
                published_date = parsed.isoformat()
            except:
                pass
        
        # Create page properties
        properties = {
            "Title": {"title": [{"text": {"content": article["title"]}}]},
            "URL": {"url": article["url"]},
            "Source": {"select": {"name": article["category"]}},
            "Scraped Date": {"date": {"start": datetime.now().isoformat()}},
            "Read Status": {"select": {"name": "Unread"}}
        }
        
        if published_date:
            properties["Published Date"] = {"date": {"start": published_date}}
        
        if article["summary"]:
            properties["Summary"] = {
                "rich_text": [{"text": {"content": article["summary"]}}]
            }
        
        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=properties
        )
        print(f"Added: {article['title']}")
    except Exception as e:
        print(f"Error adding to Notion: {e}")

def main():
    # Load sources
    with open("sources.json", "r") as f:
        sources = json.load(f)
    
    # Fetch articles
    print("Starting scrape...")
    articles = []
    articles.extend(fetch_rss_feeds(sources))
    articles.extend(scrape_websites(sources))
    
    print(f"\nFound {len(articles)} articles")
    
    # Add to Notion
    for article in articles:
        add_to_notion(article)
    
    print("\nScraping complete!")

if __name__ == "__main__":
    main()
