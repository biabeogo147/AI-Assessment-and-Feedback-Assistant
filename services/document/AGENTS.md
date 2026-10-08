# AGENTS.md — services/document

Adds to the root contract. Constraints only.

- This service decides nothing about a document's lifecycle. It reports what it read: a state, a
  page count, and a sentence a teacher can understand. BE owns the row.
- It holds no credential for any store of record. Everything needed to read a file arrives in the
  job payload, which is why `DocumentProbeRequested` carries `storage_key` rather than a row id.
  `tools/check_contract.py` fails the build if such access appears here.
- `probe.py` is the only module allowed to `import pymupdf`, and `storage.py` the only one allowed
  to `import minio`. Both SDKs are sync; a call outside a thread blocks every other job on the
  worker's loop and raises nothing.
- Use `asyncio.to_thread`, not `run_in_threadpool`. There is no web framework here on purpose.
- Register tasks under the constants from `contracts`, never under a Python function name.
- Never `import be` or `import agent`.
- No HTTP server and no port. The reply to BE travels as a job on `be_queue_name`; a port nobody
  calls is a surface nobody guards.
- Failing to read a file is a result, not an error: it becomes a `DocumentProbed` carrying
  `DocumentState.FAILED`, because a job that dies silently leaves a chip stuck at *processing*.
  Failing to hand the result back does raise, so arq retries; nothing else can report it.
- On Windows, arq cannot install signal handlers, so shutdown is not graceful. Do not rely on
  cleanup running after Ctrl+C.
