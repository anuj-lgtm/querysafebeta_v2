#!/usr/bin/env python3
"""
QuerySafe Product Document — Markdown to PDF Generator
Converts QUERYSAFE_PRODUCT_DOCUMENT.md into a professional branded PDF.

Usage:
    python generate_pdf.py

Dependencies:
    pip install fpdf2  (already in requirements.txt)
"""

import os
import re
from fpdf import FPDF

# ── Configuration ────────────────────────────────────────────────────────────
BRAND_PURPLE = (113, 37, 190)   # #7125BE
DARK_GRAY    = (52, 71, 103)    # #344767
MEDIUM_GRAY  = (108, 117, 125)  # #6c757d
LIGHT_GRAY   = (240, 240, 240)  # #f0f0f0
BLACK        = (33, 37, 41)     # #212529
WHITE        = (255, 255, 255)
TABLE_HEADER = (113, 37, 190)   # Purple header
TABLE_ALT    = (248, 246, 252)  # Light purple alternate row
GREEN        = (45, 206, 137)   # #2dce89

INPUT_FILE  = "QUERYSAFE_PRODUCT_DOCUMENT.md"
OUTPUT_FILE = "QUERYSAFE_PRODUCT_DOCUMENT.pdf"

# Characters that Helvetica (latin-1) can't render — replace with ASCII
CHAR_MAP = {
    '\u2192': '->',    # →
    '\u2190': '<-',    # ←
    '\u2194': '<->',   # ↔
    '\u2193': 'v',     # ↓
    '\u2191': '^',     # ↑
    '\u00b7': '.',     # ·
    '\u2014': '--',    # —
    '\u2013': '-',     # –
    '\u2018': "'",     # '
    '\u2019': "'",     # '
    '\u201c': '"',     # "
    '\u201d': '"',     # "
    '\u2026': '...',   # …
    '\u2022': '-',     # •
    '\u2502': '|',     # │
    '\u250c': '+',     # ┌
    '\u2510': '+',     # ┐
    '\u2514': '+',     # └
    '\u2518': '+',     # ┘
    '\u2500': '-',     # ─
    '\u251c': '+',     # ├
    '\u2524': '+',     # ┤
    '\u252c': '+',     # ┬
    '\u2534': '+',     # ┴
    '\u253c': '+',     # ┼
    '\u25bc': 'v',     # ▼
    '\u25b6': '>',     # ▶
    '\u2605': '*',     # ★
    '\u00a7': 'S',     # §
    '\u2248': '~=',    # ≈
    '\u00d7': 'x',     # ×
    '\u2265': '>=',    # ≥
    '\u2264': '<=',    # ≤
}


def safe_text(text):
    """Replace characters that latin-1/Helvetica cannot render."""
    for char, replacement in CHAR_MAP.items():
        text = text.replace(char, replacement)
    # Fallback: replace any remaining non-latin1 chars
    result = []
    for ch in text:
        try:
            ch.encode('latin-1')
            result.append(ch)
        except UnicodeEncodeError:
            result.append('?')
    return ''.join(result)


def strip_inline_formatting(text):
    """Remove markdown bold/italic markers for plain text contexts."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)  # [text](url) -> text
    return text


# ── PDF Subclass ─────────────────────────────────────────────────────────────

class QuerySafePDF(FPDF):
    """Custom PDF with QuerySafe branded header and footer."""

    def __init__(self):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(20, 20, 20)
        self._is_cover = True  # suppress header/footer on cover

    def header(self):
        if self._is_cover:
            return
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(*MEDIUM_GRAY)
        self.cell(0, 6, 'QuerySafe  |  Product Documentation', align='L')
        self.set_draw_color(*BRAND_PURPLE)
        self.set_line_width(0.3)
        self.line(20, 14, self.w - 20, 14)
        self.ln(6)

    def footer(self):
        if self._is_cover:
            return
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(*MEDIUM_GRAY)
        self.cell(0, 8, f'Page {self.page_no()}/{{nb}}', align='C')
        self.set_x(20)
        self.cell(0, 8, 'Internal + Sales  |  Metric Vibes', align='L')

    # ── Rendering helpers ────────────────────────────────────────────────

    def render_cover_page(self):
        """Render a branded cover page."""
        self._is_cover = True
        self.add_page()
        self.ln(50)

        # Purple bar
        self.set_fill_color(*BRAND_PURPLE)
        self.rect(0, 40, self.w, 4, 'F')

        # Title
        self.set_font('Helvetica', 'B', 36)
        self.set_text_color(*BRAND_PURPLE)
        self.cell(0, 20, safe_text('QuerySafe'), ln=True, align='C')

        # Subtitle
        self.set_font('Helvetica', '', 16)
        self.set_text_color(*DARK_GRAY)
        self.cell(0, 12, safe_text('Complete Product Documentation'), ln=True, align='C')

        self.ln(8)
        # Tagline
        self.set_font('Helvetica', 'I', 12)
        self.set_text_color(*MEDIUM_GRAY)
        self.cell(0, 10, safe_text('Privacy-First AI Chatbot Builder'), ln=True, align='C')

        self.ln(30)

        # Info block
        self.set_font('Helvetica', '', 11)
        self.set_text_color(*DARK_GRAY)
        info_lines = [
            'Version: 1.0',
            'Date: February 2026',
            'Prepared by: Metric Vibes',
            'Classification: Internal + Sales',
            '',
            'console.querysafe.in',
            'querysafe.ai',
        ]
        for line in info_lines:
            self.cell(0, 8, safe_text(line), ln=True, align='C')

        self.ln(25)

        # Bottom bar
        self.set_fill_color(*BRAND_PURPLE)
        self.rect(0, self.h - 30, self.w, 4, 'F')

        self.set_y(self.h - 25)
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(*MEDIUM_GRAY)
        self.cell(0, 8, safe_text('Powered by Google Cloud  |  Metric Vibes, Noida, India'), align='C')

        self._is_cover = False

    def render_heading(self, level, text):
        """Render a heading (H1-H4)."""
        text = strip_inline_formatting(text)
        text = safe_text(text)

        if level == 1:
            self.add_page()
            self.ln(4)
            self.set_font('Helvetica', 'B', 22)
            self.set_text_color(*BRAND_PURPLE)
            self.multi_cell(0, 10, text)
            # Underline
            y = self.get_y()
            self.set_draw_color(*BRAND_PURPLE)
            self.set_line_width(0.6)
            self.line(20, y + 1, self.w - 20, y + 1)
            self.ln(6)
        elif level == 2:
            self.ln(6)
            self.set_font('Helvetica', 'B', 16)
            self.set_text_color(*BRAND_PURPLE)
            self.multi_cell(0, 9, text)
            # Thin line
            y = self.get_y()
            self.set_draw_color(200, 200, 200)
            self.set_line_width(0.2)
            self.line(20, y + 1, self.w / 2, y + 1)
            self.ln(3)
        elif level == 3:
            self.ln(4)
            self.set_font('Helvetica', 'B', 13)
            self.set_text_color(*DARK_GRAY)
            self.multi_cell(0, 8, text)
            self.ln(2)
        elif level == 4:
            self.ln(3)
            self.set_font('Helvetica', 'B', 11)
            self.set_text_color(*DARK_GRAY)
            self.multi_cell(0, 7, text)
            self.ln(1)

    def render_paragraph(self, text):
        """Render a body paragraph with inline bold/italic support."""
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*BLACK)

        # Use write_html for inline formatting
        html = safe_text(text)
        # Convert **bold** to <b>bold</b>
        html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
        # Convert *italic* to <i>italic</i>
        html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', html)
        # Convert `code` to <b>code</b> (no monospace in write_html easily)
        html = re.sub(r'`(.+?)`', r'<b>\1</b>', html)
        # Convert [text](url) to just text
        html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<b>\1</b>', html)

        self.write_html(f'<font size="10">{html}</font>')
        self.ln(6)

    def render_bullet(self, text, indent=0):
        """Render a bullet point."""
        x_start = 22 + indent
        self.set_x(x_start)

        # Bullet symbol
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(*BRAND_PURPLE)
        self.cell(5, 5, '-')

        # Text
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*BLACK)

        clean = safe_text(text)
        clean = strip_inline_formatting(clean)
        w = self.w - x_start - 25
        self.multi_cell(w, 5, clean)
        self.ln(1)

    def render_numbered_item(self, number, text):
        """Render a numbered list item."""
        self.set_x(22)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(*BRAND_PURPLE)
        self.cell(8, 5, f'{number}.')

        self.set_font('Helvetica', '', 10)
        self.set_text_color(*BLACK)
        clean = safe_text(strip_inline_formatting(text))
        self.multi_cell(self.w - 50, 5, clean)
        self.ln(1)

    def render_code_block(self, lines):
        """Render a code block with gray background."""
        self.ln(2)
        self.set_fill_color(*LIGHT_GRAY)
        self.set_draw_color(200, 200, 200)

        x = 22
        w = self.w - 44

        for line in lines:
            line = safe_text(line)
            self.set_x(x)
            self.set_font('Courier', '', 8)
            self.set_text_color(60, 60, 60)

            # Check if we need a page break
            if self.get_y() > self.h - 25:
                self.add_page()

            self.cell(w, 4.5, line, fill=True, ln=True)

        self.ln(3)

    def render_blockquote(self, text):
        """Render a blockquote with left border."""
        self.ln(1)
        x = 24
        y = self.get_y()

        self.set_x(x + 4)
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(*MEDIUM_GRAY)
        clean = safe_text(strip_inline_formatting(text))
        self.multi_cell(self.w - 52, 5, clean)

        y2 = self.get_y()
        # Left border
        self.set_draw_color(*BRAND_PURPLE)
        self.set_line_width(0.8)
        self.line(x, y, x, y2)

        self.ln(3)

    def render_table(self, rows):
        """Render a markdown table."""
        if not rows or len(rows) < 2:
            return

        self.ln(2)

        # Parse cells
        parsed = []
        separator_idx = -1
        for i, row in enumerate(rows):
            cells = [c.strip() for c in row.split('|')]
            cells = [c for c in cells if c != '']  # remove empty from leading/trailing |
            if cells and all(re.match(r'^[-:]+$', c) for c in cells):
                separator_idx = i
                continue
            cells = [safe_text(strip_inline_formatting(c)) for c in cells]
            parsed.append(cells)

        if not parsed:
            return

        # Determine column count and widths
        n_cols = max(len(r) for r in parsed)
        avail_w = self.w - 44
        col_w = avail_w / n_cols if n_cols > 0 else avail_w

        # Adjust column widths based on content
        col_widths = []
        for ci in range(n_cols):
            max_len = 0
            for row in parsed:
                if ci < len(row):
                    max_len = max(max_len, len(row[ci]))
            col_widths.append(max_len)

        total = sum(col_widths) if sum(col_widths) > 0 else 1
        col_widths = [(w / total) * avail_w for w in col_widths]

        # Enforce minimum column width
        col_widths = [max(w, 15) for w in col_widths]
        # Re-scale to fit
        scale = avail_w / sum(col_widths)
        col_widths = [w * scale for w in col_widths]

        x_start = 22

        for ri, row in enumerate(parsed):
            # Check page break
            if self.get_y() > self.h - 20:
                self.add_page()

            is_header = (ri == 0 and separator_idx != -1)

            if is_header:
                self.set_fill_color(*TABLE_HEADER)
                self.set_text_color(*WHITE)
                self.set_font('Helvetica', 'B', 9)
            elif ri % 2 == 0:
                self.set_fill_color(*TABLE_ALT)
                self.set_text_color(*BLACK)
                self.set_font('Helvetica', '', 9)
            else:
                self.set_fill_color(*WHITE)
                self.set_text_color(*BLACK)
                self.set_font('Helvetica', '', 9)

            self.set_x(x_start)
            row_height = 6

            # Calculate needed height for this row
            for ci in range(n_cols):
                cell_text = row[ci] if ci < len(row) else ''
                n_lines = max(1, int(self.get_string_width(cell_text) / (col_widths[ci] - 2)) + 1)
                row_height = max(row_height, n_lines * 5)

            row_height = min(row_height, 20)  # cap height

            for ci in range(n_cols):
                cell_text = row[ci] if ci < len(row) else ''
                w = col_widths[ci]
                # Truncate if needed
                while self.get_string_width(cell_text) > (w - 3) and len(cell_text) > 3:
                    cell_text = cell_text[:-4] + '...'
                self.cell(w, row_height, ' ' + cell_text, border=1, fill=True)

            self.ln(row_height)

        self.ln(3)

    def render_hr(self):
        """Render a horizontal rule."""
        self.ln(3)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        y = self.get_y()
        self.line(20, y, self.w - 20, y)
        self.ln(5)


# ── Markdown Parser ──────────────────────────────────────────────────────────

def parse_and_render(pdf, md_text):
    """Parse markdown text line-by-line and render to PDF."""
    lines = md_text.split('\n')
    i = 0
    n = len(lines)

    # Track table accumulation
    table_rows = []
    code_lines = []
    in_code_block = False

    while i < n:
        line = lines[i]

        # ── Code blocks ──────────────────────────────────────────────
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block
                pdf.render_code_block(code_lines)
                code_lines = []
                in_code_block = False
            else:
                # Flush pending table
                if table_rows:
                    pdf.render_table(table_rows)
                    table_rows = []
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # ── Table rows ───────────────────────────────────────────────
        if line.strip().startswith('|') and line.strip().endswith('|'):
            table_rows.append(line.strip())
            i += 1
            continue
        else:
            # Flush any accumulated table
            if table_rows:
                pdf.render_table(table_rows)
                table_rows = []

        stripped = line.strip()

        # ── Empty line ───────────────────────────────────────────────
        if not stripped:
            i += 1
            continue

        # ── Horizontal rule ──────────────────────────────────────────
        if stripped == '---' or stripped == '***' or stripped == '___':
            pdf.render_hr()
            i += 1
            continue

        # ── Headings ─────────────────────────────────────────────────
        heading_match = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            pdf.render_heading(level, text)
            i += 1
            continue

        # ── Blockquote ───────────────────────────────────────────────
        if stripped.startswith('> '):
            text = stripped[2:]
            pdf.render_blockquote(text)
            i += 1
            continue

        # ── Numbered list ────────────────────────────────────────────
        num_match = re.match(r'^(\d+)\.\s+(.+)$', stripped)
        if num_match:
            num = num_match.group(1)
            text = num_match.group(2)
            pdf.render_numbered_item(num, text)
            i += 1
            continue

        # ── Bullet point ─────────────────────────────────────────────
        bullet_match = re.match(r'^[-*]\s+(.+)$', stripped)
        if bullet_match:
            text = bullet_match.group(1)
            indent = len(line) - len(line.lstrip())
            pdf.render_bullet(text, indent=min(indent, 10))
            i += 1
            continue

        # ── Indented bullet (sub-list) ───────────────────────────────
        sub_bullet = re.match(r'^\s+[-*]\s+(.+)$', line)
        if sub_bullet:
            text = sub_bullet.group(1)
            pdf.render_bullet(text, indent=6)
            i += 1
            continue

        # ── Regular paragraph ────────────────────────────────────────
        if stripped:
            pdf.render_paragraph(stripped)

        i += 1

    # Flush remaining
    if table_rows:
        pdf.render_table(table_rows)
    if code_lines:
        pdf.render_code_block(code_lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_FILE)
    output_path = os.path.join(script_dir, OUTPUT_FILE)

    print(f"Reading: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Skip the markdown's own title + TOC section (we generate our own cover + TOC).
    # Start from "## 1. Executive Summary" which is the first real content section.
    lines = md_text.split('\n')
    start = 0
    for idx, line in enumerate(lines):
        if line.strip().startswith('## 1.'):
            start = idx
            break
    md_text = '\n'.join(lines[start:])

    print("Generating PDF...")
    pdf = QuerySafePDF()
    pdf.alias_nb_pages()

    # Cover page
    pdf.render_cover_page()

    # Table of contents page (simple)
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(*BRAND_PURPLE)
    pdf.cell(0, 12, 'Table of Contents', ln=True)
    pdf.ln(4)
    pdf.set_draw_color(*BRAND_PURPLE)
    pdf.set_line_width(0.4)
    pdf.line(20, pdf.get_y(), 80, pdf.get_y())
    pdf.ln(6)

    toc_items = [
        ('1.', 'Executive Summary'),
        ('2.', 'Platform Overview'),
        ('3.', 'Complete Feature List'),
        ('  3.1', 'User Authentication & Onboarding'),
        ('  3.2', 'Dashboard'),
        ('  3.3', 'Chatbot Creation'),
        ('  3.4', 'Chatbot Editing & Retraining'),
        ('  3.5', 'RAG Training Pipeline'),
        ('  3.6', 'Chat Interface & Embeddable Widget'),
        ('  3.7', 'Conversation History'),
        ('  3.8', 'Analytics Dashboard'),
        ('  3.9', 'Subscription & Billing'),
        ('  3.10', 'Profile & Account Management'),
        ('  3.11', 'Help & Support'),
        ('  3.12', 'Administration Panel'),
        ('  3.13', 'Email Notification System'),
        ('4.', 'Privacy & Security Promise'),
        ('5.', 'Pricing & Plans'),
        ('6.', 'Technical Architecture'),
        ('7.', 'How QuerySafe Benefits Users'),
        ('8.', 'Future Roadmap'),
        ('9.', 'Contact & Links'),
        ('10.', 'Appendix'),
    ]

    for num, title in toc_items:
        is_sub = num.startswith(' ')
        x = 28 if is_sub else 22
        pdf.set_x(x)
        pdf.set_font('Helvetica', 'B' if not is_sub else '', 10 if not is_sub else 9)
        pdf.set_text_color(*DARK_GRAY if not is_sub else MEDIUM_GRAY)
        pdf.cell(12, 6, num.strip())
        pdf.set_font('Helvetica', '' if not is_sub else '', 10 if not is_sub else 9)
        pdf.cell(0, 6, title, ln=True)

    # Main content
    parse_and_render(pdf, md_text)

    # Save
    pdf.output(output_path)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"PDF generated: {output_path} ({size_kb:.0f} KB, {pdf.page_no()} pages)")


if __name__ == '__main__':
    main()
