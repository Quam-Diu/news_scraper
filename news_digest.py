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
    'parent_page_id': '2f79f7560dbc802a846dc2f52fd4a26a',  # Extract from home page
    'timezone': 'America/Guatemala',
    'sources': ['LEGO News', 'Data Science', 'Tech'],
    'max_articles_per_source': 10,
    'hours_lookback': 24,
    'skip_empty_sources': True,
    'create_if_no_articles': False,
}

# ============================================
# Initialize Notion Client
# ============================================

notion = Client(auth=CONFIG['notion_token'])

# ============================================
# Functions
# ============================================

def get_articles_from_last_24h():
    """Query NEWS_DB for articles from last 24 hours"""
    tz = pytz.timezone(CONFIG['timezone'])
    now = datetime.now(tz)
    lookback = now - timedelta(hours=CONFIG['hours_lookback'])
    
    try:
        # Correct API call for notion-client
        response = notion.databases.query(
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
        return response.get('results', [])
    except AttributeError as e:
        print(f"API Error: {e}")
        print("Trying alternative API format...")
        # Fallback for older versions
        response = notion.query_database(
            CONFIG['database_id'],
            filter={
                "and": [
                    {
                        "property": "Date",
                        "date": {"after": lookback.isoformat()}
                    },
                    {
                        "property": "Source",
                        "select": {"is_not_empty": True}
                    }
                ]
            }
        )
        return response.get('results', [])

def create_summary_by_source(articles):
    """Group articles by source and create summaries"""
    by_source = {}
    
    for article in articles:
        props = article['properties']
        
        # Extract source
        source_prop = props.get('Source', {})
        if 'select' in source_prop and source_prop['select']:
            source = source_prop['select'].get('name', 'Unknown')
        else:
            source = 'Unknown'
        
        if source not in CONFIG['sources']:
            continue
            
        if source not in by_source:
            by_source[source] = []
        
        # Extract title
        title_prop = props.get('Title', {}).get('title', [])
        title = title_prop[0].get('plain_text', 'Untitled') if title_prop else 'Untitled'
        
        # Extract URL
        url = props.get('URL', {}).get('url', '')
        
        # Extract date
        date_prop = props.get('Date', {}).get('date', {})
        date = date_prop.get('start', '') if date_prop else ''
        
        by_source[source].append({
            'title': title,
            'url': url,
            'date': date,
        })
    
    return by_source

def create_digest_page(by_source):
    """Create the daily digest page in Notion"""
    tz = pytz.timezone(CONFIG['timezone'])
    today = datetime.now(tz).strftime('%B %d, %Y')
    
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
    total = sum(len(articles) for articles in by_source.values())
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"type": "text", "text": {"content": f"Total Articles: {total}  |  "}},
                {"type": "text", "text": {"content": "  |  ".join([f"{src}: {len(arts)}" for src, arts in by_source.items()])}}
            ]
        }
    })
    
    children.append({
        "object": "block",
        "type": "divider",
        "divider": {}
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
                        {
                            "type": "text",
                            "text": {
                                "content": article['title'],
                                "link": {"url": article['url']} if article['url'] else None
                            }
                        }
                    ]
                }
            })
    
    # Create page
    try:
        new_page = notion.pages.create(
            parent={"page_id": CONFIG['parent_page_id']},
            icon={"emoji": "📰"},
            properties={
                "title": {"title": [{"text": {"content": f"Daily News - {today}"}}]}
            },
            children=children
        )
        return new_page['url']
    except Exception as e:
        print(f"Error creating page: {e}")
        raise

def main():
    print("🚀 Starting News Digest Bot...")
    print(f"Timezone: {CONFIG['timezone']}")
    print(f"Lookback: {CONFIG['hours_lookback']} hours")
    print()
    
    print("Fetching articles from NEWS_DB...")
    articles = get_articles_from_last_24h()
    print(f"Found {len(articles)} total articles")
    
    if len(articles) == 0 and not CONFIG['create_if_no_articles']:
        print("⚠️  No new articles found. Skipping digest creation.")
        return
    
    print("\nGrouping by source...")
    by_source = create_summary_by_source(articles)
    
    for source, arts in by_source.items():
        print(f"  - {source}: {len(arts)} articles")
    
    print("\nCreating digest page...")
    page_url = create_digest_page(by_source)
    
    print(f"\n✅ Daily digest created successfully!")
    print(f"📄 View at: {page_url}")

if __name__ == "__main__":
    main()
