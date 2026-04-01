"""
Clockify monthly report generator
Fetches last month's time entries and generates two PDF reports:
  - report_YYYY-MM_billable.pdf
  - report_YYYY-MM_nonbillable.pdf
"""

import requests
import re
from datetime import date, timedelta
from collections import defaultdict
from fpdf import FPDF, XPos, YPos

# =============================================================================
# CONFIG
# =============================================================================

API_KEY    = 'MTMxODMxY2EtZTQ5Ny00ODhjLWIxZDctMTkxM2FlNTg5OGI1'
BASE_URL   = 'https://api.clockify.me/api/v1'
REPORT_URL = 'https://reports.api.clockify.me/v1'

# =============================================================================
# DATE RANGE — last calendar month
# =============================================================================

today           = date.today()
first_of_month  = today.replace(day=1)
month_end       = first_of_month - timedelta(days=1)
month_start     = month_end.replace(day=1)
MONTH_LABEL     = month_start.strftime('%Y-%m')
DATE_START      = month_start.strftime('%Y-%m-%dT00:00:00.000')
DATE_END        = month_end.strftime('%Y-%m-%dT23:59:59.000')

# =============================================================================
# HELPERS
# =============================================================================

HEADERS = {
    'X-Api-Key':    API_KEY,
    'Content-Type': 'application/json',
}


def get_workspace_id():
    resp = requests.get(f'{BASE_URL}/workspaces', headers=HEADERS)
    resp.raise_for_status()
    workspaces = resp.json()
    if not workspaces:
        raise RuntimeError('No workspaces found.')
    return workspaces[0]['id']


def fetch_entries(workspace_id):
    """Fetch all detailed time entries for the month, handling pagination."""
    entries = []
    page = 1
    while True:
        body = {
            'dateRangeStart': DATE_START,
            'dateRangeEnd':   DATE_END,
            'detailedFilter': {'page': page, 'pageSize': 1000},
            'exportType':     'JSON',
        }
        resp = requests.post(
            f'{REPORT_URL}/workspaces/{workspace_id}/reports/detailed',
            headers=HEADERS, json=body
        )
        resp.raise_for_status()
        data = resp.json()
        batch = data.get('timeentries', [])
        entries.extend(batch)

        if resp.headers.get('X-Last-Page', 'false').lower() == 'true' or len(batch) < 1000:
            break
        page += 1

    return entries


def parse_duration(duration):
    """Parse duration to decimal hours. Accepts ISO 8601 string or integer seconds."""
    if not duration:
        return 0.0
    if isinstance(duration, (int, float)):
        return round(duration / 3600, 2)
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', str(duration))
    if not m:
        return 0.0
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    secs = int(m.group(3) or 0)
    return round(h + mins / 60 + secs / 3600, 2)


def hours_str(h):
    total_mins = round(h * 60)
    return f'{total_mins // 60}h {total_mins % 60:02d}m'


def safe(text):
    """Return text as a clean string. Unicode is handled by the TTF font."""
    if not text:
        return ''
    return str(text).replace('\u00a0', ' ')  # replace non-breaking space only


def group_entries(entries):
    """
    Returns {is_billable: {project_name: {user_name: [entry, ...]}}}
    Each entry: {date, description, hours}
    """
    grouped = {True: defaultdict(lambda: defaultdict(list)),
               False: defaultdict(lambda: defaultdict(list))}

    for e in entries:
        billable     = bool(e.get('billable', False))
        project_name = e.get('projectName') or 'No project'
        user_name    = e.get('userName')    or 'Unknown'
        description  = e.get('description') or ''
        entry_date   = (e.get('timeInterval', {}).get('start') or '')[:10]
        duration     = parse_duration(e.get('timeInterval', {}).get('duration', ''))

        grouped[billable][project_name][user_name].append({
            'date':        entry_date,
            'description': description,
            'hours':       duration,
        })

    return grouped


# =============================================================================
# PDF GENERATION
# =============================================================================

FONT_DIR = 'fonts'

class ReportPDF(FPDF):
    def __init__(self, title):
        super().__init__()
        self.report_title = title
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 15, 15)
        self.add_font('DejaVu',  '',  f'{FONT_DIR}/DejaVuSans.ttf')
        self.add_font('DejaVu',  'B', f'{FONT_DIR}/DejaVuSans-Bold.ttf')

    def header(self):
        self.set_font('DejaVu', 'B', 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, safe(self.report_title), align='R')
        self.ln(8)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font('DejaVu', '', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, f'Sivu {self.page_no()}', align='C')
        self.set_text_color(0, 0, 0)


def generate_pdf(project_name, users, billable, filename):
    """
    Generate one PDF for a single project.
    users: {user_name: [entries]}
    """
    month_name = month_start.strftime('%B %Y')
    title = f'{project_name} - {month_name}'
    billable_label = 'Laskutettava' if billable else 'Ei-laskutettava'

    pdf = ReportPDF(title)
    pdf.add_page()

    # ---- Report title ----
    pdf.set_font('DejaVu', 'B', 16)
    pdf.cell(0, 10, safe(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font('DejaVu', '', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, safe(f'{month_start.strftime("%d.%m.%Y")} - {month_end.strftime("%d.%m.%Y")}'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, safe(billable_label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    W = pdf.w - pdf.l_margin - pdf.r_margin

    # Column widths for entry rows
    CW_DATE  = 24
    CW_DUR   = 20
    CW_DESC  = W - CW_DATE - CW_DUR

    project_total = sum(e['hours'] for user_entries in users.values() for e in user_entries)

    for user_name, entries in sorted(users.items()):
            user_total = sum(e['hours'] for e in entries)

            # ---- User sub-header ----
            pdf.set_fill_color(220, 230, 245)
            pdf.set_font('DejaVu', 'B', 9)
            pdf.cell(W - 35, 6, safe(f'  {user_name}'), fill=True)
            pdf.cell(35, 6, safe(hours_str(user_total)), fill=True, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            # ---- Column headers ----
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font('DejaVu', 'B', 8)
            pdf.cell(CW_DATE, 5, 'Pvm', fill=True, border=0)
            pdf.cell(CW_DESC, 5, 'Kuvaus', fill=True, border=0)
            pdf.cell(CW_DUR,  5, 'Kesto', fill=True, border=0, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            # ---- Entries ----
            pdf.set_font('DejaVu', '', 8)
            for i, entry in enumerate(sorted(entries, key=lambda x: x['date'])):
                fill_color = (252, 252, 252) if i % 2 == 0 else (245, 245, 245)
                pdf.set_fill_color(*fill_color)

                desc = safe(entry['description']) or '-'
                dur  = safe(hours_str(entry['hours']))
                dt   = safe(entry['date'])

                # Use multi_cell for description to handle long text
                x_before = pdf.get_x()
                y_before = pdf.get_y()

                pdf.cell(CW_DATE, 5, dt,   fill=True, border=0)
                # Calculate height needed for description
                pdf.multi_cell(CW_DESC, 5, desc, fill=True, border=0)
                y_after = pdf.get_y()
                row_h = y_after - y_before

                # Draw duration aligned to top-right of the row
                pdf.set_xy(pdf.l_margin + CW_DATE + CW_DESC, y_before)
                pdf.cell(CW_DUR, row_h, dur, fill=True, border=0, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.ln(2)

    pdf.ln(4)

    # ---- Project total ----
    pdf.set_fill_color(200, 215, 235)
    pdf.set_font('DejaVu', 'B', 10)
    pdf.cell(W - 35, 7, 'Yhteensa', fill=True)
    pdf.cell(35, 7, safe(hours_str(project_total)), fill=True, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(filename)
    print(f'Written: {filename}')


# =============================================================================
# MAIN
# =============================================================================

def main():
    print(f'Fetching Clockify data for {MONTH_LABEL}...')

    workspace_id = get_workspace_id()
    print(f'Workspace: {workspace_id}')

    entries = fetch_entries(workspace_id)
    print(f'Fetched {len(entries)} time entries')

    grouped = group_entries(entries)

    total_pdfs = 0
    for billable, projects in grouped.items():
        for project_name, users in projects.items():
            # Safe filename: remove characters not suitable for filenames
            safe_name = re.sub(r'[^\w\s-]', '', project_name).strip().replace(' ', '_')
            billable_tag = 'billable' if billable else 'nonbillable'
            filename = f'{safe_name}_{MONTH_LABEL}_{billable_tag}.pdf'
            generate_pdf(project_name, users, billable, filename)
            total_pdfs += 1

    print(f'Done. {total_pdfs} PDF(s) generated.')


if __name__ == '__main__':
    main()
