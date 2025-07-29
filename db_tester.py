import psycopg
import os
import random
import string
import sys
import time

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

# Example connection string for insecure local CRDB
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '26257')
DB_NAME = os.getenv('DB_NAME', 'defaultdb')
DB_USER = os.getenv('DB_USER', 'root')

CONN_STR = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} sslmode=disable"

NUM_ROWS_TO_INSERT = 10000  # Set this variable to control how many rows to insert

SESSION_SETTINGS = {
    'application_name': 'my_app',
    'transaction_rows_read_err': 40000,
}

COMMON_ORDER_BY = ""
COMMON_SELECT = "*"

COMMON_LIMIT = "LIMIT 50000"
COMMON_LIMIT = ""

COMMON_SELECT_QUERY = f"SELECT {COMMON_SELECT} FROM test_table {COMMON_ORDER_BY}{COMMON_LIMIT};"

print(f"{GREEN}COMMON_SELECT_QUERY:{RESET} {COMMON_SELECT_QUERY}")

def print_error_details(e):
    print(f"{RED}Error Type:{RESET} {type(e).__name__}")
    print(f"{RED}Error Message:{RESET} {str(e)}")
    if hasattr(e, 'pgcode'):
        print(f"{RED}PostgreSQL Error Code:{RESET} {e.pgcode}")
    if hasattr(e, 'pgerror'):
        print(f"{RED}PostgreSQL Error:{RESET} {e.pgerror}")
    if hasattr(e, 'pgresult'):
        print(f"{RED}PostgreSQL Result:{RESET} {e.pgresult}")
    print("-" * 20)

def set_session_settings(conn, settings):
    try:
        with conn.cursor() as cur:
            for key, value in settings.items():
                if isinstance(value, int):
                    cur.execute(f"SET {key} = {value};")
                else:
                    cur.execute(f"SET {key} = %s;", (value,))
                print(f"{GREEN}Session setting set: {key} = {value}{RESET}")
    except Exception as e:
        print(f"{RED}Error setting session settings:{RESET}")
        print_error_details(e)

def create_table_if_not_exists(conn):
    query = """
    CREATE TABLE IF NOT EXISTS test_table (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name STRING,
        value INT
    );
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            print(f"{GREEN}Table 'test_table' ensured to exist.{RESET}")
    except Exception as e:
        print(f"{RED}Error creating table:{RESET}")
        print_error_details(e)

def insert_random_data_batch(conn, num_rows):
    # Generate all random data at once
    data = []
    for _ in range(num_rows):
        name = ''.join(random.choices(string.ascii_letters, k=8))
        value = random.randint(1, 100)
        data.append((name, value))
    
    query = "INSERT INTO test_table (name, value) VALUES (%s, %s);"
    try:
        with conn.cursor() as cur:
            cur.executemany(query, data)
            print(f"{GREEN}Batch inserted {num_rows} rows successfully.{RESET}")
    except Exception as e:
        print(f"{RED}Error in batch insert:{RESET}")
        print_error_details(e)

def query_method_1_basic_execute(conn):
    """Basic execute with fetchone - streaming results row by row"""
    print("Method1Basic execute with fetchone - STREAMING RESULTS:")
    total_rows = 0
    try:
        with conn.cursor() as cur:
            cur.execute(COMMON_SELECT_QUERY)
            while True:
                row = cur.fetchone()
                if row is None:
                    break
                print(f"{GREEN}Row {total_rows + 1}:{RESET} {row}")
                total_rows += 1
            print(f"{GREEN}Total rows streamed: {total_rows}{RESET}")
    except Exception as e:
        print(f"{RED}Error during streaming:{RESET}")
        print(f"{GREEN}PARTIAL RESULTS WERE PRINTED ABOVE - {total_rows} rows were successfully streamed{RESET}")
        print_error_details(e)
        print(f"{RED}Partial results may have been printed above{RESET}")

def query_method_2_execute_with_params(conn):
    """Execute with parameters"""
    query = f"SELECT {COMMON_SELECT} FROM test_table WHERE value > %s {COMMON_ORDER_BY}{COMMON_LIMIT};"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (50,))
            result = cur.fetchall()
            print("Method 2 - Execute with parameters:")
            print(f"{GREEN}SUCCESS - Rows returned: {len(result)}{RESET}")
            print(result)
    except Exception as e:
        print("Method 2 - Execute with parameters:")
        print_error_details(e)
        print(f"{RED}No data returned due to error{RESET}")

def query_method_3_executemany(conn):
    """Executemany with multiple parameter sets"""
    query = "INSERT INTO test_table (name, value) VALUES (%s, %s);"
    data = [
        ('batch1', 101),
        ('batch2', 102),
        ('batch3', 103),
    ]
    try:
        with conn.cursor() as cur:
            cur.executemany(query, data)
            print("Method 3 - Executemany:")
            print(f"{GREEN}SUCCESS - Batch insert completed{RESET}")
    except Exception as e:
        print("Method 3 - Executemany:")
        print_error_details(e)

def query_method_4_server_side_cursor(conn):
    """Server-side cursor for large result sets (simulated with fetchmany)"""
    try:
        with conn.cursor() as cur:
            cur.execute(COMMON_SELECT_QUERY)
            batch_size = 2
            total_rows = 0
            batch_num = 1
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                print(f"Method 4 - Server-side cursor batch {batch_num}:")
                print(f"{GREEN}SUCCESS - Batch {batch_num}: {len(rows)} rows{RESET}")
                print(rows)
                total_rows += len(rows)
                batch_num += 1
            print(f"{GREEN}Method 4 - Total rows fetched: {total_rows}{RESET}")
    except Exception as e:
        print("Method 4 - Server-side cursor:")
        print_error_details(e)
        print(f"{RED}Partial data may have been fetched before error{RESET}")

def query_method_5_execute_with_named_cursor(conn):
    """Execute with named cursor (simulated)"""
    try:
        with conn.cursor() as cur:
            cur.execute(COMMON_SELECT_QUERY)
            result = cur.fetchall()
            print("Method 5 - Named cursor:")
            print(f"{GREEN}SUCCESS - Rows returned: {len(result)}{RESET}")
            print(result)
    except Exception as e:
        print("Method 5 - Named cursor:")
        print_error_details(e)
        print(f"{RED}No data returned due to error{RESET}")

def query_method_6_execute_with_dict_cursor(conn):
    """Execute with dictionary cursor (returns dicts instead of tuples)"""
    try:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(COMMON_SELECT_QUERY)
            result = cur.fetchall()
            print("Method 6 - Dictionary cursor:")
            print(f"{GREEN}SUCCESS - Rows returned: {len(result)}{RESET}")
            print(result)
    except Exception as e:
        print("Method 6 - Dictionary cursor:")
        print_error_details(e)
        print(f"{RED}No data returned due to error{RESET}")

def query_method_7_execute_with_named_tuple_cursor(conn):
    """Execute with named tuple cursor"""
    try:
        with conn.cursor(row_factory=psycopg.rows.namedtuple_row) as cur:
            cur.execute(COMMON_SELECT_QUERY)
            result = cur.fetchall()
            print("Method 7 - Named tuple cursor:")
            print(f"{GREEN}SUCCESS - Rows returned: {len(result)}{RESET}")
            print(result)
    except Exception as e:
        print("Method 7 - Named tuple cursor:")
        print_error_details(e)
        print(f"{RED}No data returned due to error{RESET}")

def query_method_8_execute_with_custom_row_factory(conn):
    """Execute with custom row factory"""
    try:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(COMMON_SELECT_QUERY)
            result = cur.fetchall()
            print("Method 8 - Custom row factory:")
            print(f"{GREEN}SUCCESS - Rows returned: {len(result)}{RESET}")
            for row in result:
                print(f"Row: {row}")
    except Exception as e:
        print("Method 8 - Custom row factory:")
        print_error_details(e)
        print(f"{RED}No data returned due to error{RESET}")

def query_method_9_prepared_statement(conn):
    """Prepared statement with parameter"""
    query = f"SELECT {COMMON_SELECT} FROM test_table {COMMON_ORDER_BY}{COMMON_LIMIT};"
    try:
        with conn.cursor() as cur:
            cur.execute("PREPARE my_query AS " + query)
            cur.execute("EXECUTE my_query")
            result = cur.fetchall()
            print("Method 9 - Prepared statement:")
            print(f"{GREEN}SUCCESS - Rows returned: {len(result)}{RESET}")
            print(result)
    except Exception as e:
        print("Method 9 - Prepared statement:")
        print_error_details(e)
        print(f"{RED}No data returned due to error{RESET}")

def query_method_10_transaction_control(conn):
    """Explicit transaction control"""
    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN;")
            cur.execute(COMMON_SELECT_QUERY)
            result = cur.fetchall()
            cur.execute("COMMIT;")
            print("Method 10 - Explicit transaction control:")
            print(f"{GREEN}SUCCESS - Rows returned: {len(result)}{RESET}")
            print(result)
    except Exception as e:
        print("Method 10 - Explicit transaction control:")
        print_error_details(e)
        print(f"{RED}No data returned due to error{RESET}")

def query_method_1_iter_cursor(conn):
    """Stream results using cursor as an iterator"""
    print("Method 1 (iterator) - Streaming results row by row:")
    total_rows = 0
    try:
        with conn.cursor() as cur:
            cur.execute(COMMON_SELECT_QUERY)
            for row in cur:
                print(f"{GREEN}Row {total_rows + 1}:{RESET} {row}")
                total_rows += 1
            print(f"{GREEN}Total rows streamed: {total_rows}{RESET}")
    except Exception as e:
        print(f"{RED}Error during streaming:{RESET}")
        print(f"{GREEN}PARTIAL RESULTS WERE PRINTED ABOVE - {total_rows} rows were successfully streamed{RESET}")
        print_error_details(e)
        print(f"{RED}Partial results may have been printed above{RESET}")

def query_method_1_fetchmany_one(conn):
    """Stream results using fetchmany(batch_size=1)"""
    print("Method 1 (fetchmany(1)) - Streaming results row by row:")
    with conn.cursor() as cur:
        cur.execute(COMMON_SELECT_QUERY)
        total_rows = 0
        while True:
            rows = cur.fetchmany(1)
            if not rows:
                break
            print(f"{GREEN}Row {total_rows + 1}:{RESET} {rows[0]}")
            total_rows += 1
        print(f"{GREEN}Total rows streamed: {total_rows}{RESET}")

def row_stream(cursor):
    while True:
        row = cursor.fetchone()
        if row is None:
            break
        yield row

def query_method_1_generator(conn):
    """Stream results using a generator"""
    print("Method 1 (generator) - Streaming results row by row:")
    with conn.cursor() as cur:
        cur.execute(COMMON_SELECT_QUERY)
        total_rows = 0
        for row in row_stream(cur):
            print(f"{GREEN}Row {total_rows + 1}:{RESET} {row}")
            total_rows += 1
        print(f"{GREEN}Total rows streamed: {total_rows}{RESET}")

def query_method_1_detailed_streaming(conn):
    """Detailed streaming with immediate output and clear partial result indication"""
    print("Method 1 (detailed) - Streaming with immediate output:")
    total_rows = 0
    try:
        with conn.cursor() as cur:
            cur.execute(COMMON_SELECT_QUERY)
            print(f"{GREEN}Starting to fetch rows...{RESET}")
            sys.stdout.flush()  # Force immediate output
            while True:
                row = cur.fetchone()
                if row is None:
                    break
                total_rows += 1
                print(f"{GREEN}✓ Row {total_rows}:{RESET} {row}")
                sys.stdout.flush()  # Force immediate output
                time.sleep(0.1)
            print(f"{GREEN}✓ SUCCESS - All {total_rows} rows streamed{RESET}")
    except Exception as e:
        print(f"{RED}✗ ERROR during streaming:{RESET}")
        print(f"{GREEN}✓ PARTIAL RESULTS: {total_rows} rows were successfully streamed above{RESET}")
        print_error_details(e)
        print(f"{RED}The error occurred after streaming {total_rows} rows{RESET}")

def query_method_debug_cursor_info(conn):
    """Method to show lower-level cursor information"""
    print("Debug Method - Cursor Information:")
    with conn.cursor() as cur:
        print(f"{GREEN}Before execute - rowcount: {cur.rowcount}{RESET}")
        cur.execute(COMMON_SELECT_QUERY)
        print(f"{GREEN}After execute - rowcount: {cur.rowcount}{RESET}")

        # Check if we have results
        if cur.description:
            print(f"{GREEN}Query has results - columns: {len(cur.description)}{RESET}")
            print(f"{GREEN}Column names: {[desc[0] for desc in cur.description]}{RESET}")
        else:
            print(f"{RED}No results description available{RESET}")

        # Try to get first row
        first_row = cur.fetchone()
        if first_row:
            print(f"{GREEN}First row fetched: {first_row}{RESET}")
            print(f"{GREEN}After first fetch - rowcount: {cur.rowcount}{RESET}")

            # Reset cursor to beginning
            cur.scroll(0, mode='absolute')
            print(f"{GREEN}After scroll to beginning - rowcount: {cur.rowcount}{RESET}")

            # Count total rows
            total_rows = 0
            while True:
                row = cur.fetchone()
                if row is None:
                    break
                total_rows += 1
                if total_rows <= 3:
                    print(f"{GREEN}Row {total_rows}: {row}{RESET}")
                elif total_rows == 4:
                    print(f"{GREEN}... (showing first 3ws only){RESET}")
                    break
            print(f"{GREEN}Total rows in result set: {total_rows}{RESET}")
        else:
            print(f"{RED}No rows returned{RESET}")

def query_method_raw_connection_info(conn):
    print(f"{GREEN}Raw Connection Debug Method:")
    print(f"{GREEN}Connection info: {conn.info}{RESET}")
    print(f"{GREEN}Server version: {conn.info.server_version}{RESET}")
    print(f"{GREEN}Backend PID: {conn.info.backend_pid}{RESET}")
    print(f"{GREEN}Application name: {conn.info.parameter_status('application_name')}{RESET}")
    
    with conn.cursor() as cur:
        # Execute and check raw cursor state
        cur.execute(COMMON_SELECT_QUERY)
        
        # Check cursor internals
        print(f"{GREEN}Cursor closed: {cur.closed}{RESET}")
        print(f"{GREEN}Cursor description: {cur.description}{RESET}")
        print(f"{GREEN}Cursor rowcount: {cur.rowcount}{RESET}")
        
        # Try to access raw result info if available
        if hasattr(cur, '_result'):
            print(f"{GREEN}Raw result object: {cur._result}{RESET}")
        
        # Check if we can peek at the result set
        try:
            # Try to get a sample without consuming
            sample_rows = cur.fetchmany(2)
            print(f"{GREEN}Sample rows (first 2): {sample_rows}{RESET}")
            
            # Reset to beginning
            cur.scroll(0, mode='absolute')
            print(f"{GREEN}Reset to beginning successful{RESET}")
        except Exception as e:
            print(f"{RED}Error peeking at results: {e}{RESET}")

def query_method_11_alternative_approaches(conn):
    """Various alternative Python approaches to test guardrail behavior"""
    print("Method 11 - Alternative Python Approaches:")
    
    # Approach 1 a context manager with manual error handling
    print(f"{GREEN}Approach 1 - Context manager with manual handling:{RESET}")
    total_rows = 0
    try:
        cursor = conn.cursor()
        cursor.execute(COMMON_SELECT_QUERY)
        while True:
            try:
                row = cursor.fetchone()
                if row is None:
                    break
                total_rows += 1
                print(f"{GREEN}Row {total_rows}: {row}{RESET}")
            except Exception as e:
                print(f"{RED}Error during fetch: {e}{RESET}")
                break
        cursor.close()
        print(f"{GREEN}Approach 1 completed: {total_rows} rows{RESET}")
    except Exception as e:
        print(f"{RED}Approach1 failed: {e}{RESET}")
    
    # Approach 2: Using a generator function with yield
    print(f"\n{GREEN}Approach 2 - Generator function:{RESET}")
    def row_generator(cursor):
        while True:
            try:
                row = cursor.fetchone()
                if row is None:
                    break
                yield row
            except Exception as e:
                print(f"{RED}Generator error: {e}{RESET}")
                break
    
    total_rows = 0
    try:
        with conn.cursor() as cur:
            cur.execute(COMMON_SELECT_QUERY)
            for row in row_generator(cur):
                total_rows += 1
                print(f"{GREEN}Row {total_rows}: {row}{RESET}")
        print(f"{GREEN}Approach 2 completed: {total_rows} rows{RESET}")
    except Exception as e:
        print(f"{RED}Approach2 failed: {e}{RESET}")
    
    # Approach 3: Using a list comprehension with exception handling
    print(f"\n{GREEN}Approach 3 - List comprehension with error handling:{RESET}")
    try:
        with conn.cursor() as cur:
            cur.execute(COMMON_SELECT_QUERY)
            rows = []
            try:
                # This will fail but we'll catch it
                rows = cur.fetchall()
                print(f"{GREEN}Approach 3 completed: {len(rows)} rows{RESET}")
            except Exception as e:
                print(f"{RED}Approach 3fetchall failed: {e}{RESET}")
                # Try to get partial results
                try:
                    cur.scroll(0, mode='absolute')
                    partial_rows = []
                    while True:
                        row = cur.fetchone()
                        if row is None:
                            break
                        partial_rows.append(row)
                    print(f"{GREEN}Approach 3 partial results: {len(partial_rows)} rows{RESET}")
                except Exception as e2:
                    print(f"{RED}Approach 3 partial fetch also failed: {e2}{RESET}")
    except Exception as e:
        print(f"{RED}Approach3 failed: {e}{RESET}")
    
    # Approach4 a custom iterator class
    print(f"\n{GREEN}Approach 4 - Custom iterator class:{RESET}")
    class SafeRowIterator:
        def __init__(self, cursor):
            self.cursor = cursor
            self.total_rows = 0      
        def __iter__(self):
            return self
        
        def __next__(self):
            try:
                row = self.cursor.fetchone()
                if row is None:
                    raise StopIteration
                self.total_rows += 1
                return row
            except Exception as e:
                print(f"{RED}Iterator error at row {self.total_rows}: {e}{RESET}")
                raise StopIteration
    
    total_rows = 0
    try:
        with conn.cursor() as cur:
            cur.execute(COMMON_SELECT_QUERY)
            iterator = SafeRowIterator(cur)
            for row in iterator:
                print(f"  Row {iterator.total_rows}: {row}")
            total_rows = iterator.total_rows
        print(f"{GREEN}Approach 4 completed: {total_rows} rows{RESET}")
    except Exception as e:
        print(f"{RED}Approach4 failed: {e}{RESET}")
    
    # Approach 5: Using a callback function
    print(f"\n{GREEN}Approach 5 - Callback function:{RESET}")
    def process_row(row, row_num):
        print(f"  Row {row_num}: {row}")
        return True  # Continue processing
    
    total_rows = 0
    try:
        with conn.cursor() as cur:
            cur.execute(COMMON_SELECT_QUERY)
            while True:
                try:
                    row = cur.fetchone()
                    if row is None:
                        break
                    total_rows += 1
                    if not process_row(row, total_rows):
                        break
                except Exception as e:
                    print(f"{RED}Callback error at row {total_rows}: {e}{RESET}")
                    break
        print(f"{GREEN}Approach 5 completed: {total_rows} rows{RESET}")
    except Exception as e:
        print(f"{RED}Approach5 failed: {e}{RESET}")

def main():
    try:
        with psycopg.connect(CONN_STR, autocommit=True) as conn:
            set_session_settings(conn, SESSION_SETTINGS)
            create_table_if_not_exists(conn)
            print(f"{GREEN}Inserting initial data...{RESET}")
            insert_random_data_batch(conn, NUM_ROWS_TO_INSERT)
            print(f"{GREEN}Inserted {NUM_ROWS_TO_INSERT} rows.{RESET}\n")
            print("="*50)
            print("DEMONSTRATING DIFFERENT QUERY EXECUTION METHODS")
            print("="*50)
            print(f"Common query: {COMMON_SELECT_QUERY}\n")

            # Wrap each method in its own try-except to continue on errors
            try:
                query_method_1_basic_execute(conn)
            except Exception as e:
                print(f"{RED}Method1 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_1_iter_cursor(conn)
                pass
            except Exception as e:
                print(f"{RED}Method 1 (iterator) failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_1_fetchmany_one(conn)
            except Exception as e:
                print(f"{RED}Method 1 (fetchmany) failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_1_generator(conn)
            except Exception as e:
                print(f"{RED}Method 1 (generator) failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                # query_method_1_detailed_streaming(conn)
                pass
            except Exception as e:
                print(f"{RED}Method 1 (detailed streaming) failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_debug_cursor_info(conn)
            except Exception as e:
                print(f"{RED}Debug method failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_raw_connection_info(conn)
            except Exception as e:
                print(f"{RED}Raw connection debug failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_2_execute_with_params(conn)
            except Exception as e:
                print(f"{RED}Method2 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_3_executemany(conn)
            except Exception as e:
                print(f"{RED}Method3 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_4_server_side_cursor(conn)
            except Exception as e:
                print(f"{RED}Method4 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_5_execute_with_named_cursor(conn)
            except Exception as e:
                print(f"{RED}Method5 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_6_execute_with_dict_cursor(conn)
            except Exception as e:
                print(f"{RED}Method6 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_7_execute_with_named_tuple_cursor(conn)
            except Exception as e:
                print(f"{RED}Method7 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_8_execute_with_custom_row_factory(conn)
            except Exception as e:
                print(f"{RED}Method8 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_9_prepared_statement(conn)
            except Exception as e:
                print(f"{RED}Method9 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_10_transaction_control(conn)
            except Exception as e:
                print(f"{RED}Method 10 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

            try:
                query_method_11_alternative_approaches(conn)
            except Exception as e:
                print(f"{RED}Method 11 failed: {e}{RESET}")
            print("\n" + "-"*50 + "\n")

    except Exception as e:
        print(f"{RED}Connection error:{RESET}")
        print_error_details(e)

if __name__ == '__main__':
    main() 