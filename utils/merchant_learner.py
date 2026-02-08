"""
Merchant Learning Module
Automatically learns and suggests merchant-to-category mappings from historical data.
"""

from typing import List, Dict, Tuple, Optional
from utils.database import (
    get_transactions,
    get_merchant_mappings,
    add_merchant_mapping
)


def extract_merchant_from_description(description: str) -> str:
    """
    Extract merchant name from transaction description.
    
    Removes common stop words and returns the merchant identifier.
    
    Args:
        description: Full transaction description
        
    Returns:
        Extracted merchant name (uppercase)
    """
    stop_words = {
        'the', 'at', 'from', 'in', 'on', 'a', 'an', 'and', 'or', 'by',
        'to', 'for', 'with', 'of', 'via', 'through', 'transaction', 'payment'
    }
    
    words = description.lower().split()
    merchant_words = [w.strip() for w in words 
                     if w.strip() not in stop_words and len(w.strip()) > 2]
    
    # Keep first 3-4 words as merchant name
    merchant = ' '.join(merchant_words[:4]) if merchant_words else description
    return merchant.upper()


def suggest_merchant_mappings(min_frequency: int = 3, 
                             confidence_threshold: float = 0.8) -> List[Tuple[str, str, int, float]]:
    """
    Analyze historical transactions and suggest new merchant mappings.
    
    Looks at transactions where the same merchant appears multiple times with
    the same category and suggests rules to auto-categorize future transactions.
    
    Args:
        min_frequency: Minimum number of times a merchant must appear to be suggested
        confidence_threshold: Minimum confidence (0-1) to suggest a mapping
        
    Returns:
        List of (merchant_pattern, suggested_category, frequency, confidence)
        sorted by frequency (descending)
    """
    transactions = get_transactions()
    existing_mappings = {m['merchant_pattern']: m['category'] 
                        for m in get_merchant_mappings()}
    
    merchant_categories: Dict[str, Dict[str, int]] = {}
    
    # Analyze all transactions
    for trans in transactions:
        merchant = extract_merchant_from_description(trans['description'])
        
        # Skip if already has a mapping
        if merchant in existing_mappings:
            continue
        
        if merchant not in merchant_categories:
            merchant_categories[merchant] = {}
        
        category = trans['category']
        if category != 'Uncategorized':  # Skip uncategorized
            merchant_categories[merchant][category] = \
                merchant_categories[merchant].get(category, 0) + 1
    
    # Generate suggestions with high confidence
    suggestions = []
    for merchant, categories in merchant_categories.items():
        if not merchant or len(merchant) < 3:
            continue
        
        total = sum(categories.values())
        if total >= min_frequency:
            # Use most common category
            best_category, count = max(categories.items(), key=lambda x: x[1])
            confidence = count / total
            
            if confidence >= confidence_threshold:
                suggestions.append((merchant, best_category, total, confidence))
    
    # Sort by frequency (descending)
    return sorted(suggestions, key=lambda x: -x[2])


def auto_apply_merchant_mappings(min_frequency: int = 3,
                                confidence_threshold: float = 0.8) -> Dict[str, int]:
    """
    Automatically apply learned merchant mappings to the database.
    
    Args:
        min_frequency: Minimum frequency threshold
        confidence_threshold: Minimum confidence threshold
        
    Returns:
        Dictionary with statistics: {
            'added': count of new mappings added,
            'skipped': count of suggestions skipped,
            'failed': count of add operations that failed
        }
    """
    suggestions = suggest_merchant_mappings(min_frequency, confidence_threshold)
    
    stats = {
        'added': 0,
        'skipped': 0,
        'failed': 0
    }
    
    for merchant, category, frequency, confidence in suggestions:
        try:
            if add_merchant_mapping(merchant, category):
                stats['added'] += 1
            else:
                stats['failed'] += 1
        except Exception as e:
            print(f"Error adding mapping for {merchant}: {e}")
            stats['failed'] += 1
    
    return stats


def get_learning_stats() -> Dict:
    """
    Get statistics about merchant learning progress.
    
    Returns:
        Dictionary containing various learning metrics
    """
    transactions = get_transactions()
    mappings = get_merchant_mappings()
    
    total_transactions = len(transactions)
    uncategorized = sum(1 for t in transactions if t['category'] == 'Uncategorized')
    categorized = total_transactions - uncategorized
    
    # Count transactions covered by merchant mappings
    covered_by_mapping = 0
    for trans in transactions:
        merchant = extract_merchant_from_description(trans['description'])
        if any(m['merchant_pattern'] == merchant for m in mappings):
            covered_by_mapping += 1
    
    suggestions = suggest_merchant_mappings()
    
    return {
        'total_transactions': total_transactions,
        'categorized': categorized,
        'uncategorized': uncategorized,
        'merchant_mappings': len(mappings),
        'pending_suggestions': len(suggestions),
        'transactions_covered_by_mapping': covered_by_mapping,
        'coverage_percentage': (covered_by_mapping / total_transactions * 100) if total_transactions > 0 else 0
    }


def suggest_and_apply_mappings_auto(min_frequency: int = 3,
                                   confidence_threshold: float = 0.8,
                                   auto_apply: bool = False) -> Dict:
    """
    Comprehensive function to suggest and optionally apply merchant mappings.
    
    Args:
        min_frequency: Minimum frequency threshold
        confidence_threshold: Minimum confidence threshold
        auto_apply: If True, automatically apply all suggestions
        
    Returns:
        Dictionary with suggestions and application results
    """
    suggestions = suggest_merchant_mappings(min_frequency, confidence_threshold)
    
    result = {
        'suggestions': suggestions,
        'suggestion_count': len(suggestions),
        'applied': {}
    }
    
    if auto_apply and suggestions:
        result['applied'] = auto_apply_merchant_mappings(min_frequency, confidence_threshold)
    
    return result
