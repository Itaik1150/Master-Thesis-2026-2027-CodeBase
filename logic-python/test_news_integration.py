"""
Simple test to integrate news service with proactive system
"""

from services.news_service import NewsService

def test_news_integration():
    """
    Test how news service integrates with proactive research
    """
    print("=== 🧪 News Integration Test ===")
    
    # Initialize news service
    news_service = NewsService()
    
    # Fetch headlines
    print("📰 Fetching latest Israel headlines...")
    headlines = news_service.fetch_israel_headlines(max_results=5)
    
    # Extract just the titles for simple processing
    headline_titles = [h['title'] for h in headlines]
    
    print(f"\n📋 Headlines ready for processing:")
    for i, title in enumerate(headline_titles, 1):
        print(f"   {i}. {title}")
    
    # This is where we would later:
    # 1. Send headlines to LLM for processing
    # 2. Generate conversation prompts
    # 3. Inject prompts into user conversations
    
    print(f"\n🎯 Next steps (for future implementation):")
    print(f"   1. Send these headlines to LLM for analysis")
    print(f"   2. Generate conversation prompts based on news")
    print(f"   3. Inject prompts into proactive user conversations")
    
    return headline_titles

if __name__ == "__main__":
    headlines = test_news_integration()
    print(f"\n✅ Integration test complete!")
    print(f"📤 Ready to pass {len(headlines)} headlines to next stage")
