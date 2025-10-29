"""
csvs_to_mysql.py

Load multiple CSV files into a MySQL database using SQLAlchemy and pandas.

Usage:
    python csv_to_mysql.py --csv_dir ./csv_input_folder --mysql_user databaseuser --mysql_pass userpassword --mysql_host 127.0.0.1 --mysql_db databasename

Description:
- This script automates the process of importing several CSV files into a MySQL database.
- Each CSV file becomes a separate table named after its file (without extension).
- Column names are cleaned and normalized for compatibility with SQL table naming rules.
- The database is created automatically if it doesn’t already exist.

Requirements:
    pip install pandas sqlalchemy pymysql
"""

import os
import argparse
import pandas as pd
from sqlalchemy import create_engine, text


def clean_colname(c):
    """
    Clean and standardize a column name to make it SQL-safe.

    Operations:
    - Strip whitespace.
    - Replace spaces, hyphens, and slashes with underscores.
    - Remove non-alphanumeric characters (except underscores).
    - Ensure the column name is lowercase and not empty.

    Args:
        c (str): Original column name from the CSV file.

    Returns:
        str: Cleaned and SQL-safe column name.
    """
    c = c.strip()
    c = c.replace(' ', '_').replace('-', '_').replace('/', '_')
    c = ''.join(ch for ch in c if ch.isalnum() or ch == '_')
    if c == '':
        c = 'col'
    return c.lower()


def main(csv_dir, mysql_user, mysql_pass, mysql_host, mysql_port, mysql_db):
    """
    Main function that reads all CSV files from a directory and imports them into a MySQL database.

    Steps:
        1. Connect to the MySQL server using SQLAlchemy.
        2. Create the database if it doesn't exist.
        3. Iterate through all CSV files in the specified directory.
        4. Read, clean, and load each CSV into the database as a new table.

    Args:
        csv_dir (str): Path to the directory containing CSV files.
        mysql_user (str): MySQL username.
        mysql_pass (str): MySQL password.
        mysql_host (str): MySQL server hostname or IP.
        mysql_port (str): MySQL port (default: 3306).
        mysql_db (str): Target database name.
    """

    # --- Create SQLAlchemy engine to connect to the target database ---
    url = f"mysql+pymysql://{mysql_user}:{mysql_pass}@{mysql_host}:{mysql_port}/{mysql_db}"
    engine = create_engine(url, pool_recycle=3600)

    # --- Ensure the database exists ---
    # Connect to the MySQL server without specifying a database to create it if needed
    tmp_url = f"mysql+pymysql://{mysql_user}:{mysql_pass}@{mysql_host}:{mysql_port}/"
    tmp_engine = create_engine(tmp_url)
    with tmp_engine.connect() as conn:
        conn.execute(text(
            f"CREATE DATABASE IF NOT EXISTS {mysql_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))

    # --- Get all CSV files in the directory ---
    csv_files = [f for f in os.listdir(csv_dir) if f.lower().endswith('.csv')]
    if not csv_files:
        print("No CSVs found in", csv_dir)
        return

    print(f"Found {len(csv_files)} CSV files in {csv_dir}")

    # --- Loop through each CSV and import it ---
    for fn in csv_files:
        path = os.path.join(csv_dir, fn)
        tablename = os.path.splitext(fn)[0]  # Table name = file name without extension
        print(f"\nLoading {path} -> table `{tablename}`")

        # Read CSV file into a pandas DataFrame
        try:
            # Read all data as strings initially to avoid type inference errors
            df = pd.read_csv(path, dtype=str)
        except Exception as e:
            print("  Error reading CSV:", e)
            continue

        # --- Clean and normalize column names ---
        df.columns = [clean_colname(c) for c in df.columns]

        # --- Trim extra whitespace from string cells and normalize empty strings to NaN ---
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.replace(r'^\s*$', pd.NA, regex=True)

        # --- Upload the DataFrame to MySQL ---
        # "if_exists='replace'" ensures any existing table with the same name is overwritten.
        # You may switch to 'append' if you wish to add data instead of replacing.
        df.to_sql(tablename, engine, if_exists='replace', index=False, method='multi', chunksize=1000)
        print("  Inserted", len(df), "rows into", tablename)


if __name__ == '__main__':
    # --- Command-line argument parser setup ---
    parser = argparse.ArgumentParser(description="Import multiple CSV files into a MySQL database.")
    parser.add_argument('--csv_dir', required=True, help='Path to directory containing CSV files.')
    parser.add_argument('--mysql_user', default='root', help='MySQL username.')
    parser.add_argument('--mysql_pass', default='', help='MySQL password.')
    parser.add_argument('--mysql_host', default='127.0.0.1', help='MySQL host address.')
    parser.add_argument('--mysql_port', default='3306', help='MySQL port number.')
    parser.add_argument('--mysql_db', default='mydata', help='Target MySQL database name.')

    # --- Parse arguments and run main process ---
    args = parser.parse_args()
    main(args.csv_dir, args.mysql_user, args.mysql_pass, args.mysql_host, args.mysql_port, args.mysql_db)
