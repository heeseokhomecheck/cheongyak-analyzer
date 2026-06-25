#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공고문 PDF -> 텍스트 추출. 사용: python extract_pdf.py <pdf경로> [출력txt경로]
pdfplumber(표 인식 우수) 우선, 없으면 pypdf 폴백."""
import sys, io

def extract(pdf_path):
    try:
        import pdfplumber
        out = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                out.append(f"\n===== PAGE {i} =====\n")
                out.append(page.extract_text() or "")
                for t in (page.extract_tables() or []):
                    out.append("\n[TABLE]")
                    for row in t:
                        out.append(" | ".join("" if c is None else str(c) for c in row))
        return "\n".join(out)
    except ImportError:
        pass
    from pypdf import PdfReader
    r = PdfReader(pdf_path)
    out = []
    for i, page in enumerate(r.pages, 1):
        out.append(f"\n===== PAGE {i} =====\n")
        out.append(page.extract_text() or "")
    return "\n".join(out)

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    text = extract(sys.argv[1])
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            f.write(text)
        print(f"OK {len(text)} chars -> {sys.argv[2]}")
    else:
        print(text)
