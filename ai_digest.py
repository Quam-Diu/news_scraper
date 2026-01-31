import os
from notion_client import Client
from datetime import datetime, timedelta
import pytz
import requests
from bs4 import BeautifulSoup
import openai
from collections import Counter
import re

# ============================================
# CONFIGURATION
# ============================================

CONFIG = {
    'notion_token': os.environ.get('NOTION_TOKEN'),
    'openai_api_key': os.environ.get('OPENAI_API_KEY'),
    'database_id': 'a60bb86bcf5544dca9e3df6c0640ea48',
    'parent_page_id': 'YOUR_PARENT_PAGE_ID',
    'timezone': 'America/Guatemala',
    'sources': ['LEGO News', 'Data Science', 'Tech'],
    'max_articles_per_source': 10,
    'hours_lookback': 24,
    'skip_empty_sources': True,
    'ai_summary_enabled': True,
    'hot_topics_enabled': True,
    'hot_topic_threshold': 3,
}

# ============================================
# Initialize
# ============================================

notion = Client(auth=CONFIG['notion_token'])

print(f"Token present: {bool(CONFIG['notion_token'])}")
print(f"Token starts with 'ntn_': {CONFIG['notion_token'].startswith('ntn_') if CONFIG['notion_token'] else False}")

if CONFIG['ai_summary_enabled']:
    openai.api_key = CONFIG['openai_api_key']

# ============================================
# Functions
# ============================================

def get_articles_from_last_24h():
    """Query database using REST API"""
    tz = pytz.timezone(CONFIG['timezone'])
    now = datetime.now(tz)
    lookback = now - timedelta(hours=CONFIG['hours_lookback'])
    
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
                    "date": {"after": lookback.isoformat()}
                },
                {
                    "property": "Source",
                    "select": {"is_not_empty": True}
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
        print(f"❌ Error: {response.status_code}")
        print(response.json())
        return []
    
    return response.json().get('results', [])

def fetch_article_content(url):
    """Fetch article text from URL"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text[:3000]  # Limit for cost efficiency
    
    except Exception as e:
        print(f"⚠️  Failed to fetch {url}: {e}")
        return None

def generate_ai_summary(articles_by_source):
    """Generate natural, expert summaries per topic"""
    if not CONFIG['ai_summary_enabled']:
        return {}
    
    summaries = {}
    
    for source, articles in articles_by_source.items():
        print(f"  🤖 Generating AI summary for {source}...")
        
        # Prepare content
        articles_text = ""
        article_list = ""
        for i, article in enumerate(articles[:CONFIG['max_articles_per_source']], 1):
            content = article.get('content', '')
            if content:
                articles_text += f"\n\n--- Article {i}: {article['title']} ---\n{content[:1000]}"
            article_list += f"\n{i}. {article['title']}"
        
        if not articles_text:
            summaries[source] = "No article content available."
            continue
        
        try:
            # Custom expert prompts per source
            if source == "LEGO News":
                system_prompt = """You are an enthusiastic LEGO journalist writing for a LEGO magazine. 
Write a natural, engaging summary as if reporting the latest news to fellow LEGO fans. 
Mention specific set numbers, themes, or builders when relevant. 
Write in a storytelling style with personality. Keep under 1500 characters."""
            
            elif source == "Data Science":
                system_prompt = """You are a data science expert writing a briefing for colleagues. 
Explain the key insights and methodologies in a clear, natural way. 
Write as if discussing these articles over coffee with a peer. 
Be conversational yet informative. Keep under 1500 characters."""
            
            elif source == "Tech":
                system_prompt = """You are a tech industry analyst writing for tech professionals. 
Summarize trends and developments in a conversational yet insightful tone. 
Write as if explaining to an interested colleague. Keep under 1500 characters."""
            
            else:
                system_prompt = """You are an expert journalist. Write a natural summary as if reporting 
for a publication. Be engaging and informative. Keep under 1500 characters."""
            
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Summarize these {source} articles:\n{articles_text}\n\nArticle titles:{article_list}"}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            summaries[source] = response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"⚠️  OpenAI error: {e}")
            summaries[source] = "AI summary unavailable."
    
    return summaries

def detect_hot_topics(articles_by_source):
    """Detect trending keywords"""
    if not CONFIG['hot_topics_enabled']:
        return []
    
    print("🔥 Detecting hot topics...")
    
    all_text = []
    for articles in articles_by_source.values():
        for article in articles:
            all_text.append(article['title'].lower())
            if article.get('content'):
                all_text.append(article['content'][:500].lower())
    
    combined = ' '.join(all_text)
    words = re.findall(r'\b[A-Za-z]{4,}\b', combined)
    
    stopwords = {'this', 'that', 'with', 'from', 'have', 'been', 'will',
                 'their', 'what', 'about', 'which', 'when', 'make', 'than',
                 'other', 'into', 'could', 'would', 'should', 'these', 'those'}
    
    filtered = [w for w in words if w not in stopwords]
    counts = Counter(filtered)
    
    hot = [word for word, count in counts.most_common(10) 
           if count >= CONFIG['hot_topic_threshold']]
    
    return hot

def create_digest_page(by_source, ai_summaries, hot_topics):
    """Create beautiful digest page"""
    tz = pytz.timezone(CONFIG['timezone'])
    today = datetime.now(tz).strftime('%B %d, %Y')
    
    children = []
    
    # HOT TOPICS
    if hot_topics:
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"text": {"content": "🔥 Hot Topics Today"}}]
            }
        })
        
        topics_text = ", ".join([f"**{t.title()}**" for t in hot_topics[:5]])
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": topics_text}}]
            }
        })
        
        children.append({"object": "block", "type": "divider", "divider": {}})
    
    # STATS
    total = sum(len(arts) for arts in by_source.values())
    children.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"text": {"content": "📊 Overview"}}]
        }
    })
    
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"text": {"content": f"Total Articles: {total}"}}]
        }
    })
    
    for src, arts in by_source.items():
        emoji = {"LEGO News": "🧱", "Data Science": "📊", "Tech": "💻"}.get(src, "📰")
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": f"{emoji} {src}: {len(arts)} articles"}}]
            }
        })
    
    children.append({"object": "block", "type": "divider", "divider": {}})
    
    # AI SUMMARIES (natural paragraphs, no bullets!)
    for source, articles in by_source.items():
        if CONFIG['skip_empty_sources'] and len(articles) == 0:
            continue
        
        emoji = {"LEGO News": "🧱", "Data Science": "📊", "Tech": "💻"}.get(source, "📰")
        
        # Section heading
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"text": {"content": f"{emoji} {source}"}}]
            }
        })
        
        # AI summary as natural paragraphs
        if source in ai_summaries:
            summary = ai_summaries[source]
            paragraphs = [p.strip() for p in summary.split('\n\n') if p.strip()]
            
            for para in paragraphs:
                # Handle long paragraphs (split at sentences if > 1900 chars)
                if len(para) > 1900:
                    sentences = para.split('. ')
                    current = ""
                    for sent in sentences:
                        if len(current) + len(sent) + 2 < 1900:
                            current += sent + ". "
                        else:
                            if current:
                                children.append({
                                    "object": "block",
                                    "type": "paragraph",
                                    "paragraph": {
                                        "rich_text": [{"text": {"content": current.strip()}}]
                                    }
                                })
                            current = sent + ". "
                    if current:
                        children.append({
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"text": {"content": current.strip()}}]
                            }
                        })
                else:
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": para}}]
                        }
                    })
        
        # Article links (subtle, at bottom)
        if articles:
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "text": {
                            "content": "\n📎 Read the full articles:",
                            "annotations": {"italic": True}
                        }
                    }]
                }
            })
            
            for article in articles[:CONFIG['max_articles_per_source']]:
                children.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{
                            "text": {
                                "content": article['title'],
                                "link": {"url": article['url']}
                            }
                        }]
                    }
                })
        
        children.append({"object": "block", "type": "divider", "divider": {}})
    
    # Create page
    page = notion.pages.create(
        parent={"page_id": CONFIG['parent_page_id']},
        icon={"emoji": "🤖"},
        properties={
            "title": {"title": [{"text": {"content": f"🤖 AI News Digest - {today}"}}]}
        },
        children=children
    )
    
    return page.get('url', 'Created!')

def main():
    print("🚀 Starting AI News Digest Bot...")
    print(f"Timezone: {CONFIG['timezone']}")
    print(f"Lookback: {CONFIG['hours_lookback']} hours")
    print(f"AI: {'✅' if CONFIG['ai_summary_enabled'] else '❌'}")
    print(f"Hot Topics: {'✅' if CONFIG['hot_topics_enabled'] else '❌'}\n")
    
    articles = get_articles_from_last_24h()
    print(f"✅ Found {len(articles)} articles\n")
    
    if not articles:
        print("⚠️  No articles. Skipping.")
        return
    
    print("🗂️  Grouping by source...")
    by_source = {}
    
    for article in articles:
        props = article['properties']
        
        source_prop = props.get('Source', {})
        if 'select' in source_prop and source_prop['select']:
            source = source_prop['select'].get('name', 'Unknown')
        else:
            continue
        
        if source not in CONFIG['sources']:
            continue
        
        if source not in by_source:
            by_source[source] = []
        
        title_prop = props.get('Title', {}).get('title', [])
        title = title_prop[0].get('plain_text', 'Untitled') if title_prop else 'Untitled'
        url = props.get('URL', {}).get('url', '')
        
        # Fetch content for AI
        content = None
        if CONFIG['ai_summary_enabled'] and url:
            content = fetch_article_content(url)
        
        by_source[source].append({
            'title': title,
            'url': url,
            'content': content
        })
    
    for src, arts in by_source.items():
        print(f"  - {src}: {len(arts)}")
    
    # AI summaries
    ai_summaries = {}
    if CONFIG['ai_summary_enabled']:
        print("\n🤖 Generating AI summaries...")
        ai_summaries = generate_ai_summary(by_source)
    
    # Hot topics
    hot_topics = []
    if CONFIG['hot_topics_enabled']:
        hot_topics = detect_hot_topics(by_source)
        if hot_topics:
            print(f"🔥 Hot: {', '.join(hot_topics[:5])}")
    
    print("\n📝 Creating digest...")
    url = create_digest_page(by_source, ai_summaries, hot_topics)
    print(f"\n✅ Done! {url}")

if __name__ == "__main__":
    main()
