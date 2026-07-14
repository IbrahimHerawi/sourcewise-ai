# Ollama embedding batch benchmark

Date: 2026-07-14

## Corpus and method

The benchmark used the existing uploaded `dictionary.pdf` identified by the reference document ID `4578bc1b-0a35-40c4-979e-5a74f501f412`. Text extraction produced exactly 2,037,412 characters, matching the task's reference corpus. Local PDF metadata reports 660 pages rather than the task label of 650 pages; no substitute document was used.

Each batch-size variant ran in its own process against the same local Ollama model and PDF. Every run:

1. Extracted the complete PDF text without truncation.
2. Produced 1,073 ordered, nonblank chunks with `CHUNK_SIZE_CHARS=2000` and `CHUNK_OVERLAP_CHARS=100`.
3. Called `nomic-embed-text` through `/api/embed` with `truncate=false`.
4. Validated exactly one finite 768-dimensional vector per chunk.
5. Atomically persisted the extracted text and all chunks into a disposable user/document/job, verified the READY/DONE state and cardinality, then deleted the disposable rows.
6. Compared the existing reference document's status, extracted-text length, and chunk count before and after the run. The snapshot was unchanged for every variant.

The code default remained `OLLAMA_EMBED_BATCH_SIZE=32`. `EMBED_CONCURRENCY=4` was unchanged, while the batches within each document ran sequentially as required. Timings are single wall-clock observations, not CI assertions.

## Environment

- CPU: 13th Gen Intel Core i5-1340P, 12 physical cores / 16 logical processors
- Host memory: 31.66 GiB
- Docker Engine: 29.5.2
- Ollama container: `ollama/ollama:latest`, CPU execution
- Embedding read timeout: 120 seconds
- Retry attempts: 3 with the configured bounded exponential waits

Docker CPU percentages are process percentages across cores, so approximately 800% means about eight logical CPU cores were busy. CPU and memory were sampled during the embedding phase only.

## Results

| Batch size | Extraction (s) | Chunks | Embedding (s) | HTTP batches | Persistence (s) | Total (s) | Ollama CPU avg / peak | Ollama memory avg / peak | Retries |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 11.746 | 1,073 | 1,496.994 | 68 | 5.455 | 1,515.011 | 793.90% / 816.24% | 467.49 / 477.70 MiB | 0 |
| 32 | 11.779 | 1,073 | 1,494.735 | 34 | 5.586 | 1,512.175 | 796.18% / 815.20% | 469.22 / 483.10 MiB | 0 |
| 64 | 11.875 | 1,073 | 1,490.135 | 17 | 5.517 | 1,507.599 | 796.17% / 822.70% | 471.69 / 477.80 MiB | 0 |

Total duration includes extraction, chunking/validation overhead, embedding, and persistence. File loading and model warmup were performed outside the measured interval.

## Conclusion

Batch size 32 met the reference target exactly: 1,073 embeddings in 34 ordered Ollama requests with no retries. Batch size 64 was only 4.576 seconds faster end to end (about 0.3%) than batch size 32, while doubling the maximum request input count. The measurements do not justify changing the reviewed code default from 32. A deployment can evaluate 64 when minimizing request count is more important than request size, but 32 remains the recommended balanced setting for this host.
