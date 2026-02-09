import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "expenses.db")
OVERALL_BUDGET_CATEGORY = "__overall__"

def get_connection():
    """Create a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
    
    # Create transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            account TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create categories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    
    # Create bank_passwords table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_passwords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create merchant_mappings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS merchant_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_pattern TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_used TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create budget_targets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (month, category)
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
    
    cursor.execute("""
        INSERT INTO transactions (date, description, category, amount, account, source)
        VALUES (?, ?, ?, ?, ?, ?)
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
    
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []
    
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    
    if categories:
        placeholders = ','.join('?' * len(categories))
        query += f" AND category IN ({placeholders})"
        params.extend(categories)
    
    if accounts:
        placeholders = ','.join('?' * len(accounts))
        query += f" AND account IN ({placeholders})"
        params.extend(accounts)
    
    query += " ORDER BY date DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def delete_transaction(transaction_id: int) -> bool:
    """Delete a transaction by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted

def delete_all_transactions() -> bool:
    """Delete all transactions from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM transactions")
    
    conn.commit()
    conn.close()
    
    return True

def get_date_range() -> Tuple[Optional[str], Optional[str]]:
    """Get the min and max dates from transactions."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT MIN(date), MAX(date) FROM transactions")
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0] and row[1]:
        return row[0], row[1]
    return None, None

def get_transaction_months() -> List[str]:
    """Get distinct months (YYYY-MM) that have transactions."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT substr(date, 1, 7) AS month FROM transactions ORDER BY month DESC")
    rows = cursor.fetchall()
    conn.close()

    return [row['month'] for row in rows]

# ============= CATEGORY OPERATIONS =============

def add_category(name: str) -> bool:
    """Add a new category."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def get_categories() -> List[str]:
    """Get all categories."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM categories ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    
    return [row['name'] for row in rows]

def update_category(old_name: str, new_name: str) -> bool:
    """Update a category name."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Update category name
        cursor.execute("UPDATE categories SET name = ? WHERE name = ?", 
                      (new_name, old_name))
        
        # Update all transactions with this category
        cursor.execute("UPDATE transactions SET category = ? WHERE category = ?",
                      (new_name, old_name))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def delete_category(name: str) -> Tuple[bool, str]:
    """Delete a category if not used in transactions."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if category is used
    cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE category = ?", (name,))
    count = cursor.fetchone()['count']
    
    if count > 0:
        conn.close()
        return False, f"Cannot delete category '{name}' - it's used in {count} transaction(s)"
    
    cursor.execute("DELETE FROM categories WHERE name = ?", (name,))
    
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

    return execute_query(
        """
        INSERT INTO budget_targets (month, category, amount)
        VALUES (?, ?, ?)
        ON CONFLICT(month, category) DO UPDATE SET
            amount = excluded.amount,
            updated_at = CURRENT_TIMESTAMP
        """,
        (month, category_value, amount)
    )

def delete_budget_target(month: str, category: Optional[str]) -> bool:
    """Delete a monthly budget target for a category or overall."""
    category_value = category if category is not None else OVERALL_BUDGET_CATEGORY
    return execute_query(
        "DELETE FROM budget_targets WHERE month = ? AND category = ?",
        (month, category_value)
    )

def get_budget_targets(month: str) -> Dict[Optional[str], float]:
    """Get all budget targets for a given month."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT category, amount FROM budget_targets WHERE month = ?", (month,))
    rows = cursor.fetchall()
    conn.close()

    targets: Dict[Optional[str], float] = {}
    for row in rows:
        category = row['category']
        key = None if category == OVERALL_BUDGET_CATEGORY else category
        targets[key] = row['amount']

    return targets

def get_budget_months() -> List[str]:
    """Get distinct months (YYYY-MM) that have budget targets."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT month FROM budget_targets ORDER BY month DESC")
    rows = cursor.fetchall()
    conn.close()

    return [row['month'] for row in rows]

# ============= BANK PASSWORD OPERATIONS =============

def add_bank_password(bank_name: str, password: str) -> bool:
    """Add or update a bank password."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO bank_passwords (bank_name, password)
        VALUES (?, ?)
        ON CONFLICT(bank_name) DO UPDATE SET password = ?
    """, (bank_name, password, password))
    
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
    
    return [dict(row) for row in rows]

def get_bank_password(bank_name: str) -> Optional[str]:
    """Get password for a specific bank."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT password FROM bank_passwords WHERE bank_name = ?", (bank_name,))
    row = cursor.fetchone()
    conn.close()
    
    return row['password'] if row else None

def update_bank_password(bank_name: str, new_password: str) -> bool:
    """Update a bank password."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE bank_passwords SET password = ? WHERE bank_name = ?",
                  (new_password, bank_name))
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return updated

def delete_bank_password(bank_name: str) -> bool:
    """Delete a bank password."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM bank_passwords WHERE bank_name = ?", (bank_name,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted

def update_transaction_category(transaction_id: int, new_category: str) -> bool:
    """Update a transaction's category."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE transactions SET category = ? WHERE id = ?",
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
    
    try:
        # Try to insert, or update if exists
        cursor.execute("""
            INSERT INTO merchant_mappings (merchant_pattern, category)
            VALUES (?, ?)
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
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def get_merchant_mapping_for_description(description: str) -> Optional[str]:
    """Find a matching merchant mapping for a description. Returns category or None."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all patterns
    cursor.execute("SELECT merchant_pattern, category FROM merchant_mappings")
    mappings = cursor.fetchall()
    conn.close()
    
    desc_upper = description.upper()
    
    # Try exact match first
    for pattern, category in mappings:
        if pattern in desc_upper:
            return category
    
    # Try fuzzy match (substring match on key parts)
    for pattern, category in mappings:
        # Split pattern into words and check if all appear in description
        pattern_parts = pattern.split()
        if len(pattern_parts) > 0 and all(part in desc_upper for part in pattern_parts):
            return category
    
    return None

def delete_merchant_mapping(merchant_pattern: str) -> bool:
    """Delete a merchant mapping."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM merchant_mappings WHERE merchant_pattern = ?", (merchant_pattern.upper(),))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted

def update_merchant_mapping(old_pattern: str, new_pattern: str, category: str) -> bool:
    """Update a merchant mapping."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE merchant_mappings SET merchant_pattern = ?, category = ? WHERE merchant_pattern = ?",
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
    
    Args:
        description: The transaction description to match against
        exclude_id: Transaction ID to exclude from results
        similarity_threshold: Minimum similarity score (0-1)
    
    Returns:
        List of similar transactions
    """
    from rapidfuzz import fuzz
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all transactions
    cursor.execute("SELECT id, description, category, date, amount FROM transactions")
    all_transactions = [dict(row) for row in cursor.fetchall()]
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
    
    Returns:
        Number of transactions updated
    """
    from rapidfuzz import fuzz
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all transactions
    cursor.execute("SELECT id, description FROM transactions")
    all_transactions = cursor.fetchall()
    
    updated_count = 0
    
    for trans_id, trans_desc in all_transactions:
        score = fuzz.token_set_ratio(description_pattern.upper(), trans_desc.upper()) / 100.0
        
        if score >= similarity_threshold:
            cursor.execute(
                "UPDATE transactions SET category = ? WHERE id = ?",
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
    
    cursor.execute("""
        UPDATE merchant_mappings 
        SET last_used = CURRENT_TIMESTAMP 
        WHERE merchant_pattern = ?
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
