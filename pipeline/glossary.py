"""Professional glossary management - import documents and extract terminology."""
import json
import os
import re
import threading

GLOSSARY_FILE = "simultrans_glossary.json"

def _glossary_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", GLOSSARY_FILE)

class GlossaryManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._glossary = {}       # {source_term: target_term}
        self._file_glossaries = []  # list of imported filenames
        self.load()

    def load(self):
        path = _glossary_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._glossary = data.get("terms", {})
                self._file_glossaries = data.get("files", [])
            except:
                self._glossary = {}
                self._file_glossaries = []

    def save(self):
        path = _glossary_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "terms": self._glossary,
                "files": self._file_glossaries,
            }, f, indent=2, ensure_ascii=False)

    def get_terms(self):
        with self._lock:
            return dict(self._glossary)

    def add_term(self, source: str, target: str):
        with self._lock:
            self._glossary[source.strip()] = target.strip()
            self.save()

    def remove_term(self, source: str):
        with self._lock:
            self._glossary.pop(source, None)
            self.save()

    def set_terms(self, terms: dict):
        with self._lock:
            self._glossary = terms
            self.save()

    def clear_all(self):
        with self._lock:
            self._glossary = {}
            self._file_glossaries = []
            self.save()

    def import_document(self, filepath: str) -> dict:
        """
        Import a document and extract terminology pairs.
        Returns: {source_term: target_term, ...}
        """
        if not os.path.exists(filepath):
            return {"error": "文件不存在"}
        filename = os.path.basename(filepath)

        text = ""
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

        try:
            if ext == "txt":
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            elif ext == "csv":
                return self._import_csv(filepath)
            elif ext == "tsv":
                return self._import_tsv(filepath)
            elif ext == "pdf":
                text = self._extract_pdf_text(filepath)
            elif ext == "docx":
                text = self._extract_docx_text(filepath)
            else:
                return {"error": f"不支持的文件格式: .{ext}。支持: txt, csv, tsv, pdf, docx"}

            if not text.strip():
                return {"error": "未能从文件中提取到文本"}

            # Use LLM to extract term pairs from the document content
            # For now, use a heuristic approach: extract capitalized terms
            return self._extract_terms_from_text(text, filename)

        except Exception as e:
            return {"error": f"解析失败: {str(e)[:100]}"}

    def _import_csv(self, filepath: str) -> dict:
        """Import CSV with header: source,target"""
        import csv
        terms = {}
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    s, t = row[0].strip(), row[1].strip()
                    if s and t:
                        terms[s] = t
        self._merge_terms(terms, filepath)
        return {"terms": terms, "count": len(terms)}

    def _import_tsv(self, filepath: str) -> dict:
        """Import TSV with columns: source\ttarget"""
        terms = {}
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    s, t = parts[0].strip(), parts[1].strip()
                    if s and t:
                        terms[s] = t
        self._merge_terms(terms, filepath)
        return {"terms": terms, "count": len(terms)}

    def _extract_pdf_text(self, filepath: str) -> str:
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(filepath)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except ImportError:
            # Fallback: try pdftotext
            import subprocess
            result = subprocess.run(["pdftotext", filepath, "-"],
                                     capture_output=True, text=True, timeout=30)
            return result.stdout

    def _extract_docx_text(self, filepath: str) -> str:
        try:
            from docx import Document
            doc = Document(filepath)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            return ""

    def _extract_terms_from_text(self, text: str, filename: str) -> dict:
        """
        Heuristic term extraction from professional document text.
        Looks for: capitalized terms, acronyms, repeated technical terms.
        """
        lines = text.split("\n")
        terms = {}

        # Pattern 1: Lines with "术语" "定义" "简称" "英文" patterns
        term_patterns = [
            r'[""「]([^""」]+)[""」]\s*[（(]\s*(.+?)\s*[)）]',   # "术语"(翻译)
            r'([A-Z][A-Za-z\s/-]{2,50})\s*[:：]\s*([^。\n]{2,50})',  # Term: 中文
            r'([\u4e00-\u9fff]{2,20})\s*[:：]\s*([A-Z][A-Za-z\s/-]{2,50})',  # 中文: English Term
            r'简称\s*[""「]?([^""」,，\n]{2,30})[""」]?\s*[,，]?\s*(?:英文|中文)?',
            r'(?:英文|English)\s*[:：]?\s*([A-Z][A-Za-z]{2,50})\s*(?:中文|简称)?\s*[:：]?\s*([\u4e00-\u9fff\u3000-\u3037]{2,50})',
        ]

        for pattern in term_patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                if isinstance(m, tuple) and len(m) >= 2:
                    s, t = m[0].strip(), m[-1].strip()
                    if len(s) >= 2 and len(t) >= 2 and s != t:
                        # Sanity: at least one part should have meaningful length
                        if s.lower() not in terms and s not in terms.values():
                            terms[s] = t

        # Also extract from CSV-like lines in the document
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            parts = re.split(r'[,，\t|]', line)
            if len(parts) >= 2:
                s, t = parts[0].strip(), parts[1].strip()
                if s and t and len(s) >= 2 and len(t) >= 2 and s != t:
                    # Check if it looks like a term pair
                    is_term_pair = False
                    if re.match(r'[A-Z]', s) and re.search(r'[\u4e00-\u9fff]', t):
                        is_term_pair = True
                    elif re.search(r'[\u4e00-\u9fff]', s) and re.match(r'[A-Z]', t):
                        is_term_pair = True
                    if is_term_pair and s.lower() not in terms:
                        terms[s] = t

        self._merge_terms(terms, filename)
        return {"terms": terms, "count": len(terms)}

    def _merge_terms(self, new_terms: dict, filename: str):
        """Merge extracted terms into existing glossary."""
        with self._lock:
            self._glossary.update(new_terms)
            if filename and filename not in self._file_glossaries:
                self._file_glossaries.append(filename)
            self.save()

    def build_prompt_suffix(self) -> str:
        """Build glossary text to inject into translation prompt."""
        with self._lock:
            if not self._glossary:
                return ""
            items = list(self._glossary.items())[:200]  # Max 200 terms
            terms_text = "\n".join(f"  {s} → {t}" for s, t in items)
            return (
                "\n\n[专业术语表 - 请严格按以下翻译]:\n"
                f"{terms_text}\n"
                "请使用上述术语表中的翻译，保持术语一致性。"
            )

    def get_imported_files(self) -> list:
        return list(self._file_glossaries)
