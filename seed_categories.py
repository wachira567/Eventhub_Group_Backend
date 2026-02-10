"""
Seed script to add categories to the database
"""

from app import app
from extensions import db
from models import Category

# Categories matching the frontend's CATEGORIES constant
CATEGORIES = [
    {"name": "Music", "description": "Concerts, festivals, and live music events", "icon": "Headphones"},
    {"name": "Nightlife", "description": "Bars, clubs, and night events", "icon": "Sparkles"},
    {"name": "Performing & Visual Arts", "description": "Theater, dance, art exhibitions", "icon": "Palette"},
    {"name": "Holidays", "description": "Holiday-themed events and celebrations", "icon": "Calendar"},
    {"name": "Dating", "description": "Speed dating, singles events", "icon": "Heart"},
    {"name": "Hobbies", "description": "Hobby-specific events and meetups", "icon": "Gamepad2"},
    {"name": "Business", "description": "Networking, conferences, workshops", "icon": "Briefcase"},
    {"name": "Food & Drink", "description": "Food festivals, tastings, wine events", "icon": "UtensilsCrossed"},
]

def seed_categories():
    with app.app_context():
        # Check if categories already exist
        existing = Category.query.all()
        if existing:
            print(f"Categories already exist: {[c.name for c in existing]}")
            return
        
        # Add categories
        for cat_data in CATEGORIES:
            category = Category(
                name=cat_data["name"],
                description=cat_data["description"],
                icon=cat_data["icon"]
            )
            db.session.add(category)
        
        db.session.commit()
        print("Categories seeded successfully!")
        
        # Verify
        all_cats = Category.query.all()
        print(f"Categories in database: {[c.name for c in all_cats]}")

if __name__ == "__main__":
    seed_categories()
