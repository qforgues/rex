import os
import re
import shutil
from datetime import datetime
from typing import Dict, Tuple, Optional
import pandas as pd
from pathlib import Path

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

def extract_date_from_filename(filename: str) -> Optional[str]:
    """Extract date from filename (YYYY-MM-DD format)."""
    pattern = r'(\d{4}-\d{2}-\d{2})'
    match = re.search(pattern, filename)
    if match:
        return match.group(1)
    return None

def detect_institution(filename: str) -> Optional[str]:
    """Detect institution from filename."""
    filename_lower = filename.lower()

    institution_keywords = {
        'chase': ['chase'],
        'amex': ['amex', 'american express'],
        'wellsfargo': ['wells fargo', 'wellsfargo', 'wf '],
        'bankofamerica': ['bank of america', 'bofa', 'b of a'],
        'capitalone': ['capital one'],
        'discover': ['discover'],
        'fidelity': ['fidelity'],
        'vanguard': ['vanguard'],
        'charles schwab': ['schwab', 'charles schwab'],
    }

    for institution, keywords in institution_keywords.items():
        for keyword in keywords:
            if keyword in filename_lower:
                return institution

    return None

def extract_pdf_text(filepath: str) -> str:
    """Extract text from PDF."""
    if not PdfReader:
        return ""

    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def extract_csv_data(filepath: str) -> Dict:
    """Extract data from CSV file."""
    try:
        df = pd.read_csv(filepath)
        return {
            "rows": len(df),
            "columns": list(df.columns),
            "preview": df.head(3).to_dict('records')
        }
    except Exception as e:
        return {"error": str(e)}

def extract_excel_data(filepath: str) -> Dict:
    """Extract data from Excel file."""
    try:
        xls = pd.ExcelFile(filepath)
        sheets = xls.sheet_names
        return {
            "sheets": sheets,
            "rows": len(pd.read_excel(filepath, sheet_name=sheets[0])) if sheets else 0,
            "preview": "Excel file ready for processing"
        }
    except Exception as e:
        return {"error": str(e)}

def process_uploaded_file(file_path: str, account_id: str, account_folder: str) -> Dict:
    """
    Process an uploaded file and move it to the account folder.

    Returns a dict with processing results.
    """
    filename = os.path.basename(file_path)
    extracted_date = extract_date_from_filename(filename)
    detected_institution = detect_institution(filename)

    result = {
        "filename": filename,
        "account_id": account_id,
        "status": "success",
        "extracted_date": extracted_date,
        "detected_institution": detected_institution,
        "file_type": Path(file_path).suffix.lower(),
        "file_size_kb": os.path.getsize(file_path) / 1024,
        "processed_at": datetime.now().isoformat()
    }

    # Create account folder if it doesn't exist
    os.makedirs(account_folder, exist_ok=True)

    # Move file to account folder
    try:
        destination = os.path.join(account_folder, filename)

        # If file already exists, add timestamp
        if os.path.exists(destination):
            name, ext = os.path.splitext(filename)
            destination = os.path.join(
                account_folder,
                f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            )

        shutil.move(file_path, destination)
        result["destination"] = destination
        result["status"] = "success"

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result

def extract_statement_data(file_path: str) -> Dict:
    """
    Extract key data from a statement file.
    This is a basic implementation - enhance based on your statement formats.
    """
    file_ext = Path(file_path).suffix.lower()
    extracted_data = {
        "filename": os.path.basename(file_path),
        "file_type": file_ext,
        "extracted_at": datetime.now().isoformat()
    }

    if file_ext == '.pdf':
        text = extract_pdf_text(file_path)
        extracted_data["preview"] = text[:500] if text else "No text extracted"
        extracted_data["content_type"] = "pdf"

    elif file_ext in ['.csv', '.tsv']:
        csv_data = extract_csv_data(file_path)
        extracted_data.update(csv_data)
        extracted_data["content_type"] = "csv"

    elif file_ext in ['.xlsx', '.xls']:
        excel_data = extract_excel_data(file_path)
        extracted_data.update(excel_data)
        extracted_data["content_type"] = "excel"

    return extracted_data

def save_extraction_log(log_entry: Dict, log_file: str = "extraction_log.csv") -> None:
    """Save extraction data to CSV log."""
    log_path = log_file

    # Check if file exists to determine if we need headers
    file_exists = os.path.exists(log_path)

    # Convert dict to DataFrame for easy appending
    df = pd.DataFrame([log_entry])

    if file_exists:
        existing_df = pd.read_csv(log_path)
        df = pd.concat([existing_df, df], ignore_index=True)

    df.to_csv(log_path, index=False)
