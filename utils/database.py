from datetime import datetime
from typing import List, Dict, Optional, Tuple
import streamlit as st
import psycopg2
from psycopg2 import pool, extras
from psycopg2.extras import RealDictCursor
import os
from contextlib import contextmanager

# Cache the connection pool so it persists across reruns
@st.cache_resource
def init_connection_pool():
    """Initialize the connection pool."""
    from utils.profiler import scope_timer
    
    with scope_timer('DB Connection Init'):
        try:
            secrets = st.secrets["postgres"]
            return psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=secrets["host"],
                port=secrets["port"],
                dbname=secrets["dbname"],
                user=secrets["user"],
                password=secrets["password"],
                cursor_factory=RealDictCursor
            )
        except Exception as e:
            st.error(f"Failed to connect to PostgreSQL: {e}")
            st.stop()

@contextmanager
def get_db_connection():
    """
    Context manager to get a connection from the pool.
    Automatically returns the connection to the pool when done.
    Checks for connection health and retries if stale.
    """
    db_pool = init_connection_pool()
    conn = db_pool.getconn()
    try:
        # Health check: verify connection is alive
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        except psycopg2.OperationalError:
            # Connection is dead; close it and get a fresh one
            db_pool.putconn(conn, close=True)
            conn = db_pool.getconn()
        
        yield conn
        
        # Return to pool if successful
        db_pool.putconn(conn)
        
    except Exception as e:
        # specific handling for errors during usage
        if conn:
            try:
                # If the error was operational (e.g. lost connection during query), close it
                is_operational = isinstance(e, psycopg2.OperationalError)
                db_pool.putconn(conn, close=is_operational)
            except Exception:
                pass
        raise e

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
OVERALL_BUDGET_CATEGORY = "__overall__"

def get_placeholder():
    """Return the placeholder for the current database type."""
    # Always Postgres now
    return "%s"

def execute_query(query: str, params: tuple = None, fetch_one: bool = False, fetch_all: bool = False) -> any:
    """Helper to execute a query and handle commit/close."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            
            result = None
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()
            
            # Commit is needed for modifying queries. 
            # If it's a SELECT, commit does nothing (harmless).
            conn.commit()
            
            return result

def init_db():
    """Initialize the database with required tables."""
    # Use context manager
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            pk_def = "SERIAL PRIMARY KEY"
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

            # Create default categories if none exist
            cursor.execute("SELECT COUNT(*) as count FROM categories")
            if cursor.fetchone()['count'] == 0:
                default_categories = [
                    "Food & Dining", "Transportation", "Shopping", 
                    "Utilities", "Entertainment", "Health", 
                    "Travel", "Housing", "Income", "Other"
                ]
                cursor.executemany("INSERT INTO categories (name) VALUES (%s)", [(c,) for c in default_categories])

            # Create budget_targets table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS budget_targets (
                    id {pk_def},
                    month {text_type} NOT NULL,
                    category {text_type} NOT NULL,
                    amount REAL NOT NULL,
                    updated_at {text_type} DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(month, category)
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

            # Create finance_log_items table (one-to-many relationship with finance_logs)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS finance_log_items (
                    id {pk_def},
                    log_id INTEGER NOT NULL REFERENCES finance_logs(id) ON DELETE CASCADE,
                    item_type {text_type} NOT NULL CHECK (item_type IN ('asset', 'debt')),
                    name {text_type} NOT NULL,
                    amount REAL NOT NULL
                )
            """)

            # Create finance_current_items table (for the entry form state)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS finance_current_items (
                    id {pk_def},
                    item_type {text_type} NOT NULL CHECK (item_type IN ('asset', 'debt')),
                    name {text_type} NOT NULL,
                    amount REAL NOT NULL,
                    updated_at {text_type} DEFAULT CURRENT_TIMESTAMP
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

            conn.commit()

# Ensure schema exists on import (safe with IF NOT EXISTS)
init_db()

# ============= TRANSACTION OPERATIONS =============

def add_transaction(date: str, description: str, category: str, 
                   amount: float, account: str, source: str) -> int:
    """Add a new transaction to the database."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            
            cursor.execute(f"""
                INSERT INTO transactions (date, description, category, amount, account, source)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                RETURNING id
            """, (date, description, category, float(amount), account, source))
            transaction_id = cursor.fetchone()['id']
            
            conn.commit()
            st.cache_data.clear()
            return transaction_id

@st.cache_data(ttl=60, show_spinner=False)
def get_transactions(date_from: Optional[str] = None, 
                     date_to: Optional[str] = None,
                     categories: Optional[List[str]] = None,
                     accounts: Optional[List[str]] = None) -> List[Dict]:
    """Get transactions with optional filters."""
    from utils.profiler import scope_timer
    
    with scope_timer('Fetch Transactions'):
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
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
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

@st.cache_data(ttl=60, show_spinner=False)
def get_dashboard_stats() -> Dict:
    """Get summary statistics directly from SQL for the dashboard header."""
    from utils.profiler import scope_timer
    
    with scope_timer('Fetch Dashboard Stats'):
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as count, 
                        COALESCE(SUM(amount), 0) as total_amount, 
                        COUNT(DISTINCT category) as categories 
                    FROM transactions
                """)
                row = cursor.fetchone()
                return dict(row)

def delete_transaction(transaction_id: int) -> bool:
    """Delete a transaction by ID."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            cursor.execute(f"DELETE FROM transactions WHERE id = {ph}", (int(transaction_id),))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            
            if deleted:
                st.cache_data.clear()
            
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
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            cursor.execute(
                f"""
                UPDATE transactions
                SET date = {ph}, description = {ph}, category = {ph}, amount = {ph}, account = {ph}, source = {ph}
                WHERE id = {ph}
                """,
                (date, description, category, float(amount), account, source, int(transaction_id))
            )

            updated = cursor.rowcount > 0
            conn.commit()
            
            if updated:
                st.cache_data.clear()
            
            return updated

def get_date_range() -> Tuple[Optional[str], Optional[str]]:
    """Get the min and max dates from transactions."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Use aliases for safe dict access
            cursor.execute("SELECT MIN(date) as min_date, MAX(date) as max_date FROM transactions")
            row = cursor.fetchone()
            
            if row:
                return row['min_date'], row['max_date']
            return None, None

def get_transaction_months() -> List[str]:
    """Get distinct months (YYYY-MM) that have transactions."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT substr(date, 1, 7) AS month FROM transactions ORDER BY month DESC")
            rows = cursor.fetchall()
            return [row['month'] for row in rows]

# ============= CATEGORY OPERATIONS =============

def add_category(name: str) -> bool:
    """Add a new category."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                ph = get_placeholder()
                cursor.execute(f"INSERT INTO categories (name) VALUES ({ph})", (name,))
                conn.commit()
                return True
    except Exception: # sqlite3.IntegrityError or psycopg2.IntegrityError
        return False

def get_categories() -> List[str]:
    """Get all categories."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name FROM categories ORDER BY name")
            rows = cursor.fetchall()
            categories = [row['name'] for row in rows]
            
            # Ensure "Uncategorized" exists in the list
            if "Uncategorized" not in categories:
                categories.insert(0, "Uncategorized")
                
            return categories

def update_category(old_name: str, new_name: str) -> bool:
    """Update a category name."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                ph = get_placeholder()
                # Update category name
                cursor.execute(f"UPDATE categories SET name = {ph} WHERE name = {ph}", 
                              (new_name, old_name))
                
                # Update all transactions with this category
                cursor.execute(f"UPDATE transactions SET category = {ph} WHERE category = {ph}",
                              (new_name, old_name))
                
                conn.commit()
                return True
    except Exception:
        return False

def delete_category(name: str) -> Tuple[bool, str]:
    """Delete a category if not used in transactions."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            # Check if category is used
            cursor.execute(f"SELECT COUNT(*) as count FROM transactions WHERE category = {ph}", (name,))
            
            count = cursor.fetchone()['count']
                
            if count > 0:
                return False, f"Cannot delete category '{name}' - it's used in {count} transaction(s)"
            
            cursor.execute(f"DELETE FROM categories WHERE name = {ph}", (name,))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            
            if deleted:
                return True, f"Category '{name}' deleted successfully"
            else:
                return False, f"Category '{name}' not found"

# ============= BUDGET OPERATIONS =============

def upsert_budget_target(month: str, category: Optional[str], amount: float) -> bool:
    """Insert or update a monthly budget target for a category or overall."""
    category_value = category if category is not None else OVERALL_BUDGET_CATEGORY
    
    ph = get_placeholder()
    
    return execute_query(
        f"""
        INSERT INTO budget_targets (month, category, amount)
        VALUES ({ph}, {ph}, {ph})
        ON CONFLICT(month, category) DO UPDATE SET
            amount = excluded.amount,
            updated_at = CURRENT_TIMESTAMP
        """,
        (month, category_value, float(amount))
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
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            cursor.execute(f"SELECT category, amount FROM budget_targets WHERE month = {ph}", (month,))
            rows = cursor.fetchall()

            targets: Dict[Optional[str], float] = {}
            for row in rows:
                category = row['category']
                amount = row['amount']
                    
                key = None if category == OVERALL_BUDGET_CATEGORY else category
                targets[key] = amount

            return targets

def get_budget_months() -> List[str]:
    """Get distinct months (YYYY-MM) that have budget targets."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT month FROM budget_targets ORDER BY month DESC")
            rows = cursor.fetchall()
            return [row['month'] for row in rows]



# ============= FINANCE LOG OPERATIONS =============

def add_finance_log(log_date: str, total_assets: float, total_debt: float) -> int:
    """Add a finance log snapshot and return its ID."""
    net_worth = float(total_assets) - float(total_debt)
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            cursor.execute(f"""
                INSERT INTO finance_logs (log_date, total_assets, total_debt, net_worth)
                VALUES ({ph}, {ph}, {ph}, {ph})
                RETURNING id
            """, (log_date, float(total_assets), float(total_debt), net_worth))
            
            log_id = cursor.fetchone()['id']

            conn.commit()
            st.cache_data.clear()
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
    # Ensure inputs are Python floats, not numpy types
    total_assets = float(total_assets)
    total_debt = float(total_debt)
    net_worth = total_assets - total_debt
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            
            try:
                cursor.execute(f"""
                    INSERT INTO finance_logs (log_date, total_assets, total_debt, net_worth)
                    VALUES ({ph}, {ph}, {ph}, {ph})
                    RETURNING id
                """, (log_date, total_assets, total_debt, net_worth))
                log_id = cursor.fetchone()['id']

                if asset_items:
                    cursor.executemany(
                        f"""
                        INSERT INTO finance_log_items (log_id, item_type, name, amount)
                        VALUES ({ph}, 'asset', {ph}, {ph})
                        """,
                        [(log_id, name, float(amount)) for name, amount in asset_items]
                    )

                if debt_items:
                    cursor.executemany(
                        f"""
                        INSERT INTO finance_log_items (log_id, item_type, name, amount)
                        VALUES ({ph}, 'debt', {ph}, {ph})
                        """,
                        [(log_id, name, float(amount)) for name, amount in debt_items]
                    )

                conn.commit()
                st.cache_data.clear()
                return log_id
            except Exception as e:
                conn.rollback()
                print(f"Error adding finance log: {e}")
                raise e

@st.cache_data(show_spinner=False)
def get_finance_logs() -> List[Dict]:
    """Get all finance logs ordered by date ascending."""
    from utils.profiler import scope_timer
    with scope_timer('Fetch Finance Logs'):
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, log_date, total_assets, total_debt, net_worth, created_at
                    FROM finance_logs
                    ORDER BY log_date ASC, id ASC
                """)

                rows = cursor.fetchall()
                return [dict(row) for row in rows]

def get_finance_log_items(log_ids: List[int]) -> List[Dict]:
    """Get all finance log items for the given log IDs."""
    if not log_ids:
        return []

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            # Postgres requires slightly different syntax for IN clause with tuple?
            # No, standard SQL IN (val1, val2) works.
            # Psycopg2 adapts tuple to (val1, val2) automatically with %s.
            
            # But wait, `params` argument in `execute` expects a tuple/list.
            # If we have one placeholder %s and pass a tuple, Psycopg2 adapts it.
            # Let's verify: cursor.execute("SELECT ... IN %s", (tuple(ids),))
            
            # Original code manually constructed placeholders: IN ({placeholders})
            # This is safe and works for both. Let's keep it.
            
            placeholders = ','.join([ph] * len(log_ids))
            
            query = f"""
                SELECT id, log_id, item_type, name, amount
                FROM finance_log_items
                WHERE log_id IN ({placeholders})
                ORDER BY log_id ASC, item_type ASC, name ASC
            """
            
            cursor.execute(query, tuple(log_ids))

            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]

def delete_finance_log(log_id: int) -> bool:
    """Delete a finance log and its related items."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            cursor.execute(f"DELETE FROM finance_log_items WHERE log_id = {ph}", (log_id,))
            cursor.execute(f"DELETE FROM finance_logs WHERE id = {ph}", (log_id,))

            deleted = cursor.rowcount > 0
            conn.commit()
            
            if deleted:
                st.cache_data.clear()

            return deleted

def replace_finance_current_items(item_type: str, items: List[Tuple[str, float]]) -> None:
    """Replace current finance items for a given type (asset or debt)."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
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

def get_finance_current_items(item_type: str) -> List[Dict]:
    """Get current finance items for a given type (asset or debt)."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
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

            return [dict(row) for row in rows]

def update_transaction_category(transaction_id: int, new_category: str) -> bool:
    """Update a transaction's category."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            cursor.execute(
                f"UPDATE transactions SET category = {ph} WHERE id = {ph}",
                (new_category, transaction_id)
            )
            
            updated = cursor.rowcount > 0
            conn.commit()
            
            return updated

# ============= MERCHANT MAPPING OPERATIONS =============

def add_merchant_mapping(merchant_pattern: str, category: str) -> bool:
    """Add or update a merchant pattern to category mapping."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                ph = get_placeholder()
                cursor.execute(f"""
                    INSERT INTO merchant_mappings (merchant_pattern, category)
                    VALUES ({ph}, {ph})
                    ON CONFLICT(merchant_pattern) DO UPDATE SET category = excluded.category
                """, (merchant_pattern.upper(), category))
                conn.commit()
                return True
    except Exception as e:
        print(f"Error adding merchant mapping: {e}")
        return False

def get_merchant_mappings() -> List[Dict]:
    """Get all merchant mappings."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, merchant_pattern, category, created_at, last_used
                FROM merchant_mappings
                ORDER BY last_used DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
def get_merchant_mapping_for_description(description: str) -> Optional[str]:
    """Find a matching merchant mapping for a description. Returns category or None."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Get all patterns
            cursor.execute("SELECT merchant_pattern, category FROM merchant_mappings")
            mappings = [dict(row) for row in cursor.fetchall()]
    
    desc_upper = description.upper()
    
    # Helper to unpack
    def unpack(row):
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
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            cursor.execute(f"DELETE FROM merchant_mappings WHERE merchant_pattern = {ph}", (merchant_pattern.upper(),))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted

def update_merchant_mapping(old_pattern: str, new_pattern: str, category: str) -> bool:
    """Update a merchant mapping."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            cursor.execute(
                f"UPDATE merchant_mappings SET merchant_pattern = {ph}, category = {ph} WHERE merchant_pattern = {ph}",
                (new_pattern.upper(), category, old_pattern.upper())
            )
            
            updated = cursor.rowcount > 0
            conn.commit()
            return updated

def find_similar_transactions(description: str, exclude_id: Optional[int] = None, 
                             similarity_threshold: float = 0.6) -> List[Dict]:
    """
    Find transactions with similar merchant names using fuzzy matching.
    """
    from rapidfuzz import fuzz
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Get all transactions
            cursor.execute("SELECT id, description, category, date, amount FROM transactions")
            rows = cursor.fetchall()
            all_transactions = [dict(row) for row in rows]
    
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
    
    updated_count = 0
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Get all transactions
            cursor.execute("SELECT id, description FROM transactions")
            # Convert to list of dicts to detach from cursor before starting updates
            all_transactions = [dict(row) for row in cursor.fetchall()]
            
            ph = get_placeholder()
            
            for row in all_transactions:
                trans_id = row['id']
                trans_desc = row['description']
                    
                score = fuzz.token_set_ratio(description_pattern.upper(), trans_desc.upper()) / 100.0
                
                if score >= similarity_threshold:
                    cursor.execute(
                        f"UPDATE transactions SET category = {ph} WHERE id = {ph}",
                        (new_category, trans_id)
                    )
                    updated_count += 1
            
            conn.commit()
    
    return updated_count

def update_merchant_mapping_usage(merchant_pattern: str) -> bool:
    """Update the last_used timestamp for a merchant mapping."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            ph = get_placeholder()
            cursor.execute(f"""
                UPDATE merchant_mappings 
                SET last_used = CURRENT_TIMESTAMP 
                WHERE merchant_pattern = {ph}
            """, (merchant_pattern.upper(),))
            
            updated = cursor.rowcount > 0
            conn.commit()
            return updated


def get_merchant_mapping_stats() -> Dict[str, any]:
    """Get statistics about merchant mappings and their usage."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Total mappings
            cursor.execute("SELECT COUNT(*) as count FROM merchant_mappings")
            row = cursor.fetchone()
            total_mappings = row['count']
            
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
            rows = cursor.fetchall()
            
            by_category = {dict(row)['category']: dict(row)['count'] for row in rows}
    
    return {
        'total_mappings': total_mappings,
        'by_category': by_category,
        'recent_mappings': recent
    }
