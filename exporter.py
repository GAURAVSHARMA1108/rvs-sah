"""
Data Exporter Module for RajPSP Student Profile Scraper
Generates professionally formatted Excel (.xlsx) files with Signal Blue (#0057FF)
and Porcelain (#F8F7F4) styling, and TSV/JSON formats for clipboard copying.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


SIGNAL_BLUE = "0057FF"       # HEX #0057FF
PORCELAIN_BG = "F8F7F4"      # HEX #F8F7F4
PORCELAIN_TEXT = "F8F7F4"    # HEX #F8F7F4
ZEBRA_LIGHT = "F3F6FD"       # Very subtle Signal Blue tint for alternating rows
BORDER_COLOR = "D0D5DD"      # Clean neutral border


def get_default_export_dir() -> Path:
    """Returns the user's Downloads directory, or Desktop/Documents if unavailable."""
    home = Path.home()
    downloads = home / "Downloads"
    if downloads.exists():
        return downloads
    desktop = home / "Desktop"
    if desktop.exists():
        return desktop
    return home


def export_to_excel(
    headers: List[str],
    rows: List[List[Any]],
    output_path: Optional[str] = None,
    session_name: str = "",
    class_name: str = ""
) -> Dict[str, Any]:
    """
    Exports extracted student data to a beautifully styled Excel (.xlsx) file.
    
    Args:
        headers: List of column header names
        rows: List of data rows (each row is a list of values)
        output_path: Optional custom path. If None, saves to Downloads folder.
        session_name: Name of the academic session (for filename)
        class_name: Name of the class (for filename)
        
    Returns:
        Dict with success status, file path, row count, and message/reason.
    """
    if not headers or not rows:
        return {
            "success": False,
            "file_path": None,
            "row_count": 0,
            "message": "Export failed: No data records provided to export.",
            "reason": "Headers or rows list was empty."
        }

    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Student Profiles"

        # Ensure grid lines are visible
        ws.views.sheetView[0].showGridLines = True

        # Styles
        header_fill = PatternFill(start_color=SIGNAL_BLUE, end_color=SIGNAL_BLUE, fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color=PORCELAIN_TEXT)
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        data_font = Font(name="Segoe UI", size=10, color="1E293B")
        data_align_left = Alignment(horizontal="left", vertical="center")
        data_align_center = Alignment(horizontal="center", vertical="center")

        thin_side = Side(border_style="thin", color=BORDER_COLOR)
        cell_border = Border(top=thin_side, left=thin_side, right=thin_side, bottom=thin_side)

        zebra_fill = PatternFill(start_color=ZEBRA_LIGHT, end_color=ZEBRA_LIGHT, fill_type="solid")
        white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

        # Write Headers
        ws.row_dimensions[1].height = 28
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=str(header).strip())
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = cell_border

        # Write Rows
        for row_idx, row_data in enumerate(rows, start=2):
            ws.row_dimensions[row_idx].height = 22
            row_fill = zebra_fill if (row_idx % 2 == 0) else white_fill
            
            for col_idx, value in enumerate(row_data, start=1):
                val_str = "" if value is None else str(value).strip()
                cell = ws.cell(row=row_idx, column=col_idx, value=val_str)
                cell.fill = row_fill
                cell.font = data_font
                cell.border = cell_border
                
                # S.No and short numbers center aligned
                if col_idx == 1 and val_str.isdigit():
                    cell.alignment = data_align_center
                else:
                    cell.alignment = data_align_left

        # Freeze Header Row
        ws.freeze_panes = "A2"

        # Auto-adjust column widths based on maximum length with safety caps
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if "\n" in val:
                    val = max(val.split("\n"), key=len)
                max_len = max(max_len, len(val))
            # Set proportional width between 10 and 50
            adjusted_width = min(max(max_len + 4, 12), 50)
            ws.column_dimensions[col_letter].width = adjusted_width

        # Determine output file path
        if not output_path:
            clean_session = "".join(c for c in session_name if c.isalnum() or c in ("-", "_")).strip()
            clean_class = "".join(c for c in class_name if c.isalnum() or c in ("-", "_")).strip()
            session_part = f"_{clean_session}" if clean_session else ""
            class_part = f"_{clean_class}" if clean_class else ""
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"PSP_Student_Profiles{session_part}{class_part}_{timestamp}.xlsx"
            export_dir = get_default_export_dir()
            output_path = str(export_dir / filename)
        else:
            # Ensure it ends with .xlsx
            if not output_path.lower().endswith(".xlsx"):
                output_path += ".xlsx"

        wb.save(output_path)
        wb.close()

        return {
            "success": True,
            "file_path": output_path,
            "row_count": len(rows),
            "col_count": len(headers),
            "message": f"Successfully exported {len(rows)} student records to Excel file.",
            "reason": f"Workbook saved at {output_path} with Signal Blue styling and auto-fitted columns."
        }

    except Exception as e:
        return {
            "success": False,
            "file_path": None,
            "row_count": 0,
            "message": f"Failed to save Excel file: {str(e)}",
            "reason": f"Exception raised during workbook generation: {type(e).__name__}: {str(e)}"
        }


def export_to_tsv(headers: List[str], rows: List[List[Any]]) -> str:
    """
    Formats headers and rows into Tab-Separated Values (TSV).
    Allows direct and seamless pasting into Microsoft Excel, Google Sheets, or Calc.
    """
    if not headers and not rows:
        return ""

    def clean_cell(val: Any) -> str:
        s = "" if val is None else str(val).strip()
        # Clean up inner tabs and newlines for clean TSV
        return s.replace("\t", " ").replace("\r\n", " ").replace("\n", " ")

    lines = []
    if headers:
        lines.append("\t".join(clean_cell(h) for h in headers))
    
    for row in rows:
        lines.append("\t".join(clean_cell(cell) for cell in row))

    return "\n".join(lines)


def export_to_json_records(headers: List[str], rows: List[List[Any]]) -> List[Dict[str, Any]]:
    """Converts headers and rows into a list of dictionaries."""
    records = []
    for row in rows:
        record = {}
        for idx, header in enumerate(headers):
            val = row[idx] if idx < len(row) else ""
            record[str(header).strip()] = str(val).strip() if val is not None else ""
        records.append(record)
    return records
