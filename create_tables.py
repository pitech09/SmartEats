# create_tables.py

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from application.models import Base
from application.database import engine

def create_all_tables():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully.")

if __name__ == "__main__":
    create_all_tables()
