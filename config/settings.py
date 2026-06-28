import os

# ── LLM ──────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LLM_MODEL         = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
LLM_MAX_TOKENS    = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# ── Embeddings ────────────────────────────────────────────────────────────────
EMBEDDING_MODEL          = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
SIMILARITY_THRESHOLD_HIGH = float(os.getenv("SIMILARITY_THRESHOLD_HIGH", "0.92"))
SIMILARITY_THRESHOLD_LOW  = float(os.getenv("SIMILARITY_THRESHOLD_LOW",  "0.65"))

# ── Vector DB (RAG) ───────────────────────────────────────────────────────────
VECTOR_DB_PATH               = os.getenv("VECTOR_DB_PATH", "./vector_db/chroma")
VECTOR_DB_COLLECTION_MKT     = os.getenv("VECTOR_DB_COLLECTION_MKT",       "approved_mkts")
VECTOR_DB_COLLECTION_DECISIONS = os.getenv("VECTOR_DB_COLLECTION_DECISIONS", "past_decisions")
VECTOR_DB_COLLECTION_SPECS   = os.getenv("VECTOR_DB_COLLECTION_SPECS",     "product_specs")

# ── Pipeline thresholds ───────────────────────────────────────────────────────
MATH_ERROR_TOLERANCE = float(os.getenv("MATH_ERROR_TOLERANCE", "0.01"))
EXISTING_EQUIPMENT_KEYWORDS = ["ציוד קיים", "קיים", "existing"]
NOT_IN_TOTAL_KEYWORDS       = ["לא לסיכום", "אופציה", "option", "not included"]

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_DIR    = os.getenv("OUTPUT_DIR",    "./data/output")
PROCESSED_DIR = os.getenv("PROCESSED_DIR", "./data/processed")
