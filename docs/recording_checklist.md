# Recording and submission checklist

## Before recording

- [x] P0 baseline preserved: 12 documents, 282 sections, 312 chunks at 384/64.
- [x] Separate active P1 profile built: 364 chunks at 256/48; baseline processed files remain byte-identical.
- [x] Dense + BM25 retrieval with reciprocal rank fusion (constant 60) implemented sequentially in one LangGraph retrieval node; up to five selected passages.
- [x] Original 15-question P1 results preserved: 8/9 relevant-evidence retrieval, eight supported answerable answers, 5/6 expected fallbacks, one cafe/laptop false refusal and no API errors.
- [x] Original B1 legal-entitlement scope failure preserved alongside four separate no-API guard checks and a real B1 UI check. No second full-evaluation claim.
- [x] Saved P1 evaluation contains the actual N1 password answer and U1 pet-adoption fallback.
- [x] Separate real UI verification covers F1 Workday and B1 legal scope; it must not be relabelled as N1/U1 verification.
- [x] AI-assisted evidence review explicitly distinguished from independent human faithfulness scoring.
- [x] Final verification reports 90 passing tests; API checkpoint is 23/30 attempts used, seven remaining.
- [ ] Independently review the answers and evidence as the student before recording.
- [ ] Rehearse the 356 spoken words in the student's own voice; target approximately 2:45–3:15.
- [ ] Hide `.env`, account settings, terminals containing secrets and unrelated personal content.
- [ ] Prepare labelled saved outputs. Do not submit more API requests during this finishing work.

## During recording

- [ ] Identify the corpus as a static public GitLab policy demonstration.
- [ ] Explain local BGE/Chroma, dense + BM25 + fusion, LangGraph evidence gate, Gemini generation and citation checks.
- [ ] Show saved N1 exactly: “What is the minimum password length under GitLab Password Standards?”
- [ ] Inspect its 12-character answer, source section and evidence; label the result as saved.
- [ ] Show saved U1 exactly: “How many paid days off does GitLab offer for adopting a pet?”
- [ ] Show its actual P1 insufficient-evidence response; keep the saved-result label visible.
- [ ] Compare P0 and P1 with denominators, and disclose that chunking, retrieval and gate behavior changed.
- [ ] Show the original B1 failure before its separate targeted correction; do not replace historical totals with estimated post-fix results.
- [ ] State that the cafe/laptop answerable query still falls back.
- [ ] Acknowledge AI coding assistance and the student's responsibility for code and evidence review.
- [ ] Never present saved results or mocked tests as new live model calls.

## Before submission

- [ ] Include source code, `requirements.txt`, `requirements-lock.txt`, `.env.example`, README, architecture and corpus attribution.
- [ ] Include both frozen chunk profiles and completed index manifests, the approved raw HTML with matching snapshot metadata, and cleaned public documents.
- [ ] Include frozen final/development questions, preserved P0/P1 results, retrieval comparison, evidence review, correction verification and failure analysis.
- [ ] Include the completed student-recorded demo or its accessible submission link.
- [ ] Exclude `.env`, secrets, API ledger, private documents, virtual environment, model cache and Chroma database from the submission package.
- [ ] Check that the selected ZIP or repository opens correctly for the reviewer.
- [ ] Follow the documented pinned-model and snapshot-based rebuild instructions.

The checklist describes preparation and verified project artifacts. A video has not been generated, recorded, uploaded or submitted.
