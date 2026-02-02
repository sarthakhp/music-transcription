#!/usr/bin/env python3
"""
Migration script to add 'message' column to the jobs table.
Run this script to update existing database schema.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from api.database.session import engine
from api.config import settings

def add_message_column():
    print(f"Connecting to database: {settings.database_url}")
    
    with engine.connect() as conn:
        try:
            result = conn.execute(text("SELECT message FROM jobs LIMIT 1"))
            print("✓ Column 'message' already exists in jobs table")
            return
        except Exception:
            print("Column 'message' does not exist, adding it now...")
        
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN message TEXT"))
            conn.commit()
            print("✓ Successfully added 'message' column to jobs table")
        except Exception as e:
            print(f"✗ Error adding column: {e}")
            raise

if __name__ == "__main__":
    add_message_column()

