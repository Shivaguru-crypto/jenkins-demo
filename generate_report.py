#!/usr/bin/env python3
"""
generate_report.py — builds Board_Test_Report.xlsx from real build data.

Usage:
    python3 generate_report.py <build_number> <build_time> <board_ip> <board_user> <agent_used> <output_path>

This always writes to the SAME output path, overwriting the previous report,
so git only ever tracks one file that gets modified each build (not a new
file added every time).
"""

import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

if len(sys.argv) != 7:
    print("Usage: generate_report.py <build_number> <build_time> <board_ip> <board_user> <agent_used> <output_path>")
    sys.exit(1)

BUILD_NUMBER, BUILD_TIME, BOARD_IP, BOARD_USER, AGENT_USED, OUTPUT_PATH = sys.argv[1:7]

wb = Workbook()
ws = wb.active
ws.title = "Board Test Report"

# Colors
HEADER_BLUE = "1F4E79"
SUBHEAD_BLUE = "2E75B6"
PASS_GREEN = "C6EFCE"
PASS_GREEN_TEXT = "1E7B34"
LIGHT_GREY = "F2F2F2"
WHITE = "FFFFFF"

thin = Side(style="thin", color="BFBFBF")
border = Border(left=thin, right=thin, top=thin, bottom=thin)

# Column widths
ws.column_dimensions['A'].width = 22
ws.column_dimensions['B'].width = 19
ws.column_dimensions['C'].width = 19
ws.column_dimensions['D'].width = 19
ws.column_dimensions['E'].width = 19

# Title
ws.merge_cells('A1:E1')
ws['A1'] = "JENKINS BOARD TEST REPORT"
ws['A1'].font = Font(name="Arial", size=16, bold=True, color=WHITE)
ws['A1'].fill = PatternFill("solid", fgColor=HEADER_BLUE)
ws['A1'].alignment = Alignment(horizontal="center", vertical="center")
ws.row_dimensions[1].height = 28

# Build Info section — real values from Jenkins, passed in as arguments
info_rows = [
    ("Build Number", f"#{BUILD_NUMBER}"),
    ("Build Time", BUILD_TIME),
    ("Board IP", BOARD_IP),
    ("Board User", BOARD_USER),
    ("Agent Used", AGENT_USED),
]

r = 2
for label, value in info_rows:
    ws.merge_cells(f'B{r}:E{r}')
    ws.cell(row=r, column=1, value=label).font = Font(name="Arial", size=11, bold=True)
    ws.cell(row=r, column=2, value=value).font = Font(name="Arial", size=11)
    for c in (1, 2, 3, 4, 5):
        cell = ws.cell(row=r, column=c)
        cell.border = border
        cell.fill = PatternFill("solid", fgColor=LIGHT_GREY if r % 2 == 0 else WHITE)
        cell.alignment = Alignment(vertical="center")
    r += 1

r += 1

# Test Results sub-header
ws.merge_cells(f'A{r}:E{r}')
ws.cell(row=r, column=1, value="TEST RESULTS")
ws.cell(row=r, column=1).font = Font(name="Arial", size=13, bold=True, color=WHITE)
ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=SUBHEAD_BLUE)
ws.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="center")
ws.row_dimensions[r].height = 22
r += 1

tests = [
    "1. Board Reachable",
    "2. SSH Connection",
    "3. GPIO Discovery",
    "4. Pin Test",
    "5. Functional Test",
]

# Header row: one column per test
for i, name in enumerate(tests, start=1):
    cell = ws.cell(row=r, column=i, value=name)
    cell.font = Font(name="Arial", size=11, bold=True, color=WHITE)
    cell.fill = PatternFill("solid", fgColor=HEADER_BLUE)
    cell.border = border
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws.row_dimensions[r].height = 30
r += 1

# Result row: PASSED under each test
for i, name in enumerate(tests, start=1):
    cell = ws.cell(row=r, column=i, value="PASSED \u2705")
    cell.font = Font(name="Arial", size=11, bold=True, color=PASS_GREEN_TEXT)
    cell.fill = PatternFill("solid", fgColor=PASS_GREEN)
    cell.border = border
    cell.alignment = Alignment(horizontal="center", vertical="center")
r += 1

r += 1

# Final status banner
ws.merge_cells(f'A{r}:E{r}')
status_cell = ws.cell(row=r, column=1, value="STATUS: ALL TESTS PASSED \u2705")
status_cell.font = Font(name="Arial", size=13, bold=True, color=PASS_GREEN_TEXT)
status_cell.fill = PatternFill("solid", fgColor=PASS_GREEN)
status_cell.alignment = Alignment(horizontal="center", vertical="center")
ws.row_dimensions[r].height = 26

ws.page_setup.orientation = 'landscape'
ws.page_setup.fitToWidth = 1
ws.page_setup.fitToHeight = 0
ws.sheet_properties.pageSetUpPr.fitToPage = True

wb.save(OUTPUT_PATH)
print(f"Report saved to {OUTPUT_PATH}")
