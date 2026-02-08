# Quick Reference: Merchant Auto-Categorization

## Files Added/Modified

### New Files
```
✅ utils/merchant_learner.py          - Core learning engine
✅ pages/5_Merchant_Rules.py          - UI for managing rules
✅ MERCHANT_AUTOMATION.md              - Full documentation
```

### Modified Files
```
✅ utils/categorizer.py              - Added batch processing functions
✅ utils/database.py                 - Added tracking functions
```

## Key Functions

### In `merchant_learner.py`
```python
suggest_merchant_mappings(min_frequency=3, confidence_threshold=0.8)
# → Returns list of (merchant, category, frequency, confidence)

auto_apply_merchant_mappings(min_frequency=3, confidence_threshold=0.8)
# → Adds all suggested rules to database
# → Returns {'added': N, 'failed': N, 'skipped': N}

get_learning_stats()
# → Returns {'total_transactions', 'merchant_mappings', 'coverage_percentage', ...}
```

### In `categorizer.py`
```python
batch_auto_categorize(descriptions, confidence_threshold=60.0)
# → Categorize multiple descriptions at once

get_categorization_confidence_breakdown(description)
# → Debug: see scores for all categories
```

## How to Use

### Via UI
1. Open app: `streamlit run app.py`
2. Navigate to: **🏪 Merchant Rules** (5th sidebar option)
3. Choose action:
   - **Apply All Suggestions** - Automate suggested merchants
   - **Create Custom Rule** - Add your own merchant patterns
   - **Delete Rule** - Remove rules no longer needed

### Via Code
```python
from utils.merchant_learner import suggest_merchant_mappings, auto_apply_merchant_mappings

# See what can be automated
suggestions = suggest_merchant_mappings()
print(f"{len(suggestions)} merchants ready for automation")

# Automate them
result = auto_apply_merchant_mappings()
print(f"Added {result['added']} rules")
```

## How It Works

```
Your Transaction History
        ↓
    [ANALYZE]
Extract merchant names & group by category
        ↓
   [PATTERN CHECK]
Find merchants appearing 3+ times with 75%+ confidence
        ↓
  [SUGGESTION]
Show rules ready to apply
        ↓
   [APPLY/LEARN]
Add rules to database
        ↓
Future Transactions Auto-Categorized ✅
```

## Configuration

**Current defaults** (conservative, high accuracy):
- Min transactions: 3
- Confidence: 75%

**To change**, edit `pages/5_Merchant_Rules.py` line ~60:
```python
suggest_merchant_mappings(min_frequency=3, confidence_threshold=0.75)
```

**Options:**
- `min_frequency=2, confidence_threshold=0.60` - Aggressive (more suggestions, less accurate)
- `min_frequency=3, confidence_threshold=0.75` - Balanced (current)
- `min_frequency=5, confidence_threshold=0.90` - Conservative (fewer suggestions, very accurate)

## Examples

### Example Transaction Flow
```
1. You add: "Jollibee Robinsons" → Category: "Food & Dining"
2. You add: "JOLLIBEE EDSA" → Category: "Food & Dining"
3. You add: "Jollibee IT Park" → Category: "Food & Dining"

System learns: Merchant "JOLLIBEE" → "Food & Dining"

4. You add: "Jollibee PBCom" 
   ✅ Auto-categorized as "Food & Dining" (no action needed!)
```

### Example Manual Rule
```
Pattern: "MCDONALD'S"
Category: "Food & Dining"

Now matches:
- "MCDONALD'S GCM MALL"
- "MCDO ROCKWELL"
- "MCDONALD'S ERMITA"
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No suggestions appear | Add more transactions (need 3+ per merchant) |
| Rule not matching | Check merchant name in transaction description |
| Too many suggestions | Increase `min_frequency` or `confidence_threshold` |
| Wrong categorization | Delete rule and create a new one |

## Performance

- Suggestions generated: < 1 second
- Rules applied: Instant
- Coverage: Grows as you add transactions

## Data Privacy

All data stays local in `data/expenses.db` - no cloud uploads or external APIs used.

---

**Next Step:** Open the app and visit the **🏪 Merchant Rules** page to start automating! 🚀
