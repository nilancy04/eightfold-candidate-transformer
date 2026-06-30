"""Test helper utilities."""

from __future__ import annotations

from pathlib import Path


def create_minimal_pdf(path: Path, lines: list[str] | None = None) -> None:
    """Write a minimal valid PDF with optional text lines for extraction tests."""
    text_lines = lines or [
        "Jane Doe",
        "jane.doe@example.com",
        "9876543210",
        "Skills: Python, React, JavaScript, cpp",
        "B.Tech Computer Science, IIT Delhi",
        "Software Engineer | Acme Corp (2019-01 - 2023-06)",
    ]

    y_pos = 720
    stream_parts = ["BT /F1 12 Tf"]
    for line in text_lines:
        escaped = line.replace("(", "\\(").replace(")", "\\)")
        stream_parts.append(f"72 {y_pos} Td ({escaped}) Tj")
        stream_parts.append("0 -20 Td")
        y_pos -= 20
    stream_parts.append("ET")
    stream_content = "\n".join(stream_parts)
    stream_len = len(stream_content.encode("latin-1", errors="replace"))

    pdf_content = f"""%PDF-1.1
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj
4 0 obj<< /Length {stream_len} >>stream
{stream_content}
endstream endobj
5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000274 00000 n 
0000000500 00000 n 
trailer<< /Size 6 /Root 1 0 R >>
startxref
580
%%EOF"""

    path.write_text(pdf_content, encoding="latin-1")


def create_corrupted_pdf(path: Path) -> None:
    """Write invalid PDF bytes to simulate a corrupted file."""
    path.write_bytes(b"%PDF-1.4\nthis is not a valid pdf structure\n%%EOF")
