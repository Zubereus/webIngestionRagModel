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

## Current corpus

These counts describe the corpus checked into `data/`; they are not a benchmark of answer quality.

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

The active embedding model defaults to `bge-m3:latest`; `WEBRAG_EMBED_MODEL` can override it. The app uses `data/chroma_bge_m3` for its active index and keeps the previous index under `data/chroma`.

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

The benchmark scripts measure whether a labeled relevant passage is retrieved and where it ranks. They do **not** measure answer correctness, citation quality, or end-to-end refusal quality.

| Test set | Answerable queries | Hybrid: Hit@1 / Hit@5 / MRR@5 | After reranking: Hit@1 / Hit@5 / MRR@5 |
| --- | ---: | ---: | ---: |
| Development (`embedding_queries.json`) | 20 (10 English, 10 Vietnamese) | 0.50 / 0.95 / 0.677 | **0.75 / 1.00 / 0.875** |
| Holdout (`reranker_holdout.json`) | 15 of 40 (8 English, 7 Vietnamese) | 0.40 / 0.80 / 0.550 | **0.40 / 0.933 / 0.628** |

Both runs used hybrid retrieval to select 12 candidates, then compared the original top 5 with the top 5 from `BAAI/bge-reranker-v2-m3` (256-token input limit). On the holdout, all 15 answer passages were present in the raw candidate pool, but one was filtered before reranking. All 25 unanswerable holdout questions passed the current relevance gate, so these results do not support a claim that the system reliably detects unsupported questions.

On the 20-query development run, reranking averaged 4.49 seconds per query (4.59 seconds p50) on a GTX 1650 Ti; loading the model took 10.89 seconds. Treat those timings as a reading from that machine, not a general performance guarantee.

The sets are small and should be expanded before drawing broad conclusions. In particular, keep the answerable-only ranking results separate from the 25 unanswerable holdout cases.

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
data/                     Checked-in source corpus and vector indexes
```
