# Improvements

## Suggested Next Steps

### 1. Clean up stale sessions and queue state

- Add an admin or maintenance workflow to identify and clean up sessions stuck in `waiting` or `extracting`.
- Add a safer requeue/reset mechanism so broken sessions do not need manual database intervention.
- Consider a small operational view that highlights stale runs and queue backlog.

### 2. Tune parallel extraction for available hardware

- Benchmark different `CER_MAX_CONCURRENT_SESSIONS` values against the current GPU and memory limits.
- Start with conservative values and measure:
  - end-to-end extraction time
  - Ollama throughput
  - GPU memory pressure
  - failure rate under load
- Consider different defaults for smaller versus larger local models.

### 3. Improve extraction robustness for malformed model outputs

- Harden JSON parsing in `cer_service` so malformed model responses are repaired or retried where possible.
- Consider:
  - a lightweight JSON repair step
  - retrying a chunk once with a stricter prompt
  - logging the raw response for failed chunks in a controlled/debug-safe way
- Make malformed-output failures more visible in the UI console and telemetry.

### 4. Commit the current stabilization work

- Create a clean commit that captures:
  - local Ollama / GPT-OSS integration
  - corrected CER endpoint wiring
  - safer extraction failure handling
  - improved process monitoring UI
  - backend telemetry
  - parallel CRE execution
- If needed, split the work into multiple commits for easier review.

## 5 Add Graph RAG possibilities to extract data from the graph

## 6 Add RAG reranker

## 7 Add way to remove collections

## 8 Add a button to export an extraction to a central graph

## 9 Add model selection for different extraction models
