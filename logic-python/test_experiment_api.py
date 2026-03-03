"""
Test the experiment API endpoint directly
"""
import requests

def test_experiment_api():
    """Test the /experiments/:id endpoint"""
    experiment_id = "695948af6ac218de3379a861"
    
    # Test different URLs
    urls = [
        "http://localhost:5000/experiments/" + experiment_id,
        "http://10.0.2.2:5000/experiments/" + experiment_id,
        "http://localhost:5000/experiments/" + experiment_id + "/content"
    ]
    
    for url in urls:
        print(f"\n🔍 Testing: {url}")
        try:
            response = requests.get(url, timeout=5)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if 'title' in data:
                    print(f"   ✅ Title: {data.get('title', 'N/A')}")
                if 'content' in data:
                    print(f"   ✅ Content: {data.get('content', 'N/A')}")
                if 'isActive' in data:
                    print(f"   ✅ Active: {data.get('isActive', 'N/A')}")
            else:
                print(f"   ❌ Error: {response.text}")
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection failed - server might not be running")
        except requests.exceptions.Timeout:
            print(f"   ❌ Request timed out")
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_experiment_api()
