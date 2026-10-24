"""
Vercel entry point for FoodWasteZero Flask app.
Forces SQLite mode (no MySQL on Vercel) and pre-seeds the database on cold start.
"""
import os
import sys

# Add parent directory to path so all app modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force SQLite mode on Vercel (no MySQL available)
os.environ.setdefault("FWZ_DB", "sqlite")

# Use /tmp for writable SQLite storage on Vercel (filesystem is read-only except /tmp)
os.environ.setdefault("SQLITE_PATH", "/tmp/foodwastezero.sqlite3")

# Import config after setting env vars so they take effect
import config

# Override SQLITE_PATH in config to use /tmp
config.SQLITE_PATH = os.environ.get("SQLITE_PATH", "/tmp/foodwastezero.sqlite3")

# Auto-seed the database if it doesn't exist yet
import setup_db
if not setup_db.database_ready():
    try:
        setup_db.main(empty=False)
    except Exception as e:
        print("DB seed failed:", e)

# Import the Flask app
from app import app

# Vercel expects a WSGI app called `app`
