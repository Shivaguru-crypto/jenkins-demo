#!/usr/bin/env python3
"""
generate_report.py

Generates Board_Test_Report.xlsx using REAL captured log output from each
pipeline stage, regardless of whether that stage passed or failed.

Called as:
    python3 generate_report.py \
        <build_number> <build_time> <board_ip> <board_user> <agent> <output_path> \
        <log_A> <status_A> \
        <log_B> <status_B> \
        <log_C> <status_C> \
        <log_D> <status_D> \
        <log_E> <status_E>

Where:
    <log_X>    = path to a text file containing the captured stdout/stderr
                 for that test column (A=Board Reachable, B=SSH Connection,
                 C=GPIO Discovery, D=Pin Test, E=Functional Test)
    <status_X> = "PASS" or "FAIL" — the real exit status of that stage's
                 command, written by the pipeline regardless of outcome

If a log file is missing or empty, the cell will show
"(no output captured)" rather than silently leaving stale/fake data.
"""

import sys
import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

MAX_LOG_CHARS = 4000  # safety cap so one runaway log doesn't blow up the cell


def read_log(path):
    if not path or not os.path.isfile(path):
        return "(no output captured)"
    try:
        with open(path, "r", errors="replace") as f:
            content = f.read().strip()
    except Exception as e:
        return f"(error reading log: {e})"
    if not content:
        return "(no output captured)"
    if len(content) > MAX_LOG_CHARS:
        content = content[:MAX_LOG_CHARS] + "\n... (truncated)"
    return content


def main():
    args = sys.argv[1:]
    if len(args) < 16:
        print("ERROR: expected 16 arguments, got", len(args))
        sys.exit(1)

    (build_number, build_time, board_ip, board_user, agent, output_path,
     log_a, status_a,
     log_b, status_b,
     log_c, status_c,
     log_d, status_d,
     log_e, status_e) = args[:16]

    columns = [
        ("A", "1. Board Reachable", log_a, status_a),
        ("B", "2. SSH Connection",  log_b, status_b),
        ("C", "3. GPIO Discovery",  log_c, status_c),
        ("D", "4. Pin Test",        log_d, status_d),
        ("E", "5. Functional Test", log_e, status_e),
    ]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Board Test Report"

    # ---- Color palette ----
    DARK_BLUE   = "FF1F4E79"
    MID_BLUE    = "FF2E75B6"
    LIGHT_GREY  = "FFF2F2F2"
    WHITE       = "FFFFFFFF"
    GREEN_FILL  = "FFC6EFCE"
    GREEN_TEXT  = "FF1E7B34"
    RED_FILL    = "FFFFC7CE"
    RED_TEXT    = "FF9C0006"

    white_bold    = Font(bold=True, color=WHITE)
    black_bold    = Font(bold=True, color="FF000000")
    black_normal  = Font(bold=False, color="FF000000")
    green_bold    = Font(bold=True, color=GREEN_TEXT)
    red_bold      = Font(bold=True, color=RED_TEXT)

    wrap_top_left = Alignment(wrap_text=True, vertical="top", horizontal="left")
    center = Alignment(horizontal="center", vertical="center")

    thin = Side(style="thin", color="FFCCCCCC")
    box_border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # ---- Column widths ----
    ws.column_dimensions['A'].width = 58.32
    ws.column_dimensions['B'].width = 51.04
    ws.column_dimensions['C'].width = 50.71
    ws.column_dimensions['D'].width = 25.91
    ws.column_dimensions['E'].width = 60.42

    # ---- Row 1: Title bar ----
    ws.merge_cells('A1:E1')
    ws['A1'] = "JENKINS BOARD TEST REPORT"
    ws['A1'].fill = PatternFill(start_color=DARK_BLUE, end_color=DARK_BLUE, fill_type="solid")
    ws['A1'].font = white_bold
    ws['A1'].alignment = center
    ws.row_dimensions[1].height = 27.75

    # ---- Rows 2-6: Build info ----
    info_rows = [
        ("Build Number", f"#{build_number}", LIGHT_GREY),
        ("Build Time",   build_time,         WHITE),
        ("Board IP",     board_ip,           LIGHT_GREY),
        ("Board User",   board_user,         WHITE),
        ("Agent Used",   agent,              LIGHT_GREY),
    ]
    row = 2
    for label, value, bg in info_rows:
        ws[f'A{row}'] = label
        ws[f'A{row}'].font = black_bold
        ws[f'A{row}'].fill = PatternFill(start_color=bg, end_color=bg, fill_type="solid")

        ws.merge_cells(f'B{row}:E{row}')
        ws[f'B{row}'] = value
        ws[f'B{row}'].font = black_normal
        ws[f'B{row}'].fill = PatternFill(start_color=bg, end_color=bg, fill_type="solid")
        ws.row_dimensions[row].height = 15.0
        row += 1

    # ---- Row 8: TEST RESULTS section header ----
    ws.merge_cells('A8:E8')
    ws['A8'] = "TEST RESULTS"
    ws['A8'].fill = PatternFill(start_color=MID_BLUE, end_color=MID_BLUE, fill_type="solid")
    ws['A8'].font = white_bold
    ws['A8'].alignment = center
    ws.row_dimensions[8].height = 21.75

    # ---- Row 9: Column headers ----
    for col, header, _, _ in columns:
        cell = ws[f'{col}9']
        cell.value = header
        cell.fill = PatternFill(start_color=DARK_BLUE, end_color=DARK_BLUE, fill_type="solid")
        cell.font = white_bold
        cell.alignment = center
    ws.row_dimensions[9].height = 30.0

    # ---- Row 10: LOG SECTION — real captured output ----
    # FIX: previously used PatternFill(fill_type=None) to try to clear the
    # background, but that does not reliably reset a fill in openpyxl/Excel —
    # it was rendering as the same dark blue as the header row above it
    # (A10:E10), making the wrapped log text unreadable. Explicitly setting a
    # solid WHITE fill is the reliable fix.
    for col, _, log_path, _ in columns:
        cell = ws[f'{col}10']
        cell.value = read_log(log_path)
        cell.fill = PatternFill(start_color=WHITE, end_color=WHITE, fill_type="solid")
        cell.font = black_normal
        cell.alignment = wrap_top_left
        cell.border = box_border
    ws.row_dimensions[10].height = 345.5

    # ---- Row 11: PASS/FAIL status row — reflects REAL status per column ----
    any_failed = False
    for col, _, _, status in columns:
        is_pass = status.strip().upper() == "PASS"
        if not is_pass:
            any_failed = True
        cell = ws[f'{col}11']
        cell.value = "PASSED \u2705" if is_pass else "FAILED \u274c"
        if is_pass:
            cell.fill = PatternFill(start_color=GREEN_FILL, end_color=GREEN_FILL, fill_type="solid")
            cell.font = green_bold
        else:
            cell.fill = PatternFill(start_color=RED_FILL, end_color=RED_FILL, fill_type="solid")
            cell.font = red_bold
        cell.alignment = center
    ws.row_dimensions[11].height = 13.8

    # ---- Row 13: Overall status banner — reflects REAL combined status ----
    ws.merge_cells('A13:E13')
    if any_failed:
        ws['A13'] = "STATUS: ONE OR MORE TESTS FAILED \u274c"
        ws['A13'].fill = PatternFill(start_color=RED_FILL, end_color=RED_FILL, fill_type="solid")
        ws['A13'].font = red_bold
    else:
        ws['A13'] = "STATUS: ALL TESTS PASSED \u2705"
        ws['A13'].fill = PatternFill(start_color=GREEN_FILL, end_color=GREEN_FILL, fill_type="solid")
        ws['A13'].font = green_bold
    ws['A13'].alignment = center
    ws.row_dimensions[13].height = 25.5

    wb.save(output_path)
    print(f"Report saved to {output_path}")
    print(f"Overall result: {'FAILED' if any_failed else 'PASSED'}")


if __name__ == "__main__":
    main()
