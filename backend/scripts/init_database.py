"""
Database initialization and setup script
Run this to create all tables and initialize the database
"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path.parent))

from models.database import engine, init_db
from models.orm_models import (
    User, Portfolio, Position, Trade, Signal, PriceData, MacroData, ExecutionLog
)

def init_database():
    """Initialize database and create all tables"""
    print("🔧 Initializing QuantTrade Database...")
    
    try:
        # Create all tables
        init_db()
        print("✅ Database tables created successfully!")
        
        # Print table info
        print("\n📊 Created tables:")
        tables = [
            "users",
            "portfolios", 
            "positions",
            "trades",
            "signals",
            "price_data",
            "macro_data",
            "execution_logs",
        ]
        for table in tables:
            print(f"   • {table}")
        
        print("\n✨ Database initialization complete!")
        print("\n📋 Next steps:")
        print("   1. Configure .env with your database credentials")
        print("   2. Run: python backend/scripts/setup_initial_data.py")
        print("   3. Start the API server: python backend/main.py")
        
    except Exception as e:
        print(f"❌ Error initializing database: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    init_database()
