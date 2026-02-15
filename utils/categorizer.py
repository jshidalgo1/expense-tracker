from rapidfuzz import fuzz, process
from typing import List, Optional, Tuple, Dict
from utils.database import get_categories, add_category, get_merchant_mapping_for_description

# Common keywords for automatic categorization
CATEGORY_KEYWORDS = {
    "Food & Dining": [
        "restaurant", "cafe", "coffee", "food", "dining", "mcdonald", "jollibee",
        "starbucks", "pizza", "burger", "kitchen", "bistro", "grill", "bakery",
        "fastfood", "delivery", "grab food", "foodpanda"
    ],
    "Transportation": [
        "grab", "uber", "taxi", "transport", "gas", "gasoline", "petron", "shell",
        "caltex", "parking", "toll", "lrt", "mrt", "bus", "jeep", "angkas"
    ],
    "Shopping": [
        "mall", "store", "shop", "lazada", "shopee", "sm", "robinsons", "ayala",
        "department", "retail", "market", "supermarket", "grocery"
    ],
    "Utilities": [
        "meralco", "maynilad", "pldt", "globe", "smart", "electric", "water",
        "internet", "phone", "bill", "utility", "converge", "skycable"
    ],
    "Entertainment": [
        "cinema", "movie", "netflix", "spotify", "youtube", "game", "gaming",
        "concert", "theater", "entertainment", "gym", "fitness"
    ],
    "Healthcare": [
        "hospital", "clinic", "doctor", "pharmacy", "medicine", "medical",
        "health", "dental", "mercury drug", "watsons", "southstar"
    ],
    "Bills & Fees": [
        "fee", "charge", "annual", "membership", "subscription", "insurance",
        "payment", "installment", "loan", "credit card"
    ]
}

def suggest_category(description: str, existing_categories: Optional[List[str]] = None) -> Tuple[str, float]:
    """
    Suggest a category for a transaction based on description.
    
    Returns:
        Tuple of (suggested_category, confidence_score)
        confidence_score is between 0 and 100
    """
    if existing_categories is None:
        existing_categories = get_categories()
    
    description_lower = description.lower()
    
    # First, try keyword matching
    best_keyword_match = None
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in description_lower:
                best_keyword_match = category
                break
        if best_keyword_match:
            break
    
    # If we have existing categories, try fuzzy matching
    if existing_categories:
        # Try to match against existing categories
        result = process.extractOne(
            description,
            existing_categories,
            scorer=fuzz.token_set_ratio
        )
        
        if result:
            matched_category, score, _ = result
            
            # If keyword match exists and fuzzy match score is low, prefer keyword
            if best_keyword_match and score < 60:
                return best_keyword_match, 75.0
            
            # If fuzzy match is strong, use it
            if score >= 60:
                return matched_category, float(score)
    
    # If keyword match found but no strong fuzzy match
    if best_keyword_match:
        return best_keyword_match, 75.0
    
    # Default to "Uncategorized" with low confidence
    return "Uncategorized", 30.0

def auto_categorize(description: str, confidence_threshold: float = 60.0) -> Optional[str]:
    """
    Automatically categorize a transaction if confidence is above threshold.
    
    Args:
        description: Transaction description
        confidence_threshold: Minimum confidence to auto-assign (default 60%)
    
    Returns:
        Category name if confident enough, None otherwise
    """
    # First, check if there's a merchant mapping for this description
    mapped_category = get_merchant_mapping_for_description(description)
    if mapped_category:
        return mapped_category
    
    existing_categories = get_categories()
    suggested_category, confidence = suggest_category(description, existing_categories)
    
    if confidence >= confidence_threshold:
        # user_request: strictly stick to existing categories
        if suggested_category in existing_categories:
            return suggested_category
    
    return None

def get_or_create_category(category_name: str) -> str:
    """
    Get existing category or create new one if it doesn't exist.
    
    Returns:
        The category name (normalized)
    """
    existing_categories = get_categories()
    
    # Check if category already exists (case-insensitive)
    for existing in existing_categories:
        if existing.lower() == category_name.lower():
            return existing
    
    # Create new category
    add_category(category_name)
    return category_name


def batch_auto_categorize(descriptions: List[str], confidence_threshold: float = 60.0) -> Dict[str, Optional[str]]:
    """
    Auto-categorize multiple descriptions at once.
    
    Args:
        descriptions: List of transaction descriptions
        confidence_threshold: Minimum confidence to auto-assign
        
    Returns:
        Dictionary mapping description -> suggested_category (or None)
    """
    results = {}
    for desc in descriptions:
        results[desc] = auto_categorize(desc, confidence_threshold)
    return results


def get_categorization_confidence_breakdown(description: str) -> Dict[str, float]:
    """
    Get confidence scores for all potential categories.
    Useful for debugging categorization decisions.
    
    Args:
        description: Transaction description
        
    Returns:
        Dictionary of category -> confidence_score
    """
    description_lower = description.lower()
    scores = {}
    
    # Score based on keyword matches
    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = sum(1 for keyword in keywords if keyword in description_lower)
        scores[category] = min(100, matches * 30)  # Each keyword adds 30 points
    
    return dict(sorted(scores.items(), key=lambda x: -x[1]))
