"""
csvs_to_mysql.py
Usage:
  python csvs_to_mysql.py --csv_dir ./csv_armenian_epi --mysql_user etl_user --mysql_pass EtlUserPss --mysql_host 127.0.0.1 --mysql_db mydata
"""

import os
import argparse
import pandas as pd
from sqlalchemy import create_engine, text

def clean_colname(c):
    # simple cleanup: strip, replace spaces and special chars
    c = c.strip()
    c = c.replace(' ', '_').replace('-', '_').replace('/', '_')
    c = ''.join(ch for ch in c if ch.isalnum() or ch == '_')
    if c == '':
        c = 'col'
    return c.lower()

def main(csv_dir, mysql_user, mysql_pass, mysql_host, mysql_port, mysql_db):
    # Create SQLAlchemy engine
    url = f"mysql+pymysql://{mysql_user}:{mysql_pass}@{mysql_host}:{mysql_port}/{mysql_db}"
    engine = create_engine(url, pool_recycle=3600)

    # Ensure database exists (connect to server first without db)
    tmp_url = f"mysql+pymysql://{mysql_user}:{mysql_pass}@{mysql_host}:{mysql_port}/"
    tmp_engine = create_engine(tmp_url)
    with tmp_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {mysql_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))

    csv_files = [f for f in os.listdir(csv_dir) if f.lower().endswith('.csv')]
    if not csv_files:
        print("No CSVs found in", csv_dir)
        return
    print(f"Found {len(csv_files)} CSV files in {csv_dir}")
    for fn in csv_files:
        path = os.path.join(csv_dir, fn)
        tablename = os.path.splitext(fn)[0]
        print(f"\nLoading {path} -> table `{tablename}`")

        # Read CSV (try to guess encoding)
        try:
            df = pd.read_csv(path, dtype=str)  # read all as string first for safety
        except Exception as e:
            print("  Error reading CSV:", e)
            continue

        # Clean column names
        df.columns = [clean_colname(c) for c in df.columns]
        # Trim whitespace in string cells and normalize empty -> NaN
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.replace(r'^\s*$', pd.NA, regex=True)

        # Upload: replace existing table (change if_exists to 'append' if you prefer)
        df.to_sql(tablename, engine, if_exists='replace', index=False, method='multi', chunksize=1000)
        print("  Inserted", len(df), "rows into", tablename)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv_dir', required=True)
    parser.add_argument('--mysql_user', default='root')
    parser.add_argument('--mysql_pass', default='')
    parser.add_argument('--mysql_host', default='127.0.0.1')
    parser.add_argument('--mysql_port', default='3306')
    parser.add_argument('--mysql_db', default='mydata')
    args = parser.parse_args()
    main(args.csv_dir, args.mysql_user, args.mysql_pass, args.mysql_host, args.mysql_port, args.mysql_db)
