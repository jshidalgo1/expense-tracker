import pytesseract
from PIL import Image
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime

def extract_text_from_image(image_file) -> str:
    """
    Extract text from an image file using Tesseract OCR.
    Uses PSM 6 (Assume a single uniform block of text) which works well for
    row-by-row transaction lists.
    """
    try:
        image = Image.open(image_file)
        # --psm 6: Assume a single uniform block of text.
        text = pytesseract.image_to_string(image, config='--psm 6')
        return text
    except Exception as e:
        print(f"Error during OCR: {e}")
        return ""

def parse_bpi_transactions(text: str) -> List[Dict]:
    """
    Parse BPI transactions.
    Format: "Nov 28 Dec 1 Description 1,234.56" (Double Date)
    or "Dec 1 Description 50.00" (Single Date)
    """
    transactions = []
    lines = text.split('\n')
    current_year = datetime.now().year
    
    amount_re = r'(?:PHP\s*)?([-\d,]+\.\d{2})'
    # Month Name (3+ chars) + Day (1-2 digits)
    date_part_re = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}'

    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue
            
        # 1. Check for amount at end
        amount_match = re.search(amount_re + r'\s*$', clean_line)
        if not amount_match:
            continue
            
        amount_str = amount_match.group(1)
        remaining_text = clean_line[:amount_match.start()].strip()
        
        try:
            amount = float(amount_str.replace(',', ''))
        except ValueError:
            continue
            
        # 2. Check for dates at the beginning
        date_matches = list(re.finditer(date_part_re, remaining_text, re.IGNORECASE))
        
        if not date_matches:
            continue
            
        # Take the first date found as the transaction date
        first_date_match = date_matches[0]
        date_str = first_date_match.group(0)
        
        # Description is after the last date
        last_date_match = date_matches[-1]
        description = remaining_text[last_date_match.end():].strip()
        
        try:
            # Parse text date
            date_str_clean = date_str.replace('.', '')
            parsed_date = None
            
            for fmt in ['%b %d', '%B %d']:
                try:
                    dt = datetime.strptime(date_str_clean, fmt)
                    parsed_date = dt.replace(year=current_year)
                    break
                except ValueError:
                    continue
            
            if parsed_date:
                # Year rollover logic: if current is Jan and trans is Dec, use prev year
                now = datetime.now()
                if now.month == 1 and parsed_date.month == 12:
                    parsed_date = parsed_date.replace(year=now.year - 1)
                
                formatted_date = parsed_date.strftime('%Y-%m-%d')
                
                transactions.append({
                    'date': formatted_date,
                    'description': description,
                    'amount': amount
                })
        except Exception:
            continue
            
    return transactions

def parse_ub_transactions(text: str) -> List[Dict]:
    """
    Parse UnionBank transactions.
    Format: "01/19/26 01/20/26 Description 1,234.56" (Double Date MM/DD/YY)
    """
    transactions = []
    lines = text.split('\n')
    
    amount_re = r'(?:PHP\s*)?([-\d,]+\.\d{2})'
    # MM/DD/YY
    date_part_re = r'\d{2}/\d{2}/\d{2}'

    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue
            
        # 1. Check for amount at end
        amount_match = re.search(amount_re + r'\s*$', clean_line)
        if not amount_match:
            continue
            
        amount_str = amount_match.group(1)
        remaining_text = clean_line[:amount_match.start()].strip()
        
        try:
            amount = float(amount_str.replace(',', ''))
        except ValueError:
            continue
            
        # 2. Check for dates at the beginning
        date_matches = list(re.finditer(date_part_re, remaining_text))
        
        if not date_matches:
            continue
            
        first_date_match = date_matches[0]
        date_str = first_date_match.group(0)
        
        last_date_match = date_matches[-1]
        description = remaining_text[last_date_match.end():].strip()
        
        try:
            parsed_date = datetime.strptime(date_str, '%m/%d/%y')
            # 2-digit year is handled by strptime (mapping 00-68 to 2000-2068, 69-99 to 1969-1999)
            formatted_date = parsed_date.strftime('%Y-%m-%d')
            
            transactions.append({
                'date': formatted_date,
                'description': description,
                'amount': amount
            })
        except Exception:
            continue
            
    return transactions

def extract_transactions_from_image(image_file: str, bank_name: str = "") -> Tuple[bool, List[Dict], Optional[str]]:
    """
    Main entry point for image-based transaction extraction.
    Args:
        image_file: Path to image
        bank_name: Name of the bank (e.g. "BPI", "UnionBank")
    """
    try:
        text = extract_text_from_image(image_file)
        if not text:
            return False, [], "No text could be extracted from the image."
            
        transactions = []
        
        # Normalize bank name for checking
        bank_norm = bank_name.lower().replace(" ", "")
        
        if "unionbank" in bank_norm or "ub" in bank_norm:
            transactions = parse_ub_transactions(text)
        elif "bpi" in bank_norm:
            transactions = parse_bpi_transactions(text)
        else:
            # Fallback: Try both or use a generic approach?
            # Let's try matching patterns:
            # If text has slashes in dates, try UB
            if re.search(r'\d{2}/\d{2}/\d{2}', text):
                transactions = parse_ub_transactions(text)
            else:
                # Default to BPI style (Month Name)
                transactions = parse_bpi_transactions(text)
        
        if not transactions:
            return False, [], f"Text extracted but no transactions found matching extraction logic for {bank_name or 'unknown bank'}."
            
        return True, transactions, None
        
    except Exception as e:
        return False, [], f"Error processing image: {str(e)}"
