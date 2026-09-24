# Enterprise Policy Q&A

A local RAG demonstration for the Gen Academy Week 2 project. Ask questions about a static collection of 12 English GitLab public-handbook policy pages and inspect the evidence behind an answer.

Delivered P1 uses local BGE-small/Chroma dense retrieval plus BM25 and reciprocal-rank fusion (RRF), Gemini 3.5 Flash-Lite for grounded generation, LangGraph orchestration and Streamlit. Active chunks use 256 tokens with 48-token overlap. The dense-only P0 baseline (384 / 64) is preserved. Reranking remains deferred to P2.

## Run the existing local installation

### Free public demonstration and narrated video

The publication repository is [ASWATHHARISH/gen-academy-week2-policy-rag](https://github.com/ASWATHHARISH/gen-academy-week2-policy-rag).
For the lightweight free public demonstration, deploy `deployment/replay/streamlit_app.py` on Streamlit Community Cloud, using Python 3.12 and branch `main`. See [deployment instructions](docs/deployment.md).
This public target replays actual saved N1, U1 and F1 evaluation results: it does **not** answer new live questions, load the embedding model or contact Gemini. The complete live RAG source remains included and works locally. The separate protected-live cloud entrypoint is opt-in; its Linux deployment has not yet been verified.

The local interface also offers **Saved evaluation replay** (`?demo=1`) for honest, quota-free demonstrations. The generated video uses real screenshots of that mode and an explicitly approved local synthetic voice; it is not a live-query recording or the student's real voice. Scripts in `scripts/` reproduce the narration, captures and MP4. Video files are delivered separately from source archives.

Deployment/replay additions pass 110 offline tests (11.49 seconds). Historical P0/P1 measurements and the 90-test P1 checkpoint below are preserved unchanged. No additional Gemini attempts were spent: the last confirmed ledger remains 23/30.

From PowerShell in the project directory:

```powershell
.\.venv\Scripts\python.exe -m streamlit run ui/streamlit_app.py --server.address 127.0.0.1
```

Open the local address printed by Streamlit, normally `http://127.0.0.1:8501`. The server binds to `127.0.0.1`. A form submission runs one question; interacting with evidence expanders or rerendering the page does not automatically resubmit it.

## Reproduce setup

Use a supported Python installation and an isolated environment. Direct dependency pins are in `requirements.txt`; `requirements-lock.txt` records the installed environment, including transitive dependencies. The CPU PyTorch wheel uses the official CPU package index.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.12.1+cpu --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

Copy `.env.example` to a local `.env` if setting up a new checkout. Enter the Gemini API key locally as `GOOGLE_API_KEY`; do not commit or paste the key into application questions. Set `GEMINI_FREE_TIER_CONFIRMED=true` only after confirming free-tier access for the configured model and project. The app uses the Gemini Developer API, not Vertex AI. API availability and quotas are account-dependent.

```powershell
.\.venv\Scripts\python.exe -m ingestion.download_model --model BAAI/bge-small-en-v1.5
.\.venv\Scripts\python.exe -m ingestion.ingest --profile 256
.\.venv\Scripts\python.exe -m evaluation.evaluate --questions evaluation/questions.json --retrieval hybrid --profile 256 --gate p1 --retrieval-only --output evaluation/results/local_retrieval_check.json
```

These commands assume the delivered ZIP's raw snapshots and processed documents are present. Profile 256 verifies and reuses them. For a source-only checkout without snapshots, first run `python -m ingestion.ingest --profile 384` to fetch/extract the approved pages, then build profile 256. Embedding and retrieval run locally after model download. Ingestion builds the index once, not on each question.

Saved calibration artifacts are included; do not blindly recalibrate or overwrite historical results. `python -m evaluation.calibrate_p1 --profile 256 --retrieval hybrid` is for an intentionally new experiment and refuses an existing calibration file. Calibration uses development, not final, questions. To reproduce the four-way offline comparison, build both profiles, then run `python -m evaluation.compare_retrieval`; this replaces its comparison outputs. Use a fresh output filename for a new evaluation run.

Only after free-tier access and API use are authorized, the following commands contact Gemini:

```powershell
.\.venv\Scripts\python.exe scripts/check_gemini.py --max-calls 1
.\.venv\Scripts\python.exe -m evaluation.evaluate --questions evaluation/questions.json --retrieval hybrid --profile 256 --gate p1 --output evaluation/results/local_generation_check.json
```

The configured API-attempt budget is 30 with a minimum five-second interval. It is an application guard, not a guarantee about provider billing or quotas. Do not enable paid billing to resolve a quota error. Tracing to LangSmith is disabled.

## How answers are produced

Ingestion extracts article content, removes repeated navigation and splits by headings. Two profiles are preserved: baseline 384 / 64 and active 256 / 48. Both retain document title, identity, source URL and section metadata. Local BGE embeddings populate Chroma; saved chunks also supply BM25.

One graph node runs dense retrieval, BM25 and RRF sequentially. It fuses each retriever's top ten with rank constant 60 and selects up to five deduplicated passages. A development-calibrated query-relevance gate can fall back before generation. Otherwise Gemini receives the question and passages, and citation identity/quotation checks verify provenance. A post-evaluation P1 guard handles personal legal/statutory-entitlement requests before retrieval; it is not a general jurisdiction or semantic checker.

Citation and quotation checks establish provenance and text presence. They do not prove that every claim is semantically entailed by the passage. Human faithfulness review remains part of evaluation. A retrieval score is not an answer-confidence percentage.

## Corpus and attribution

The manifest in `ingestion/sources.json` identifies the fetched URLs. The 23 September 2026 snapshot contains 12 documents and 282 sections. Cleaned article bodies contain 207,166 characters / 32,505 whitespace-delimited words. Baseline 384 / 64 has 312 chunks and 50,801 total tokens; active 256 / 48 has 364 chunks and 54,132 tokens. Totals include headings, special tokens and overlap. The snapshot contains:

1. [Time Off Types](https://handbook.gitlab.com/handbook/people-group/time-off-and-absence/time-off-types/)
2. [Anti-Harassment Policy](https://handbook.gitlab.com/handbook/people-group/anti-harassment/)
3. [GitLab Onboarding](https://handbook.gitlab.com/handbook/people-group/general-onboarding/)
4. [GitLab Password Standards](https://handbook.gitlab.com/handbook/security/policies_and_standards/password-standard/)
5. [GitLab Data Classification Standard](https://handbook.gitlab.com/handbook/security/policies_and_standards/data-classification-standard/)
6. [Security Awareness Training Standard](https://handbook.gitlab.com/handbook/security/security-assurance/governance/sec-training/)
7. [Physical Security Standard for Company Assets](https://handbook.gitlab.com/handbook/security/policies_and_standards/physical-security-standard-for-company-assets/)
8. [Global Travel and Expense Policy](https://handbook.gitlab.com/handbook/finance/expenses/)
9. [Anti-Corruption Policy](https://handbook.gitlab.com/handbook/legal/anti-corruption-policy/)
10. [Anti-Retaliation Policy](https://handbook.gitlab.com/handbook/legal/anti-retaliation-policy/)
11. [Policies related to Gifts and Contributions](https://handbook.gitlab.com/handbook/legal/policies/gifts-contributions/)
12. [GitLab’s Ethics and Compliance Program](https://handbook.gitlab.com/handbook/legal/ethics-compliance-program/)

GitLab identifies its handbook as [CC BY-SA 4.0](https://handbook.gitlab.com/handbook/about/handbook-usage/#external-use-of-the-handbook). See `THIRD_PARTY_NOTICES.md` for attribution and changes. The corpus does not cover all GitLab rules or linked internal materials. Country-specific entitlements must not be inferred from global summaries.

## Evaluation and deliverables

P1 results are saved separately in `evaluation/results/p1_hybrid_256_evaluation.json`. On the same fifteen diagnostic questions, hybrid found gold evidence for 8/9 answerable questions (88.9% Hit@5 and mean passage Recall@5), compared with P0's 7/9. Eight of nine answerable questions received supported answers. There were nine total answers because B1 incorrectly substituted company sick-leave policy for an unspecified personal legal entitlement. Five of six expected fallbacks succeeded; there were no provider errors. Full-run overall median/max was 4.8070 / 5.1296 seconds, excluding 13.9483 seconds of cold start; this is not a service guarantee.

The failed B1 result remains unchanged. A subsequent scope guard passed four targeted zero-API checks and a separate real UI B1 check. This is not a rerun establishing a new 6/6 full-suite fallback score. `p1_evidence_review.json` labels AI-assisted review of eight supported answers and the B1 scope failure; no human-scored faithfulness is claimed.

The four-way comparison is in `docs/comparison.md`. All configurations tied on three positive development questions. The automatic context-cost selector chose 256 dense; active 256 hybrid is an explicit product-mode choice to deliver the approved feature. Within hybrid, 256 uses fewer development context tokens than 384. P1 measurements are diagnostic follow-ups because P0 failures were already inspected.

Final P1 verification: 90 offline tests passed in 6.99 seconds. `p1_ui_smoke.json` records a real Workday answer and B1 scope fallback; rerenders added no API attempts. The final checkpoint used 23/30 attempts, leaving seven. P0 results and checkpoint details below are historical, not the active remaining budget.

### Preserved P0 baseline

`evaluation/questions.json` holds the 15-question evaluation set. Retrieval can be tested without Gemini using `--retrieval-only`. Full generation evaluation consumes API attempts. For each answerable question, Recall@5 is the fraction of its labelled gold passages found verbatim (with whitespace and case normalized) in the top five retrieved chunks from the correct document. The summary averages these per-question values. Hit@5 records whether at least one gold passage was found. Questions expected to fall back are excluded from retrieval-recall denominators and evaluated separately. Report the denominator with each result; do not present a target as an achieved score.

The saved dense baseline in `evaluation/results/dense_evaluation.json` processed all 15 questions: 9 answerable and 6 expected fallbacks. Hit@5 and mean passage Recall@5 were 77.8% (7/9 answerable questions had their gold evidence). The application answered 4 questions, fell back on 10, and returned 1 provider error. It refused 5/9 answerable questions and correctly fell back on 5/6 expected-fallback questions. The remaining expected-fallback case, U1, was a service error and is not counted as successful abstention.

Warm retrieval median was 0.133 seconds. Across all outcomes, end-to-end median was 0.156 seconds, dominated by quick fallbacks; the four answered questions had a 9.776-second median. Maximum end-to-end time was 48.295 seconds for the provider-error case. Initial local model/index warm-up took 32.567 seconds. These are one-run local measurements, not service guarantees.

The conservative threshold, approximately 0.777081, accepted 2/3 answerable development questions and rejected all 3 unsupported development questions. It was not tuned on the final test set. The baseline demonstrates a substantial false-refusal trade-off. Mechanical citation validation is not a human faithfulness score; any AI-assisted evidence review is labelled separately in the report.

Verification completed: 46 offline tests passed in 17.84 seconds, including six mocked Streamlit UI tests; `pip check` found no broken requirements; the one-attempt Gemini smoke check passed. The baseline used six Gemini attempts, plus one earlier smoke attempt: 7/30 at that checkpoint.

Separate live Streamlit verification in `evaluation/results/ui_smoke.json` answered the exact N1 password question and correctly fell back on the exact U1 pet-adoption leave question. U1's original provider error remains in the frozen baseline. Rerendering either result added no API attempts. The final verification checkpoint used 9/30 attempts, leaving 21; subsequent user runs consume the remaining budget. The live check uses real Streamlit AppTest and the real graph/API, not a browser screenshot.

`evaluation/results/evidence-review.json` records an AI-assisted inspection of four released answers containing five claims. Those inspected claims were supported by the cited passages. This is a small conditional sample, not an independent human evaluation or a general faithfulness score. Student review remains required before claiming human-scored results.

See `architecture.md`, `docs/project_report.md`, `docs/failure_analysis.md`, and the demo materials in `docs/`. The demo is designed for the student to record with their own narration; no video or voice recording is implied by these files.

## Source ZIP and the frozen snapshot

The delivered P1 archive is `artifacts/enterprise-policy-rag-p1-source.zip`. The original `artifacts/enterprise-policy-rag-source.zip` is preserved as the P0 archive. The P1 ZIP includes application/test source, setup files, the dependency lock, public raw HTML with snapshot metadata, both processed chunk profiles, evaluation evidence and documentation. It excludes `.env`, API credentials, the attempt ledger, `.venv`, model files and Chroma storage. Corpus files retain the CC BY-SA 4.0 notice.

Extract into a new folder, install the locked dependencies, create a local `.env` from `.env.example`, download the pinned BGE model and run ingestion to rebuild Chroma from the included snapshots. The model downloader pins revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`. The saved evaluation results are readable without calling Gemini again. The excluded attempt ledger means a new extraction starts a separate local counter; it does not restore provider quota or authorize additional spend.

## Troubleshooting

| Symptom | Action |
|---|---|
| Missing local embedding model | Complete the model download command, then retry. |
| Missing or empty index | Run ingestion and inspect its summary before opening the UI. |
| Missing key or free-tier confirmation | Check the local `.env` configuration without printing it. |
| Gemini quota/rate-limit error | Wait or stop the run; keep the provider error separate from policy fallback. |
| Evidence fallback on an answerable question | Inspect retrieved headings and passages, then record the case in failure analysis. |
| Unsupported jurisdiction-specific answer | Add the applicable document in a later approved corpus revision, or keep the fallback. |

This is a student demonstration, not an official GitLab service. Generated answers describe the saved corpus, and the source pages may later change.
