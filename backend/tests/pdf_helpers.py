"""Helper to build real, valid PDF bytes for tests — not a mock, an actual PDF."""
from fpdf import FPDF
from fpdf.enums import XPos, YPos


def make_pdf_bytes(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in text.splitlines():
        if line.strip() == "":
            pdf.ln(8)
        else:
            pdf.multi_cell(0, 8, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    output = pdf.output()
    return bytes(output)
