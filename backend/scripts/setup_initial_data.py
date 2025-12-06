"""
Initial data setup script
Creates default user and portfolio for testing
"""
import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))

from models.database import get_db_context
from models.orm_models import User, Portfolio


def hash_password(password: str) -> str:
    """Hash password using SHA256 (simplified - use bcrypt in production)"""
    return hashlib.sha256(password.encode()).hexdigest()


def setup_initial_data():
    """Create initial user and portfolio"""
    print("🔧 Setting up initial data...")
    
    try:
        with get_db_context() as db:
            # Check if demo user already exists
            existing_user = db.query(User).filter(User.username == "demo").first()
            
            if existing_user:
                print("⚠️  Demo user already exists (ID: {})".format(existing_user.id))
                user = existing_user
            else:
                # Create demo user
                user = User(
                    username="demo",
                    email="demo@quanttrade.com",
                    password_hash=hash_password("demo123"),
                    is_active=True,
                )
                db.add(user)
                db.flush()  # Get the ID without committing
                print(f"✅ User created: demo (ID: {user.id})")
            
            # Check if portfolio already exists
            existing_portfolio = db.query(Portfolio).filter(
                Portfolio.user_id == user.id,
                Portfolio.name == "T1_Strategy"
            ).first()
            
            if existing_portfolio:
                print("⚠️  Portfolio already exists (ID: {})".format(existing_portfolio.id))
                portfolio = existing_portfolio
            else:
                # Create default portfolio
                initial_capital = 100000.0
                portfolio = Portfolio(
                    user_id=user.id,
                    name="T1_Strategy",
                    description="T+1 Trading Strategy - Automated Portfolio",
                    initial_capital=initial_capital,
                    current_cash=initial_capital,
                    total_equity=initial_capital,
                    max_positions=5,
                    stop_loss_pct=-0.05,
                    max_holding_days=20,
                    is_active=True,
                    last_updated=datetime.utcnow(),
                )
                db.add(portfolio)
                db.flush()
                print(f"✅ Portfolio created: T1_Strategy (ID: {portfolio.id}, Capital: ${initial_capital:,.2f})")
            
            # Commit all changes
            db.commit()
            
            print("\n📋 Summary:")
            print(f"   User ID: {user.id}")
            print(f"   Username: {user.username}")
            print(f"   Email: {user.email}")
            print(f"   Portfolio ID: {portfolio.id}")
            print(f"   Portfolio Name: {portfolio.name}")
            print(f"   Initial Capital: ${portfolio.initial_capital:,.2f}")
            print(f"   Current Cash: ${portfolio.current_cash:,.2f}")
            print(f"   Max Positions: {portfolio.max_positions}")
            print(f"   Stop Loss %: {portfolio.stop_loss_pct * 100}%")
            print(f"   Max Holding Days: {portfolio.max_holding_days}")
            
            print("\n✨ Initial data setup complete!")
            print("\n💡 To use in API calls, reference:")
            print(f"   - user_id: {user.id}")
            print(f"   - portfolio_id: {portfolio.id}")
            
    except Exception as e:
        print(f"❌ Error during setup: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    setup_initial_data()
