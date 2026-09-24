# Demo narration

Use the student's own voice. The spoken script below contains **356 words**, excluding bracketed stage cues: approximately three minutes at 120 words per minute. This version uses saved real outputs to conserve API attempts. Keep the label **Saved P1 evaluation result — not a live request** visible whenever showing N1 or U1. Stage cues and this preparation note are not spoken.

[Show the application title, GitLab corpus label, and active 256/48 hybrid configuration.]

This is my Enterprise Policy Q and A bot for the Gen Academy Week Two project. It searches twelve public GitLab handbook pages covering HR, onboarding, security, travel, and compliance. The documents are a fixed snapshot, and every answer should lead back to evidence.

[Show the active configuration and architecture diagram. Keep the saved N1 result ready without submitting a request.]

The active configuration uses three hundred and sixty four chunks, with a two hundred and fifty six token limit and forty eight tokens of overlap. Headings and source links stay attached. BGE creates embeddings locally on the CPU, and Chroma stores them.

LangGraph runs dense retrieval and keyword retrieval with BM25 sequentially inside one node. Reciprocal rank fusion combines their rankings with a constant of sixty, then the system selects up to five passages. An evidence gate decides whether to continue. Gemini writes a grounded response, followed by checks of citations and supporting quotations.

[Show saved N1 from evaluation/results/p1_hybrid_256_evaluation.json: “What is the minimum password length under GitLab Password Standards?” Expand its answer, source citations and quotation. Then show saved U1: “How many paid days off does GitLab offer for adopting a pet?” Keep the saved-result label visible. Do not claim these are the separately verified F1/B1 UI interactions.]

The first question asks for GitLab's minimum password length. The saved P1 run answers twelve characters and links to the password standard. I can inspect the actual excerpt. The next question asks about paid leave for adopting a pet. Its saved result returns insufficient evidence. These are labelled saved outputs, not new live calls.

[Show the measured P0/P1 table in docs/project_report.md and the development-only selection record in evaluation/results/p1_retrieval_comparison.json.]

I compared both chunk sizes and retrieval methods using development questions. On the fifteen question diagnostic evaluation, retrieval found evidence for eight of nine answerable questions, compared with seven in the baseline. Eight answerable questions received supported answers, compared with four previously. Five of six expected fallbacks succeeded, and there were no API errors.

[Show the original B1 failure in the saved P1 evaluation, then the separate p1_corrections_verification.json and p1_ui_smoke.json records. The latter real UI checks cover F1 Workday and B1 legal scope.]

One answer incorrectly treated company sick leave as a personal legal entitlement. The original failure remains recorded. A later scope guard passed four targeted checks without API calls and a real UI check, but that is not a new complete evaluation. The cafe laptop question still produces a false refusal.

[Show p1_evidence_review.json, the final verification record, and README. End on the application.]

AI assisted review supported eight answers and identified that legal scope failure; this is not independent human faithfulness scoring. Ninety tests pass. Twenty three of thirty API attempts have been used, so this recording conserves the remaining seven. AI coding tools helped with implementation, tests, and documentation. I remain responsible for understanding the code, reviewing evidence, and explaining these limitations.

[End recording. A finished video must still be recorded and submitted by the student.]
