#!/usr/bin/env python3

import sys
sys.path.append('/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base

def test_postgresql_connection():
    """Test PostgreSQL connection and create tables."""
    database_url = "postgresql://postgres:postgres@db:5432/postgres"
    
    try:
        engine = create_engine(database_url, echo=True)
        print(f"Engine dialect: {engine.dialect.name}")
        
        # Test connection
        connection = engine.connect()
        print(f"Connection successful: {connection}")
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully")
        
        # Create session
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = TestingSessionLocal()
        print(f"Session created: {session}")
        print(f"Session engine dialect: {session.bind.dialect.name}")
        
        session.close()
        connection.close()
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = test_postgresql_connection()
    print(f"Test result: {'SUCCESS' if success else 'FAILURE'}")
