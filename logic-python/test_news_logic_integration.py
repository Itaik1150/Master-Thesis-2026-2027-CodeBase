"""
Integration Test: News Service + LLM Service
Tests the complete flow from news fetching to LLM analysis
"""

from services.news_service import NewsService
from services.llm_service import ProactiveLogic

def test_news_to_logic_integration():
    """
    Test the complete flow: News -> LLM Analysis -> Ready Messages
    """
    print("=== 🔄 News-to-Logic Integration Test ===")
    
    # Initialize services
    news_service = NewsService()
    logic = ProactiveLogic()
    
    # Step 1: Fetch news headlines
    print("📰 Step 1: Fetching headlines...")
    headlines = news_service.fetch_israel_headlines(max_results=5)
    headline_titles = [h['title'] for h in headlines]
    
    print(f"✅ Fetched {len(headline_titles)} headlines")
    
    # Step 2: Analyze each headline with LLM
    print("\n🧠 Step 2: Analyzing headlines with LLM...")
    proactive_messages = []
    
    for i, headline in enumerate(headline_titles, 1):
        print(f"\n{i}. Analyzing: {headline}")
        analysis = logic.analyze_headline(headline)
        
        if analysis["should_send"]:
            message = analysis["message"]
            proactive_messages.append({
                "original_headline": headline,
                "proactive_message": message
            })
            print(f"   ✅ Message: {message}")
        else:
            print(f"   ❌ Not suitable for proactive messaging")
    
    # Step 3: Summary and results
    print(f"\n📊 Integration Results:")
    print(f"   📰 Total headlines: {len(headline_titles)}")
    print(f"   📤 Proactive messages: {len(proactive_messages)}")
    print(f"   ❌ Rejected: {len(headline_titles) - len(proactive_messages)}")
    
    # Step 4: Show final messages ready for injection
    print(f"\n📋 Ready for injection into user conversations:")
    for i, msg in enumerate(proactive_messages, 1):
        print(f"   {i}. {msg['proactive_message']}")
        print(f"      (from: {msg['original_headline'][:50]}...)")
    
    # Step 5: Export format for next integration
    simple_messages = [msg['proactive_message'] for msg in proactive_messages]
    
    print(f"\n🎯 Next step ready:")
    print(f"   📤 Messages to inject: {simple_messages}")
    print(f"   🔗 Ready for database/FCM integration")
    
    return proactive_messages

def test_edge_cases():
    """
    Test edge cases for the proactive logic
    """
    print("\n=== 🧪 Edge Case Testing ===")
    
    logic = ProactiveLogic()
    
    edge_cases = [
        "Stock Market Crashes Amid Economic Uncertainty",  # Should not send
        "Local Cat Rescued from Tree",  # Should send (light, positive)
        "Political Scandal Rocks Government",  # Should not send (controversial)
        "New Pizza Place Opens in Neighborhood",  # Should send (friendly)
        "Traffic Accident Causes Major Delays",  # Should not send (negative)
    ]
    
    print("🧪 Testing edge cases...")
    
    for headline in edge_cases:
        analysis = logic.analyze_headline(headline)
        status = "✅ SEND" if analysis["should_send"] else "❌ SKIP"
        message = analysis["message"] if analysis["should_send"] else "NONE"
        print(f"   {status}: {headline}")
        print(f"      → {message}")

if __name__ == "__main__":
    # Main integration test
    messages = test_news_to_logic_integration()
    
    # Edge case testing
    test_edge_cases()
    
    print(f"\n🎉 Integration test complete!")
    print(f"📤 Ready to inject {len(messages)} proactive messages")
