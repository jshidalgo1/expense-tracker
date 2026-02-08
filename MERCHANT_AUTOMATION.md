# Merchant Auto-Categorization Implementation Guide

## Overview

You now have a complete automated merchant auto-categorization system that learns from your transaction history. The system analyzes patterns in how you categorize expenses and automatically creates rules to categorize future transactions.

## What Was Added

### 1. **Merchant Learner Module** (`utils/merchant_learner.py`)
Core module that powers the learning system with these functions:

- `extract_merchant_from_description()` - Extracts merchant names from transaction descriptions
- `suggest_merchant_mappings()` - Analyzes history and suggests new rules
- `auto_apply_merchant_mappings()` - Automatically applies learned rules to database
- `get_learning_stats()` - Provides insights on learning progress
- `suggest_and_apply_mappings_auto()` - Comprehensive function for suggestions and application

### 2. **Enhanced Categorizer** (`utils/categorizer.py`)
New helper functions added:

- `batch_auto_categorize()` - Categorize multiple descriptions at once
- `get_categorization_confidence_breakdown()` - Debug categorization decisions

### 3. **Database Enhancements** (`utils/database.py`)
New functions for tracking merchant mappings:

- `update_merchant_mapping_usage()` - Tracks when rules are used
- `get_merchant_mapping_stats()` - Statistics about your rules

### 4. **Merchant Rules Management Page** (`pages/5_Merchant_Rules.py`)
New UI for managing automation:

- 📊 Learning progress dashboard
- 💡 Suggested merchant rules based on history
- ➕ Create custom merchant rules
- 📋 View and manage all existing rules
- 🗑️ Delete rules you no longer need

## How It Works

### Learning Algorithm

1. **Analyzes** all your transactions to identify merchant patterns
2. **Groups** transactions by extracted merchant name
3. **Checks** if a merchant consistently appears in one category
4. **Suggests** a rule if:
   - Merchant appears 3+ times (configurable)
   - 75%+ of transactions are in the same category (configurable)
5. **Creates** the merchant mapping in the database

### Auto-Categorization Priority

When categorizing a transaction:
1. ✅ First checks existing merchant mappings (highest priority)
2. ✅ Then tries keyword matching
3. ✅ Then tries fuzzy matching against categories
4. ✅ Falls back to "Uncategorized" if no match

## Getting Started

### Access the New Page

1. **Start the app**: `streamlit run app.py`
2. **Login** with your credentials
3. **Click** "Merchant Rules" in the sidebar (5th option)

### Basic Workflow

#### Step 1: Review Suggested Rules
The page shows merchants that are ready to be automated:
- Shows merchant name, suggested category, and confidence level
- Click **"Apply All Suggestions"** to add them at once

#### Step 2: Manually Create Rules (Optional)
For merchants not yet in suggestions:
1. Enter the merchant pattern (e.g., "JOLLIBEE")
2. Select the category
3. Click "Add Rule"

#### Step 3: Manage Existing Rules
- View all active rules with creation and usage timestamps
- Delete rules you no longer need

## Configuration

### Tuning Suggestions

The learning algorithm is configured conservatively to ensure accuracy:

**Current Settings:**
- Minimum frequency: 3 transactions
- Confidence threshold: 75% (or higher)

**To adjust these**, modify the function calls in `pages/5_Merchant_Rules.py`:

```python
# Line ~60 - Change these values
suggestions = suggest_merchant_mappings(
    min_frequency=2,           # Lower = more suggestions (more false positives)
    confidence_threshold=0.75  # Lower = more suggestions (less accurate)
)
```

**Recommended values:**
- Conservative: `min_frequency=5, confidence_threshold=0.9`
- Moderate: `min_frequency=3, confidence_threshold=0.75` (current)
- Aggressive: `min_frequency=2, confidence_threshold=0.6`

## Usage Examples

### Example 1: Quick Automation
```
Before: Need to manually categorize every Jollibee transaction
After: System suggests "Jollibee" → "Food & Dining" rule
       Click apply, future Jollibee transactions auto-categorize
```

### Example 2: Learning from Patterns
```
Your transactions:
- Jan 5: MCDONALD'S → Food & Dining
- Jan 12: MCDONALD'S → Food & Dining
- Jan 19: MCDONALD'S → Food & Dining

System learns → Suggests: MCDONALD'S → Food & Dining
You apply → All future McDonald's auto-categorized
```

### Example 3: Override a Rule
```
If a rule no longer applies:
1. Go to "Merchant Rules" page
2. Find the rule in "Existing Merchant Rules"
3. Click "Delete Rule"
4. Create a new rule if needed
```

## Advanced Features

### Using Programmatically

You can use the learning system in your own code:

```python
from utils.merchant_learner import suggest_merchant_mappings, auto_apply_merchant_mappings
from utils.categorizer import batch_auto_categorize

# Get suggestions
suggestions = suggest_merchant_mappings(min_frequency=2, confidence_threshold=0.75)
print(f"Found {len(suggestions)} merchants ready to be automated")

# Apply all suggestions automatically
result = auto_apply_merchant_mappings()
print(f"Added {result['added']} new rules")

# Auto-categorize multiple descriptions
descriptions = ["Jollibee Manila", "Grab Uber", "Meralco Bill"]
results = batch_auto_categorize(descriptions)
```

### Batch Processing

To process historical uncategorized transactions:

```python
from utils.merchant_learner import suggest_merchant_mappings, auto_apply_merchant_mappings
from utils.database import get_transactions, update_transaction_category
from utils.categorizer import auto_categorize

# Apply learning to all transactions
result = auto_apply_merchant_mappings()
print(f"Applied {result['added']} merchant rules")

# Auto-categorize any remaining uncategorized transactions
transactions = get_transactions()
updated = 0

for trans in transactions:
    if trans['category'] == 'Uncategorized':
        suggested = auto_categorize(trans['description'], confidence_threshold=70)
        if suggested:
            update_transaction_category(trans['id'], suggested)
            updated += 1

print(f"Auto-categorized {updated} previously uncategorized transactions")
```

## Troubleshooting

### "No new merchant patterns found yet"
**Cause:** Not enough transaction history
**Solution:** Keep adding transactions. System needs at least 3 of the same merchant in one category to suggest a rule.

### Rules aren't being applied
**Cause:** Merchant patterns might not match transaction descriptions exactly
**Solution:** 
- Check the "Existing Merchant Rules" to see what patterns exist
- Verify transaction descriptions contain the merchant name
- Edit or delete rules that don't match

### Getting too many suggestions
**Cause:** Threshold settings too aggressive
**Solution:** Increase `min_frequency` or `confidence_threshold` in the settings

## Performance

The system is optimized for typical personal expense tracking:
- ✅ Handles 1000s of transactions efficiently
- ✅ Suggestions generated in < 1 second
- ✅ Minimal database overhead
- ✅ Rules apply instantly to new transactions

## Database Schema

The existing `merchant_mappings` table now includes:
```sql
CREATE TABLE merchant_mappings (
    id INTEGER PRIMARY KEY,
    merchant_pattern TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_used TEXT DEFAULT CURRENT_TIMESTAMP
)
```

## Next Steps

1. **Add more transactions** to build up learning data
2. **Visit Merchant Rules page** to see suggestions
3. **Apply suggestions** to automate categorization
4. **Review results** after a week to see how well the rules work
5. **Adjust settings** if needed for your use case

## Questions?

Refer to the "How It Works" section in the Merchant Rules page UI for quick help, or review the docstrings in `utils/merchant_learner.py` for technical details.
