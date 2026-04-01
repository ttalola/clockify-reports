# Clockify Monthly Report Generator

Fetches last month's time entries from Clockify and generates PDF reports per project, split by billable and non-billable.

## Output

One PDF per project per billing type, e.g.:

```
Consti_Vilhonkatu_7_2026-03_billable.pdf
Business_Finland_2026-03_nonbillable.pdf
```

Each PDF contains:
- Project name and month in the title
- Date range and billable/non-billable label
- Per-user sections with individual time entries (date, description, duration)
- Per-user totals and project grand total

## Setup

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install requests fpdf2
```

### 2. Configure API key

Edit `clockify_report.py` and set your Clockify API key:

```python
API_KEY = 'your_api_key_here'
```

Find your API key in Clockify under **Profile Settings → API**.

### 3. Run

```bash
python clockify_report.py
```

The script automatically targets the previous calendar month. PDFs are written to the current directory.

## Requirements

- Python 3.8+
- `requests`
- `fpdf2`
- DejaVu Sans fonts (included in `fonts/`) — required for Finnish characters (ä, ö, å)
