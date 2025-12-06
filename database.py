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
    
    Raises:
        ValueError: If table does not exist or database cannot be accessed
    """
    engine = create_engine(db_path)
    query = f"SELECT * FROM '{table_name}'"
    
    try:
        df = pd.read_sql(query, engine)
    except Exception as e:
        # Provide more helpful error message
        if "no such table" in str(e).lower():
            raise ValueError(f"Table '{table_name}' does not exist in {db_path}. Available tables: {list_tables(db_path)}")
        else:
            raise ValueError(f"Error loading '{table_name}' from {db_path}: {str(e)}")
    
    # Normalize common index/timestamp column names into a proper DatetimeIndex
    # Common names: 'timestamp', 'date', 'datetime', 'index'
    idx_candidates = [c for c in df.columns if c.lower() in ("timestamp", "date", "datetime", "time", "index")]
    if idx_candidates:
        # Prefer explicit 'timestamp' if present
        preferred = None
        for name in idx_candidates:
            if name.lower() == 'timestamp':
                preferred = name
                break
        if preferred is None:
            preferred = idx_candidates[0]

        try:
            df[preferred] = pd.to_datetime(df[preferred], errors='coerce')
            df = df.rename(columns={preferred: 'timestamp'})
            df = df.set_index('timestamp')
        except Exception:
            # If conversion fails, leave as-is
            pass

    # Ensure index is a DatetimeIndex when possible
    try:
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, errors='coerce')
            if df.index.notna().sum() == 0:
                # If conversion failed, leave original index
                df.index = df.index
    except Exception:
        pass

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
