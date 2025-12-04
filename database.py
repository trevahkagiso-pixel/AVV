"""
Database operations module.
Handles storing and retrieving data from SQLite databases.
"""

import pandas as pd
from sqlalchemy import create_engine, inspect


def save_to_database(df: pd.DataFrame, table_name: str, db_path: str, if_exists: str = "replace") -> None:
    """
    Save DataFrame to SQLite database.
    
    Args:
        df: DataFrame to save
        table_name: Name of the table in database
        db_path: Database path (e.g., 'sqlite:///forex.db')
        if_exists: How to behave if table exists ('fail', 'replace', 'append')
    """
    engine = create_engine(db_path)
    df.to_sql(table_name, engine, if_exists=if_exists)
    print(f"✅ {table_name} saved to {db_path}")


def save_to_csv(df: pd.DataFrame, filename: str) -> None:
    """
    Save DataFrame to CSV file.
    
    Args:
        df: DataFrame to save
        filename: Output CSV filename
    """
    df.to_csv(filename)
    print(f"✅ Data saved to {filename}")


def load_from_database(table_name: str, db_path: str) -> pd.DataFrame:
    """
    Load DataFrame from SQLite database table.
    
    Args:
        table_name: Name of the table in database
        db_path: Database path (e.g., 'sqlite:///forex.db')
    
    Returns:
        DataFrame loaded from database
    """
    engine = create_engine(db_path)
    query = f"SELECT * FROM '{table_name}'"
    df = pd.read_sql(query, engine)
    
    # Convert index column to datetime if present
    if "index" in df.columns:
        df["index"] = pd.to_datetime(df["index"])
        df = df.rename(columns={"index": "timestamp"})
        df = df.set_index("timestamp")
    
    return df


def list_tables(db_path: str) -> list:
    """
    List all tables in the database.
    
    Args:
        db_path: Database path (e.g., 'sqlite:///forex.db')
    
    Returns:
        List of table names
    """
    engine = create_engine(db_path)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return tables


def get_database_info(db_path: str) -> dict:
    """
    Get information about all tables in the database.
    
    Args:
        db_path: Database path (e.g., 'sqlite:///forex.db')
    
    Returns:
        Dictionary with table information
    """
    engine = create_engine(db_path)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    info = {}
    for table in tables:
        columns = inspector.get_columns(table)
        info[table] = [col['name'] for col in columns]
    
    return info
