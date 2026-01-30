import os
import requests
from datetime import datetime, timedelta
from notion_client import Client
import pytz

# ============================================
# CONFIGURATION - Edit these values
# ============================================

CONFIG = {
    'notion_token': os.environ.get('NOTION_TOKEN'), 
    'database_id': 'a60bb86bcf5544dca9e3df6c0640ea48',
    'parent_page_id': '2f79f7560dbc802a846dc2f52fd4a26a',  # Extract from home page
    'timezone': 'America/Guatemala',
    'sources': ['LEGO News', 'Data Science', 'Tech'],
    'max_articles_per_source': 10,
    'hours_lookback': 24,
    'skip_empty_sources': True,
    'create_if_no_articles': False,
}

# ============================================
# Initialize Client
# ============================================

notion = Client(auth=CONFIG['notion_token'])

print(f"Token present: {bool(CONFIG['notion_token'])}")
print(f"Token starts with 'ntn_': {CONFIG['notion_token'].startswith('ntn_') if CONFIG['notion_token'] else False}")

# ============================================
# Functions
# ============================================

def get_articles_from_last_24h():
    """Query database using REST API (since notion.databases.query doesn't exist)"""
    tz = pytz.timezone(CONFIG['timezone'])
    now = datetime.now(tz)
    lookback = now - timedelta(hours=CONFIG['hours_lookback'])

    # DEBUG - ADD THESE LINES
    print(f"DEBUG: Token exists: {bool(CONFIG['notion_token'])}")
    print(f"DEBUG: Token length: {len(CONFIG['notion_token']) if CONFIG['notion_token'] else 0}")
    print(f"DEBUG: Token starts with: {CONFIG['notion_token'][:10] if CONFIG['notion_token'] else 'None'}...")
    # END DEBUG
    
    # Use REST API for querying (notion-client doesn't have .query method)
    headers = {
        "Authorization": f"Bearer {CONFIG['notion_token']}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    payload = {
        "filter": {
            "and": [
                {
                    "property": "Scraped Date",
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
        "sorts": [{"property": "Source", "direction": "ascending"}]
    }
    
    response = requests.post(
        f"https://api.notion.com/v1/databases/{CONFIG['database_id']}/query",
        headers=headers,
        json=payload
    )
    
    if response.status_code != 200:
        print(f"❌ Error querying database: {response.status_code}")
        print(response.json())
        return []
    
    return response.json().get('results', [])

def group_articles_by_source(articles):
    """Group articles by source"""
    by_source = {}
    
    for article in articles:
        props = article['properties']
        
        # Extract source
        source_prop = props.get('Source', {})
        if 'select' in source_prop and source_prop['select']:
            source = source_prop['select'].get('name', 'Unknown')
        else:
            continue
        
        if source not in CONFIG['sources']:
            continue
            
        if source not in by_source:
            by_source[source] = []
        
        # Extract title
        title_prop = props.get('Title', {}).get('title', [])
        title = title_prop[0].get('plain_text', 'Untitled') if title_prop else 'Untitled'
        
        # Extract URL
        url = props.get('URL', {}).get('url', '')
        
        # Extract summary
        summary_prop = props.get('Summary', {}).get('rich_text', [])
        summary = summary_prop[0].get('plain_text', '') if summary_prop else ''
        
        by_source[source].append({
            'title': title,
            'url': url,
            'summary': summary,
        })
    
    return by_source

def create_digest_page(by_source):
    """Create digest page using notion.pages.create (same as your scraper)"""
    tz = pytz.timezone(CONFIG['timezone'])
    today = datetime.now(tz).strftime('%B %d, %Y')
    
    # Build content as rich text blocks
    content_blocks = []
    
    # Add statistics
    total = sum(len(articles) for articles in by_source.values())
    stats_text = f"Total Articles: {total}\n\n"
    for src, arts in by_source.items():
        emoji = {"LEGO News": "🧱", "Data Science": "📊", "Tech": "💻"}.get(src, "📰")
        stats_text += f"{emoji} {src}: {len(arts)} articles\n"
    
    content_blocks.append(stats_text + "\n" + "―" * 50 + "\n\n")
    
    # Add articles by source
    for source, articles in by_source.items():
        if CONFIG['skip_empty_sources'] and len(articles) == 0:
            continue
        
        emoji = {"LEGO News": "🧱", "Data Science": "📊", "Tech": "💻"}.get(source, "📰")
        content_blocks.append(f"\n## {emoji} {source}\n\n")
        
        for article in articles[:CONFIG['max_articles_per_source']]:
            content_blocks.append(f"• [{article['title']}]({article['url']})\n")
            if article['summary']:
                content_blocks.append(f"  _{article['summary'][:200]}..._\n")
            content_blocks.append("\n")
    
    full_content = "".join(content_blocks)
    
    # Create page using notion.pages.create (same pattern as your scraper)
    page = notion.pages.create(
        parent={"page_id": CONFIG['parent_page_id']},
        icon={"emoji": "📰"},
        properties={
            "title": {"title": [{"text": {"content": f"📰 Daily News - {today}"}}]}
        },
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": full_content}}]
                }
            }
        ]
    )
    
    return page.get('url', 'Created successfully')

def main():
    print("🚀 Starting News Digest Bot...")
    print(f"Timezone: {CONFIG['timezone']}")
    print(f"Lookback: {CONFIG['hours_lookback']} hours\n")
    
    print("Fetching articles from NEWS_DB...")
    articles = get_articles_from_last_24h()
    print(f"✅ Found {len(articles)} total articles\n")
    
    if len(articles) == 0:
        print("⚠️  No new articles found. Skipping digest creation.")
        return
    
    print("Grouping by source...")
    by_source = group_articles_by_source(articles)
    
    for source, arts in by_source.items():
        print(f"  - {source}: {len(arts)} articles")
    
    print("\nCreating digest page...")
    page_url = create_digest_page(by_source)
    
    print(f"\n✅ Daily digest created successfully!")
    print(f"📄 View at: {page_url}")

if __name__ == "__main__":
    main()
