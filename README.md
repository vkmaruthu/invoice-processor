# Invoice Processor

Automated end-to-end invoice processing pipeline:

```
Gmail (IMAP) → Attachment Download → docTR OCR → Gemini AI Extraction → MongoDB
```

---

## Project Structure

```
invoice_processor/
├── config/
│   ├── __init__.py
│   └── settings.py          ← all config (reads .env)
├── services/
│   ├── __init__.py
│   ├── email_service.py     ← IMAP monitoring + attachment download
│   ├── ocr_service.py       ← Tesseract / pdfplumber OCR
│   ├── gemini_service.py    ← Gemini AI JSON extraction
│   └── database_service.py ← MongoDB CRUD
├── controllers/
│   ├── __init__.py
│   └── invoice_controller.py ← pipeline orchestrator
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   └── file_helpers.py
├── downloads/               ← attachments saved here (auto-created)
├── logs/                    ← rotating log files (auto-created)
├── main.py                  ← ← ← ENTRY POINT — run this
├── requirements.txt
├── .env.example
└── README.md
```

---

## Prerequisites

### 1 — Python 3.11+
```bash
python --version   # should show 3.11 or higher
```

### 2 — Tesseract OCR binary

**Ubuntu / Debian**
```bash
sudo apt install tesseract-ocr tesseract-ocr-eng
```

**macOS**
```bash
brew install tesseract
```

**Windows**
Download installer from https://github.com/tesseract-ocr/tessdoc and add to PATH.

### 3 — Poppler (required by pdf2image for PDF rasterisation)

**Ubuntu / Debian**
```bash
sudo apt install poppler-utils
```

**macOS**
```bash
brew install poppler
```

**Windows**
Download from https://github.com/oschwartz10612/poppler-windows and add `bin/` to PATH.

### 4 — MongoDB
Install locally (https://www.mongodb.com/try/download/community) **or** use MongoDB Atlas (cloud).
For local:
```bash
sudo systemctl start mongod   # Linux
brew services start mongodb-community  # macOS
```

---

## Setup

### Step 1 — Clone / unzip the project
```bash
cd invoice_processor
```

### Step 2 — Create and activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
```

### Step 3 — Install Python dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Configure credentials
```bash
cp .env.example .env
```
Edit `.env` and fill in:

| Variable | Description |
|---|---|
| `EMAIL_ADDRESS` | Your Gmail address |
| `EMAIL_PASSWORD` | Gmail **App Password** (see below) |
| `MONGO_URI` | MongoDB connection string |
| `GEMINI_API_KEY` | Google AI Studio API key |

#### Getting a Gmail App Password
1. Enable 2-factor authentication on your Google account.
2. Go to https://myaccount.google.com/apppasswords
3. Create a new app password — copy the 16-character code into `.env`.

#### Getting a Gemini API Key
1. Visit https://aistudio.google.com/app/apikey
2. Create a key and paste it into `.env`.

---

## Running the App

```bash
# Make sure venv is active and you are in the project root
python main.py
```

The app will:
1. Connect to Gmail via IMAP.
2. Search for **unseen** emails with subject containing `"Invoice Copy"`.
3. Download PDF / JPG / PNG attachments to `downloads/`.
4. Run OCR on each attachment.
5. Send OCR text to Gemini for structured data extraction.
6. Save the extracted JSON to MongoDB (`invoice_db.invoices`).
7. Repeat every 30 seconds (configurable via `POLL_INTERVAL`).

Stop with `Ctrl-C` — the app shuts down cleanly.

---

## Sample Extracted JSON

```json
{
  "invoice_number": "INV-2024-0042",
  "invoice_date": "2024-03-10",
  "due_date": "2024-03-25",
  "vendor_name": "ABC Supplies Ltd",
  "vendor_email": "billing@abcsupplies.com",
  "customer_name": "Your Company",
  "line_items": [
    {
      "description": "Office Chairs",
      "quantity": 5,
      "unit_price": 250.00,
      "total": 1250.00
    }
  ],
  "subtotal": 1250.00,
  "tax_percentage": 18,
  "tax_amount": 225.00,
  "total_amount": 1475.00,
  "currency": "INR",
  "source_email": "supplier@example.com",
  "pdf_filename": "invoice_042.pdf",
  "processed_at": "2024-03-17T08:30:00Z",
  "status": "processed"
}
```

---

## Logs

Logs are written to `logs/invoice_processor.log` and also printed to the console.
Log files rotate at 10 MB (5 backups kept).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `IMAP login failed` | Check email/password; use App Password for Gmail |
| `TesseractNotFoundError` | Tesseract binary missing from PATH |
| `ServerSelectionTimeoutError` | MongoDB not running |
| `GEMINI_API_KEY is not configured` | Edit `.env` and add your key |
| PDF produces no text | PDF might be image-only; ensure poppler is installed for OCR fallback |
