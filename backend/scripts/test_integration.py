"""
Integration test script - Verify all components are working
"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))

def test_imports():
    """Test all imports"""
    print("🔍 Testing imports...")
    try:
        from models.database import engine, get_db_context, init_db
        print("   ✅ Database module")
    except Exception as e:
        print(f"   ❌ Database module: {e}")
        return False
    
    try:
        from models.orm_models import (
            User, Portfolio, Position, Trade, Signal, 
            PriceData, MacroData, ExecutionLog
        )
        print("   ✅ ORM models")
    except Exception as e:
        print(f"   ❌ ORM models: {e}")
        return False
    
    try:
        from services.enhanced_portfolio_service import enhanced_portfolio_service
        print("   ✅ Enhanced portfolio service")
    except Exception as e:
        print(f"   ❌ Enhanced portfolio service: {e}")
        return False
    
    try:
        from services.data_integration_service import data_integration_service
        print("   ✅ Data integration service")
    except Exception as e:
        print(f"   ❌ Data integration service: {e}")
        return False
    
    return True


def test_database_connection():
    """Test database connection"""
    print("\n🗄️ Testing database connection...")
    try:
        from models.database import engine
        with engine.connect() as connection:
            result = connection.execute("SELECT 1 as connected")
            print("   ✅ Database connected")
        return True
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        print("   💡 Make sure PostgreSQL is running and DATABASE_URL is correct")
        return False


def test_table_existence():
    """Test that all tables exist"""
    print("\n📊 Checking tables...")
    try:
        from models.database import get_db_context
        from models.orm_models import (
            User, Portfolio, Position, Trade, Signal,
            PriceData, MacroData, ExecutionLog
        )
        
        with get_db_context() as db:
            # Try to query each table
            tables_to_check = [
                ("users", User),
                ("portfolios", Portfolio),
                ("positions", Position),
                ("trades", Trade),
                ("signals", Signal),
                ("price_data", PriceData),
                ("macro_data", MacroData),
                ("execution_logs", ExecutionLog),
            ]
            
            for table_name, model in tables_to_check:
                try:
                    db.query(model).limit(1).all()
                    print(f"   ✅ {table_name}")
                except Exception as e:
                    print(f"   ❌ {table_name}: {str(e)[:50]}")
                    return False
            
        return True
    except Exception as e:
        print(f"   ❌ Error checking tables: {e}")
        return False


def test_data_files():
    """Test that required data files exist"""
    print("\n📁 Checking data files...")
    try:
        master_df_path = os.getenv("MASTER_DF_PATH", "data/master/master_df.parquet")
        if os.path.exists(master_df_path):
            print(f"   ✅ master_df.parquet exists")
        else:
            print(f"   ⚠️  master_df.parquet not found at {master_df_path}")
        
        live_state_path = os.getenv("LIVE_STATE_PATH", "src/quanttrade/models_2.0/live_state_T1.json")
        if os.path.exists(live_state_path):
            print(f"   ✅ live_state_T1.json exists")
        else:
            print(f"   ⚠️  live_state_T1.json not found at {live_state_path}")
        
        return True
    except Exception as e:
        print(f"   ❌ Error checking files: {e}")
        return False


def test_env_configuration():
    """Test environment configuration"""
    print("\n⚙️ Checking environment configuration...")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        required_vars = [
            "DATABASE_URL",
            "MASTER_DF_PATH",
            "LIVE_STATE_PATH",
            "LIVE_EQUITY_PATH",
            "LIVE_TRADES_PATH",
        ]
        
        for var in required_vars:
            value = os.getenv(var)
            if value:
                # Show truncated value for security
                display_value = value[:40] + "..." if len(value) > 40 else value
                print(f"   ✅ {var}: {display_value}")
            else:
                print(f"   ❌ {var}: Not set")
                return False
        
        return True
    except Exception as e:
        print(f"   ❌ Error checking environment: {e}")
        return False


def test_user_and_portfolio():
    """Test that demo user and portfolio exist"""
    print("\n👤 Checking demo user and portfolio...")
    try:
        from models.database import get_db_context
        from models.orm_models import User, Portfolio
        
        with get_db_context() as db:
            user = db.query(User).filter(User.username == "demo").first()
            if user:
                print(f"   ✅ Demo user exists (ID: {user.id}, Email: {user.email})")
                
                portfolio = db.query(Portfolio).filter(
                    Portfolio.user_id == user.id,
                    Portfolio.name == "T1_Strategy"
                ).first()
                
                if portfolio:
                    print(f"   ✅ Portfolio exists (ID: {portfolio.id}, Capital: ${portfolio.initial_capital:,.2f})")
                    return True
                else:
                    print(f"   ⚠️  Portfolio not found for user {user.id}")
                    print(f"   💡 Run: python backend/scripts/setup_initial_data.py")
                    return False
            else:
                print(f"   ⚠️  Demo user not found")
                print(f"   💡 Run: python backend/scripts/setup_initial_data.py")
                return False
                
    except Exception as e:
        print(f"   ❌ Error checking user/portfolio: {e}")
        return False


def test_data_integration():
    """Test data integration services"""
    print("\n🔄 Testing data integration...")
    try:
        from services.data_integration_service import data_integration_service
        
        # Try loading master_df
        master_df = data_integration_service.load_master_df()
        if master_df is not None:
            print(f"   ✅ master_df loaded: {master_df.shape[0]} rows, {master_df.shape[1]} columns")
        else:
            print(f"   ⚠️  Could not load master_df")
        
        # Get signal stats (may be empty)
        stats = data_integration_service.get_signal_stats()
        print(f"   ✅ Signal stats: {stats.get('total_signals', 0)} total, {stats.get('executed_signals', 0)} executed")
        
        return True
    except Exception as e:
        print(f"   ❌ Error testing data integration: {e}")
        return False


def test_portfolio_service():
    """Test portfolio service"""
    print("\n📈 Testing portfolio service...")
    try:
        from services.enhanced_portfolio_service import enhanced_portfolio_service
        
        # Get portfolio state (with fallback)
        state = enhanced_portfolio_service.get_portfolio_state(portfolio_id=1, use_file_fallback=True)
        print(f"   ✅ Portfolio state loaded: Cash=${state.cash:,.2f}, Positions={len(state.positions)}")
        
        # Get equity history
        equity_history = enhanced_portfolio_service.get_equity_history(portfolio_id=1, use_file_fallback=True)
        print(f"   ✅ Equity history: {len(equity_history)} records")
        
        # Get trades
        trades = enhanced_portfolio_service.get_trades_history(portfolio_id=1, use_file_fallback=True)
        print(f"   ✅ Trades history: {len(trades)} trades")
        
        return True
    except Exception as e:
        print(f"   ❌ Error testing portfolio service: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 QuantTrade Backend Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Environment", test_env_configuration),
        ("Database Connection", test_database_connection),
        ("Table Existence", test_table_existence),
        ("Data Files", test_data_files),
        ("User & Portfolio", test_user_and_portfolio),
        ("Data Integration", test_data_integration),
        ("Portfolio Service", test_portfolio_service),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Backend is ready.")
        print("\n📝 Next steps:")
        print("   1. Start backend: python backend/main.py")
        print("   2. Connect frontend to http://localhost:8000")
        print("   3. Test button clicks and data flow")
    else:
        print("\n⚠️  Some tests failed. See details above.")
        print("\n💡 Troubleshooting:")
        print("   - Check BACKEND_SETUP_GUIDE.md for PostgreSQL setup")
        print("   - Verify DATABASE_URL in .env")
        print("   - Run: python backend/scripts/init_database.py")
        print("   - Run: python backend/scripts/setup_initial_data.py")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
