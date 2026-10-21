# AGENTS.md — services/document

Adds to the root contract. Constraints only.

- This service decides nothing about a document's lifecycle. It reports what it read: a state, a
  page count, and a sentence a teacher can understand. BE owns the row.
- No credential for any store of record. Everything needed arrives in the job payload, which is
  why the payloads carry `storage_key`, not a row id. `tools/check_contract.py` enforces it.
- One SDK, one module: `pdf.py` imports `pymupdf`, `storage.py` `minio`, only `ocr/layout.py` and
  `ocr/textline.py` `paddleocr`, `content_store.py` `pymongo`, `index/jev.py` `typesafe_sdk`,
  `index/llm.py` `langchain` (and passes the API key in). Sync SDKs go through
  `asyncio.to_thread`, never `run_in_threadpool`. `probe.py` and `index/rules.py` hold the
  thresholds, never an SDK.
- MongoDB is the content store, not a store of record. Raw pages are written only by the
  file-reading path; the tree only by `index_handlers`. `READY` leaves **only** from
  `index_handlers`, after `put_index` (plan 3c): content first, `state` second.
- Two processes: `document.ocr_worker` (OCR, one job at a time) and `document.index_worker` (the
  document agent, waits on the network). Register tasks under the constants from `contracts`.
- Never `import be` or `import agent`. No HTTP server and no port: replies travel as jobs on
  `ingest_queue_name`; a port nobody calls is a surface nobody guards.
- A job never dies silently: an unreadable file, or an index that cannot be built, becomes a
  `DocumentProbed` carrying `FAILED`. Failing to store or hand back raises `arq.Retry` (arq
  retries nothing else); on the last try it sends `FAILED` instead. Jev or OpenAI being down is not a failure: the tree falls back to rules.
- On Windows, arq cannot install signal handlers, so shutdown is not graceful. Do not rely on
  cleanup running after Ctrl+C.
