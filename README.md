# 💰 Secure Personal Expense Tracker

A mobile-friendly, password-protected personal expense tracking application built with Streamlit. Track expenses manually or upload bank statement PDFs for automatic transaction extraction. Designed for privacy and ease of use.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.30+-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ Features

- 🔐 **Secure Authentication** - Password-protected with bcrypt hashing using Streamlit secrets
- ✍️ **Manual Entry** - Quick expense input with smart category suggestions based on merchant names
- 📄 **PDF Upload** - Extract transactions from password-protected bank statements (BPI, UnionBank, auto-detected formats)
- 📸 **OCR Support** - Automatic optical character recognition for scanned/image-based PDFs
- 🏦 **Bank Password Management** - Save and manage bank passwords for quick future uploads
- 🤖 **Smart Auto-Categorization** - Intelligent categorization using fuzzy matching and keyword recognition
- 📊 **Interactive Dashboard** - Visualize spending patterns with Plotly charts and analytics
- 🏷️ **Category Management** - Create, edit, organize, and delete expense categories
- 📱 **Mobile-Friendly** - Responsive design optimized for all device sizes
- ☁️ **Cloud Storage** - Data stored securely in Supabase PostgreSQL
- 🆓 **100% Free & Open Source** - Designed for free tier Supabase hosting
- 🏪 **Merchant Rules** - Link merchant patterns to categories for consistent auto-categorization
- 📈 **Bulk Operations** - Update multiple transactions at once for efficiency

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- pip package manager
- **Supabase Account** (Free Tier is sufficient)
- Git (optional, for cloning)

### Installation

1. **Clone or download this repository**

```bash
cd expense-tracker
```

2. **Create a virtual environment** (recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Configure Secrets**

You must create a `.streamlit/secrets.toml` file with your credentials and database connection details.

```toml
[cookie]
expiry_days = 30
key = "random_signature_key_change_this_in_production"
name = "expense_tracker_cookie"

[credentials.usernames.jsmith]
email = "jsmith@gmail.com"
name = "John Smith"
password = "$2b$12$VeDlrIbQ/wFkyadrM0QPyuVnbUx7X8DCcdG//zmKWsgqrRLlsyvsi"

[postgres]
host = "aws-0-[region].pooler.supabase.com"
port = 6543
dbname = "postgres"
user = "postgres.[your-project-ref]"
password = "[YOUR-DB-PASSWORD]"
```

**Note**: Use the **Transaction Pooler** connection settings from Supabase (Port 6543) for best compatibility with IPv4 networks.

5. **Run the application**

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`. The database schema will be created automatically on first run.

## 📖 User Guide

### 🔐 Login

1. Open the app in your browser (http://localhost:8501)
2. Enter your username (default: configured in `.streamlit/secrets.toml`)
3. Enter your password (default: configured in `.streamlit/secrets.toml`)
4. Click "Login"

### ✍️ Adding Expenses Manually

1. Navigate to **Add Expense** page (from sidebar)
2. Fill in the form:
   - **Date**: Transaction date (defaults to today)
   - **Description**: What you spent on (e.g., "Lunch at Jollibee")
   - **Amount**: How much you spent in PHP (₱)
   - **Account**: Payment method (Cash/Bank/Credit Card)
   - **Category**: Expense category (auto-suggested based on description)
3. Click **Add Expense**

**Smart Features**:
- Category suggestions based on merchant names using fuzzy matching
- Create new categories on the fly if needed
- Recent transactions displayed below the form for quick reference
- Automatic description parsing for better categorization

### 📄 Uploading Bank Statements

1. Navigate to **Upload Statements** page
2. Select your bank from the dropdown (used for password storage only)
3. Choose account type (if applicable)
4. Enter PDF password (auto-filled if previously saved)
5. Upload one or more PDF files
6. Click **Process Statements**
7. Review the **Preview & Edit Transactions** table and apply any fixes
8. Click **Save Transactions**

**Supported Banks**:
- BPI (Bank of the Philippine Islands) - with specific transaction table parsing
- UnionBank - with specific transaction table parsing
- Other formats - automatic detection and text extraction

**Bank Password Management**:
- Check "Save password" to securely store it for future uploads
- View and delete saved passwords in the password management section
- Each bank password is stored separately for security
- Bank selection is only used for password storage; parsing uses auto-detection

**PDF Processing Features**:
- Extracts transaction date, description, and amount automatically
- Unlocks password-protected PDFs
- Skips headers, footers, and non-transaction lines
- **Automatic OCR** - Detects image-based PDFs and uses Tesseract OCR for text extraction
- Intelligent page processing (reverse order to find transactions quickly)
- Batch processing for multiple statements
- PDFs are processed via temporary files and deleted immediately after extraction

**Preview & Edit**:
- Review extracted transactions before saving
- Fix dates, descriptions, amounts, and categories in bulk

**Danger Zone**:
- **Clear All Transactions** removes all transactions from the database (use with care)

### 📊 Viewing Dashboard

1. Navigate to **Dashboard** page
2. Use sidebar filters to customize your view:
   - **Date Range**: Select start and end dates for analysis
   - **Categories**: Filter by specific categories or view all
   - **Accounts**: Filter by account type (Cash/Bank/Credit Card) or view all
3. View interactive charts and analytics:
   - **Spending by Category** - Pie chart showing category breakdown
   - **Spending by Account** - Bar chart comparing account types
   - **Monthly Trend** - Line chart showing spending over time
   - **Top Expenses** - Table of largest transactions
   - **Category Breakdown** - Detailed spending per category
4. Additional features:
   - **Quick Stats** - Total transactions, total spending, unique categories
   - **Export Data** - Download transaction data as CSV
   - **Edit Categories** - Update transaction categories directly from dashboard

### 🏷️ Managing Categories

1. Navigate to **Categories** page
2. **Add new category**: 
   - Enter category name in the input field
   - Click "Add Category"
3. **View category details**:
   - See transaction count and total spending per category
4. **Edit category**:
   - Expand the category section
   - Change the name in the edit field
   - Click "Save" to update
5. **Delete category**:
   - Click "Delete" button (only available for categories with no transactions)
6. **Category Statistics**:
   - View how many transactions are in each category
   - See total amount spent in each category
   - Track category growth over time

### 🏪 Managing Merchant Rules

1. Navigate to **Merchant Rules** page
2. **Review suggestions** generated from your history
3. **Apply all suggestions** or create a **custom rule**
4. **Manage existing rules** (view and delete)
5. **Triage uncategorized** transactions with bulk updates

## 🔒 Security & Privacy

- ✅ Passwords hashed with bcrypt algorithm
- ✅ Session-based authentication with configurable expiry
- ✅ Cloud PostgreSQL storage (Supabase)
- ✅ PDF passwords stored locally only (or in DB if implemented)
- ✅ No external API calls or third-party trackers
- ✅ Sensitive files excluded from git version control
- ✅ Secrets-based configuration (easy to customize)
- ✅ No telemetry or data collection

**Files excluded from version control** (via `.gitignore`):
- `.streamlit/` - Local configuration files
- Virtual environment files

## 🌐 Deploying to Streamlit Cloud

1. **Push to GitHub**

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

2. **Deploy on Streamlit Cloud**

   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Click "New app"
   - Select your repository
   - Set main file: `app.py`
   - Click "Deploy"

3. **Add Secrets**

   In Streamlit Cloud dashboard:
   - Go to app settings → Secrets
   - Copy contents of `.streamlit/secrets.toml`
   - Paste and save

4. **Access your app**

   Your app will be available at: `https://your-app-name.streamlit.app`

## 📁 Project Structure

```
expense-tracker/
├── app.py                      # Main application with authentication & home page
├── .streamlit/
│   └── secrets.toml            # User credentials and session configuration (gitignored)
├── requirements.txt            # Python dependencies (streamlit, pikepdf, etc.)
├── docs/
│   ├── _INDEX.md               # Documentation index and quick links
│   ├── MERCHANT_QUICK_START.md # Quick reference guide
│   ├── MERCHANT_AUTOMATION.md  # Full implementation guide
│   ├── IMPLEMENTATION_SUMMARY.md # Technical overview and API reference
│   └── VISUAL_SUMMARY.txt      # Visual representation of implementation
├── pages/
│   ├── 1_Add_Expense.py       # Manual expense entry with category suggestions
│   ├── 2_Upload_Statements.py # PDF upload and bank statement processing
│   ├── 3_Dashboard.py         # Analytics, visualizations, and data export
│   ├── 4_Categories.py        # Category management and statistics
│   └── 5_Merchant_Rules.py    # Merchant rules, suggestions, and bulk actions
├── utils/
│   ├── database.py            # SQLite operations & schema management
│   ├── pdf_parser.py          # PDF text extraction & password handling
│   ├── categorizer.py         # Smart categorization with fuzzy matching
│   └── merchant_learner.py    # Merchant rule suggestions and stats
├── data/
│   └── expenses.db             # SQLite database (created on first run, .gitignored)
├── .gitignore                 # Excluded files from version control
└── README.md                  # This documentation
```

## 🛠️ Technical Stack

- **Framework**: Streamlit 1.30+ - Fast Python web framework for data apps
- **Authentication**: streamlit-authenticator 0.3.3 - Secure user authentication
- **Database**: SQLite3 - Lightweight local database (no server required)
- **PDF Processing**: 
  - pikepdf 8.0+ - PDF password handling and unlocking
  - pdfplumber 0.10+ - Text extraction from PDFs
  - pytesseract + pdf2image (optional) - OCR support for image-based PDFs
- **Categorization**: rapidfuzz 3.0+ - Fuzzy string matching for smart categorization
- **Data Processing**: pandas 2.0+ - DataFrames and data manipulation
- **Visualizations**: Plotly Express 5.18+ - Interactive charts and graphs
- **Image Processing**: Pillow 10.0+ - Image handling for OCR
- **Testing**: pytest 8.0+ - Unit and regression testing

## 🔄 Future Enhancements (Roadmap)

- [ ] Migration to PostgreSQL (Supabase) for multi-device sync
- [ ] Budget alerts and spending notifications
- [ ] Recurring expense detection and tracking
- [ ] Multi-currency conversion support
- [ ] Data export to Excel with formatted charts
- [ ] Customizable budget categories and subcategories
- [ ] Monthly/yearly reports generation
- [ ] Spending forecasting using historical data
- [ ] Family expense sharing (multi-user support)
- [ ] Dark mode for better night-time usability
- [ ] Mobile app (Flutter/React Native)

## 🐛 Troubleshooting

### PDF Upload Issues

**Problem**: "Incorrect password" error
- **Solution**: Verify the PDF password is correct. Most bank PDFs use your birthdate (DDMMYYYY or YYYYMMDD). Try different date formats.

**Problem**: "No text found in PDF"
- **Solution**: The PDF is image-based. The app will automatically attempt OCR extraction if the PDF appears to contain scanned images. If OCR is not working:
  - Ensure `pytesseract` and `pdf2image` are installed: `pip install pytesseract pdf2image`
  - Install Tesseract OCR engine: `brew install tesseract` (macOS) or `apt-get install tesseract-ocr` (Linux)
  - On Windows, download from https://github.com/UB-Mannheim/tesseract/wiki

**Problem**: "Could not extract any transactions"
- **Solution**: The PDF format may not be recognized. Try:
   - Manually checking if the PDF format matches known bank layouts
   - Contact your bank for a text-based statement version

**Problem**: "File too large or processing timeout"
- **Solution**: Upload PDFs in smaller batches. Process one or two months at a time instead of entire year.

### Authentication Issues

**Problem**: Can't login or session expires quickly
- **Solution**: Check `.streamlit/secrets.toml` exists and contains valid credentials. Verify the username and password match exactly (case-sensitive).

**Problem**: "Username/password is incorrect" even with correct credentials
- **Solution**: 
  - Clear browser cache and cookies
  - Restart Streamlit application
   - Verify `.streamlit/secrets.toml` has proper TOML formatting
  - Check for hidden characters or extra spaces in credentials

### Database Issues

**Problem**: Transactions not saving or "database is locked" error
- **Solution**: 
   - Check file permissions for `data/expenses.db`
  - Ensure the app has write access to the directory
  - Close other instances of the app using the database
  - Try restarting the Streamlit server

**Problem**: "Database corrupted" or unable to open database
- **Solution**: 
   - Backup your current `data/expenses.db`
   - Delete corrupted `data/expenses.db` to start fresh
  - Restore from your backup if needed

### Display Issues

**Problem**: Charts not displaying correctly on mobile
- **Solution**: The app is fully responsive but some charts may be condensed. Rotate to landscape for better visibility or use a desktop browser.

**Problem**: Sidebar navigation not working
- **Solution**: Ensure JavaScript is enabled in browser. Try refreshing the page or clearing cache.

## 🚀 Deployment

### Local Deployment

The application runs locally by default and stores all data on your machine.

```bash
# Start the app
streamlit run app.py

# Access at http://localhost:8501
```

### Streamlit Cloud Deployment

To deploy to Streamlit Cloud for remote access:

1. **Push to GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

2. **Deploy on Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Click "New app"
   - Select your repository and `app.py` as main file
   - Click "Deploy"

3. **Add Secrets** (in Streamlit Cloud dashboard)
   - Go to app settings → Secrets
   - Add your authentication credentials matching `.streamlit/secrets.toml` format

4. **Important Security Notes**
   - Change default credentials before deploying
   - Use strong, unique passwords
   - Do not commit `data/expenses.db` to GitHub
   - Store `.streamlit/secrets.toml` in Streamlit Secrets, not in repository

## 📊 Data Management

### Backup Strategy

- **Manual Backups**: Copy `data/expenses.db` to a safe location regularly
- **Export Data**: Use Dashboard → Export Data to save transactions as CSV for external backup

### Database Maintenance

- **File Size**: Database grows with transaction count (typically <5MB for 10,000 transactions)
- **Cleanup**: Use Categories page to delete unused categories and archive old data if needed

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

- **Report Issues**: Open a GitHub issue with detailed description
- **Suggest Features**: Provide use cases and expected behavior
- **Submit PRs**: For bug fixes and improvements (maintain code style and add tests)

## 📝 License

MIT License - Feel free to use, modify, and distribute for personal and commercial use. See LICENSE file for details.

---

## 📞 Support & Feedback

- **Issues**: Open a GitHub issue with detailed reproduction steps
- **Questions**: Check the troubleshooting section or FAQ
- **Feature Requests**: Describe your use case and expected behavior
- **Feedback**: Share your experience and suggestions for improvement

---

**Made with ❤️ using Streamlit**

**Currency**: Philippine Peso (₱)

**Last Updated**: February 2026
