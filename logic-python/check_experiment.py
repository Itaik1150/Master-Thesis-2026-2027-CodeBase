"""
Quick test to check if experiment ID exists in MongoDB
"""
import os
from bson import ObjectId
from utils.mongodb_client import mongodb_client

def check_experiment_exists():
    """Check if experiment ID 695948af6ac218de3379a861 exists"""
    experiment_id = "695948af6ac218de3379a861"
    
    print(f"🔍 Checking experiment ID: {experiment_id}")
    
    if not mongodb_client.connect():
        print("❌ Failed to connect to MongoDB")
        return
    
    try:
        # List all collections first
        collections = mongodb_client.db.list_collection_names()
        print(f"📋 Available collections: {collections}")
        
        # Check experiments collection (try both string and ObjectId)
        experiment = mongodb_client.db["experiments"].find_one({"_id": experiment_id})
        
        # If not found with string, try ObjectId
        if not experiment:
            try:
                experiment = mongodb_client.db["experiments"].find_one({"_id": ObjectId(experiment_id)})
            except:
                pass
        
        if experiment:
            print(f"✅ Experiment found:")
            print(f"   📋 Title: {experiment.get('title', 'N/A')}")
            print(f"   📊 isActive: {experiment.get('isActive', 'N/A')}")
            print(f"   📝 Description: {experiment.get('description', 'N/A')[:100]}...")
        else:
            print(f"❌ Experiment NOT found in experiments collection")
            
            # List all experiments for debugging
            all_experiments = list(mongodb_client.db["experiments"].find({}).limit(5))
            print(f"\n📋 Available experiments (first 5):")
            for exp in all_experiments:
                exp_id = exp.get('_id', 'N/A')
                title = exp.get('title', 'N/A')
                is_active = exp.get('isActive', 'N/A')
                print(f"   📋 {exp_id} - {title} (active: {is_active})")
        
    except Exception as e:
        print(f"❌ Error checking experiment: {e}")
    
    finally:
        mongodb_client.disconnect()

if __name__ == "__main__":
    check_experiment_exists()
