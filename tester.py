import psycopg2
from contextlib import contextmanager

DB_CONFIG = dict(
    dbname="defaultdb",
    user="myuser",
    host="localhost",
    port=26257
)

# --- Role settings update functions (run as root) ---
ROOT_DB_CONFIG = dict(
    dbname="defaultdb",
    user="root",
    host="localhost",
    port=26257
)

def set_transaction_rows_read_err(limit):
    """Set transaction_rows_read_err for myuser."""
    with psycopg2.connect(**ROOT_DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER ROLE myuser SET transaction_rows_read_err = %s", (limit,))
            conn.commit()
            print(f"Set transaction_rows_read_err to {limit} for myuser.")

def set_large_full_scan_rows(limit):
    """Set large_full_scan_rows for myuser."""
    with psycopg2.connect(**ROOT_DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER ROLE myuser SET large_full_scan_rows = %s", (limit,))
            conn.commit()
            print(f"Set large_full_scan_rows to {limit} for myuser.")

def set_disallow_full_table_scans(disallow):
    """Set disallow_full_table_scans for myuser."""
    value = 'true' if disallow else 'false'
    with psycopg2.connect(**ROOT_DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(f"ALTER ROLE myuser SET disallow_full_table_scans = {value}")
            conn.commit()
            print(f"Set disallow_full_table_scans to {value} for myuser.")

@contextmanager
def get_conn_cursor():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    try:
        yield conn, cur
    finally:
        cur.close()
        conn.close()

def insert_records(num_records=10000):
    with get_conn_cursor() as (conn, cur):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS test_table2 (
                id SERIAL PRIMARY KEY,
                data TEXT
            )
        """)
        conn.commit()

        for i in range(num_records):
            cur.execute("INSERT INTO test_table2 (data) VALUES (%s)", (f"record {i}",))
            if i % 1000 == 0:
                conn.commit()  # Commit every 1000 records for performance

        conn.commit()
        print(f"Inserted {num_records} records.")

def full_table_scan():
    with get_conn_cursor() as (_, cur):
        cur.execute("SELECT * FROM test_table2")
        rows = cur.fetchall()
        print(f"Full table scan: {len(rows)} rows found.")
        if rows:
            print("First 5 rows:")
            for row in rows[:5]:
                print(row)
            print("\nLast 5 rows:")
            for row in rows[-5:]:
                print(row)

def explain_full_table_scan():
    with get_conn_cursor() as (_, cur):
        cur.execute("EXPLAIN SELECT * FROM test_table2")
        rows = cur.fetchall()
        GREEN = '\033[92m'
        RESET = '\033[0m'
        highlight_terms = [
            'actual row count',
            'KV rows decoded',
            'estimated row count'
        ]
        print(f"EXPLAIN output: {len(rows)} rows returned.\n")
        if rows:
            for idx, row in enumerate(rows, 1):
                if len(row) == 1 and isinstance(row[0], str):
                    line = row[0]
                    for term in highlight_terms:
                        if term in line:
                            line = line.replace(term, f"{GREEN}{term}{RESET}")
                    print(f"{idx:2d}: {line}")
                else:
                    print(f"{idx:2d}: {row}")
        else:
            print("No output returned.")
        print("\n--- End of EXPLAIN output ---\n")

def explain_analyze_full_table_scan():
    with get_conn_cursor() as (_, cur):
        cur.execute("EXPLAIN ANALYZE SELECT * FROM test_table2")
        rows = cur.fetchall()
        GREEN = '\033[92m'
        RESET = '\033[0m'
        highlight_terms = [
            'actual row count',
            'KV rows decoded',
            'estimated row count'
        ]
        print(f"EXPLAIN ANALYZE output: {len(rows)} rows returned.\n")
        if rows:
            for idx, row in enumerate(rows, 1):
                if len(row) == 1 and isinstance(row[0], str):
                    line = row[0]
                    for term in highlight_terms:
                        if term in line:
                            line = line.replace(term, f"{GREEN}{term}{RESET}")
                    print(f"{idx:2d}: {line}")
                else:
                    print(f"{idx:2d}: {row}")
        else:
            print("No output returned.")
        print("\n--- End of EXPLAIN ANALYZE output ---\n")

if __name__ == "__main__":


    set_transaction_rows_read_err(10000)
    set_large_full_scan_rows(100000)
    set_disallow_full_table_scans(True)
    print()
    
    try:
        explain_full_table_scan()
    except Exception as e:
        print(f"Error in explain_full_table_scan: {e}")

    try:
        explain_analyze_full_table_scan()
    except Exception as e:
        print(f"Error in explain_analyze_full_table_scan: {e}")

    try:
        full_table_scan()
    except Exception as e:
        print(f"Error in full_table_scan: {e}")
    
    
    
    
    #insert_records()