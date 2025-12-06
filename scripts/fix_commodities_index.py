"""
Normalize commodity DB tables: ensure each table has a proper datetime index stored as a column named 'timestamp'.

Usage:
    python3 scripts/fix_commodities_index.py

This script will:
 - Inspect all tables in `commodities.db`.
 - For each table, read it into a DataFrame.
 - Detect a date-like column (common names: 'timestamp', 'date', 'datetime', 'index', 'Unnamed: 0'). If none found, it will assume the first column is the date index.
 - Convert that column to `datetime` with `pd.to_datetime`, set as index, and write back the table with `index_label='timestamp'`.
"""

import re
import sqlite3
import pandas as pd
from sqlalchemy import create_engine

DB_PATH = 'commodities.db'  # sqlite file in repo root

DATE_CANDIDATES = ['timestamp', 'date', 'datetime', 'time', 'index', 'Unnamed: 0']


def list_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [r[0] for r in cur.fetchall()]


def guess_date_column(df: pd.DataFrame):
    # Look for obvious candidates (case-insensitive)
    cols = df.columns.tolist()
    for cand in DATE_CANDIDATES:
        for c in cols:
            if c.lower() == cand.lower():
                return c
    # Look for any column that looks like a date string (contains '-' or '/')
    for c in cols:
        sample = df[c].dropna().astype(str).head(10).tolist()
        if any(re.search(r"\d{4}-\d{2}-\d{2}", s) or re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", s) for s in sample):
            return c
    # Fallback: first column
    return cols[0] if cols else None


def normalize_tables(db_path=DB_PATH):
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    engine = create_engine(f"sqlite:///{db_path}")

    try:
        tables = list_tables(conn)
        if not tables:
            print("No tables found in DB.")
            return

        for tbl in tables:
            print(f"\nProcessing table: {tbl}")
            try:
                df = pd.read_sql_query(f"SELECT * FROM '{tbl}'", conn)
                if df.empty:
                    print("  - empty table, skipping")
                    continue

                date_col = guess_date_column(df)
                if date_col is None:
                    print("  - no columns found, skipping")
                    continue

                print(f"  - guessed date column: '{date_col}'")

                # Convert to datetime
                try:
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                except Exception as e:
                    print(f"  - datetime conversion failed for column {date_col}: {e}")
                    df[date_col] = pd.to_datetime(df[date_col].astype(str), errors='coerce')

                # If conversion produced many NaT, try to coerce index style values
                non_na = df[date_col].notna().sum()
                if non_na == 0:
                    # Maybe the original index was stored as plain integers; try interpreting as epoch
                    try:
                        df[date_col] = pd.to_datetime(df[date_col].astype(float), unit='s', errors='coerce')
                        print(f"  - attempted epoch conversion for {date_col}")
                    except Exception:
                        pass

                # Final check
                non_na = df[date_col].notna().sum()
                total = len(df)
                print(f"  - {non_na}/{total} rows have valid timestamps after conversion")

                # Set as index and sort
                df = df.set_index(date_col)
                df.index.name = 'timestamp'
                df = df.sort_index()

                # Write back to DB replacing table; keep index as 'timestamp'
                df.to_sql(tbl, engine, if_exists='replace', index=True, index_label='timestamp')
                print(f"  - table '{tbl}' rewritten with index_label='timestamp' ({len(df)} rows)")

            except Exception as e:
                print(f"  - failed to process {tbl}: {e}")

    finally:
        conn.close()
        engine.dispose()


if __name__ == '__main__':
    normalize_tables()
