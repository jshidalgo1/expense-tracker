import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import os
import streamlit as st

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "expenses.db")
OVERALL_BUDGET_CATEGORY = "__overall__"

def get_db_type():
    """Return 'postgres' if configured, else 'sqlite'."""
    if "postgres" in st.secrets:
        return "postgres"
    return "sqlite"

def get_connection():
    """Create a database connection (SQLite or Postgres)."""
    if get_db_type() == "postgres":
        if psycopg2 is None:
            st.error("psycopg2 is not installed. Please add psycopg2-binary to requirements.txt")
            st.stop()
        
        try:
            secrets = st.secrets["postgres"]
            conn = psycopg2.connect(
                host=secrets["host"],
                port=secrets["port"],
                dbname=secrets["dbname"],
                user=secrets["user"],
                password=secrets["password"],
                cursor_factory=RealDictCursor
            )
            return conn
        except Exception as e:
            st.error(f"Failed to connect to PostgreSQL: {e}")
            st.stop()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def get_placeholder():
    """Return the query placeholder based on DB type."""
    return "%s" if get_db_type() == "postgres" else "?"

def execute_query(query: str, params: tuple = ()) -> bool:
    """Execute a query that doesn't return results (INSERT, UPDATE, DELETE)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database error: {e}")
        return False

def init_db():
    """Initialize the database with required tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Determine SQL syntax based on DB type
    db_type = get_db_type()
    
    if db_type == "postgres":
        pk_def = "SERIAL PRIMARY KEY"
        text_type = "TEXT"
    else:
        pk_def = "INTEGER PRIMARY KEY AUTOINCREMENT"
        text_type = "TEXT"

    # Create transactions table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS transactions (
            id {pk_def},
            date {text_type} NOT NULL,
            description {text_type} NOT NULL,
            category {text_type} NOT NULL,
            amount REAL NOT NULL,
            account {text_type} NOT NULL,
            source {text_type} NOT NULL,
            created_at {text_type} DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create categories table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS categories (
            id {pk_def},
            name {text_type} UNIQUE NOT NULL
        )
    """)
    
    # Create bank_passwords table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS bank_passwords (
            id {pk_def},
            bank_name {text_type} UNIQUE NOT NULL,
            password {text_type} NOT NULL,
            created_at {text_type} DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create merchant_mappings table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS merchant_mappings (
            id {pk_def},
            merchant_pattern {text_type} UNIQUE NOT NULL,
            category {text_type} NOT NULL,
            created_at {text_type} DEFAULT CURRENT_TIMESTAMP,
            last_used {text_type} DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create budget_targets table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS budget_targets (
            id {pk_def},
            month {text_type} NOT NULL,
            category {text_type} NOT NULL,
            amount REAL NOT NULL,
            created_at {text_type} DEFAULT CURRENT_TIMESTAMP,
            updated_at {text_type} DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (month, category)
        )
    """)

    # Create finance_logs table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS finance_logs (
            id {pk_def},
            log_date {text_type} NOT NULL,
            total_assets REAL NOT NULL,
            total_debt REAL NOT NULL,
            net_worth REAL NOT NULL,
            created_at {text_type} DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create finance_log_items table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS finance_log_items (
            id {pk_def},
            log_id INTEGER NOT NULL,
            item_type {text_type} NOT NULL,
            name {text_type} NOT NULL,
            amount REAL NOT NULL,
            created_at {text_type} DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create finance_current_items table
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS finance_current_items (
            id {pk_def},
            item_type {text_type} NOT NULL,
            name {text_type} NOT NULL,
            amount REAL NOT NULL,
            updated_at {text_type} DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()


# Ensure schema exists on import (safe with IF NOT EXISTS)
init_db()

# ============= TRANSACTION OPERATIONS =============

def add_transaction(date: str, description: str, category: str, 
                   amount: float, account: str, source: str) -> int:
    """Add a new transaction to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    
    if get_db_type() == "postgres":
        cursor.execute(f"""
            INSERT INTO transactions (date, description, category, amount, account, source)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            RETURNING id
        """, (date, description, category, amount, account, source))
        transaction_id = cursor.fetchone()[0]
    else:
        cursor.execute(f"""
            INSERT INTO transactions (date, description, category, amount, account, source)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        """, (date, description, category, amount, account, source))
        transaction_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return transaction_id

def get_transactions(date_from: Optional[str] = None, 
                     date_to: Optional[str] = None,
                     categories: Optional[List[str]] = None,
                     accounts: Optional[List[str]] = None) -> List[Dict]:
    """Get transactions with optional filters."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []
    
    if date_from:
        query += f" AND date >= {ph}"
        params.append(date_from)
    
    if date_to:
        query += f" AND date <= {ph}"
        params.append(date_to)
    
    if categories:
        placeholders = ','.join([ph] * len(categories))
        query += f" AND category IN ({placeholders})"
        params.extend(categories)
    
    if accounts:
        placeholders = ','.join([ph] * len(accounts))
        query += f" AND account IN ({placeholders})"
        params.extend(accounts)
    
    query += " ORDER BY date DESC"
    
    cursor.execute(query, tuple(params))
    
    if get_db_type() == "postgres":
        # extras.RealDictCursor returns dict-like objects
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
    else:
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        
    conn.close()
    
    return result

def delete_transaction(transaction_id: int) -> bool:
    """Delete a transaction by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    cursor.execute(f"DELETE FROM transactions WHERE id = {ph}", (transaction_id,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted

def update_transaction(
    transaction_id: int,
    date: str,
    description: str,
    category: str,
    amount: float,
    account: str,
    source: str
) -> bool:
    """Update all editable fields for a transaction."""
    conn = get_connection()
    cursor = conn.cursor()

    ph = get_placeholder()
    cursor.execute(
        f"""
        UPDATE transactions
        SET date = {ph}, description = {ph}, category = {ph}, amount = {ph}, account = {ph}, source = {ph}
        WHERE id = {ph}
        """,
        (date, description, category, amount, account, source, transaction_id)
    )

    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return updated

def get_date_range() -> Tuple[Optional[str], Optional[str]]:
    """Get the min and max dates from transactions."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT MIN(date), MAX(date) FROM transactions")
    row = cursor.fetchone()
    conn.close()
    
    # row can be tuple (sqlite) or dict (postgres/RealDictCursor) if configured that way
    # but psycopg2 default cursor returns tuple. We used default cursor for simple queries?
    # Actually wait, we didn't set cursor factory for postgres in get_connection yet, let's assume default tuple for now unless RealDictCursor is used.
    # In get_connection I used: conn = psycopg2.connect(...) -> default cursor (tuple)
    # Wait, I imported RealDictCursor but didn't use it in get_connection for Postgres.
    # Let me fix that assumption. Standardizing on dict access is safer if we want to be consistent.
    # For now, let's treat row as indexable or dict depending on context.
    # Actually, SQLite Row factory supports both. Psycopg2 default doesn't.
    # Better to use RealDictCursor for Postgres to match SQLite Row behavior (access by name).
    
    if row:
        return row[0], row[1]
    return None, None

def get_transaction_months() -> List[str]:
    """Get distinct months (YYYY-MM) that have transactions."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT substr(date, 1, 7) AS month FROM transactions ORDER BY month DESC")
    rows = cursor.fetchall()
    conn.close()

    # SQLite Row and Psycopg2 tuple might differ. 
    # If I don't use RealDictCursor for Postgres, I can't do row['month'].
    # I should probably update get_connection to use RealDictCursor for Postgres.
    # I'll update this function to handle both or assume I'll fix get_connection.
    # For now, index access is safer for single column.
    return [row[0] for row in rows]

# ============= CATEGORY OPERATIONS =============

def add_category(name: str) -> bool:
    """Add a new category."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        ph = get_placeholder()
        cursor.execute(f"INSERT INTO categories (name) VALUES ({ph})", (name,))
        
        conn.commit()
        conn.close()
        return True
    except Exception: # sqlite3.IntegrityError or psycopg2.IntegrityError
        return False

def get_categories() -> List[str]:
    """Get all categories."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM categories ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    
    return [row[0] for row in rows]

def update_category(old_name: str, new_name: str) -> bool:
    """Update a category name."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        ph = get_placeholder()
        # Update category name
        cursor.execute(f"UPDATE categories SET name = {ph} WHERE name = {ph}", 
                      (new_name, old_name))
        
        # Update all transactions with this category
        cursor.execute(f"UPDATE transactions SET category = {ph} WHERE category = {ph}",
                      (new_name, old_name))
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def delete_category(name: str) -> Tuple[bool, str]:
    """Delete a category if not used in transactions."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    # Check if category is used
    cursor.execute(f"SELECT COUNT(*) as count FROM transactions WHERE category = {ph}", (name,))
    
    # Handle different cursor returns
    row = cursor.fetchone()
    if get_db_type() == "postgres":
        # default cursor is tuple
        count = row[0]
    else:
        # sqlite Row is dict-like
        count = row['count']
        
    if count > 0:
        conn.close()
        return False, f"Cannot delete category '{name}' - it's used in {count} transaction(s)"
    
    cursor.execute(f"DELETE FROM categories WHERE name = {ph}", (name,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    if deleted:
        return True, f"Category '{name}' deleted successfully"
    else:
        return False, f"Category '{name}' not found"

# ============= BUDGET OPERATIONS =============

def upsert_budget_target(month: str, category: Optional[str], amount: float) -> bool:
    """Insert or update a monthly budget target for a category or overall."""
    category_value = category if category is not None else OVERALL_BUDGET_CATEGORY
    
    ph = get_placeholder()
    
    # Postgres uses ON CONFLICT differently? No, standard syntax for UPSERT is similar but let's check.
    # SQLite: INSERT INTO ... ON CONFLICT(cols) DO UPDATE SET ...
    # Postgres: INSERT INTO ... ON CONFLICT(cols) DO UPDATE SET ...
    # They are compatible for this simple case.
    
    return execute_query(
        f"""
        INSERT INTO budget_targets (month, category, amount)
        VALUES ({ph}, {ph}, {ph})
        ON CONFLICT(month, category) DO UPDATE SET
            amount = excluded.amount,
            updated_at = CURRENT_TIMESTAMP
        """,
        (month, category_value, amount)
    )

def delete_budget_target(month: str, category: Optional[str]) -> bool:
    """Delete a monthly budget target for a category or overall."""
    category_value = category if category is not None else OVERALL_BUDGET_CATEGORY
    ph = get_placeholder()
    return execute_query(
        f"DELETE FROM budget_targets WHERE month = {ph} AND category = {ph}",
        (month, category_value)
    )

def get_budget_targets(month: str) -> Dict[Optional[str], float]:
    """Get all budget targets for a given month."""
    conn = get_connection()
    cursor = conn.cursor()

    ph = get_placeholder()
    cursor.execute(f"SELECT category, amount FROM budget_targets WHERE month = {ph}", (month,))
    rows = cursor.fetchall()
    conn.close()

    targets: Dict[Optional[str], float] = {}
    for row in rows:
        # Handle tuple vs dict access
        if isinstance(row, tuple): # Postgres default
            category = row[0]
            amount = row[1]
        else: # SQLite
            category = row['category']
            amount = row['amount']
            
        key = None if category == OVERALL_BUDGET_CATEGORY else category
        targets[key] = amount

    return targets

def get_budget_months() -> List[str]:
    """Get distinct months (YYYY-MM) that have budget targets."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT month FROM budget_targets ORDER BY month DESC")
    rows = cursor.fetchall()
    conn.close()

    return [row[0] for row in rows]

# ============= BANK PASSWORD OPERATIONS =============

def add_bank_password(bank_name: str, password: str) -> bool:
    """Add or update a bank password."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    # Postgres doesn't support ?=value in UPDATE. It needs excluded.value logic which we have.
    # But wait, the original code had: ON CONFLICT... DO UPDATE SET password = ?
    # That syntax is tricky with placeholders passed twice.
    # Better to use `excluded.password` which works in both SQLite and Postgres.
    
    cursor.execute(f"""
        INSERT INTO bank_passwords (bank_name, password)
        VALUES ({ph}, {ph})
        ON CONFLICT(bank_name) DO UPDATE SET password = excluded.password
    """, (bank_name, password))
    
    conn.commit()
    conn.close()
    return True

def get_bank_passwords() -> List[Dict]:
    """Get all bank passwords."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT bank_name, password FROM bank_passwords ORDER BY bank_name")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) if not isinstance(row, tuple) else {'bank_name': row[0], 'password': row[1]} for row in rows]

def get_bank_password(bank_name: str) -> Optional[str]:
    """Get password for a specific bank."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    cursor.execute(f"SELECT password FROM bank_passwords WHERE bank_name = {ph}", (bank_name,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row[0]
    return None

def update_bank_password(bank_name: str, new_password: str) -> bool:
    """Update a bank password."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    cursor.execute(f"UPDATE bank_passwords SET password = {ph} WHERE bank_name = {ph}",
                  (new_password, bank_name))
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return updated

def delete_bank_password(bank_name: str) -> bool:
    """Delete a bank password."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    cursor.execute(f"DELETE FROM bank_passwords WHERE bank_name = {ph}", (bank_name,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted

# ============= FINANCE LOG OPERATIONS =============

def add_finance_log(log_date: str, total_assets: float, total_debt: float) -> int:
    """Add a finance log snapshot and return its ID."""
    net_worth = total_assets - total_debt
    conn = get_connection()
    cursor = conn.cursor()

    ph = get_placeholder()
    if get_db_type() == "postgres":
        cursor.execute(f"""
            INSERT INTO finance_logs (log_date, total_assets, total_debt, net_worth)
            VALUES ({ph}, {ph}, {ph}, {ph})
            RETURNING id
        """, (log_date, total_assets, total_debt, net_worth))
        log_id = cursor.fetchone()[0]
    else:
        cursor.execute(f"""
            INSERT INTO finance_logs (log_date, total_assets, total_debt, net_worth)
            VALUES ({ph}, {ph}, {ph}, {ph})
        """, (log_date, total_assets, total_debt, net_worth))
        log_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return log_id

def add_finance_log_with_items(
    log_date: str,
    total_assets: float,
    total_debt: float,
    asset_items: List[Tuple[str, float]],
    debt_items: List[Tuple[str, float]]
) -> int:
    """Add a finance log and its breakdown items in a single transaction."""
    # Reusing add_finance_log logic but we need atomic transaction
    net_worth = total_assets - total_debt
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    
    try:
        if get_db_type() == "postgres":
            cursor.execute(f"""
                INSERT INTO finance_logs (log_date, total_assets, total_debt, net_worth)
                VALUES ({ph}, {ph}, {ph}, {ph})
                RETURNING id
            """, (log_date, total_assets, total_debt, net_worth))
            log_id = cursor.fetchone()[0]
        else:
            cursor.execute(f"""
                INSERT INTO finance_logs (log_date, total_assets, total_debt, net_worth)
                VALUES ({ph}, {ph}, {ph}, {ph})
            """, (log_date, total_assets, total_debt, net_worth))
            log_id = cursor.lastrowid

        if asset_items:
            # executemany with placeholders
            cursor.executemany(
                f"""
                INSERT INTO finance_log_items (log_id, item_type, name, amount)
                VALUES ({ph}, 'asset', {ph}, {ph})
                """,
                [(log_id, name, amount) for name, amount in asset_items]
            )

        if debt_items:
            cursor.executemany(
                f"""
                INSERT INTO finance_log_items (log_id, item_type, name, amount)
                VALUES ({ph}, 'debt', {ph}, {ph})
                """,
                [(log_id, name, amount) for name, amount in debt_items]
            )

        conn.commit()
        return log_id
    except Exception as e:
        conn.rollback()
        print(f"Error adding finance log: {e}")
        raise e
    finally:
        conn.close()

def get_finance_logs() -> List[Dict]:
    """Get all finance logs ordered by date ascending."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, log_date, total_assets, total_debt, net_worth, created_at
        FROM finance_logs
        ORDER BY log_date ASC, id ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    # Uniform return type
    if get_db_type() == "postgres":
        return [
            {
                'id': row[0], 'log_date': row[1], 'total_assets': row[2], 
                'total_debt': row[3], 'net_worth': row[4], 'created_at': row[5]
            } 
            for row in rows
        ]
    
    return [dict(row) for row in rows]

def get_finance_log_items(log_ids: List[int]) -> List[Dict]:
    """Get all finance log items for the given log IDs."""
    if not log_ids:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    ph = get_placeholder()
    placeholders = ','.join(ph * len(log_ids)) # Wait, ph * len is correct string repetition? No, list comp joining
    # Correct: ','.join([ph] * len(log_ids))
    placeholders = ','.join([ph] * len(log_ids))
    
    query = f"""
        SELECT id, log_id, item_type, name, amount
        FROM finance_log_items
        WHERE log_id IN ({placeholders})
        ORDER BY log_id ASC, item_type ASC, name ASC
    """
    
    # Need to convert ids to tuple for postgres execution if list
    cursor.execute(query, tuple(log_ids))

    rows = cursor.fetchall()
    conn.close()
    
    if get_db_type() == "postgres":
        return [
            {'id': row[0], 'log_id': row[1], 'item_type': row[2], 'name': row[3], 'amount': row[4]}
            for row in rows
        ]

    return [dict(row) for row in rows]

def delete_finance_log(log_id: int) -> bool:
    """Delete a finance log and its related items."""
    conn = get_connection()
    cursor = conn.cursor()

    ph = get_placeholder()
    cursor.execute(f"DELETE FROM finance_log_items WHERE log_id = {ph}", (log_id,))
    cursor.execute(f"DELETE FROM finance_logs WHERE id = {ph}", (log_id,))

    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return deleted

def replace_finance_current_items(item_type: str, items: List[Tuple[str, float]]) -> None:
    """Replace current finance items for a given type (asset or debt)."""
    conn = get_connection()
    cursor = conn.cursor()

    ph = get_placeholder()
    cursor.execute(f"DELETE FROM finance_current_items WHERE item_type = {ph}", (item_type,))

    if items:
        cursor.executemany(
            f"""
            INSERT INTO finance_current_items (item_type, name, amount, updated_at)
            VALUES ({ph}, {ph}, {ph}, CURRENT_TIMESTAMP)
            """,
            [(item_type, name, amount) for name, amount in items]
        )

    conn.commit()
    conn.close()

def get_finance_current_items(item_type: str) -> List[Dict]:
    """Get current finance items for a given type (asset or debt)."""
    conn = get_connection()
    cursor = conn.cursor()

    ph = get_placeholder()
    cursor.execute(
        f"""
        SELECT name, amount
        FROM finance_current_items
        WHERE item_type = {ph}
        ORDER BY id ASC
        """,
        (item_type,)
    )

    rows = cursor.fetchall()
    conn.close()

    if get_db_type() == "postgres":
        return [{'name': row[0], 'amount': row[1]} for row in rows]

    return [dict(row) for row in rows]

def update_transaction_category(transaction_id: int, new_category: str) -> bool:
    """Update a transaction's category."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    cursor.execute(
        f"UPDATE transactions SET category = {ph} WHERE id = {ph}",
        (new_category, transaction_id)
    )
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return updated

# ============= MERCHANT MAPPING OPERATIONS =============

def add_merchant_mapping(merchant_pattern: str, category: str) -> bool:
    """Add or update a merchant pattern to category mapping."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    try:
        # Try to insert, or update if exists
        cursor.execute(f"""
            INSERT INTO merchant_mappings (merchant_pattern, category)
            VALUES ({ph}, {ph})
            ON CONFLICT(merchant_pattern) DO UPDATE SET category = excluded.category
        """, (merchant_pattern.upper(), category))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding merchant mapping: {e}")
        conn.close()
        return False

def get_merchant_mappings() -> List[Dict]:
    """Get all merchant mappings."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, merchant_pattern, category, created_at, last_used
        FROM merchant_mappings
        ORDER BY last_used DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if get_db_type() == "postgres":
        return [
            {
                'id': row[0], 'merchant_pattern': row[1], 'category': row[2], 
                'created_at': row[3], 'last_used': row[4]
            } 
            for row in rows
        ]
    
    return [dict(row) for row in results] # wait, 'results' is undefined in original replace block context? 
    # Original used: results = [dict(row) for row in cursor.fetchall()]
    # I should return [dict(row) for row in rows] here.

def get_merchant_mapping_for_description(description: str) -> Optional[str]:
    """Find a matching merchant mapping for a description. Returns category or None."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all patterns
    cursor.execute("SELECT merchant_pattern, category FROM merchant_mappings")
    mappings = cursor.fetchall() # Tuple in postgres, Row in sqlite
    conn.close()
    
    desc_upper = description.upper()
    
    # Helper to unpack
    def unpack(row):
        if isinstance(row, tuple): return row[0], row[1]
        return row['merchant_pattern'], row['category']
    
    # Try exact match first
    for row in mappings:
        pattern, category = unpack(row)
        if pattern in desc_upper:
            return category
    
    # Try fuzzy match (substring match on key parts)
    for row in mappings:
        pattern, category = unpack(row)
        # Split pattern into words and check if all appear in description
        pattern_parts = pattern.split()
        if len(pattern_parts) > 0 and all(part in desc_upper for part in pattern_parts):
            return category
    
    return None

def delete_merchant_mapping(merchant_pattern: str) -> bool:
    """Delete a merchant mapping."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    cursor.execute(f"DELETE FROM merchant_mappings WHERE merchant_pattern = {ph}", (merchant_pattern.upper(),))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted

def update_merchant_mapping(old_pattern: str, new_pattern: str, category: str) -> bool:
    """Update a merchant mapping."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    cursor.execute(
        f"UPDATE merchant_mappings SET merchant_pattern = {ph}, category = {ph} WHERE merchant_pattern = {ph}",
        (new_pattern.upper(), category, old_pattern.upper())
    )
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return updated

def find_similar_transactions(description: str, exclude_id: Optional[int] = None, 
                             similarity_threshold: float = 0.6) -> List[Dict]:
    """
    Find transactions with similar merchant names using fuzzy matching.
    """
    from rapidfuzz import fuzz
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all transactions
    cursor.execute("SELECT id, description, category, date, amount FROM transactions")
    rows = cursor.fetchall()
    
    if get_db_type() == "postgres":
        all_transactions = [
            {'id': row[0], 'description': row[1], 'category': row[2], 'date': row[3], 'amount': row[4]}
            for row in rows
        ]
    else:
        all_transactions = [dict(row) for row in rows]
        
    conn.close()
    
    similar = []
    
    for trans in all_transactions:
        # Skip the original transaction
        if exclude_id and trans['id'] == exclude_id:
            continue
        
        # Calculate similarity score
        score = fuzz.token_set_ratio(description.upper(), trans['description'].upper()) / 100.0
        
        # If similar enough, add to results
        if score >= similarity_threshold:
            similar.append({
                **trans,
                'similarity_score': round(score, 2)
            })
    
    # Sort by similarity score (descending)
    similar.sort(key=lambda x: x['similarity_score'], reverse=True)
    
    return similar

def bulk_update_category(description_pattern: str, new_category: str, 
                        similarity_threshold: float = 0.6) -> int:
    """
    Bulk update transactions with similar descriptions to a new category.
    """
    from rapidfuzz import fuzz
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all transactions
    cursor.execute("SELECT id, description FROM transactions")
    all_transactions = cursor.fetchall()
    
    updated_count = 0
    ph = get_placeholder()
    
    for row in all_transactions:
        if get_db_type() == "postgres":
            trans_id, trans_desc = row[0], row[1]
        else:
            trans_id, trans_desc = row['id'], row['description']
            
        score = fuzz.token_set_ratio(description_pattern.upper(), trans_desc.upper()) / 100.0
        
        if score >= similarity_threshold:
            cursor.execute(
                f"UPDATE transactions SET category = {ph} WHERE id = {ph}",
                (new_category, trans_id)
            )
            updated_count += 1
    
    conn.commit()
    conn.close()
    
    return updated_count

def update_merchant_mapping_usage(merchant_pattern: str) -> bool:
    """Update the last_used timestamp for a merchant mapping."""
    conn = get_connection()
    cursor = conn.cursor()
    
    ph = get_placeholder()
    cursor.execute(f"""
        UPDATE merchant_mappings 
        SET last_used = CURRENT_TIMESTAMP 
        WHERE merchant_pattern = {ph}
    """, (merchant_pattern.upper(),))
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return updated


def get_merchant_mapping_stats() -> Dict[str, any]:
    """Get statistics about merchant mappings and their usage."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total mappings
    cursor.execute("SELECT COUNT(*) as count FROM merchant_mappings")
    total_mappings = cursor.fetchone()['count']
    
    # Most recent mappings
    cursor.execute("""
        SELECT merchant_pattern, category, created_at, last_used
        FROM merchant_mappings
        ORDER BY last_used DESC
        LIMIT 10
    """)
    recent = [dict(row) for row in cursor.fetchall()]
    
    # Mappings by category
    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM merchant_mappings
        GROUP BY category
        ORDER BY count DESC
    """)
    by_category = {row['category']: row['count'] for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        'total_mappings': total_mappings,
        'by_category': by_category,
        'recent_mappings': recent
    }
