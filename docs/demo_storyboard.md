# Three-minute demo storyboard

Use the student's own screen recording and the 356-word own-voice script in `demo_narration.md`. Target approximately 2:45–3:15. This storyboard uses saved real N1/U1 outputs and makes no new API requests.

| Time | Screen and action | What to explain |
|---|---|---|
| 0:00–0:25 | Show application title, GitLab corpus label and active configuration. | Twelve public policy pages; static educational snapshot with inspectable evidence. |
| 0:25–1:00 | Show active profile and architecture. | 256 tokens / 48 overlap, 364 chunks; local CPU BGE and persistent Chroma. LangGraph runs dense and BM25 sequentially within one retrieval node, uses reciprocal rank fusion with constant 60, selects up to five passages, then gates evidence, generates with Gemini and checks citations. |
| 1:00–1:30 | Show saved N1: “What is the minimum password length under GitLab Password Standards?” Inspect its 12-character answer and supporting source. Then show saved U1: “How many paid days off does GitLab offer for adopting a pet?” | N1 is supported; U1 returns insufficient evidence in the complete saved P1 run. Label both **Saved P1 evaluation result — not a live request**. |
| 1:30–2:00 | Show the P0/P1 report table and development selection record. | Original P1 run: evidence for 8/9 answerable questions versus P0 7/9; eight supported answers versus four; 5/6 expected fallbacks and no API errors. This is a diagnostic follow-up, not a new unseen test set. |
| 2:00–2:35 | Show original B1 output, then separate correction verification and UI record. | Company benefits did not establish personal legal entitlement. Preserve that failure. The later guard passed four targeted no-API checks and a real B1 UI check; do not claim a new full 6/6 fallback evaluation. The cafe/laptop false refusal remains. |
| 2:35–3:05 | Show evidence review, final verification, and README; return to application. | AI-assisted review is not human-scored faithfulness. Ninety tests pass; the checkpoint is 23/30 attempts, seven remaining. Acknowledge AI coding help and student responsibility. |

## Which evidence belongs to which run

- `evaluation/results/p1_hybrid_256_evaluation.json`: original complete 15-question P1 run; actual N1 answer, U1 fallback and B1 failure. The CSV is a compact companion.
- `evaluation/results/p1_corrections_verification.json`: four targeted scope checks with retrieval and generation prohibited; no API calls. This is not a second full evaluation.
- `evaluation/results/p1_ui_smoke.json`: separate real UI verification of F1, “Where must GitLab team members log their time away?”, and B1, “How many paid sick days am I legally entitled to?”. It is not the N1/U1 run.
- `evaluation/results/p1_evidence_review.json`: AI-assisted answer review: eight supported correct answers, one material B1 context failure, one cafe/laptop false refusal; 11 citation entries verified.
- `evaluation/results/p1_retrieval_comparison.json`: development-driven selection across both chunk profiles and dense/hybrid retrieval; no generation calls.

Recorded result latency belongs to that run and is not a guaranteed response time. Display saved output directly, or reuse already-visible application results without resubmitting. Never disguise a replay or mocked test output as a live model call.

No further API calls are authorized for this finishing work. The final checkpoint is **23/30 attempts used, seven remaining**; preserve that allowance. An optional new live recording would require a separately authorized request, with its real outcome and latency reported.

These files prepare the demo; no video has been recorded, uploaded or submitted.
