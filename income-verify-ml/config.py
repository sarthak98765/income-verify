import os
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))

# Secrets and connection strings: the only values read from the environment.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://income:income@localhost:5434/income_verify").strip()
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://income:income@localhost:5674/").strip()
STORAGE_DIR = os.environ.get("STORAGE_DIR", os.path.join(os.path.dirname(__file__), "..", "storage")).strip()
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "0") or 0)
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
LANGFUSE_HOST = (os.environ.get("LANGFUSE_HOST", "") or "https://cloud.langfuse.com").strip().rstrip("/")

ML_PORT = 5910
WORKER_CONCURRENCY = 2

# LLM (OpenAI direct). Prices per 1M tokens (input, output) from openrouter.ai/models, checked 2026-11-02.
LLM_TIMEOUT = 300
LLM_RETRY_ATTEMPTS = 3
LLM_BACKOFF_BASE = 2
MAX_OUTPUT_TOKENS = 32000
CLASSIFY_MODEL = "gpt-6-luna"
EXTRACT_MODEL = "gpt-6.1-terra"
REREAD_MODEL = "gpt-6.1-sol"
CATEGORIZE_MODEL = "gpt-6-luna"
SUMMARY_MODEL = "gpt-6-luna"
MODEL_POLICY = {"classify": CLASSIFY_MODEL, "extract": EXTRACT_MODEL, "reread": REREAD_MODEL, "categorize": CATEGORIZE_MODEL, "summary": SUMMARY_MODEL}
# When every retry on a model fails (outage, rate limit, timeout), one more try on this one.
FALLBACK_MODELS = {"gpt-6.1-terra": "gpt-6.1-sol", "gpt-6.1-sol": "gpt-6.1-terra", "gpt-6-luna": "gpt-6.1-terra"}
TRACE_IO_CHARS = 4000
PRICES = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-terra": (1.00, 5.00),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-4.1-mini": (0.40, 1.60),
}
REASONING_EFFORT = {"gpt-6-luna": "low", "gpt-6.1-terra": "low", "gpt-6.1-sol": "medium"}

# OCR (Mistral)
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
OCR_MODEL = "mistral-ocr-latest"
OCR_COST_PER_PAGE = 0.001
OCR_TIMEOUT = 180
OCR_MAX_ATTEMPTS = 4
OCR_BACKOFFS = [5, 15, 30]
OCR_RETRY_DPI = 200
OCR_CACHE_VERSION = "v1"
MIN_PAGE_CHARS = 40

# Extraction
STATEMENT_BATCH_PAGES = 3
MAX_PAGES = 30
MAX_FILE_MB = 15

# Checks: tolerances in rupees unless named otherwise
AMOUNT_TOLERANCE = 1.0
SALARY_MATCH_TOLERANCE = 0.01  # share of net pay
ANNUAL_INCOME_TOLERANCE = 0.10  # Form 16 gross vs 12 × payslip gross
NAME_MATCH_MIN = 85  # rapidfuzz token_set_ratio
PF_RATE = 0.12
PF_WAGE_CEILING = 15000
ESI_GROSS_CEILING = 21000
ESI_EMPLOYEE_RATE = 0.0075
# Monthly professional tax by state: [(gross above, tax)], highest slab first. None = state levies no PT.
# Simplified from state notifications; verify before relying on it (Feb months can differ).
PT_SLABS = {
    "Maharashtra": [(10000, 200), (7500, 175), (0, 0)],
    "Karnataka": [(25000, 200), (0, 0)],
    "Telangana": [(20000, 200), (15000, 150), (0, 0)],
    "West Bengal": [(40000, 200), (25000, 150), (15000, 130), (10000, 110), (0, 0)],
    "Delhi": None,
    "Haryana": None,
    "Uttar Pradesh": None,
}
STANDARD_DEDUCTION = {"new": 75000, "old": 50000}

# Decision
AUTHENTICITY_FLAG_BELOW = 70
SIGNAL_WEIGHTS = {
    "pdf_edited": 25, "odd_font": 20, "math_broken": 30, "balance_chain_break": 35, "round_amounts": 10,
    "window_dressing": 15, "circular_money": 15, "salary_not_credited": 25, "statutory_mismatch": 10, "latest_month_edit": 20,
}
PDF_EDITORS = ("ilovepdf", "smallpdf", "sejda", "pdfescape", "canva", "photoshop", "pdf-xchange", "foxit phantom", "nitro", "adobe acrobat pro", "microsoft word")

# Queue
RABBITMQ_EXCHANGE = "income_verify"
RABBITMQ_MAIN_QUEUE = "main_queue"
RABBITMQ_RETRY_QUEUE = "retry_queue"
RABBITMQ_DL_QUEUE = "dlq_queue"
MAX_RETRIES = 2
DOC_TYPES = ["payslip", "bank_statement", "form16"]
