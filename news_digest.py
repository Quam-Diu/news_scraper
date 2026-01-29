import os
import requests
from datetime import datetime, timedelta
from notion_client import Client
import pytz

# ============================================
# CONFIGURATION - Edit these values
# ============================================

CONFIG = {
    'notion_token': os.environ.get('DIGEST_TOKEN'), 
    'database_id': '5ad52157ba4d490aa5b8364a0fa56ca3',
    'parent_page_id': '2f79f7560dbc802a846dc2f52fd4a26a',  # Extract from https://www.notion.so/19f9f7560dbc80c9a359fad251d9eff5
    'timezone': 'America/Guatemala',
    'sources': ['LEGO News', 'Data Science', 'Tech'],
    'max_articles_per_source': 10,
    'summary_length': 'medium',
    'hours_lookback': 24,
    'skip_empty_sources': True,
    'create_if_no_articles': False,
    'fetch_full_content': True,
}

# ============================================
# Main Script
# ============================================

notion = Client(auth=CONFIG['notion_token'])

def get_articles_from_last_24h():
    """Query NEWS_DB for articles from last 24 hours"""
    tz = pytz.timezone(CONFIG['timezone'])
    now = datetime.now(tz)
    lookback = now - timedelta(hours=CONFIG['hours_lookback'])
    
    # Query Notion database
    results = notion.databases.query(
        database_id=CONFIG['database_id'],
        filter={
            "and": [
                {
                    "property": "Date",
                    "date": {
                        "after": lookback.isoformat()
                    }
                },
                {
                    "property": "Source",
                    "select": {
                        "is_not_empty": True
                    }
                }
            ]
        },
        sorts=[{"property": "Source", "direction": "ascending"}]
    )
    
    return results['results']

def fetch_article_content(url):
    """Fetch full article text from URL (optional)"""
    if not CONFIG['fetch_full_content']:
        return None
    
    try:
        response = requests.get(url, timeout=10)
        # Add your content extraction logic here
        # (BeautifulSoup, newspaper3k, etc.)
        return response.text[:1000]  # Placeholder
    except:
        return None

def create_summary_by_source(articles):
    """Group articles by source and create summaries"""
    by_source = {}
    
    for article in articles:
        props = article['properties']
        source = props.get('Source', {}).get('select', {}).get('name', 'Unknown')
        
        if source not in CONFIG['sources']:
            continue
            
        if source not in by_source:
            by_source[source] = []
        
        by_source[source].append({
            'title': props.get('Title', {}).get('title', [{}])[0].get('plain_text', 'Untitled'),
            'url': props.get('URL', {}).get('url', ''),
            'date': props.get('Date', {}).get('date', {}).get('start', ''),
        })
    
    return by_source

def create_digest_page(by_source):
    """Create the daily digest page in Notion"""
    today = datetime.now(pytz.timezone(CONFIG['timezone'])).strftime('%B %d, %Y')
    
    # Build page content
    children = [
        {
            "object": "block",
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"type": "text", "text": {"content": f"📰 Daily News Summary - {today}"}}]
            }
        },
        {
            "object": "block",
            "type": "divider",
            "divider": {}
        }
    ]
    
    # Add statistics
    if CONFIG.get('add_statistics', True):
        total = sum(len(articles) for articles in by_source.values())
        stats_text = f"**Total Articles:** {total}  |  "
        stats_text += "  |  ".join([f"**{src}:** {len(arts)}" for src, arts in by_source.items()])
        
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": stats_text}}]
            }
        })
    
    # Add content by source
    for source, articles in by_source.items():
        if CONFIG['skip_empty_sources'] and len(articles) == 0:
            continue
            
        # Source heading
        emoji = {"LEGO News": "🧱", "Data Science": "📊", "Tech": "💻"}.get(source, "📰")
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": f"{emoji} {source} ({len(articles)} articles)"}}]
            }
        })
        
        # Add articles
        for article in articles[:CONFIG['max_articles_per_source']]:
            children.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": article['title'], "link": {"url": article['url']}}}
                    ]
                }
            })
    
    # Create page
    notion.pages.create(
        parent={"page_id": CONFIG['parent_page_id']},
        icon={"emoji": "📰"},
        properties={
            "title": {"title": [{"text": {"content": f"Daily News - {today}"}}]}
        },
        children=children
    )

def main():
    print("Fetching articles from NEWS_DB...")
    articles = get_articles_from_last_24h()
    
    if len(articles) == 0 and not CONFIG['create_if_no_articles']:
        print("No new articles found. Skipping digest creation.")
        return
    
    print(f"Found {len(articles)} articles. Grouping by source...")
    by_source = create_summary_by_source(articles)
    
    print("Creating digest page...")
    create_digest_page(by_source)
    
    print("✅ Daily digest created successfully!")

if __name__ == "__main__":
    main()
