import pdfplumber
import pikepdf
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import tempfile
import os

# OCR imports (optional, will gracefully degrade if not available)
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

def unlock_pdf(pdf_path: str, password: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Unlock a password-protected PDF.
    
    Returns:
        Tuple of (success, unlocked_pdf_path, error_message)
    """
    try:
        # Try to open with pikepdf
        with pikepdf.open(pdf_path, password=password) as pdf:
            # Create temporary file for unlocked PDF
            temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf')
            os.close(temp_fd)
            
            # Save unlocked PDF
            pdf.save(temp_path)
            
            return True, temp_path, None
    except pikepdf.PasswordError:
        return False, None, "Incorrect password"
    except Exception as e:
        return False, None, f"Error unlocking PDF: {str(e)}"

def extract_text_from_pdf(pdf_path: str, password: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Extract text from PDF (with optional password).
    Reads pages in reverse order since transactions are typically on last pages.
    
    Returns:
        Tuple of (success, extracted_text, error_message)
    """
    unlocked_path = None
    
    try:
        # If no password provided, quickly detect encrypted PDFs
        if not password:
            try:
                with pikepdf.open(pdf_path):
                    pass
            except pikepdf.PasswordError:
                return False, None, "PDF is password-protected. Please enter the password."

        # If password provided, unlock first
        if password:
            success, unlocked_path, error = unlock_pdf(pdf_path, password)
            if not success:
                return False, None, error
            pdf_to_read = unlocked_path
        else:
            pdf_to_read = pdf_path
        
        # Extract text using pdfplumber
        # Read pages in REVERSE order (last pages first) since transactions are usually at the end
        text = ""
        with pdfplumber.open(pdf_to_read) as pdf:
            # Reverse the page order
            for page in reversed(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        # Clean up temporary file if created
        if unlocked_path and os.path.exists(unlocked_path):
            os.remove(unlocked_path)
        
        # Check if text is garbled or empty
        # Garbled text often contains (cid:XXX) patterns or has very low alphanumeric ratio
        is_garbled = (
            not text.strip() or 
            '(cid:' in text or  # Common in garbled PDFs
            len([c for c in text if c.isalnum()]) / max(len(text), 1) < 0.3  # Less than 30% alphanumeric
        )
        
        if is_garbled:
            # Try OCR as fallback
            if OCR_AVAILABLE:
                return extract_text_with_ocr(pdf_path, password)
            else:
                return False, None, "No readable text found in PDF. This appears to be an image-based PDF. Please install OCR dependencies (pytesseract, pdf2image)."
        
        return True, text, None
        
    except Exception as e:
        # Clean up temporary file if created
        if unlocked_path and os.path.exists(unlocked_path):
            os.remove(unlocked_path)
        
        return False, None, f"Error reading PDF: {str(e)}"

def extract_text_with_ocr(pdf_path: str, password: Optional[str] = None, 
                          stop_at_marker: str = "Statement of Accounts") -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Extract text from image-based PDF using OCR.
    Processes pages in REVERSE order (last to first) and stops when marker text is found.
    
    Args:
        pdf_path: Path to PDF file
        password: Optional password for protected PDFs
        stop_at_marker: Text marker to stop processing (default: "Statement of Accounts")
    
    Returns:
        Tuple of (success, extracted_text, error_message)
    """
    if not OCR_AVAILABLE:
        return False, None, "OCR libraries not installed. Please install pytesseract and pdf2image."
    
    unlocked_path = None
    
    try:
        # If password provided, unlock first
        if password:
            success, unlocked_path, error = unlock_pdf(pdf_path, password)
            if not success:
                return False, None, error
            pdf_to_read = unlocked_path
        else:
            pdf_to_read = pdf_path
        
        # Convert PDF to images (all pages at once for efficiency)
        images = convert_from_path(pdf_to_read, dpi=300)
        
        # Process pages in REVERSE order (last to first)
        text = ""
        pages_processed = 0
        stopped_early = False
        
        for i, image in enumerate(reversed(images)):
            page_num = len(images) - i
            
            # Perform OCR on the page
            page_text = pytesseract.image_to_string(image, lang='eng')
            
            # Check if we've reached the stopping marker
            if stop_at_marker and stop_at_marker.lower() in page_text.lower():
                stopped_early = True
                print(f"[OCR] Stopped at page {page_num} - found '{stop_at_marker}'")
                break
            
            # Add page text
            if page_text.strip():
                text += f"\n=== PAGE {page_num} ===\n" + page_text + "\n"
                pages_processed += 1
        
        # Clean up temporary file if created
        if unlocked_path and os.path.exists(unlocked_path):
            os.remove(unlocked_path)
        
        if not text.strip():
            return False, None, "No text extracted via OCR."
        
        info_msg = f"OCR processed {pages_processed} pages"
        if stopped_early:
            info_msg += f" (stopped at '{stop_at_marker}')"
        
        return True, text, info_msg
        
    except Exception as e:
        # Clean up temporary file if created
        if unlocked_path and os.path.exists(unlocked_path):
            os.remove(unlocked_path)
        
        return False, None, f"Error during OCR: {str(e)}"

def parse_bpi_statement(text: str) -> List[Dict]:
    """Parse BPI credit card statement format (including OCR-extracted text)."""
    transactions = []
    
    lines = text.split('\n')
    
    # 1. Extract Statement Date/Year
    # Look for "STATEMENT DATE" pattern (e.g., "STATEMENT DATE NOVEMBER 12, 2025")
    statement_year = datetime.now().year
    statement_month_num = datetime.now().month
    
    for line in lines:  # Check all lines for header info (as Page 1 might be at the end)
        if "STATEMENT DATE" in line.upper():
            # Try to find a year in this line
            year_match = re.search(r'\b20\d{2}\b', line)
            if year_match:
                try:
                    statement_year = int(year_match.group(0))
                    # Also try to get the month to handle year boundaries correctly
                    for m_name, m_num in {
                        'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4, 'MAY': 5, 'JUNE': 6,
                        'JULY': 7, 'AUGUST': 8, 'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12
                    }.items():
                        if m_name in line.upper():
                            statement_month_num = m_num
                            break
                except:
                    pass
                # match found, stop searching
                break

    # Find where actual transactions start (after "Customer Number" text)
    # This filters out summary tables and extra information
    customer_number_found = False
    start_idx = 0
    for i, line in enumerate(lines):
        if 'Customer Number' in line:
            customer_number_found = True
        if customer_number_found and 'Description' in line and 'Amount' in line:
            start_idx = i + 1
            break
    
    # Track state for multi-line transactions and installment sections
    pending_description = None
    skip_until_amortization = False
    
    # Parse transactions from that point
    for i in range(start_idx, len(lines)):
        line = lines[i].strip()
        
        if not line:
            # Empty line resets pending description
            pending_description = None
            continue
        
        # Stop at summary sections (end of actual transactions)
        # Note: Don't stop at page boundaries (=== PAGE ===) as transactions may continue across pages
        if any(stop in line for stop in ['Installment Balance Summary', 'Payment Instructions', 
                                          'Contact Us', 'KEEP US UPDATED', 'Bank of the Philippine Islands']):
            break
        
        # Check for section markers
        if 'Installment Purchase:' in line:
            skip_until_amortization = True
            pending_description = None
            continue
        elif 'Installment Amortization:' in line:
            skip_until_amortization = False
            pending_description = None
            continue
        
        # Skip if we're in the installment purchase section
        if skip_until_amortization:
            continue
        
        # Skip summary lines and headers
        if any(skip in line for skip in ['Payment -', 'Finance Charge', 'Previous Balance', 
                                          'Past Due', 'Ending Balance', 'Unbilled', 
                                          'Total', 'Transaction', 'Post Date', 
                                          'Purchase Amount', 'Remaining', 'Date', 'Last Payment']):
            pending_description = None
            continue
        
        # Pattern: Description followed by amount at the end
        # Amount is always at the end: digits with optional comma and 2 decimal places
        amount_pattern = r'(.+?)\s+([\d,]+\.\d{2})$'
        match = re.search(amount_pattern, line)
        
        if match:
            description, amount_str = match.groups()
            description = description.strip()
            
            # If we have a pending description from previous line, combine them
            if pending_description:
                description = pending_description + ' ' + description
                pending_description = None
            
            # Skip if description is too short
            if len(description) < 3:
                continue
            
            try:
                amount = float(amount_str.replace(',', ''))
                
                # Determine transaction year
                # If statement is Jan 2026, and transaction is Dec, it's Dec 2025
                # For now, simplistic approach using extracted statement year
                # (Standard parser usually doesn't have date on the same line, assumes statement month)
                
                transactions.append({
                    'date': f"{statement_year}-{statement_month_num:02d}-01", # Placeholder date
                    'description': description,
                    'amount': amount
                })
            except:
                continue
        else:
            # No amount on this line - might be first part of multi-line transaction
            # Only save as pending if the line doesn't contain date patterns
            # (lines with dates are likely transaction lines that got split)
            has_date = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}', line)
            if line and len(line) > 3 and not has_date:
                pending_description = line
            else:
                pending_description = None
    
    # Post-processing: Handle continuation pages where merchants and amounts are in separate sections
    # This happens on some pages where the format is: merchants, then "Statement of Account", then amounts
    for i in range(len(lines)):
        if '=== PAGE' in lines[i]:
            merchants = []
            merchants_dates = [] # Store extracted date for each merchant
            amounts = []
            
            # Collect potential merchants (lines with text but no amount pattern)
            for j in range(i+1, min(i+100, len(lines))): # Increased lookahead
                line = lines[j].strip()
                
                # Stop if we hit the next page
                if '===' in line and 'PAGE' in line:
                    break
                
                # Skip empty lines
                if not line:
                    continue
                
                # Check if line looks like a merchant
                # CRITICAL FIX: In split-column mode, merchant lines MUST start with a date (Month Day)
                # This filters out labels like "Finance Charge", "Previous Balance" etc.
                date_match = re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})', line, re.IGNORECASE)
                
                if (line and len(line) > 3 and 
                    not re.match(r'^[\d,]+\.\d{2}$', line) and
                    date_match and # MUST have a date
                    not any(skip in line for skip in ['BPI Credit Cards', 'Customer Number', 'Transaction', 'Post Date', 'BPI REWARDS', 'Statement of Account'])):
                    
                    # Store merchant and its date
                    merchants.append(line)
                    
                    # Parse the date
                    m_name = date_match.group(1).upper()
                    day = int(date_match.group(2))
                    month_num = {
                        'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4, 'MAY': 5, 'JUNE': 6,
                        'JULY': 7, 'AUGUST': 8, 'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12
                    }.get(m_name, statement_month_num)
                    
                    # Logic to handle year rollovers (e.g. statement Jan 2026, trans Dec 25)
                    trans_year = statement_year
                    if statement_month_num == 1 and month_num == 12:
                        trans_year = statement_year - 1
                        
                    merchants_dates.append(f"{trans_year}-{month_num:02d}-{day:02d}")
                
                # After collecting merchants, look for "Statement of Account" marker
                # This should appear after the merchants and before the amounts
                if 'Statement of Account' in line and len(merchants) > 0:
                    # Start collecting amounts after this marker
                    for k in range(j+1, min(j+30, len(lines))):
                        amount_line = lines[k].strip()
                        if re.match(r'^[\d,]+\.\d{2}$', amount_line):
                            amounts.append(amount_line)
                        elif amount_line and '===' not in amount_line and not re.match(r'^[\d,]+\.\d{2}$', amount_line):
                             # Stop if we hit non-amount text (unless it looks like a total or something we can skip)
                             # But usually amounts are contiguous
                             # If we encounter a labeled line, stop.
                             pass
                    break
            
            # If we found matching merchants (and enough amounts), add them as transactions
            # We assume transaction amounts come first, followed by summary amounts (Finance Charge, etc.)
            if merchants and amounts and len(amounts) >= len(merchants):
                # Only take the first len(merchants) amounts
                valid_amounts = amounts[:len(merchants)]
                
                for i in range(len(merchants)):
                    try:
                        amount = float(amounts[i].replace(',', ''))
                        
                        # Clean up description (remove date from start if present, though sometimes it's nice to keep)
                        # The regex matched the date at start, let's keep it as part of description or remove?
                        # Usually description cleanup helps.
                        # But `merchants[i]` is the full line.
                        
                        transactions.append({
                            'date': merchants_dates[i],
                            'description': merchants[i], # Cleaned description
                            'amount': amount
                        })
                    except:
                        continue
    
    return transactions

def parse_unionbank_statement(text: str) -> List[Dict]:
    """Parse UnionBank credit card statement format."""
    transactions = []
    
    # UnionBank statements often include a transaction table, but PDFs can contain other
    # sections with similar date-like patterns. To avoid false positives, we parse
    # line-by-line and require the *entire* line to match a strict structure.
    #
    # Expected format (common):
    #   11/02/25 11/04/25 SHOPEE PH, MANDALUYONG PHP 220.00
    # Amount may be negative, may have commas, and may omit the PHP token.
    line_pattern = re.compile(
        r'^\s*'
        r'(?P<trx_date>\d{2}/\d{2}/\d{2})\s+'
        r'(?P<post_date>\d{2}/\d{2}/\d{2})\s+'
        r'(?P<desc>.+?)\s+'
        r'(?:(?P<ccy>PHP)\s+)?'
        r'(?P<amt>-?[\d,]+\.\d{2})'
        r'\s*$'
    )

    skip_keywords = [
        'BALANCE', 'SUBTOTAL', 'TOTAL', 'AMOUNT DUE',
        'CREDIT LIMIT', 'AVAILABLE', 'POINTS', 'STATEMENT DATE',
        'FINANCE CHARGE', 'REWARDS VISA PLATINUM', 'CARD NO',
        'MINIMUM AMOUNT DUE', 'PREVIOUS BALANCE', 'ENDING BALANCE'
    ]

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = line_pattern.match(line)
        if not m:
            continue

        date_str = m.group('trx_date')
        description = m.group('desc').strip()
        amount_str = m.group('amt')

        if not description or len(description) < 3:
            continue
        
        # Skip header/summary lines (more specific checks)
        if any(keyword in description.upper() for keyword in skip_keywords):
            continue
        # Skip lines that look like statement headers (start with common patterns)
        if description.upper().startswith(('STATEMENT', 'PAGE', 'TRANSACTION')):
            continue

        try:
            amount = float(amount_str.replace(',', ''))
        except ValueError:
            continue
        
        # Skip negative amounts (credits, refunds, payments)
        if amount < 0:
            continue

        try:
            date_obj = datetime.strptime(date_str, '%m/%d/%y')
            date = date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue

        transactions.append({'date': date, 'description': description, 'amount': amount})
    
    return transactions

def parse_generic_statement(text: str) -> List[Dict]:
    """Generic parser for common statement formats."""
    transactions = []
    
    # Keywords to skip (headers, summaries, example tables)
    skip_keywords = [
        'PAYMENT', 'BALANCE', 'SUBTOTAL', 'TOTAL', 'AMOUNT DUE',
        'CREDIT LIMIT', 'AVAILABLE', 'POINTS', 'STATEMENT DATE',
        'FINANCE CHARGE', 'DATE POST', 'DESCRIPTION AMOUNT',
        'MINIMUM AMOUNT DUE', 'PREVIOUS BALANCE', 'ENDING BALANCE',
        'POST DATE TRANSACTION', 'CARD NO', 'INTEREST RATE',
        'STATEMENT SUMMARY', 'OVERLIMIT', 'DEBITS CREDITS'
    ]
    
    # Try multiple common patterns
    patterns = [
        r'(\d{2}/\d{2}/\d{4})\s+([A-Z0-9\s\-\.\,\&\/]+?)\s+([\d,]+\.\d{2})',  # MM/DD/YYYY
        r'(\d{4}-\d{2}-\d{2})\s+([A-Z0-9\s\-\.\,\&\/]+?)\s+([\d,]+\.\d{2})',  # YYYY-MM-DD
        r'(\d{2}/\d{2})\s+([A-Z0-9\s\-\.\,\&\/]+?)\s+([\d,]+\.\d{2})',        # MM/DD
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            groups = match.groups()
            if len(groups) == 3:
                date_str, description, amount_str = groups
                
                # Clean up description
                description = description.strip()
                
                # Skip if description is too short or contains skip keywords
                if len(description) < 3:
                    continue
                if any(keyword in description.upper() for keyword in skip_keywords):
                    continue
                
                # Parse amount
                try:
                    amount = float(amount_str.replace(',', ''))
                except:
                    continue
                
                # Skip negative amounts (credits, refunds, payments)
                if amount < 0:
                    continue
                
                # Skip very large round numbers that look like examples (20000, 19500, etc.)
                if amount > 10000 and amount % 100 == 0:
                    continue
                
                # Parse date
                try:
                    if '/' in date_str and len(date_str.split('/')) == 2:
                        # MM/DD format
                        month, day = date_str.split('/')
                        current_year = datetime.now().year
                        date = f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"
                    elif '/' in date_str:
                        # MM/DD/YYYY format
                        date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                        date = date_obj.strftime('%Y-%m-%d')
                    else:
                        # YYYY-MM-DD format
                        date = date_str
                except:
                    continue
                
                transactions.append({
                    'date': date,
                    'description': description,
                    'amount': amount
                })
    
    return transactions

def extract_transactions(pdf_path: str, password: Optional[str] = None, 
                        bank_type: str = "auto") -> Tuple[bool, List[Dict], Optional[str]]:
    """
    Extract transactions from a PDF statement.
    
    Args:
        pdf_path: Path to PDF file
        password: Optional password for protected PDFs
        bank_type: "bpi", "unionbank", or "auto" for automatic detection
    
    Returns:
        Tuple of (success, transactions_list, error_message)
    """
    # Extract text from PDF
    success, text, error = extract_text_from_pdf(pdf_path, password)
    
    if not success:
        return False, [], error
    
    # Try to parse based on bank type
    transactions = []
    
    # Check for bank type in text (case-insensitive)
    text_upper = text.upper()
    
    # Check UnionBank FIRST (more specific), then BPI (more general)
    if bank_type == "unionbank" or (bank_type == "auto" and ("UNIONBANK" in text_upper or "UNION BANK" in text_upper)):
        transactions = parse_unionbank_statement(text)
    elif bank_type == "bpi" or (bank_type == "auto" and ("BPI" in text_upper or "BANK OF THE PHILIPPINE ISLANDS" in text_upper)):
        transactions = parse_bpi_statement(text)
    
    # If bank-specific parser found transactions (even just a few), use them
    # Only fall back to generic parser if bank-specific found nothing
    if not transactions:
        transactions = parse_generic_statement(text)
    
    if not transactions:
        return False, [], "Could not extract any transactions. The PDF format may not be supported yet."
    
    return True, transactions, None
