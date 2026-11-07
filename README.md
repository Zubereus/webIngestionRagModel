# WebRAG

WebRAG turns saved web pages into a small, searchable research library. Add a URL or start a bounded site crawl, then ask questions in English or Vietnamese and inspect the passages behind each answer.

The project has two parts: a React interface for managing sources and asking questions, and a Python service for fetching, indexing, retrieval, and answer generation.

## What it does

- Extracts page content into Markdown and splits it into heading-aware passages.
- Keeps sources in named collections, with a SQLite catalog and ChromaDB vector index.
- Searches with dense embeddings or hybrid semantic and BM25 retrieval.
- Answers with Gemini or a local Ollama model, with source citations and a passage viewer.
- Crawls a bounded number of pages on the starting host, observes `robots.txt`, and reports progress.
- Offers both a browser interface and a command-line workflow.

## PDF and image sources

Single-page ingestion and crawls accept HTML, PDF, PNG, and JPEG responses. HTML extraction is unchanged. PDF and image pages are OCR'd with Tesseract's `vie+eng` languages; PDF pages with at least 40 native text characters are not OCR'd. Each resulting chunk carries its source page and whether OCR supplied its text, and PDF page citations include those fields.

Install the Tesseract binary with its Vietnamese (`vie`) and English (`eng`) language data separately from Python requirements. If the binary or either language pack is unavailable, WebRAG logs one warning and continues with native PDF text. Image-only pages then have no extractable text.

`MAX_RESPONSE_BYTES` remains 5 MiB for HTML and image responses. `WEBRAG_MAX_PDF_BYTES` configures the PDF response cap (default 20 MiB), `WEBRAG_OCR_MIN_PAGE_CHARS` configures the per-page OCR threshold (default 40), and `WEBRAG_OCR_DPI` configures PDF rasterization (default 300).

PDF/image support adds `pypdf` (BSD-3-Clause), `pypdfium2` (Apache-2.0; bundled PDFium is BSD-3-Clause), `Pillow` (MIT), and `pytesseract` (Apache-2.0). `reportlab` (BSD-3-Clause) is used only to generate local PDF test fixtures. Tesseract itself is a separately installed Apache-2.0 program.

Run `python scripts/check_ocr_accuracy.py` to check five synthetic Vietnamese paragraphs at 150 and 300 DPI. It prints a clear skip if Tesseract, the `vie`/`eng` data, or a suitable local font is missing; synthetic results are not a claim about real-document OCR quality.

## Current corpus

These counts describe the local corpus in `data/`; that directory is excluded from Git, and the counts are not a benchmark of answer quality.

| Collection | Pages | Chunks |
| --- | ---: | ---: |
| `default` | 1 | 8 |
| `ai_tech` | 2 | 40 |
| `immigration` | 20 | 321 |
| `research` | 2 | 71 |
| **Total** | **25** | **440** |

Page counts come from the SQLite catalog; 22 pages are marked ready and 3 are still marked extracted.

## Run locally

You’ll need Python 3.11 or newer and Node.js 20.19 or newer. To generate answers, configure Gemini or run Ollama locally. Ollama is also used for embeddings.

```shell
git clone https://github.com/Zubereus/webIngestionRagModel.git
cd webIngestionRagModel
python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```shell
# macOS / Linux
source .venv/bin/activate
```

Install the Python and frontend dependencies, then build the web app:

```shell
python -m pip install -r requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
```

Start the service and open [http://localhost:8000](http://localhost:8000). The API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

```shell
python serve.py
```

### Choose a model

Gemini 3.5 Flash is the backend default. Set the key in the server’s environment before starting WebRAG:

```powershell
$env:GEMINI_API_KEY = "your-key"
```

```shell
export GEMINI_API_KEY="your-key"
```

Keep the key on the backend; don’t put it in frontend code or commit it. You can instead select an Ollama generation model in **Settings**. For a local setup, install Ollama and pull the embedding and generation models:

```shell
ollama pull bge-m3
ollama pull qwen2.5:3b
```

The active embedding model defaults to `bge-m3:latest`; `WEBRAG_EMBED_MODEL` can override it. Query embeddings wait up to 120 seconds for Ollama by default; set `WEBRAG_EMBED_TIMEOUT_SECONDS` to adjust the timeout. The app uses `data/chroma_bge_m3` for its active index and keeps the previous index under `data/chroma`.

Document embeddings are cached in a separate SQLite file adjacent to the active Chroma directory (by default, `data/chroma_bge_m3_embedding_cache.sqlite3`). The cache key includes the exact model name and prefixed text sent to Ollama. If you pull a new model version under the same tag, delete this cache file so the app does not reuse vectors from the previous model; **Clear library** also deletes it.

## Use the CLI

```shell
# Save a page to a collection
python cli.py ingest https://fastapi.tiangolo.com/tutorial/first-steps/ --collection ai_tech

# See saved pages and index any new passages
python cli.py list
python cli.py index

# Retrieve passages and generate a cited answer
python cli.py query "How do I create a basic path operation in FastAPI?" --collection ai_tech
```

To re-fetch a page or rebuild its passages after extraction changes, add `--force` to `ingest`. To rebuild the vector index after changing embeddings, run `python cli.py index --force`.

## Retrieval evaluation

The benchmark scripts measure whether a labeled target page is retrieved and where it ranks. The query cases store a `question`, `expected_url`, and an exact `answer` passage copied from the frozen extracted source; the answer passage is a reference, while URL presence determines Hit@k and MRR. These passages are not manually verified gold facts. The scripts do **not** measure answer correctness, citation quality, or end-to-end refusal quality.

The previous reported retrieval scores used target chunk IDs. They are historical and not comparable to the current URL-based evaluator, which treats any retrieved passage from the expected page as a hit and remains stable when chunk IDs change. Reranking still selects 12 hybrid candidates and compares the original top 5 with the top 5 from `BAAI/bge-reranker-v2-m3` (256-token input limit).

The sets are small and should be expanded before drawing broad conclusions. In particular, keep the answerable-only ranking results separate from the 25 unanswerable holdout cases.

## Offline extraction and chunking benchmark

`scripts/benchmark_ingest.py` re-runs the production extractor and chunker against the 25 frozen HTML snapshots represented in `bench/gold.jsonl`. It never fetches pages or writes to the catalog or active vector index. The snapshot corpus is local-only and excluded from Git, so run this where `data/raw/` is available. The BAAI/bge-m3 tokenizer must already be cached; the script loads it in local-only mode and will report an error rather than download it.

The label strings are candidate examples, not verified gold labels. Each case is marked `TODO: verify`; review them before treating fact-recall or survival figures as quality claims. Boilerplate leakage checks the labeled `login` term in raw pages that contain it.

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_ingest.py
```

The script prints extraction recall/leakage and compares all nine combinations of 150/250/350 words and 0/40/80 words of overlap. It reports BAAI/bge-m3 token-length p50/p95/max, counts over 256/512 tokens, chunks under 30 words, table rows not intact in any one chunk, fact survival, and extraction/chunking latency p50/p95. Each configuration also reports the chunk, over-256-token, row-cut, and fact-survival counts grouped by page host. The result is a baseline for this small local corpus, not a general performance claim.

`--max-words 20` runs the three overlap settings with a 20-word limit; this is a metric sensitivity check, not a production chunker change. The run reports the 10 longest chunks for 150/40 with URL, section, bge-m3 body-token count, context-token count, and a 200-character preview. It also reports the largest URL-template group. For example:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_ingest.py --max-words 20
```

Add `--embed` to time embedding each configuration's context-enriched chunks through local Ollama using `bge-m3:latest`. It reports a cold run and a warm cached run, including cache hit rates. Each configuration uses a temporary SQLite cache, so the benchmark does not write to the app's cache or index. Ollama must be running with the model available.

The extractor strips inline <font>, <span>, <u>, and <b> formatting tags while retaining their text. Note that changed extraction changes content_hash, so affected pages re-index on their next fetch (or re-ingest immediately with --force and rebuild the index). Furthermore, the chunker enforces a hard cap on chunk size in BAAI/bge-m3 tokens (default 400 for the body, configurable via parameter or WEBRAG_MAX_CHUNK_TOKENS); after the word-based split, chunks exceeding the cap are split further on line boundaries, and single lines over the cap are split by tokens.

On the current 25-page snapshot set, the unverified candidate labels scored 25/25 on extraction and survival, with 0/21 labeled boilerplate terms retained; these are not quality claims until the labels are reviewed. With the 400-token hard cap, at 150 words / 40 overlap the run produced 750 chunks (token p50/p95/max 150/304/393; 81 over 256, 0 over 512; 179 under 30 words). At 350 / 40 it produced 552 chunks (158/393/400; 189 over 256, 0 over 512; 171 under 30 words). No table rows were cut (0/287) in either configuration. At 20 words, 179/287 table rows were no longer intact, while all 25 facts survived because the current labels are only 9-19 words; at 10 words, 242/287 rows were cut and only 2/25 facts survived. At 150/40, 62 of 81 chunks over 256 tokens came from the two arXiv pages; the portal contributed none. The largest URL-template group is 20/25 pages from the same Bộ Công an portal template. Latencies vary with hardware and cache state.

### Run the benchmarks

The reranker benchmark compares hybrid retrieval and reranking on the labeled development set:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_reranker.py
```

Run the same evaluation on the separate holdout in two batches:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_reranker.py `
  --cases benchmarks\reranker_holdout.json `
  --start-index 0 --end-index 20 `
  --candidate-k 12 --batch-size 8 --max-length 256

.\.venv\Scripts\python.exe scripts\benchmark_reranker.py `
  --cases benchmarks\reranker_holdout.json `
  --start-index 20 --end-index 40 `
  --candidate-k 12 --batch-size 8 --max-length 256
```

The embedding benchmark compares dense and hybrid retrieval for three Ollama embedding models on 20 English and Vietnamese queries. It re-embeds the corpus in memory and leaves the app’s active index unchanged:

```shell
ollama pull nomic-embed-text
ollama pull qwen3-embedding:0.6b
python scripts/benchmark_embeddings.py --details
```

## Project layout

```text
frontend/                 React + TypeScript web interface
src/webrag/fetch/         Page fetching and bounded crawling
src/webrag/extract/       Content cleanup and Markdown extraction
src/webrag/chunk/         Heading-aware passage splitting
src/webrag/store/         SQLite catalog and JSONL storage
src/webrag/index/         Ollama embeddings, ChromaDB, BM25, reranking
src/webrag/rag/           Local Ollama answer generation
src/webrag/api/           FastAPI endpoints and streaming responses
benchmarks/               Labeled retrieval query sets
bench/                    Offline extraction/chunking labels
data/                     Local source corpus and vector indexes (Git-ignored)
```
