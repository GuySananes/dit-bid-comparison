# docs/decisions.md
# Architectural Decision Log

Every significant design choice is recorded here with its reasoning.
Before proposing a change to the architecture, read this file first.
If a decision needs to be revisited, add a new entry rather than deleting the old one.

---

## Decision 1 — Three-Layer Architecture

**Decision:** Separate the pipeline into Layer 1 (parsing), Layer 2 (normalization),
Layer 3 (AI agents) rather than one monolithic script or one large agent.

**Why:**
- Each layer has a clear, testable responsibility
- Layers 1 and 2 run without any API calls — fast, free, deterministic
- If the LLM API is down, the first two layers still work
- Easier to debug: if output is wrong, you know which layer to look at
- Intermediate JSON files let you resume from any point without re-running everything

**Rejected alternative:** One large AI agent that reads Excel and produces the comparison table.
Rejected because: unpredictable, expensive, not testable, hallucinates numeric values.

---

## Decision 2 — Local Embeddings (sentence-transformers) not API Embeddings

**Decision:** Use `sentence-transformers` running locally for MKT similarity matching,
not the Anthropic or OpenAI embeddings API.

**Why:**
- Contractor pricing data never leaves the machine (privacy)
- No API cost per embedding call (could be thousands of rows)
- No network latency per row
- `all-MiniLM-L6-v2` is accurate enough for product name similarity
- Works offline

**Rejected alternative:** OpenAI `text-embedding-ada-002` or Anthropic embeddings.
Rejected because: pricing data privacy, cost at scale, unnecessary for short strings.

---

## Decision 3 — ChromaDB not Pinecone for Vector DB

**Decision:** Use ChromaDB (local file-based) as the vector database.

**Why:**
- Runs entirely locally — no account, no API key, no cost
- Data stays on the machine (contractor data privacy)
- Simple Python API, no infrastructure to manage
- Sufficient for the scale of this use case (hundreds to low thousands of MKTs)
- Easy to migrate to Pinecone later if needed (same interface pattern)

**Rejected alternative:** Pinecone (managed cloud vector DB).
Rejected because: requires sending data to external service, cost, overkill for current scale.

**Future:** If DIT scales to many simultaneous projects and teams,
revisit Pinecone or Weaviate for multi-user access.

---

## Decision 4 — Prompts in `config/prompts.py`, Not Inline

**Decision:** All LLM prompts are defined in `config/prompts.py` as string constants,
not written inline inside agent files.

**Why:**
- Prompts need iteration independent of code logic
- Easy to version-control prompt changes separately
- Can A/B test prompt variants without touching agent logic
- Single place to audit what instructions we give the LLM

**Rule:** If you are writing a string that goes into an LLM call — it belongs in `config/prompts.py`.

---

## Decision 5 — Agents Always Return JSON

**Decision:** Every AI agent must return structured JSON, never free prose.

**Why:**
- Downstream code needs to process the output programmatically
- Free text output requires another parsing step (fragile, error-prone)
- JSON output can be validated against a schema immediately
- Failures are explicit (JSON parse error) not silent (wrong prose)

**Implementation:** Every agent prompt instructs the model to return only JSON.
`llm_client.py` parses and validates the response before returning it.
If JSON parsing fails twice — raise `LLMError` with the raw response for debugging.

---

## Decision 6 — Four Separate Agents, Not One

**Decision:** Use four specialized agents (A: ambiguity, B: deviation, C: letter, D: summary)
rather than one general-purpose agent.

**Why:**
- Each agent has a narrow, well-defined task → better prompt quality
- Easier to test each agent in isolation
- Different agents can use different models or temperature settings
- If Agent B fails on one row, it doesn't block Agent C
- Costs are easier to track per function

**Rejected alternative:** One agent that does everything.
Rejected because: prompt becomes too complex, failure modes are unclear,
hard to improve one capability without affecting others.

---

## Decision 7 — Text Normalization Before Embeddings

**Decision:** Run text normalization (lowercase, remove noise words, etc.)
BEFORE computing embeddings, not instead of embeddings.

**Why:**
- Text normalization resolves the easy cases instantly (no compute needed)
- Embeddings are then only called for genuinely ambiguous cases
- The combination catches more cases than either alone:
  - Normalization: `POLY X52` = `Poly Studio X52` (noise word removal)
  - Embeddings: `Polycom Eagle Eye X52` ≈ `POLY X52` (semantic similarity)

**Order:** normalize → exact match check → embeddings → agent A (if still uncertain)

---

## Decision 8 — Save Intermediate JSON After Each Layer

**Decision:** After each layer completes, save its output JSON to `data/processed/<project_id>/`.

**Why:**
- If the pipeline crashes at Layer 3, we don't re-run the expensive Excel parsing
- Easier to debug — can inspect exactly what each layer produced
- Enables resuming from any step
- Creates an audit trail for each project

**Files saved:**
- After Layer 1: `parsed_<contractor_id>.json`
- After Layer 2: `normalized_<contractor_id>.json`
- After Layer 3: `reviewed_<contractor_id>.json`

---

## Decision 9 — Vector DB Stores Decisions, Not Prices

**Decision:** The Vector DB (`past_decisions` collection) stores technical deviation
rulings and MKT approvals — never contractor prices.

**Why:**
- Prices are commercially sensitive between competing contractors
- Technical decisions (is 330 NIT acceptable?) generalize across projects
- Prices do not generalize — they change per project, per market conditions
- Keeps the RAG system useful without creating privacy risks

**What is stored:** product names, technical specs, deviation rulings, reasoning.
**What is never stored:** unit prices, total prices, contractor identities linked to prices.
