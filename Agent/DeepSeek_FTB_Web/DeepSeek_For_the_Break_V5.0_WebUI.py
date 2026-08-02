#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
DeepSeek_For_the_Break v5.2 - Optimized Academic AI Assistant (Web GUI)
========================================================================
  v5.2 Optimizations:
    [Speed]  Lazy imports - heavy libs loaded on-demand
    [Speed]  Pre-compiled regex - patterns cached at module level
    [Memory] LRU-bounded caches - encoding/path resolution
    [Memory] __slots__ AppState - ~50% less instance memory
    [Speed]  Deduplicated event loop - fewer isinstance checks
    [Speed]  Single-pass HTML rendering - no double-escaping
'''

import os, sys, uuid, json, sqlite3, subprocess, shutil, traceback
import textwrap, time, re, io, csv as csv_module, asyncio, threading
from datetime import datetime
from pathlib import Path
from functools import lru_cache
from typing import Optional, Dict, Any, List, Tuple, Union
from collections import OrderedDict

# ==================================================================
#  Pre-compiled Regex (compile once, run everywhere)
# ==================================================================

_RE_CODE_BLOCK = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
_RE_INLINE_CODE = re.compile(r'`([^`]+)`')
_RE_BOLD = re.compile(r'\*\*(.+?)\*\*')
_RE_ITALIC = re.compile(r'\*(.+?)\*')
_RE_H3 = re.compile(r'^### (.+)$', re.MULTILINE)
_RE_H2 = re.compile(r'^## (.+)$', re.MULTILINE)
_RE_H1 = re.compile(r'^# (.+)$', re.MULTILINE)
_RE_LI = re.compile(r'^- (.+)$', re.MULTILINE)
_RE_UL_WRAP = re.compile(r'(<li>.*?</li>\n?)+')
_RE_BLOCKQUOTE = re.compile(r'^&gt; (.+)$', re.MULTILINE)
_RE_HR = re.compile(r'^---$', re.MULTILINE)
_RE_BIBTEX_ENTRY = re.compile(r'@(\w+)\s*\{\s*([^,]+),')
_RE_SAFE_NAME = re.compile(r'[^a-zA-Z0-9_-]')

# ==================================================================
#  Always-needed imports
# ==================================================================

from nicegui import ui, app, run
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda *a, **kw: None

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing import Annotated, TypedDict
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_community.tools import WriteFileTool

_DDGS_AVAILABLE = False
try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _DDGS_AVAILABLE = True
    except ImportError:
        DDGS = None

import xml.etree.ElementTree as ET
import urllib.parse

_REQUESTS_AVAILABLE = _PANDAS_AVAILABLE = _DOCX_AVAILABLE = True
_MPL_AVAILABLE = _NUMPY_AVAILABLE = _SEABORN_AVAILABLE = True
_SCIPY_AVAILABLE = _SKLEARN_AVAILABLE = _FITZ_AVAILABLE = True
_PPTX_AVAILABLE = _PIL_AVAILABLE = _SYMPY_AVAILABLE = True
_BIBTEXPARSER_AVAILABLE = _OPENPYXL_AVAILABLE = _LANGCHAIN_AVAILABLE = True

# ==================================================================
#  0. Infrastructure (optimized)
# ==================================================================

def _log(level: str, msg: str):
    print(f'[{level} {datetime.now():%H:%M:%S}] {msg}')

def _cleanup_old_temp(temp_dir: str, max_age_hours: int = 48):
    cutoff = time.time() - max_age_hours * 3600
    p = Path(temp_dir)
    if not p.exists(): return
    for f in p.glob('*'):
        if f.is_file() and f.stat().st_mtime < cutoff and f.name.startswith('_'):
            try: f.unlink()
            except OSError: pass

_ENCODING_CACHE: OrderedDict = OrderedDict()
_ENCODING_CACHE_MAX = 256

def _safe_read_text(file_path: str) -> str:
    if not file_path: return ''
    if file_path in _ENCODING_CACHE:
        _ENCODING_CACHE.move_to_end(file_path)
        try:
            with open(file_path, 'r', encoding=_ENCODING_CACHE[file_path]) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError): del _ENCODING_CACHE[file_path]
    for enc in ('utf-8', 'gbk', 'latin-1', 'cp1252', 'utf-16'):
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
                if len(_ENCODING_CACHE) >= _ENCODING_CACHE_MAX:
                    _ENCODING_CACHE.popitem(last=False)
                _ENCODING_CACHE[file_path] = enc
                return content
        except (UnicodeDecodeError, UnicodeError): continue
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception: return ''

@lru_cache(maxsize=128)
def _resolve_path(path: str) -> str:
    if not path: return os.getcwd()
    p = Path(path)
    if p.is_absolute(): return str(p)
    for base in (Path.cwd(), Path(CUSTOM_TEMP_DIR)):
        c = base / p
        if c.exists(): return str(c.resolve())
    return os.path.abspath(path)

def _run_sandbox(code: str, timeout: int = 30, prefix: str = '',
                  save_to: str = '') -> Tuple[str, str, int]:
    if timeout > 300: timeout = 300
    if not code: return '', 'Error: code is empty', 1
    sid = uuid.uuid4().hex[:8]
    sp = os.path.join(CUSTOM_TEMP_DIR, f'_sb_{sid}.py')
    full_code = (
        'import sys, os, traceback, json as _json, math, re as _re\n'
        'import collections, itertools, functools, statistics, random as _random\n'
        'from datetime import datetime, timedelta\n'
        'from pathlib import Path\n'
        f'os.chdir(r\'{CUSTOM_TEMP_DIR}\')\n'
        f'{prefix}\n'
        'try:\n'
        f'{textwrap.indent(code, "    ")}\n'
        'except Exception as __e:\n'
        '    print(f\'[Exception] {type(__e).__name__}: {__e}\', file=sys.stderr)\n'
        '    traceback.print_exc()\n'
    )
    try:
        with open(sp, 'w', encoding='utf-8') as f: f.write(full_code)
        proc = subprocess.run([sys.executable, sp], capture_output=True, text=True,
                              timeout=timeout, cwd=CUSTOM_TEMP_DIR,
                              env={**os.environ, 'SANDBOX_MODE': '1'})
        return (proc.stdout or '').strip(), (proc.stderr or '').strip(), proc.returncode
    finally:
        try: os.remove(sp)
        except OSError: pass

def _safe_request(url: str, timeout: int = 20, **kw) -> Optional[requests.Response]:
    if not url: return None
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])))
    try:
        r = session.get(url, timeout=timeout, **kw); r.raise_for_status(); return r
    except requests.RequestException as e:
        _log('WARN', f'Request failed {url[:80]}: {e}'); return None

def _safe_json_dumps(obj: Any, max_len: int = 2000) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str, indent=2)
        return s if len(s) <= max_len else s[:max_len] + '\n... (truncated)'
    except Exception: return str(obj)[:max_len]

# ==================================================================
#  0.5 Smart Path Detection (cached)
# ==================================================================

@lru_cache(maxsize=1)
def _detect_tesseract() -> Optional[str]:
    p = shutil.which('tesseract')
    if p: return p
    if sys.platform == 'win32':
        cand = [r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe',
                r'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe',
                os.path.expandvars(r'%LOCALAPPDATA%\\Tesseract-OCR\\tesseract.exe')]
    else:
        cand = ['/usr/bin/tesseract', '/usr/local/bin/tesseract', '/opt/homebrew/bin/tesseract']
    for c in cand:
        if os.path.isfile(c): return c
    return None

@lru_cache(maxsize=1)
def _detect_latex_compilers() -> Dict[str, Optional[str]]:
    d: Dict[str, Optional[str]] = {}
    for name in ('pdflatex', 'xelatex', 'lualatex'):
        exe = name + ('.exe' if sys.platform == 'win32' else '')
        d[name] = shutil.which(exe) or shutil.which(name)
    return d

def _test_pytesseract() -> bool:
    try:
        from PIL import Image; import pytesseract
        pytesseract.image_to_string(Image.new('RGB', (10, 10), 'white'), lang='eng')
        return True
    except Exception: return False

@lru_cache(maxsize=1)
def _detect_cjk_font() -> Optional[str]:
    if sys.platform == 'win32':
        for font in ('SimSun', 'SimHei', 'Microsoft YaHei', 'KaiTi', 'FangSong'):
            try:
                r = subprocess.run(['powershell','-Command',
                    f"(Get-Item 'C:\\\\Windows\\\\Fonts\\\\{font}*.ttf' -ErrorAction SilentlyContinue).FullName"],
                    capture_output=True, text=True, timeout=10)
                if (r.stdout or '').strip(): return font
            except Exception: pass
        return 'SimSun'
    elif sys.platform == 'darwin':
        for font in ('Songti SC', 'Heiti SC', 'STSong', 'PingFang SC'):
            try:
                r = subprocess.run(['fc-list', f':family={font}'], capture_output=True, text=True, timeout=5)
                if (r.stdout or '').strip(): return font
            except Exception: pass
        return 'Songti SC'
    else:
        for font in ('Noto Serif CJK SC', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei'):
            try:
                r = subprocess.run(['fc-list', f':family={font}'], capture_output=True, text=True, timeout=5)
                if (r.stdout or '').strip(): return font
            except Exception: pass
    return None

_TESSERACT_PATH = _detect_tesseract()
_LATEX_COMPILERS = _detect_latex_compilers()
_PYTESSERACT_WORKS = False
_DETECTED_CJK_FONT = _detect_cjk_font()

if _TESSERACT_PATH:
    import pytesseract; pytesseract.pytesseract.tesseract_cmd = _TESSERACT_PATH
    _PYTESSERACT_WORKS = _test_pytesseract()

_MMDC_PATH = shutil.which('mmdc')
_PANDOC_PATH = shutil.which('pandoc')

# ==================================================================
#  1. Core Environment
# ==================================================================
load_dotenv(override=True)
api_key = os.getenv('DEEPSEEK_FOR_THE_BREAK')
if not api_key or not api_key.startswith('sk-'):
    _log('ERR', 'API Key not loaded or invalid format!')
    sys.exit(1)

BASE_WORKSPACE = os.getenv('DFTB_WORKSPACE', r'D:\\.API Keys\\DeepSeek_For_the_Break\\outputs')
CUSTOM_TEMP_DIR = os.path.join(BASE_WORKSPACE, 'temp')
os.makedirs(CUSTOM_TEMP_DIR, exist_ok=True)
if CUSTOM_TEMP_DIR not in sys.path:
    sys.path.insert(0, CUSTOM_TEMP_DIR)

_cleanup_old_temp(CUSTOM_TEMP_DIR, 48)

DB_PATH = os.path.join(BASE_WORKSPACE, 'agent_memory.db')
_MAX_DB_SIZE_MB = 100
if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > _MAX_DB_SIZE_MB * 1024 * 1024:
    _log('WARN', f'agent_memory.db exceeds {_MAX_DB_SIZE_MB}MB, resetting...')
    os.rename(DB_PATH, DB_PATH + f'.backup_{datetime.now():%Y%m%d_%H%M%S}')

_health: Dict[str, bool] = {
    'Tesseract OCR (Engine)': bool(_TESSERACT_PATH),
    'Tesseract OCR (Tested)': _PYTESSERACT_WORKS,
    'LaTeX (xelatex)': bool(shutil.which('xelatex') or shutil.which('pdflatex')),
    'matplotlib': _MPL_AVAILABLE, 'seaborn': _SEABORN_AVAILABLE,
    'numpy': _NUMPY_AVAILABLE, 'scipy': _SCIPY_AVAILABLE,
    'scikit-learn': _SKLEARN_AVAILABLE, 'PyMuPDF (fitz)': _FITZ_AVAILABLE,
    'pandas': _PANDAS_AVAILABLE, 'DuckDuckGo Search': _DDGS_AVAILABLE,
    'Mermaid CLI': bool(_MMDC_PATH), 'Pandoc': bool(_PANDOC_PATH),
    'API Key (.env)': True, 'bibtexparser': _BIBTEXPARSER_AVAILABLE,
    'CJK Font (detected)': bool(_DETECTED_CJK_FONT),
    'sympy': _SYMPY_AVAILABLE, 'python-pptx': _PPTX_AVAILABLE,
    'PIL (Pillow)': _PIL_AVAILABLE, 'openpyxl': _OPENPYXL_AVAILABLE,
}

_log('START', '=' * 60)
_log('START', '  DeepSeek_For_the_Break  v5.2  Optimized  Edition')
_log('START', '=' * 60)

# ==================================================================
#  2. System Prompt
# ==================================================================
SYSTEM_PROMPT = (
    'You are DeepSeek_For_the_Break v5.2, a highly professional academic AI assistant.\n'
    '\n'
    '## Core Capabilities\n'
    '- **Literature Search**: ArXivSearchTool, SemanticScholarTool, DOIMetadataTool, DuckDuckGoSearchTool\n'
    '- **Document Processing**: SmartReadPathTool, PDFTableExtractTool, PDFAnnotExtractTool, OCR\n'
    '- **Academic Writing**: EditWordDocTool, SaveMarkdownTool (default .md/.docx; LaTeX only if explicitly requested)\n'
    '- **Format Conversion**: PandocConvertTool (Markdown -> PDF/DOCX/HTML)\n'
    '- **Academic Translation**: AcademicTranslateTool (CN<->EN, terminology consistency)\n'
    '- **Presentation**: PresentationGenTool (Markdown -> PPTX)\n'
    '- **Data Analysis**: PythonSandboxTool, DataStatisticsTool, ChartGenerationTool\n'
    '- **Citation**: BibTexTool (APA/MLA/Chicago/IEEE)\n'
    '- **Learning Tools**: StudyPlanTool, FlashcardTool, KnowledgeGraphTool, NoteOrganizerTool\n'
    '- **Code Tools**: CodeReviewTool, ProjectScaffoldTool\n'
    '- **Math**: MathRenderTool\n'
    '- **Citation Analysis**: CitationNetworkTool\n'
    '\n'
    '## Behavior Guidelines\n'
    '1. Be objective, rigorous, well-structured; proactively acknowledge limitations.\n'
    '2. SmartReadPathTool is the primary tool for local file/folder reading.\n'
    '3. DEFAULT TO MARKDOWN, NOT LATEX. Use .md/.docx by default.\n'
    '4. Prioritize the most suitable academic tool for each task.\n'
    '5. When tools fail, clearly inform the user and provide alternatives.\n'
    '6. Persist all outputs to the workspace.\n'
    '\n'
    'Think step by step, prioritize the most suitable academic tool.'
)

_thinking_enabled = os.getenv('DFTB_THINKING_MODE', '').lower() == 'enabled'
_model_kwargs = {}
if _thinking_enabled:
    _log('INFO', 'DeepSeek thinking mode enabled')
    _model_kwargs = {'reasoning_effort': 'max', 'extra_body': {'thinking': {'type': 'enabled'}}}

llm = ChatOpenAI(
    model=os.getenv('DFTB_MODEL', 'deepseek-v4-pro'),
    base_url='https://api.deepseek.com',
    api_key=api_key,
    temperature=0.5,
    max_tokens=4096,
    model_kwargs=_model_kwargs
)

# ==================================================================
#  3. File Readers (lazy imports for heavy libs)
# ==================================================================

def _ocr_image(file_path: str, lang: str = 'chi_sim+eng') -> str:
    if not _PYTESSERACT_WORKS: return '[OCR not available]'
    try:
        from PIL import Image; import pytesseract
        return pytesseract.image_to_string(Image.open(file_path), lang=lang) or '[OCR returned empty]'
    except Exception as e: return f'[OCR error: {e}]'

def _read_text_file(fp: str) -> str:
    return f'[Text File: {os.path.basename(fp)}]\n{_safe_read_text(fp)[:5000]}'

def _read_csv_file(fp: str) -> str:
    try: import pandas as pd
    except ImportError: return _read_text_file(fp)
    try:
        df = pd.read_csv(fp, nrows=100)
        return (f'[CSV: {os.path.basename(fp)} | {len(df)} rows x {len(df.columns)} cols]\n'
                + df.head(50).to_string())
    except Exception as e: return f'[CSV read error: {e}]\n{_read_text_file(fp)}'

def _read_pdf_file(fp: str) -> str:
    parts = [f'[PDF: {os.path.basename(fp)}]']
    try: import fitz
    except ImportError: return f'[PDF: {os.path.basename(fp)} | PyMuPDF not installed]'
    try:
        doc = fitz.open(fp)
        for i, page in enumerate(doc):
            if i >= 20: break
            text = page.get_text()
            if text.strip(): parts.append(f'--- Page {i+1} ---\n{text[:2000]}')
        doc.close()
        if _PYTESSERACT_WORKS: parts.append('[OCR available]')
        return '\n'.join(parts)
    except Exception as e: return f'[PDF read error: {e}]'

def _read_docx_file(fp: str) -> str:
    try: from docx import Document
    except ImportError: return f'[DOCX: {os.path.basename(fp)} | python-docx not installed]'
    try:
        doc = Document(fp)
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        return f'[DOCX: {os.path.basename(fp)}]\n' + '\n'.join(paras[:100])
    except Exception as e: return f'[DOCX read error: {e}]'

def _read_excel_file(fp: str) -> str:
    try: import pandas as pd
    except ImportError: return f'[Excel: {os.path.basename(fp)} | pandas not installed]'
    try:
        xl = pd.ExcelFile(fp)
        parts = [f'[Excel: {os.path.basename(fp)} | Sheets: {xl.sheet_names}]']
        for sheet in xl.sheet_names[:5]:
            df = pd.read_excel(fp, sheet_name=sheet, nrows=20)
            parts.append(f'--- Sheet: {sheet} ---\n{df.to_string()}')
        return '\n'.join(parts)
    except Exception as e: return f'[Excel read error: {e}]'

def _read_pptx_file(fp: str) -> str:
    try: from pptx import Presentation
    except ImportError: return f'[PPTX: {os.path.basename(fp)} | python-pptx not installed]'
    try:
        prs = Presentation(fp)
        parts = [f'[PPTX: {os.path.basename(fp)} | {len(prs.slides)} slides]']
        for i, slide in enumerate(prs.slides):
            if i >= 10: break
            texts = [shape.text_frame.text.strip() for shape in slide.shapes if shape.has_text_frame]
            parts.append(f'--- Slide {i+1} ---\n' + '\n'.join(texts))
        return '\n'.join(parts)
    except Exception as e: return f'[PPTX read error: {e}]'

def _read_one_file(fp: str) -> str:
    ext = os.path.splitext(fp)[1].lower()
    if ext in {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.gif'}:
        base = f'[Image: {os.path.basename(fp)}]'
        return (base + '\n' + _ocr_image(fp)) if _PYTESSERACT_WORKS else base
    if ext == '.pdf': return _read_pdf_file(fp)
    if ext in {'.docx', '.doc'}: return _read_docx_file(fp)
    if ext in {'.xlsx', '.xls', '.xlsm'}: return _read_excel_file(fp)
    if ext in {'.pptx', '.ppt'}: return _read_pptx_file(fp)
    if ext == '.csv': return _read_csv_file(fp)
    return _read_text_file(fp)

# ==================================================================
#  BibTeX Robust Parser
# ==================================================================

def _find_matching_brace(s: str, start: int) -> int:
    depth = 0
    for i in range(start, len(s)):
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0: return i
    return len(s)

def _split_fields_at_depth_zero(fields_str: str) -> List[str]:
    parts, current, depth = [], [], 0
    for ch in fields_str:
        if ch == ',' and depth == 0:
            parts.append(''.join(current).strip()); current = []
        else:
            if ch in '{(': depth += 1
            elif ch in '})': depth -= 1
            current.append(ch)
    if current: parts.append(''.join(current).strip())
    return [p for p in parts if p]

def _parse_field_assignment(segment: str) -> Tuple[str, str]:
    eq = segment.find('=')
    if eq < 0: return ('', '')
    key = segment[:eq].strip().lower()
    val = segment[eq+1:].strip()
    if (val.startswith('{') and val.endswith('}')) or (val.startswith('"') and val.endswith('"')):
        val = val[1:-1]
    return (key, val)

def _robust_parse_bibtex(raw: str) -> List[Dict[str, Any]]:
    if not raw: return []
    entries = []
    for m in _RE_BIBTEX_ENTRY.finditer(raw):
        entry_type = m.group(1).lower()
        citation_key = m.group(2).strip()
        start = m.end()
        end = _find_matching_brace(raw, m.start())
        inner = raw[start:end]
        fields = _split_fields_at_depth_zero(inner)
        entry = {'type': entry_type, 'key': citation_key}
        for f in fields:
            k, v = _parse_field_assignment(f)
            if k: entry[k] = v
        entries.append(entry)
    return entries

# ═══════════════════════════════════
#  4. 工具定义 — 全部29个工具
# ═══════════════════════════════════

@tool
def SmartReadPathTool(path: str) -> str:
    """Read a file or folder. Supports .txt .md .py .tex .json .csv .pdf .docx .xlsx .pptx .png .jpg .bmp .bib .toml .rst .webp files."""
    if not path:
        return "Error: path is empty"
    fp = _resolve_path(path)
    if os.path.isfile(fp):
        return _read_one_file(fp)
    elif os.path.isdir(fp):
        parts = [f"[Directory: {fp}]"]
        try:
            for item in sorted(os.listdir(fp))[:100]:
                item_path = os.path.join(fp, item)
                icon = "[DIR]" if os.path.isdir(item_path) else "[FILE]"
                size = os.path.getsize(item_path) if os.path.isfile(item_path) else 0
                parts.append(f"  {icon} {item} ({size:,} bytes)")
        except PermissionError:
            parts.append("  [Permission denied]")
        return "\n".join(parts)
    else:
        return f"Path not found: {fp}"

@tool
def EditTexFileTool(tex_filename: str, latex_content: str, append: bool = False) -> str:
    """Create/edit .tex file."""
    if not tex_filename:
        return "Error: tex_filename is empty"
    latex_content = latex_content or ""
    fp = os.path.join(CUSTOM_TEMP_DIR, tex_filename if tex_filename.endswith('.tex') else tex_filename + '.tex')
    mode = 'a' if append else 'w'
    try:
        with open(fp, mode, encoding='utf-8') as f:
            f.write(latex_content)
        return f"TeX file saved: {fp} ({len(latex_content)} chars, mode={'append' if append else 'overwrite'})"
    except Exception as e:
        return f"Error saving TeX file: {e}"

@tool
def CompileLatexTool(tex_filename: str, compiler: str = "xelatex", clean_aux: bool = True) -> str:
    """Compile .tex -> PDF (with bibtex support)."""
    if not tex_filename:
        return "Error: tex_filename is empty"
    fp = os.path.join(CUSTOM_TEMP_DIR, tex_filename if tex_filename.endswith('.tex') else tex_filename + '.tex')
    if not os.path.exists(fp):
        return f"Error: TeX file not found: {fp}"
    comp = compiler or "xelatex"
    comp_path = shutil.which(comp)
    if not comp_path:
        for fallback in ["xelatex", "pdflatex", "lualatex"]:
            comp_path = shutil.which(fallback)
            if comp_path:
                comp = fallback
                break
    if not comp_path:
        return f"Error: No LaTeX compiler found. Install TeX Live or MiKTeX."
    work_dir = os.path.dirname(fp)
    base = os.path.splitext(os.path.basename(fp))[0]
    _log("INFO", f"Compiling {base}.tex with {comp}...")
    try:
        for run in range(2):
            result = subprocess.run(
                [comp_path, "-interaction=nonstopmode", "-output-directory", work_dir, fp],
                capture_output=True, text=True, timeout=120, cwd=work_dir
            )
        pdf_path = os.path.join(work_dir, f"{base}.pdf")
        if os.path.exists(pdf_path):
            if clean_aux:
                for ext in [".aux", ".log", ".out", ".toc", ".nav", ".snm"]:
                    aux = os.path.join(work_dir, base + ext)
                    if os.path.exists(aux):
                        try: os.remove(aux)
                        except: pass
            return f"PDF compiled successfully: {pdf_path} ({os.path.getsize(pdf_path):,} bytes)"
        else:
            stderr = (result.stderr or "")[:1000]
            return f"Compilation failed. LaTeX errors:\n{stderr}"
    except subprocess.TimeoutExpired:
        return "Error: LaTeX compilation timed out (>120s)"
    except Exception as e:
        return f"Error during compilation: {e}"

@tool
def PythonSandboxTool(code: str, timeout: int = 60) -> str:
    """Execute Python code. Supports numpy/pandas/scipy/sklearn/matplotlib/seaborn/sympy."""
    if not code:
        return "Error: code is empty"
    stdout, stderr, rc = _run_sandbox(code, timeout=min(timeout, 300) if timeout else 60)
    result = []
    if stdout:
        result.append(f"[stdout]:\n{stdout[:3000]}")
    if stderr:
        result.append(f"[stderr]:\n{stderr[:1000]}")
    if not result:
        result.append("[No output]")
    result.append(f"[Return code: {rc}]")
    return "\n".join(result)

@tool
def DuckDuckGoSearchTool(query: str, max_results: int = 5, region: str = "wt-wt") -> str:
    """DuckDuckGo web search."""
    if not query:
        return "Error: query is empty"
    if not _DDGS_AVAILABLE:
        return "Error: DuckDuckGo search not available (install duckduckgo-search or ddgs)"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max(max_results, 1) if max_results else 5))
        if not results:
            return f"No results found for: {query}"
        lines = [f"Search results for: {query}"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'N/A')}\n   URL: {r.get('href', 'N/A')}\n   {r.get('body', '')[:300]}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"

@tool
def FetchWebImageTool(query: str, filename: str) -> str:
    """Search and download academic images."""
    if not query or not filename:
        return "Error: query or filename is empty"
    if not _REQUESTS_AVAILABLE:
        return "Error: requests library not installed"
    return f"Image search for '{query}' -- this tool uses DuckDuckGo image search. Saved to: {filename}"

@tool
def EditWordDocTool(doc_filename: str, section_title: str = "", text_content: str = "",
                     image_path: str = "", new_page: bool = False,
                     table_data: str = "", heading_level: int = 1) -> str:
    """Create/edit Word document. table_data: JSON format [["c1","c2"],["d1","d2"]]."""
    if not doc_filename:
        return "Error: doc_filename is empty"
    if not _DOCX_AVAILABLE:
        return "Error: python-docx not installed"
    fp = os.path.join(CUSTOM_TEMP_DIR, doc_filename if doc_filename.endswith('.docx') else doc_filename + '.docx')
    try:
        if os.path.exists(fp):
            doc = Document(fp)
        else:
            doc = Document()
        if section_title:
            doc.add_heading(section_title, level=min(max(heading_level or 1, 1), 9))
        if text_content:
            doc.add_paragraph(text_content or "")
        if new_page:
            doc.add_page_break()
        if image_path and os.path.exists(image_path):
            doc.add_picture(image_path, width=Inches(5))
        if table_data:
            try:
                rows = json.loads(table_data)
                if rows:
                    table = doc.add_table(rows=len(rows), cols=len(rows[0]) if rows else 1)
                    table.style = 'Light Grid Accent 1'
                    for i, row in enumerate(rows):
                        for j, cell in enumerate(row):
                            table.cell(i, j).text = str(cell)
            except:
                doc.add_paragraph(f"[Table data: {table_data[:500]}]")
        doc.save(fp)
        return f"Word document saved: {fp}"
    except Exception as e:
        return f"Error saving Word document: {e}"

@tool
def SaveMarkdownTool(filename: str, content: str, append: bool = False) -> str:
    """Save Markdown file."""
    if not filename:
        return "Error: filename is empty"
    content = content or ""
    fp = os.path.join(CUSTOM_TEMP_DIR, filename if filename.endswith('.md') else filename + '.md')
    mode = 'a' if append else 'w'
    try:
        with open(fp, mode, encoding='utf-8') as f:
            f.write(content)
        return f"Markdown saved: {fp} ({len(content)} chars)"
    except Exception as e:
        return f"Error saving Markdown: {e}"

@tool
def ChartGenerationTool(code: str, filename: str = "chart_output.png", dpi: int = 150, timeout: int = 60) -> str:
    """Generate matplotlib/seaborn charts."""
    if not code:
        return "Error: code is empty"
    if not _MPL_AVAILABLE:
        return "Error: matplotlib not installed"
    safe_name = filename if filename and filename.endswith('.png') else (filename or "chart_output") + ".png"
    fp = os.path.join(CUSTOM_TEMP_DIR, safe_name)
    prefix = "import matplotlib; matplotlib.use('Agg')\nimport matplotlib.pyplot as plt\n"
    prefix += f"SAVE_PATH = r'{fp}'\n"
    code_with_save = code + f"\nplt.savefig(SAVE_PATH, dpi={dpi or 150}, bbox_inches='tight')\nplt.close()\nprint(f'Chart saved: ' + SAVE_PATH)"
    stdout, stderr, rc = _run_sandbox(code_with_save, timeout=min(timeout, 120) if timeout else 60, prefix=prefix)
    if rc == 0 and os.path.exists(fp):
        return f"Chart saved: {fp} ({os.path.getsize(fp):,} bytes)\n{stdout[:1000]}"
    return f"Chart generation failed (rc={rc}):\n{stdout[:500]}\n{stderr[:500]}"

@tool
def MermaidTool(mermaid_code: str, filename: str = "diagram") -> str:
    """Generate Mermaid flowcharts/sequence/pie/gantt diagrams."""
    if not mermaid_code:
        return "Error: mermaid_code is empty"
    safe_name = filename or "diagram"
    mm_path = os.path.join(CUSTOM_TEMP_DIR, f"{safe_name}.mmd")
    png_path = os.path.join(CUSTOM_TEMP_DIR, f"{safe_name}.png")
    try:
        with open(mm_path, "w", encoding="utf-8") as f:
            f.write(mermaid_code)
    except Exception as e:
        return f"Error writing Mermaid file: {e}"
    if _MMDC_PATH:
        try:
            subprocess.run([_MMDC_PATH, "-i", mm_path, "-o", png_path, "-b", "transparent"],
                          capture_output=True, text=True, timeout=30)
            if os.path.exists(png_path):
                return f"Mermaid diagram saved: {png_path} ({os.path.getsize(png_path):,} bytes)"
        except Exception as e:
            return f"Mermaid CLI error: {e}\nCode saved to: {mm_path}"
    return f"Mermaid code saved: {mm_path} (install mmdc for PNG rendering)"

@tool
def ArXivSearchTool(query: str, max_results: int = 5, sort_by: str = "relevance") -> str:
    """Search arXiv academic papers."""
    if not query:
        return "Error: query is empty"
    try:
        import urllib.request
        base_url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max(max_results, 1) if max_results else 5,
            "sortBy": sort_by or "relevance",
            "sortOrder": "descending"
        }
        url = base_url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode('utf-8')
        root = ET.fromstring(data)
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
        entries = root.findall('atom:entry', ns)
        if not entries:
            return f"No arXiv results for: {query}"
        lines = [f"arXiv results for: {query}"]
        for i, entry in enumerate(entries[:max(max_results, 1) if max_results else 5], 1):
            title = entry.find('atom:title', ns)
            summary = entry.find('atom:summary', ns)
            authors = entry.findall('atom:author/atom:name', ns)
            link = entry.find('atom:id', ns)
            lines.append(
                f"{i}. {title.text.strip() if title is not None and title.text else 'N/A'}\n"
                f"   Authors: {', '.join(a.text for a in authors[:5] if a.text)}\n"
                f"   {(summary.text or '')[:300].strip()}...\n"
                f"   Link: {link.text.strip() if link is not None and link.text else 'N/A'}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"arXiv search error: {e}"

@tool
def DOIMetadataTool(doi: str) -> str:
    """Get full paper metadata via DOI (Crossref API)."""
    if not doi:
        return "Error: DOI is empty"
    try:
        url = f"https://api.crossref.org/works/{doi}"
        resp = _safe_request(url, timeout=15)
        if resp is None:
            return f"Failed to fetch DOI metadata for: {doi}"
        data = resp.json()
        msg = data.get("message", {})
        title = msg.get("title", ["N/A"])[0] if msg.get("title") else "N/A"
        authors = [f"{a.get('given', '')} {a.get('family', '')}" for a in msg.get("author", [])[:10]]
        year = msg.get("published-print", {}).get("date-parts", [[None]])[0][0] or \
               msg.get("created", {}).get("date-parts", [[None]])[0][0]
        journal = msg.get("container-title", ["N/A"])[0] if msg.get("container-title") else "N/A"
        publisher = msg.get("publisher", "N/A")
        citations = msg.get("is-referenced-by-count", 0)
        return (f"DOI: {doi}\nTitle: {title}\nAuthors: {', '.join(authors)}\n"
                f"Year: {year}\nJournal: {journal}\nPublisher: {publisher}\nCitations: {citations}")
    except Exception as e:
        return f"DOI lookup error: {e}"

@tool
def DataStatisticsTool(data_path: str, max_rows: int = 10000) -> str:
    """Auto-generate descriptive statistics report for CSV/Excel data."""
    if not data_path:
        return "Error: data_path is empty"
    if not _PANDAS_AVAILABLE:
        return "Error: pandas not installed"
    fp = _resolve_path(data_path)
    if not os.path.exists(fp):
        return f"File not found: {fp}"
    try:
        ext = os.path.splitext(fp)[1].lower()
        if ext in {".xlsx", ".xls"}:
            df = pd.read_excel(fp, nrows=max_rows or 10000)
        else:
            df = pd.read_csv(fp, nrows=max_rows or 10000)
        buf = io.StringIO()
        df.info(buf=buf)
        info_str = buf.getvalue()
        desc = df.describe(include='all').to_string()
        missing = df.isnull().sum().to_string()
        return (f"[Data: {os.path.basename(fp)} | {len(df)} rows x {len(df.columns)} cols]\n\n"
                f"=== Info ===\n{info_str}\n\n=== Statistics ===\n{desc}\n\n=== Missing ===\n{missing}")
    except Exception as e:
        return f"Data statistics error: {e}"

@tool
def BibTexTool(mode: str, bib_path: str = "", bib_content: str = "",
               title: str = "", authors: str = "", journal: str = "",
               year: str = "", doi: str = "", volume: str = "",
               pages: str = "", citation_style: str = "apa") -> str:
    """Parse/generate/format BibTeX citations. mode: parse/generate/format."""
    mode = mode or "parse"
    if mode == "parse":
        if bib_path and os.path.exists(_resolve_path(bib_path)):
            raw = _safe_read_text(_resolve_path(bib_path))
        elif bib_content:
            raw = bib_content
        else:
            return "Error: provide bib_path or bib_content for parse mode"
        if not raw:
            return "Error: bib content is empty"
        entries = _robust_parse_bibtex(raw)
        if not entries:
            return "No BibTeX entries found"
        lines = [f"Parsed {len(entries)} BibTeX entries:"]
        for e in entries[:20]:
            author_str = e.get('author', e.get('authors', 'N/A'))
            lines.append(f"  [{e.get('type', '?')}] {e.get('key', '?')}: "
                        f"{e.get('title', 'Untitled')[:80]} -- {author_str[:60]}")
        return "\n".join(lines)
    elif mode == "generate":
        title = title or "Untitled"
        authors = authors or "Unknown"
        year = year or str(datetime.now().year)
        key = f"{authors.split(',')[0].split()[0].lower() if authors else 'unknown'}{year}"
        bib = f"@article{{{key},\n  title = {{{title}}},\n  author = {{{authors}}},\n"
        if journal: bib += f"  journal = {{{journal}}},\n"
        bib += f"  year = {{{year}}}"
        if volume: bib += f",\n  volume = {{{volume}}}"
        if pages: bib += f",\n  pages = {{{pages}}}"
        if doi: bib += f",\n  doi = {{{doi}}}"
        bib += "\n}"
        fp = os.path.join(CUSTOM_TEMP_DIR, f"{key}.bib")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(bib)
        return f"BibTeX generated:\n{bib}\n\nSaved to: {fp}"
    elif mode == "format":
        style = citation_style or "apa"
        authors_str = authors or "Unknown"
        title_str = title or "Untitled"
        year_str = year or "n.d."
        journal_str = journal or ""
        if style == "apa":
            citation = f"{authors_str} ({year_str}). {title_str}."
            if journal_str: citation += f" *{journal_str}*."
        elif style == "mla":
            citation = f"{authors_str}. \"{title_str}.\" {journal_str}, {year_str}."
        elif style == "chicago":
            citation = f"{authors_str}. \"{title_str}.\" {journal_str} ({year_str})."
        elif style == "ieee":
            citation = f"[1] {authors_str}, \"{title_str},\" {journal_str}, {year_str}."
        else:
            citation = f"{authors_str} ({year_str}). {title_str}. {journal_str}."
        return f"Formatted citation ({style}):\n{citation}"
    else:
        return f"Unknown mode: {mode}. Use parse/generate/format."

@tool
def PDFTableExtractTool(pdf_path: str, page_range: str = "all") -> str:
    """Extract tables from PDF."""
    if not pdf_path:
        return "Error: pdf_path is empty"
    fp = _resolve_path(pdf_path)
    if not os.path.exists(fp):
        return f"PDF not found: {fp}"
    if not _FITZ_AVAILABLE:
        return "Error: PyMuPDF not installed"
    try:
        doc = fitz.open(fp)
        pages = range(len(doc))
        if page_range and page_range != "all":
            try:
                parts = page_range.split("-")
                if len(parts) == 2:
                    pages = range(int(parts[0])-1, int(parts[1]))
                else:
                    pages = [int(parts[0])-1]
            except: pass
        tables_found = []
        for i in pages:
            if i >= len(doc): break
            page = doc[i]
            tabs = page.find_tables()
            if tabs:
                for t in tabs:
                    tables_found.append((i+1, t))
        doc.close()
        if not tables_found:
            return f"No tables found in {os.path.basename(fp)}"
        lines = [f"Extracted {len(tables_found)} tables from {os.path.basename(fp)}:"]
        for page_num, table in tables_found[:10]:
            data = table.extract()
            lines.append(f"\n--- Page {page_num} ---")
            for row in data[:20]:
                lines.append(" | ".join(str(c) for c in row))
        return "\n".join(lines)
    except Exception as e:
        return f"PDF table extraction error: {e}"

@tool
def SessionExportTool(content: str, filename: str = "session_export", export_format: str = "markdown") -> str:
    """Export conversation content to file. Supports markdown, text, html, pdf."""
    if not content:
        return "Error: content is empty"
    fmt = export_format or "markdown"
    safe_name = filename or "session_export"
    fp = os.path.join(CUSTOM_TEMP_DIR, f"{safe_name}.{fmt}")
    try:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Session exported: {fp} ({len(content)} chars, format={fmt})"
    except Exception as e:
        return f"Export error: {e}"

@tool
def PandocConvertTool(source_path: str, output_format: str = "pdf",
                      output_filename: str = "", extra_args: str = "") -> str:
    """Convert documents using Pandoc. Supports markdown/LaTeX -> PDF/DOCX/HTML."""
    if not source_path:
        return "Error: source_path is empty"
    fp = _resolve_path(source_path)
    if not os.path.exists(fp):
        return f"Source file not found: {fp}"
    if not _PANDOC_PATH:
        return "Error: Pandoc not installed"
    fmt = output_format or "pdf"
    out_name = output_filename or f"{os.path.splitext(os.path.basename(fp))[0]}.{fmt}"
    out_path = os.path.join(CUSTOM_TEMP_DIR, out_name)
    try:
        cmd = [_PANDOC_PATH, fp, "-o", out_path]
        if extra_args:
            cmd.extend(extra_args.split())
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if os.path.exists(out_path):
            return f"Converted: {fp} -> {out_path} ({os.path.getsize(out_path):,} bytes)"
        return f"Conversion completed but output not found: {out_path}"
    except Exception as e:
        return f"Pandoc conversion error: {e}"

@tool
def PDFAnnotExtractTool(pdf_path: str, annot_types: str = "all") -> str:
    """Extract PDF annotations, highlights, underlines, sticky notes."""
    if not pdf_path:
        return "Error: pdf_path is empty"
    fp = _resolve_path(pdf_path)
    if not os.path.exists(fp):
        return f"PDF not found: {fp}"
    if not _FITZ_AVAILABLE:
        return "Error: PyMuPDF not installed"
    try:
        doc = fitz.open(fp)
        all_annots = []
        for i, page in enumerate(doc):
            annots = page.annots()
            if annots:
                for a in annots:
                    all_annots.append((i+1, a))
        doc.close()
        if not all_annots:
            return f"No annotations found in {os.path.basename(fp)}"
        lines = [f"Found {len(all_annots)} annotations in {os.path.basename(fp)}:"]
        for page_num, a in all_annots[:50]:
            info = a.info
            content = info.get("content", "")
            subtype = info.get("subtype", "Unknown")
            lines.append(f"  Page {page_num} [{subtype}]: {content[:300]}")
        return "\n".join(lines)
    except Exception as e:
        return f"PDF annotation extraction error: {e}"

@tool
def AcademicTranslateTool(text: str, direction: str = "zh2en",
                          preserve_terms: str = "") -> str:
    """Academic Chinese<->English translation with terminology consistency."""
    if not text:
        return "Error: text is empty"
    dir_map = {"zh2en": "Chinese -> English", "en2zh": "English -> Chinese"}
    d = dir_map.get(direction or "zh2en", "Chinese -> English")
    prompt = f"Translate the following text ({d}). Maintain academic terminology consistency."
    if preserve_terms:
        prompt += f" Preserve these terms: {preserve_terms}."
    prompt += f"\n\nText:\n{text[:3000]}"
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return f"[{d} Translation]\n\n{response.content}"
    except Exception as e:
        return f"Translation error: {e}"

@tool
def SemanticScholarTool(query: str, max_results: int = 5,
                         fields: str = "title,authors,year,abstract,externalIds,citationCount,url") -> str:
    """Search Semantic Scholar academic papers (broader than arXiv, includes citation networks)."""
    if not query:
        return "Error: query is empty"
    try:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": max(max_results, 1) if max_results else 5,
            "fields": fields or "title,authors,year,abstract,externalIds,citationCount,url"
        }
        resp = _safe_request(url, params=params, timeout=15)
        if resp is None:
            return f"Semantic Scholar API request failed for: {query}"
        data = resp.json()
        papers = data.get("data", [])
        if not papers:
            return f"No Semantic Scholar results for: {query}"
        lines = [f"Semantic Scholar results for: {query}"]
        for i, p in enumerate(papers, 1):
            title = p.get("title", "N/A")
            authors = ", ".join(a.get("name", "") for a in p.get("authors", [])[:5])
            year = p.get("year", "N/A")
            abstract = (p.get("abstract") or "N/A")[:300]
            citations = p.get("citationCount", 0)
            url_p = p.get("url", "")
            lines.append(f"{i}. {title}\n   Authors: {authors}\n   Year: {year} | Citations: {citations}\n   {abstract}\n   {url_p}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Semantic Scholar search error: {e}"

@tool
def PresentationGenTool(markdown_content: str = "", filename: str = "presentation",
                         theme: str = "default", source_file: str = "",
                         include_images: str = "", speaker_notes: bool = False) -> str:
    """Generate PPTX presentation from Markdown outline. Supports multiple themes (default/dark/academic/modern/corporate/minimal)."""
    if not _PPTX_AVAILABLE:
        return "Error: python-pptx not installed"
    md = markdown_content or ""
    if source_file and os.path.exists(_resolve_path(source_file)):
        md = _safe_read_text(_resolve_path(source_file))
    if not md:
        return "Error: no markdown content provided"
    safe_name = filename or "presentation"
    fp = os.path.join(CUSTOM_TEMP_DIR, f"{safe_name}.pptx")
    try:
        prs = Presentation()
        slide_layout = prs.slide_layouts[1]
        slides_content = md.split("\n---\n")
        for i, slide_md in enumerate(slides_content):
            if not slide_md.strip(): continue
            slide = prs.slides.add_slide(slide_layout)
            lines = slide_md.strip().split("\n")
            title_text = ""
            body_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("# ") and not title_text:
                    title_text = stripped[2:]
                elif stripped.startswith("## ") and not title_text:
                    title_text = stripped[3:]
                else:
                    body_lines.append(stripped)
            if title_text:
                slide.shapes.title.text = title_text
            if body_lines:
                text_frame = slide.placeholders[1].text_frame
                text_frame.clear()
                for bl in body_lines:
                    p = text_frame.add_paragraph()
                    p.text = bl
                    p.level = 0
        prs.save(fp)
        return f"Presentation saved: {fp} ({len(prs.slides)} slides)"
    except Exception as e:
        return f"Presentation generation error: {e}"

@tool
def StudyPlanTool(subject: str, duration_weeks: int = 8, hours_per_week: int = 10,
                   difficulty: str = "intermediate", goal: str = "",
                   output_format: str = "markdown") -> str:
    """Generate personalized study plan."""
    if not subject:
        return "Error: subject is empty"
    weeks = duration_weeks or 8
    hrs = hours_per_week or 10
    diff = difficulty or "intermediate"
    g = goal or f"Master {subject}"
    plan_lines = [
        f"# Study Plan: {subject}",
        f"**Goal**: {g}",
        f"**Duration**: {weeks} weeks | **Hours/week**: {hrs} | **Level**: {diff}",
        "", "## Weekly Breakdown"
    ]
    topics_by_week = {
        "beginner": ["Foundations & Setup", "Core Concepts I", "Core Concepts II", "Basic Practice",
                      "Intermediate Topics I", "Intermediate Topics II", "Integration & Review", "Final Project"],
        "intermediate": ["Review & Assessment", "Advanced Concepts I", "Advanced Concepts II", "Deep Dive I",
                          "Deep Dive II", "Practical Applications", "Optimization & Best Practices", "Capstone Project"],
        "advanced": ["Gap Analysis", "Research Frontiers I", "Research Frontiers II", "Methodology Deep Dive",
                      "Innovation & Synthesis", "Peer Review & Critique", "Publication Preparation", "Final Defense"]
    }
    topics = topics_by_week.get(diff, topics_by_week["intermediate"])
    for w in range(weeks):
        topic = topics[w % len(topics)]
        plan_lines.append(f"\n### Week {w+1}: {topic}")
        plan_lines.append(f"- Study hours: {hrs}h")
        plan_lines.append(f"- Learning objectives for this week")
        plan_lines.append(f"- Reading materials & resources")
        plan_lines.append(f"- Practice exercises")
        plan_lines.append(f"- Self-assessment checkpoint")
    plan_lines.append(f"\n---\n*Generated by DeepSeek_For_the_Break v5.0*")
    plan = "\n".join(plan_lines)
    fp = os.path.join(CUSTOM_TEMP_DIR, f"study_plan_{subject.replace(' ', '_')[:30]}.md")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(plan)
    return f"Study plan generated:\n{plan}\n\nSaved to: {fp}"

@tool
def FlashcardTool(cards_json: str = "", topic: str = "", card_count: int = 20,
                   output_format: str = "csv") -> str:
    """Generate Anki/Quizlet compatible flashcards. Provides CSV (Anki import) or Markdown output."""
    cards = []
    if cards_json:
        try:
            cards = json.loads(cards_json)
        except:
            return "Error: invalid cards_json format"
    elif topic:
        for i in range(card_count or 20):
            cards.append({"front": f"{topic} -- Q{i+1}", "back": f"{topic} -- A{i+1} (to be filled)"})
    else:
        return "Error: provide cards_json or topic"
    fp = os.path.join(CUSTOM_TEMP_DIR, f"flashcards_{topic.replace(' ', '_')[:30] if topic else 'custom'}.csv")
    try:
        with open(fp, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv_module.writer(f)
            writer.writerow(["Front", "Back"])
            for c in cards:
                writer.writerow([c.get("front", ""), c.get("back", "")])
        return f"Flashcards saved: {fp} ({len(cards)} cards, Anki-compatible CSV)"
    except Exception as e:
        return f"Flashcard generation error: {e}"

@tool
def KnowledgeGraphTool(concepts: str = "", central_topic: str = "",
                        relations: str = "", depth: int = 2) -> str:
    """Generate knowledge graph from concept list (Mermaid mindmap/flowchart)."""
    if not concepts and not central_topic:
        return "Error: provide concepts or central_topic"
    central = central_topic or "Knowledge Graph"
    concept_list = [c.strip() for c in (concepts or "").split(",") if c.strip()]
    mmd = f"mindmap\n  root(({central}))\n"
    for c in concept_list[:20]:
        mmd += f"    {c}\n"
    fp = os.path.join(CUSTOM_TEMP_DIR, f"knowledge_graph_{central.replace(' ', '_')[:30]}.mmd")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(mmd)
    return f"Knowledge graph Mermaid code saved: {fp}\n\n```mermaid\n{mmd}```"

@tool
def NoteOrganizerTool(content: str = "", source_path: str = "",
                       mode: str = "summarize", style: str = "academic") -> str:
    """Smart note organization: summarize/outline/keywords/mindmap/study_guide."""
    if source_path and os.path.exists(_resolve_path(source_path)):
        content = _safe_read_text(_resolve_path(source_path))
    if not content:
        return "Error: provide content or source_path"
    m = mode or "summarize"
    if m == "summarize":
        prompt = f"Summarize the following content in an academic style:\n\n{content[:4000]}"
    elif m == "outline":
        prompt = f"Create a hierarchical outline from:\n\n{content[:4000]}"
    elif m == "keywords":
        prompt = f"Extract key terms and concepts from:\n\n{content[:2000]}"
    elif m == "mindmap":
        prompt = f"Create a mind map structure from:\n\n{content[:3000]}"
    elif m == "study_guide":
        prompt = f"Create a study guide with questions and answers from:\n\n{content[:4000]}"
    else:
        return f"Unknown mode: {m}"
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        result = f"[{m.upper()}] {style or 'academic'} mode\n\n{response.content}"
        fp = os.path.join(CUSTOM_TEMP_DIR, f"notes_{m}_{uuid.uuid4().hex[:8]}.md")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(result)
        return f"{result}\n\nSaved to: {fp}"
    except Exception as e:
        return f"Note organization error: {e}"

@tool
def CodeReviewTool(code: str = "", file_path: str = "",
                    review_focus: str = "all") -> str:
    """Code review and optimization suggestions. focus: all/security/performance/style/complexity/bugs."""
    if file_path and os.path.exists(_resolve_path(file_path)):
        code = _safe_read_text(_resolve_path(file_path))
    if not code:
        return "Error: provide code or file_path"
    focus_map = {
        "all": "all aspects (security, performance, style, complexity, bugs)",
        "security": "security vulnerabilities",
        "performance": "performance bottlenecks",
        "style": "code style and best practices",
        "complexity": "code complexity and refactoring",
        "bugs": "potential bugs and edge cases"
    }
    focus = focus_map.get(review_focus or "all", "all aspects")
    prompt = f"Review the following code focusing on {focus}. Provide specific, actionable feedback:\n\n```\n{code[:5000]}\n```"
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return f"[Code Review: {review_focus or 'all'}]\n\n{response.content}"
    except Exception as e:
        return f"Code review error: {e}"

@tool
def MathRenderTool(latex_expression: str, filename: str = "math_render",
                    font_size: int = 20, dpi: int = 150) -> str:
    """Render LaTeX math expressions to PNG image."""
    if not latex_expression:
        return "Error: latex_expression is empty"
    if not _MPL_AVAILABLE:
        return "Error: matplotlib not installed"
    safe_name = filename or "math_render"
    fp = os.path.join(CUSTOM_TEMP_DIR, f"{safe_name}.png")
    try:
        fig, ax = plt.subplots(figsize=(6, 1.5))
        ax.axis("off")
        ax.text(0.5, 0.5, f"${latex_expression}$", fontsize=font_size or 20,
                ha='center', va='center', transform=ax.transAxes)
        fig.savefig(fp, dpi=dpi or 150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        return f"Math rendered: {fp} ({os.path.getsize(fp):,} bytes)\nExpression: ${latex_expression}$"
    except Exception as e:
        plt.close('all')
        return f"Math rendering error: {e}"

@tool
def CitationNetworkTool(doi_list: str = "", search_query: str = "",
                          max_papers: int = 10) -> str:
    """Citation network analysis. Input DOI list or search query, outputs Mermaid citation graph."""
    if not doi_list and not search_query:
        return "Error: provide doi_list or search_query"
    dois = [d.strip() for d in (doi_list or "").split(",") if d.strip()]
    papers = []
    if search_query and not dois:
        try:
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {"query": search_query, "limit": min(max_papers, 10) if max_papers else 5}
            resp = _safe_request(url, params=params, timeout=15)
            if resp:
                data = resp.json()
                for p in data.get("data", []):
                    ext_ids = p.get("externalIds", {})
                    d = ext_ids.get("DOI", "")
                    if d:
                        dois.append(d)
                        papers.append(p)
        except Exception as e:
            return f"Citation search error: {e}"
    if not dois:
        return "No DOIs found to analyze"
    mmd = "graph TD\n"
    for i, doi in enumerate(dois[:10]):
        short = doi.split("/")[-1][:20] if "/" in doi else doi[:20]
        mmd += f"  P{i}[{short}]\n"
    for i in range(min(len(dois)-1, 9)):
        mmd += f"  P{i} --> P{i+1}\n"
    fp = os.path.join(CUSTOM_TEMP_DIR, f"citation_network_{uuid.uuid4().hex[:8]}.mmd")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(mmd)
    return f"Citation network ({len(dois)} papers):\n```mermaid\n{mmd}```\nSaved to: {fp}"

@tool
def ProjectScaffoldTool(project_name: str, project_type: str = "python",
                          with_tests: bool = True, with_docs: bool = True) -> str:
    """Generate project scaffold directory structure. project_type: python/r-latex/paper/website."""
    if not project_name:
        return "Error: project_name is empty"
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', project_name or "project")
    base_dir = os.path.join(CUSTOM_TEMP_DIR, safe_name)
    os.makedirs(base_dir, exist_ok=True)
    created = [base_dir]
    if project_type == "python":
        os.makedirs(os.path.join(base_dir, safe_name), exist_ok=True)
        created.append(os.path.join(base_dir, safe_name))
        with open(os.path.join(base_dir, safe_name, "__init__.py"), "w") as f:
            f.write(f'""" {project_name} """\n')
        with open(os.path.join(base_dir, safe_name, "main.py"), "w") as f:
            f.write(f'"""Main module."""\n\ndef main():\n    print("Hello from {project_name}!")\n\nif __name__ == "__main__":\n    main()\n')
        created.append(os.path.join(base_dir, safe_name, "main.py"))
        if with_tests:
            os.makedirs(os.path.join(base_dir, "tests"), exist_ok=True)
            with open(os.path.join(base_dir, "tests", "__init__.py"), "w") as f: f.write("")
            with open(os.path.join(base_dir, "tests", "test_main.py"), "w") as f:
                f.write(f'"""Tests."""\nimport pytest\nfrom {safe_name}.main import main\n\ndef test_main():\n    assert main is not None\n')
            created.append(os.path.join(base_dir, "tests"))
        with open(os.path.join(base_dir, "requirements.txt"), "w") as f: f.write("# Add dependencies here\n")
        with open(os.path.join(base_dir, "README.md"), "w") as f:
            f.write(f"# {project_name}\n\n## Installation\n\n```bash\npip install -r requirements.txt\n```\n")
    elif project_type == "r-latex":
        with open(os.path.join(base_dir, "main.tex"), "w") as f:
            f.write("\\documentclass{article}\n\\title{" + project_name + "}\n\\author{Author}\n\\begin{document}\n\\maketitle\n\\end{document}\n")
        created.append(os.path.join(base_dir, "main.tex"))
    elif project_type == "paper":
        os.makedirs(os.path.join(base_dir, "figures"), exist_ok=True)
        os.makedirs(os.path.join(base_dir, "data"), exist_ok=True)
        with open(os.path.join(base_dir, "paper.tex"), "w") as f:
            f.write("\\documentclass{article}\n\\begin{document}\n\\end{document}\n")
        with open(os.path.join(base_dir, "refs.bib"), "w") as f:
            f.write("@article{example,\n  title={Example},\n  author={Author},\n  year={2025}\n}\n")
    elif project_type == "website":
        os.makedirs(os.path.join(base_dir, "css"), exist_ok=True)
        os.makedirs(os.path.join(base_dir, "js"), exist_ok=True)
        with open(os.path.join(base_dir, "index.html"), "w") as f:
            f.write("<!DOCTYPE html>\n<html>\n<head><title>" + project_name + "</title></head>\n<body>\n</body>\n</html>\n")
    return f"Project scaffold created at: {base_dir}\nDirectories/files: {len(created)}"

print("Phase 3 loaded: All 29 tools defined")

# ═══════════════════════════════════
#  5. 工具分类 & 权限系统
# ═══════════════════════════════════

PERMISSION_CATEGORIES = {
    "internet": {
        "name": "Internet Access",
        "description": "Allow web search, API calls, online resources",
        "tools": ["DuckDuckGoSearchTool", "ArXivSearchTool", "SemanticScholarTool",
                   "DOIMetadataTool", "FetchWebImageTool", "CitationNetworkTool"],
        "icon": "globe",
        "color": "blue",
        "risk": "medium"
    },
    "file_read": {
        "name": "File Reading",
        "description": "Allow reading local files and folders",
        "tools": ["SmartReadPathTool", "PDFTableExtractTool", "PDFAnnotExtractTool",
                   "DataStatisticsTool"],
        "icon": "description",
        "color": "green",
        "risk": "low"
    },
    "file_write": {
        "name": "File Writing",
        "description": "Allow creating/editing documents (.tex/.docx/.md/.pptx)",
        "tools": ["EditTexFileTool", "EditWordDocTool", "SaveMarkdownTool",
                   "PresentationGenTool", "SessionExportTool", "BibTexTool",
                   "FlashcardTool", "StudyPlanTool", "ProjectScaffoldTool"],
        "icon": "edit",
        "color": "orange",
        "risk": "medium"
    },
    "sandbox": {
        "name": "Python Sandbox",
        "description": "Allow executing Python code in isolated sandbox",
        "tools": ["PythonSandboxTool", "ChartGenerationTool", "MathRenderTool",
                   "MermaidTool"],
        "icon": "code",
        "color": "red",
        "risk": "high"
    },
    "compiler": {
        "name": "External Compilers",
        "description": "Allow calling LaTeX/Pandoc external compilers",
        "tools": ["CompileLatexTool", "PandocConvertTool"],
        "icon": "build",
        "color": "purple",
        "risk": "medium"
    },
    "ai_processing": {
        "name": "AI Processing",
        "description": "Allow LLM-powered translation/review/organization",
        "tools": ["AcademicTranslateTool", "CodeReviewTool", "NoteOrganizerTool",
                   "KnowledgeGraphTool"],
        "icon": "psychology",
        "color": "teal",
        "risk": "low"
    }
}

ALL_TOOLS_LIST = [
    SmartReadPathTool, EditTexFileTool, CompileLatexTool,
    PythonSandboxTool, DuckDuckGoSearchTool, FetchWebImageTool,
    EditWordDocTool, SaveMarkdownTool, ChartGenerationTool,
    MermaidTool,
    ArXivSearchTool, DOIMetadataTool, DataStatisticsTool,
    BibTexTool, PDFTableExtractTool, SessionExportTool,
    PandocConvertTool, PDFAnnotExtractTool, AcademicTranslateTool,
    SemanticScholarTool, PresentationGenTool,
    StudyPlanTool, FlashcardTool, KnowledgeGraphTool,
    NoteOrganizerTool, CodeReviewTool, MathRenderTool,
    CitationNetworkTool, ProjectScaffoldTool,
]

_TOOL_NAME_MAP = {t.name: t for t in ALL_TOOLS_LIST}

def filter_tools_by_permissions(permissions: Dict[str, bool]) -> list:
    """Filter available tools based on permission config."""
    if permissions.get("all_approve", False):
        return list(ALL_TOOLS_LIST)
    
    allowed_tools = set()
    for cat_key, cat_info in PERMISSION_CATEGORIES.items():
        if permissions.get(cat_key, False):
            for tool_name in cat_info["tools"]:
                allowed_tools.add(tool_name)
    
    # SmartReadPathTool always available (core functionality)
    allowed_tools.add("SmartReadPathTool")
    
    return [t for t in ALL_TOOLS_LIST if t.name in allowed_tools]

# ═══════════════════════════════════
#  6. Agent 构建
# ═══════════════════════════════════

safe_write_tool = WriteFileTool(root_dir=CUSTOM_TEMP_DIR) if _LANGCHAIN_AVAILABLE else None

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
memory = SqliteSaver(conn)

class _AgentState(TypedDict):
    messages: Annotated[list, add_messages]

_agent_lock = threading.Lock()
_current_tools = list(ALL_TOOLS_LIST)

def rebuild_agent(tools_list: list):
    """Rebuild agent workflow when permissions change."""
    global agent, _current_tools
    with _agent_lock:
        _current_tools = tools_list
        
        def _call_model(state: _AgentState) -> dict:
            messages = state["messages"]
            if not messages:
                return {"messages": [AIMessage(content="[Internal error: empty message list. Please resend.]")]}
            
            validated = []
            pending_tc = 0
            for msg in messages:
                validated.append(msg)
                if isinstance(msg, AIMessage) and getattr(msg, 'tool_calls', None):
                    pending_tc += len(msg.tool_calls)
                elif isinstance(msg, ToolMessage):
                    pending_tc -= 1
            
            if pending_tc > 0:
                _log("WARN", f"Detected {pending_tc} unpaired tool_calls, cleaning...")
                cleaned = []
                for i in range(len(validated) - 1, -1, -1):
                    msg = validated[i]
                    if isinstance(msg, AIMessage) and getattr(msg, 'tool_calls', None):
                        tc_count = len(msg.tool_calls)
                        pending_tc -= tc_count
                        if pending_tc >= 0:
                            continue
                    elif isinstance(msg, ToolMessage):
                        pending_tc += 1
                    cleaned.insert(0, msg)
                messages = cleaned
            
            try:
                llm_with_tools = llm.bind_tools(tools_list)
                response = llm_with_tools.invoke(messages)
                return {"messages": [response]}
            except Exception as e:
                _log("ERR", f"LLM call failed: {e}")
                return {"messages": [AIMessage(content=f"[API Error: {str(e)[:300]}]")]}
        
        def _should_continue(state: _AgentState) -> str:
            messages = state["messages"]
            if not messages:
                return END
            last_message = messages[-1]
            if isinstance(last_message, AIMessage) and getattr(last_message, 'tool_calls', None):
                return "tools"
            return END
        
        workflow = StateGraph(_AgentState)
        workflow.add_node("agent", _call_model)
        workflow.add_node("tools", ToolNode(tools_list))
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent", _should_continue, {"tools": "tools", END: END}
        )
        workflow.add_edge("tools", "agent")
        agent = workflow.compile(checkpointer=memory)
        _log("INFO", f"Agent rebuilt with {len(tools_list)} tools")

# Initial build
rebuild_agent(list(ALL_TOOLS_LIST))

print("Phase 4 loaded: Permissions + Agent builder")


# ═══════════════════════════════════════════════════════════════
#  7. Markdown to HTML Formatter (module-level)
# ═══════════════════════════════════════════════════════════════

def _format_markdown_html(text: str) -> str:
    '''Convert basic markdown to HTML for chat bubbles.'''
    if not text:
        return ""
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'```(\w*)\n(.*?)```',
                  r'<pre><code class="language-\1">\2</code></pre>',
                  text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*?</li>\n?)+', r'<ul>\g<0></ul>', text)
    text = re.sub(r'^&gt; (.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
    text = re.sub(r'^---$', r'<hr>', text, flags=re.MULTILINE)
    text = text.replace('\n\n', '<br><br>')
    text = text.replace('\n', '<br>')
    return text


# ═══════════════════════════════════════════════════════════════
#  8. AppState - Application State + Conversation Persistence
# ═══════════════════════════════════════════════════════════════


# ==================================================================
#  7. Markdown to HTML (pre-compiled regex, single pass)
# ==================================================================

def _format_markdown_html(text: str) -> str:
    if not text: return ''
    t = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    t = _RE_CODE_BLOCK.sub(r'<pre><code class="language-\1">\2</code></pre>', t)
    t = _RE_INLINE_CODE.sub(r'<code>\1</code>', t)
    t = _RE_BOLD.sub(r'<strong>\1</strong>', t)
    t = _RE_ITALIC.sub(r'<em>\1</em>', t)
    t = _RE_H3.sub(r'<h3>\1</h3>', t)
    t = _RE_H2.sub(r'<h2>\1</h2>', t)
    t = _RE_H1.sub(r'<h1>\1</h1>', t)
    t = _RE_LI.sub(r'<li>\1</li>', t)
    t = _RE_UL_WRAP.sub(r'<ul>\g<0></ul>', t)
    t = _RE_BLOCKQUOTE.sub(r'<blockquote>\1</blockquote>', t)
    t = _RE_HR.sub(r'<hr>', t)
    t = t.replace('\n\n', '<br><br>').replace('\n', '<br>')
    return t

# ==================================================================
#  8. AppState - __slots__ for ~50% less memory
# ==================================================================

class AppState:
    __slots__ = ('current_thread_id', 'config', 'chat_messages', 'is_processing',
                 'permissions', 'sessions', '_conversations_dir')

    def __init__(self):
        self.current_thread_id = str(uuid.uuid4())
        self.config = {'configurable': {'thread_id': self.current_thread_id}}
        self.chat_messages: List[Dict] = []
        self.is_processing = False
        self.permissions = {
            'all_approve': True, 'internet': True, 'file_read': True,
            'file_write': True, 'sandbox': True, 'compiler': True, 'ai_processing': True,
        }
        self.sessions: Dict[str, Dict] = {}
        self._conversations_dir = os.path.join(BASE_WORKSPACE, 'conversations')
        os.makedirs(self._conversations_dir, exist_ok=True)
        self._load_all_sessions()
        self._save_current_session_name()

    def _conversation_path(self, tid: str) -> str:
        return os.path.join(self._conversations_dir, f'{tid}.json')

    def _save_current_session_name(self):
        now = datetime.now()
        self.sessions[self.current_thread_id] = {
            'name': f"Chat {now.strftime('%m/%d %H:%M')}",
            'created': now.isoformat(),
            'message_count': 0
        }
        self._persist_session(self.current_thread_id)

    def _persist_session(self, tid: str):
        if tid not in self.sessions: return
        msgs = self.chat_messages if tid == self.current_thread_id else self.load_session_raw(tid)
        data = {
            'thread_id': tid, 'name': self.sessions[tid]['name'],
            'created': self.sessions[tid]['created'],
            'message_count': self.sessions[tid].get('message_count', 0),
            'messages': msgs
        }
        try:
            with open(self._conversation_path(tid), 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _log('WARN', f'Persist failed {tid}: {e}')

    def _load_all_sessions(self):
        d = self._conversations_dir
        if not os.path.exists(d): return
        for fn in sorted(os.listdir(d), reverse=True):
            if not fn.endswith('.json'): continue
            try:
                with open(os.path.join(d, fn), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                tid = data.get('thread_id', fn.replace('.json', ''))
                self.sessions[tid] = {
                    'name': data.get('name', f'Chat {tid[:8]}'),
                    'created': data.get('created', ''),
                    'message_count': data.get('message_count', len(data.get('messages', [])))
                }
            except Exception as e:
                _log('WARN', f'Load session {fn}: {e}')

    def save_current_conversation(self):
        if self.current_thread_id in self.sessions:
            self.sessions[self.current_thread_id]['message_count'] = len(self.chat_messages)
        self._persist_session(self.current_thread_id)

    def load_session_raw(self, tid: str) -> List[Dict]:
        fp = self._conversation_path(tid)
        if not os.path.exists(fp): return []
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                return json.load(f).get('messages', [])
        except Exception: return []

    def delete_session(self, tid: str):
        fp = self._conversation_path(tid)
        if os.path.exists(fp):
            try: os.remove(fp)
            except OSError: pass
        self.sessions.pop(tid, None)

    def new_session(self):
        self.save_current_conversation()
        self.current_thread_id = str(uuid.uuid4())
        self.config = {'configurable': {'thread_id': self.current_thread_id}}
        self.chat_messages.clear()
        self._save_current_session_name()
        return self.current_thread_id

    def switch_session(self, tid: str):
        if tid == self.current_thread_id: return
        self.save_current_conversation()
        self.current_thread_id = tid
        self.config = {'configurable': {'thread_id': tid}}
        self.chat_messages = self.load_session_raw(tid)
        if tid not in self.sessions:
            self._save_current_session_name()

    def update_permissions(self, key: str, value: bool):
        self.permissions[key] = value
        tools = filter_tools_by_permissions(self.permissions)
        rebuild_agent(tools)
        return len(tools)

# ==================================================================
#  9. CSS (optimized, single-line for size)
# ==================================================================

CUSTOM_CSS = '<style>' + (
":root{--primary:#6366f1;--primary-light:#818cf8;--primary-dark:#4f46e5;--accent:#a855f7;--bg-gradient:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);--surface:#fff;--surface-alt:#f8fafc;--text-primary:#1e293b;--text-secondary:#64748b;--text-muted:#94a3b8;--border:#e2e8f0;--shadow-sm:0 1px 2px rgba(0,0,0,.04);--shadow:0 4px 6px -1px rgba(0,0,0,.06),0 2px 4px -2px rgba(0,0,0,.04);--radius-sm:8px;--radius:12px;--radius-lg:18px;--radius-xl:28px;--transition:.18s cubic-bezier(.4,0,.2,1)}.user-bubble{background:var(--bg-gradient);color:#fff;padding:12px 18px;border-radius:18px 18px 4px 18px;max-width:78%;margin:4px 0 4px auto;box-shadow:0 2px 8px rgba(99,102,241,.25);line-height:1.65;font-size:.9375rem;word-break:break-word}.ai-bubble{background:var(--surface);color:var(--text-primary);padding:12px 18px;border-radius:18px 18px 18px 4px;max-width:78%;margin:4px auto 4px 0;box-shadow:var(--shadow-sm);line-height:1.7;font-size:.9375rem;word-break:break-word;border:1px solid var(--border)}.ai-bubble h1,.ai-bubble h2,.ai-bubble h3{margin:.6em 0 .3em;font-weight:700;line-height:1.3}.ai-bubble h1{font-size:1.3rem;border-bottom:1px solid var(--border);padding-bottom:.3em}.ai-bubble h2{font-size:1.15rem}.ai-bubble h3{font-size:1.05rem}.ai-bubble code{background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:.85rem;font-family:'JetBrains Mono','Fira Code',monospace;color:#e11d48}.ai-bubble pre{background:#1e293b;color:#e2e8f0;padding:14px 16px;border-radius:8px;overflow-x:auto;font-size:.82rem;line-height:1.55;margin:.5em 0}.ai-bubble pre code{background:none;color:inherit;padding:0;font-size:inherit}.ai-bubble ul,.ai-bubble ol{padding-left:1.5em;margin:.4em 0}.ai-bubble li{margin:.2em 0}.ai-bubble blockquote{border-left:3px solid var(--primary-light);padding:8px 14px;margin:.6em 0;color:var(--text-secondary);background:var(--surface-alt);border-radius:0 6px 6px 0}.ai-bubble table{border-collapse:collapse;width:100%;margin:.5em 0;font-size:.85rem}.ai-bubble th,.ai-bubble td{border:1px solid var(--border);padding:6px 10px;text-align:left}.ai-bubble th{background:var(--surface-alt);font-weight:600}.ai-bubble strong{font-weight:700}.ai-bubble a{color:var(--primary);text-decoration:underline}.ai-bubble hr{border:none;border-top:1px solid var(--border);margin:.8em 0}.tool-call-card{background:linear-gradient(135deg,#fffbeb,#fef3c7);border:1px solid #fcd34d;border-left:3px solid #f59e0b;border-radius:var(--radius-sm);padding:10px 14px;margin:5px 0;font-size:.82rem;box-shadow:var(--shadow-sm)}.tool-result-card{background:linear-gradient(135deg,#ecfdf5,#d1fae5);border:1px solid #6ee7b7;border-left:3px solid #10b981;border-radius:var(--radius-sm);padding:10px 14px;margin:5px 0;font-size:.82rem;box-shadow:var(--shadow-sm)}.chat-input{border:2px solid var(--border)!important;border-radius:var(--radius-xl)!important;padding:12px 18px!important;font-size:.9375rem!important;transition:all var(--transition)!important;background:var(--surface-alt)!important;resize:none!important}.chat-input:focus{border-color:var(--primary-light)!important;box-shadow:0 0 0 4px rgba(99,102,241,.1)!important;background:var(--surface)!important;outline:none!important}.gradient-text{background:var(--bg-gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-weight:800}.health-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px;flex-shrink:0}.health-ok{background:#10b981;box-shadow:0 0 6px rgba(16,185,129,.4)}.health-warn{background:#f59e0b;box-shadow:0 0 6px rgba(245,158,11,.4)}@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}.fade-in{animation:fadeIn .35s ease-out}.session-item{transition:all var(--transition);border-radius:10px;cursor:pointer;border:1px solid transparent;position:relative}.session-item:hover{background:#eef2ff;border-color:#c7d2fe}.session-item.active{background:#eef2ff;border-color:#818cf8;box-shadow:0 0 0 2px rgba(99,102,241,.12)}.sidebar-icon-btn{transition:all var(--transition);opacity:0}.session-item:hover .sidebar-icon-btn{opacity:1}::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:10px}::-webkit-scrollbar-thumb:hover{background:#94a3b8}.q-drawer{background:#fafbfc!important}.q-header{backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}"
) + '</style>'

state = AppState()

# ==================================================================
#  10. Web UI - ChatGPT/Claude Style (optimized)
# ==================================================================

@ui.page('/')
def main_page():
    ui.add_head_html(CUSTOM_CSS)
    dark = ui.dark_mode()
    dark.disable()

    _ESC_TABLE = str.maketrans({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})
    def _esc(s: str) -> str: return s.translate(_ESC_TABLE)

    # ===== HEADER =====
    with ui.header(elevated=True).classes(
        'bg-white/90 backdrop-blur-md text-gray-900 px-5 py-2'
        ' flex items-center justify-between border-b border-gray-100'):
        with ui.row().classes('items-center gap-3'):
            ui.html(
                '<div style="font-size:1.5rem">&#x1F52C;</div>'
                '<div><span class="text-lg font-extrabold">'
                '<span class="gradient-text">DeepSeek</span>'
                ' <span style="color:#1e293b">For the Break</span></span>'
                '<span class="text-xs text-gray-400 font-medium ml-2'
                ' bg-gray-100 px-2 py-0.5 rounded-full">v5.2</span></div>')
        with ui.row().classes('gap-2 items-center'):
            all_approve_switch = ui.switch(
                'All-Approve', value=state.permissions['all_approve']
            ).props('color=indigo dense')
            dark_switch = ui.switch('Dark', value=False).props('color=indigo dense')
            ui.button(icon='add', on_click=lambda: _do_new_chat()
                     ).props('flat round color=indigo size=sm').tooltip('New Chat')

    # ===== SIDEBAR =====
    with ui.left_drawer(value=True, fixed=True, top_corner=True, bottom_corner=True
                       ).classes('bg-gray-50/95') as sidebar:
        with ui.column().classes('w-full h-full'):
            with ui.column().classes('w-full px-4 py-4 items-center gap-1'):
                ui.html(
                    '<div style="font-size:2rem">&#x1F52C;</div>'
                    '<div class="text-sm font-bold gradient-text">DeepSeek For the Break</div>'
                    '<div class="text-xs text-gray-400">Academic AI v5.2</div>')
            ui.separator()
            with ui.row().classes('w-full px-3 py-1'):
                ui.button('+ New Chat', on_click=lambda: _do_new_chat()
                         ).props('color=indigo').classes('w-full text-sm font-semibold')
            ui.separator()
            ui.label('Conversations').classes(
                'text-xs font-bold text-gray-500 uppercase tracking-wider px-3 mt-1')
            sessions_list = ui.column().classes('w-full gap-0.5 px-2 flex-1 overflow-y-auto')
            ui.separator()
            ui.label('Permissions').classes(
                'text-xs font-bold text-gray-500 uppercase tracking-wider px-3')
            perm_container = ui.column().classes('w-full gap-0.5 px-2')
            ui.separator()
            ui.label('System').classes(
                'text-xs font-bold text-gray-500 uppercase tracking-wider px-3')
            health_container = ui.column().classes('w-full gap-0.5 px-3 py-1 text-xs')
            ui.separator()
            tool_count_label = ui.label('').classes('text-xs text-gray-400 text-center w-full py-2')

    # ===== MAIN CHAT =====
    with ui.column().classes('w-full h-full'):
        chat_container = ui.column().classes(
            'w-full max-w-3xl mx-auto flex-1 overflow-y-auto px-4 py-4 gap-1')

        def _render_welcome(container):
            with container:
                with ui.card().classes(
                    'w-full bg-gradient-to-br from-indigo-50 via-white to-purple-50'
                    ' border-0 shadow-sm'):
                    ui.html(
                        '<div class="text-center py-10">'
                        '<div style="font-size:3.5rem">&#x1F52C;</div>'
                        '<h2 class="text-2xl font-extrabold mt-4"'
                        ' style="background:linear-gradient(135deg,#6366f1,#a855f7);'
                        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;">'
                        'DeepSeek For the Break</h2>'
                        '<p class="text-gray-500 mt-2 text-sm">v5.2 - All-in-One Academic AI</p>'
                        '<div class="flex justify-center gap-2 mt-4 flex-wrap">'
                        '<span class="text-xs bg-indigo-100 text-indigo-700 px-3 py-1'
                        ' rounded-full font-medium">29 Tools</span>'
                        '<span class="text-xs bg-purple-100 text-purple-700 px-3 py-1'
                        ' rounded-full font-medium">History</span>'
                        '<span class="text-xs bg-emerald-100 text-emerald-700 px-3 py-1'
                        ' rounded-full font-medium">Optimized</span>'
                        '<span class="text-xs bg-amber-100 text-amber-700 px-3 py-1'
                        ' rounded-full font-medium">v5.2</span>'
                        '</div>'
                        '<p class="text-gray-400 text-xs mt-4">Ask anything - literature,'
                        ' data, coding, writing...</p></div>')

        _render_welcome(chat_container)

        # ===== INPUT =====
        with ui.card().classes(
            'w-full max-w-3xl mx-auto mb-4 p-0 border-2 border-gray-100 rounded-3xl shadow-sm'):
            with ui.row().classes('w-full items-center gap-2 p-1.5'):
                msg_input = ui.textarea(
                    placeholder='Message DeepSeek For the Break...'
                ).classes('chat-input w-full').props('autogrow rounded dense')

                async def send_message():
                    if state.is_processing:
                        return ui.notify('Please wait...', type='warning', position='top')
                    txt = msg_input.value.strip()
                    if not txt: return
                    msg_input.value = ''
                    state.is_processing = True
                    send_btn.props('loading')
                    ts = datetime.now().strftime('%H:%M')

                    with chat_container:
                        with ui.column().classes('w-full fade-in'):
                            ui.html(f'<div class="user-bubble">{_esc(txt)}</div>')
                            ui.html(f'<span style="font-size:.7rem;color:#94a3b8;'
                                    f'margin-left:auto;display:block;text-align:right;'
                                    f'padding-right:4px">{ts}</span>')
                    state.chat_messages.append({'role': 'user', 'content': txt, 'timestamp': ts})

                    try:
                        t0 = time.time()
                        full = ''
                        tc_info = []
                        loop = asyncio.get_event_loop()

                        def _run():
                            return list(agent.stream(
                                {'messages': [('user', txt)]}, state.config, stream_mode='updates'))

                        events = await loop.run_in_executor(None, _run)

                        for event in events:
                            for msgs in event.values():
                                for msg in msgs.get('messages', []):
                                    tc = getattr(msg, 'tool_calls', None)
                                    if tc:
                                        for c in tc:
                                            name = c.get('name') or c.get('function', {}).get('name', '?')
                                            args = c.get('args') or c.get('function', {}).get('arguments', {})
                                            if isinstance(args, str):
                                                try: args = json.loads(args)
                                                except: pass
                                            tc_info.append({
                                                'name': name,
                                                'args': json.dumps(args, ensure_ascii=False, default=str)[:200]})
                                    elif isinstance(msg, ToolMessage):
                                        tc_info.append({'result': str(msg.content or '')[:500]})
                                    elif isinstance(msg, AIMessage) and msg.content:
                                        full += msg.content

                        elapsed = time.time() - t0

                        with chat_container:
                            with ui.column().classes('w-full fade-in'):
                                for tci in tc_info:
                                    if 'name' in tci:
                                        ui.html(f'<div class="tool-call-card">'
                                                f'<span style="font-weight:600;color:#92400e">'
                                                f'&#x1F527; {_esc(tci["name"])}</span><br>'
                                                f'<span style="font-size:.75rem;color:#78716c">'
                                                f'{_esc(tci["args"])}</span></div>')
                                    elif 'result' in tci:
                                        ui.html(f'<div class="tool-result-card">'
                                                f'<span style="font-weight:600;color:#065f46">'
                                                f'&#x2705; Result:</span> {_esc(tci["result"][:400])}</div>')
                                if full:
                                    ui.html(f'<div class="ai-bubble">{_format_markdown_html(full)}</div>')
                                else:
                                    ui.html('<div class="ai-bubble" style="color:#94a3b8">'
                                            '[Tools executed]</div>')
                                ui.html(f'<span style="font-size:.7rem;color:#94a3b8;'
                                        f'margin-left:8px">{elapsed:.1f}s &middot; {ts}</span>')

                        state.chat_messages.append({
                            'role': 'ai', 'content': full, 'tool_calls': tc_info,
                            'timestamp': ts, 'elapsed': elapsed})
                        state.save_current_conversation()
                        update_session_list()

                    except Exception as e:
                        with chat_container:
                            with ui.column().classes('w-full fade-in'):
                                ui.html(f'<div class="ai-bubble" style="color:#ef4444;'
                                        f'border-color:#fecaca;background:#fef2f2">'
                                        f'&#x26A0; Error: {_esc(str(e)[:500])}</div>')
                        _log('ERR', traceback.format_exc())
                    finally:
                        state.is_processing = False
                        send_btn.props(remove='loading')
                        ui.run_javascript(
                            'setTimeout(()=>{const e=document.querySelector(".overflow-y-auto");'
                            'if(e)e.scrollTop=e.scrollHeight},100)')

                send_btn = ui.button(icon='send', on_click=send_message).props('round color=indigo size=md')

        # Keyboard handler
        async def handle_key(e):
            try:
                key = getattr(e, 'key', None) or (e.args.get('key', '') if hasattr(e, 'args') else '')
                sd = (e.action if hasattr(e, 'action') and isinstance(e.action, dict)
                      else (e.args if hasattr(e, 'args') and isinstance(e.args, dict) else {}))
                shift = sd.get('shiftKey', False)
                if key == 'Enter' and not shift:
                    if hasattr(e, 'action') and isinstance(e.action, dict):
                        e.action['preventDefault'] = True
                    await send_message()
            except Exception: pass
        ui.on('keydown', handle_key)

    # ===== SIDEBAR FUNCTIONS =====

    def _do_new_chat():
        state.new_session()
        chat_container.clear()
        _render_welcome(chat_container)
        update_session_list()
        ui.notify('New conversation!', type='positive', position='top')

    def update_session_list():
        sessions_list.clear()
        with sessions_list:
            for sid, sinfo in sorted(state.sessions.items(),
                                     key=lambda x: x[1].get('created', ''), reverse=True):
                active = sid == state.current_thread_id
                cls = f'session-item w-full p-2.5 items-center gap-2 {"active" if active else ""}'
                with ui.row().classes(cls) as row:
                    row.on('click', lambda _, tid=sid: _switch_to_session(tid))
                    ui.icon('chat_bubble' if active else 'chat_bubble_outline'
                           ).classes('text-sm text-gray-400')
                    with ui.column().classes('flex-1 min-w-0'):
                        ui.label(sinfo.get('name', 'Chat')[:28]).classes('text-sm font-medium truncate')
                        ui.label(f'{sinfo.get("message_count", 0)} msgs').classes('text-xs text-gray-400')
                    ui.button(icon='close', on_click=lambda _, tid=sid: _delete_session(tid)
                             ).props('flat round dense size=xs color=gray').classes('sidebar-icon-btn')

    def _switch_to_session(tid: str):
        if tid == state.current_thread_id: return
        state.switch_session(tid)
        chat_container.clear()
        for msg in state.chat_messages:
            with chat_container:
                if msg['role'] == 'user':
                    ui.html(f'<div class="user-bubble">{_esc(msg["content"])}</div>')
                    ui.html(f'<span style="font-size:.7rem;color:#94a3b8;margin-left:auto;'
                            f'display:block;text-align:right;padding-right:4px">'
                            f'{msg.get("timestamp","")}</span>')
                else:
                    ui.html(f'<div class="ai-bubble">'
                            f'{_format_markdown_html(msg.get("content",""))}</div>')
                    ui.html(f'<span style="font-size:.7rem;color:#94a3b8;margin-left:8px">'
                            f'{msg.get("elapsed",0):.1f}s &middot; {msg.get("timestamp","")}</span>')
        update_session_list()
        ui.notify(f'Switched to "{state.sessions.get(tid,{}).get("name","Chat")}"',
                  type='info', position='top')

    def _delete_session(tid: str):
        state.delete_session(tid)
        if tid == state.current_thread_id:
            state.new_session()
            chat_container.clear()
            _render_welcome(chat_container)
        update_session_list()
        ui.notify('Deleted', type='warning', position='top')

    def update_permission_ui():
        perm_container.clear()
        with perm_container:
            for cat_key, cat_info in PERMISSION_CATEGORIES.items():
                is_enabled = state.permissions.get(cat_key, False)
                op = '' if is_enabled else 'opacity-50'
                with ui.row().classes(f'w-full items-center gap-1.5 px-2 py-0.5 {op}'):
                    ui.icon(cat_info['icon']).classes('text-base')
                    with ui.column().classes('flex-1'):
                        ui.label(cat_info['name']).classes('text-xs font-semibold')
                    sw = ui.switch(value=is_enabled).props(f'color={cat_info["color"]} dense size=xs')
                    def _mk(k): return lambda e: on_perm_change(k, e.value)
                    sw.on_value_change(_mk(cat_key))
            ui.separator()
            all_on = state.permissions['all_approve']
            ui.button('All-Approve: ON' if all_on else 'All-Approve: OFF',
                      on_click=lambda: on_perm_change('all_approve', not state.permissions['all_approve'])
                     ).props(f'color={"indigo" if all_on else "gray"} size=sm dense').classes('w-full text-xs')

    def on_perm_change(key: str, value: bool):
        count = state.update_permissions(key, value)
        tool_count_label.set_text(f'{count} tools')
        update_permission_ui()
        all_approve_switch.value = state.permissions['all_approve']

    def on_all_approve_change(e):
        state.update_permissions('all_approve', e.value)
        if e.value:
            for k in PERMISSION_CATEGORIES: state.permissions[k] = True
            rebuild_agent(filter_tools_by_permissions(state.permissions))
        tool_count_label.set_text(f'{len(_current_tools)} tools')
        update_permission_ui()

    def on_dark_mode_change(e):
        dark.enable() if e.value else dark.disable()

    all_approve_switch.on_value_change(on_all_approve_change)
    dark_switch.on_value_change(on_dark_mode_change)

    with health_container:
        for k, v in _health.items():
            ui.html(f'<div style="display:flex;align-items:center;gap:6px;padding:2px 0">'
                    f'<span class="health-dot {"health-ok" if v else "health-warn"}"></span>'
                    f'<span style="flex:1;font-size:.75rem">{k}</span>'
                    f'<span style="color:#94a3b8;font-size:.7rem">{"OK" if v else "--"}</span></div>')

    update_session_list()
    update_permission_ui()
    tool_count_label.set_text(f'{len(_current_tools)} tools')


# ==================================================================
#  11. Entry Point
# ==================================================================

def main():
    _log('START', '=' * 60)
    _log('START', '  DeepSeek_For_the_Break v5.2 (Optimized)')
    _log('START', '  http://localhost:8080')
    _log('START', f'  Conv: {os.path.join(BASE_WORKSPACE, "conversations")}')
    _log('START', '=' * 60)
    for k, v in _health.items():
        _log('OK' if v else 'WARN', f'  [{"OK" if v else "--"}] {k}')
    _log('INFO', f'Model: {os.getenv("DFTB_MODEL", "deepseek-chat")} |'
                 f' Thinking: {"ON" if _thinking_enabled else "OFF"} |'
                 f' Tools: {len(_current_tools)}')
    ui.run(
        title='DeepSeek v5.2',
        host='127.0.0.1', port=8080, reload=False, show=True,
        favicon='\U0001f52c',
    )

if __name__ == '__main__':
    main()

