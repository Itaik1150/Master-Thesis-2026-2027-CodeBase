"""
Simple News Service for Proactive Research
Fetches top headlines from Israel using free News API
"""

import os
import requests
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class NewsService:
    """
    Simple news service to fetch headlines from Israel
    """
    
    def __init__(self):
        """Initialize news service with free News API"""
        # Using NewsAPI.org - free tier allows 1000 requests/day
        self.api_key = os.getenv('NEWS_API_KEY', '')
        self.base_url = "https://newsapi.org/v2"
        
    def fetch_israel_headlines(self, max_results: int = 5) -> List[Dict]:
        """
        Fetch top headlines from Israel, trying backup topics if primary query
        returns fewer results than needed.
        """
        if not self.api_key:
            print("🔧 No API key — using mock data")
            return self._get_mock_headlines(max_results)

        # Primary + backup queries tried in order until we have enough articles.
        # Backups are broad global topics — interesting to any user regardless of location.
        queries = [
            "israel",
            "technology",
            "science",
            "health",
            "innovation",
            "environment",
        ]

        collected: List[Dict] = []
        seen_titles = set()

        for query in queries:
            if len(collected) >= max_results:
                break
            try:
                url = f"{self.base_url}/top-headlines"
                params = {
                    "q": query,
                    "language": "en",
                    "pageSize": max_results,
                    "apiKey": self.api_key,
                }
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                if data.get("status") != "ok":
                    print(f"❌ API Error for '{query}': {data.get('message', 'Unknown error')}")
                    continue

                for article in data.get("articles", []):
                    title = article.get("title", "")
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        collected.append({
                            "title": title,
                            "description": article.get("description", ""),
                            "source": article.get("source", {}).get("name", ""),
                            "published_at": article.get("publishedAt", ""),
                            "url": article.get("url", ""),
                        })
                    if len(collected) >= max_results:
                        break

                print(f"📡 '{query}' → {len(collected)} articles total so far")

            except requests.exceptions.RequestException as e:
                print(f"❌ Network error for query '{query}': {e}")
            except Exception as e:
                print(f"❌ Error for query '{query}': {e}")

        if not collected:
            print("⚠️ All queries returned 0 results — falling back to mock data")
            return self._get_mock_headlines(max_results)

        return collected[:max_results]
    
    def _get_mock_headlines(self, max_results: int = 5) -> List[Dict]:
        """
        Get mock headlines for testing without API key
        """
        mock_headlines = [
            {
                "title": "Israel Announces New Technology Initiative",
                "description": "Government launches new program to support tech startups",
                "source": "Times of Israel",
                "published_at": "2024-01-15T10:00:00Z",
                "url": "https://example.com/news1"
            },
            {
                "title": "Tel Aviv University Research Breakthrough",
                "description": "Scientists discover new approach to renewable energy",
                "source": "Haaretz",
                "published_at": "2024-01-15T09:30:00Z",
                "url": "https://example.com/news2"
            },
            {
                "title": "Jerusalem Cultural Festival Begins",
                "description": "Annual event showcases Israeli art and music",
                "source": "Jerusalem Post",
                "published_at": "2024-01-15T08:45:00Z",
                "url": "https://example.com/news3"
            },
            {
                "title": "Israeli Economy Shows Strong Growth",
                "description": "GDP exceeds expectations in latest quarterly report",
                "source": "Globes",
                "published_at": "2024-01-15T08:00:00Z",
                "url": "https://example.com/news4"
            },
            {
                "title": "New Medical Research Center Opens in Haifa",
                "description": "State-of-the-art facility focuses on cancer treatment",
                "source": "Ynet",
                "published_at": "2024-01-15T07:30:00Z",
                "url": "https://example.com/news5"
            }
        ]
        
        return mock_headlines[:max_results]
    
    def print_headlines(self, headlines: List[Dict]) -> None:
        """
        Print headlines in a readable format
        
        Args:
            headlines: List of headline dictionaries
        """
        if not headlines:
            print("📰 No headlines found")
            return
        
        print(f"\n📰 Top {len(headlines)} Headlines from Israel:")
        print("=" * 50)
        
        for i, headline in enumerate(headlines, 1):
            print(f"\n{i}. {headline['title']}")
            print(f"   📝 {headline['description']}")
            print(f"   📺 {headline['source']}")
            print(f"   🕒 {headline['published_at']}")
            print(f"   🔗 {headline['url']}")

def main():
    """
    Test the news service
    """
    print("=== 📰 Israel News Service Test ===")
    
    # Initialize news service
    news_service = NewsService()
    
    # Fetch headlines
    print("🔍 Fetching headlines from Israel...")
    headlines = news_service.fetch_israel_headlines(max_results=5)
    
    # Print results
    news_service.print_headlines(headlines)
    
    print(f"\n✅ Found {len(headlines)} headlines")
    
    # For integration testing, return the headlines as a simple list
    simple_headlines = [h['title'] for h in headlines]
    print(f"\n📋 Simple list for integration:")
    for i, title in enumerate(simple_headlines, 1):
        print(f"   {i}. {title}")

if __name__ == "__main__":
    main()
