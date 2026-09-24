# Failure analysis

This analysis preserves P0 in `dense_evaluation.json` and the separate P1 diagnostic run in `p1_hybrid_256_evaluation.json`. P0 had four answers, ten fallbacks and one error. P1 had nine answers (including one incorrect-scope answer), six fallbacks and no provider errors. Post-evaluation corrections are explicitly separate from full-run scores.

## P1 changes and observed outcomes

Hybrid BM25/RRF recovered F1's Workday evidence, raising retrieval Hit@5 and mean passage Recall@5 from 7/9 to 8/9. The query-level relevance gate retained complementary passages, allowing P2, A1 and M1 to answer. Eight of nine answerable questions received supported answers. The cafe/laptop gold passage remained absent from top five and the system correctly avoided inventing an answer, but this is still a false refusal. Both chunk sizes produced the same retrieval accuracy within each retrieval mode.

The active 256 hybrid configuration is an explicit product choice. The independent development selector actually chose 256 dense on context cost; within hybrid, 256 used fewer tokens at equal development recall. See `comparison.md`. Final questions were already inspected during P0 diagnosis, so these results are not new held-out evidence.

### B1: genuine quotations, wrong question answered

The question “How many paid sick days am I legally entitled to?” should fall back because jurisdiction and employment terms are missing. P1 instead answered with a company allowance of 25 paid sick days and a rolling twelve-month period. The quotations are present in the corpus, but the response fails to distinguish corporate policy from statutory entitlement. AI-assisted source review confirmed this material context failure. Mechanical citation checks alone did not catch it.

The full run remains nine answers, five of six correct expected fallbacks, and one false refusal. A generic P1 personal-legal/statutory-entitlement guard was added only afterward. Four targeted graph checks in `p1_corrections_verification.json` fell back before retrieval/generation with zero API calls; a separate real UI B1 check also fell back with zero calls. No new complete evaluation was performed after the correction, so a new 6/6 fallback score is not claimed. The guard is a narrow scope boundary, not comprehensive legal interpretation or semantic validation.

The gate was also restricted to calculate relevance from the selected five passages rather than an unused sixth-or-lower candidate. An audit confirmed the nine original generated answers would clear the selected-evidence rule, but this is not a fresh model run. Original results are preserved.

### P1 verification and residual limitations

P1's full run had a 4.8070-second all-outcome median and 5.1296-second maximum, excluding 13.9483 seconds cold start. The separate real UI F1 check took 22.4903 seconds including startup, demonstrating that even this follow-up does not guarantee sub-twenty-second responses. Rerenders added no API attempts. The final checkpoint was 23/30 attempts and 90 offline tests passed.

`p1_evidence_review.json` labels AI-assisted review of eight supported answers and B1's scope failure; no human-scored faithfulness metric is claimed. The unresolved cafe retrieval miss, static corpus limitations and conflicting hotline sources remain. More evidence retrieval is not the same as more reliable interpretation.

## Preserved P0 evaluation cases

| Question ID | Expected evidence / behavior | Observed retrieval and answer | Failure stage | Proposed change | Retest result |
|---|---|---|---|---|---|
| F1 | Time away must be logged in Workday | Gold passage absent from top five; generation returned insufficient evidence after 25.6004 s | Retrieval, then generation abstention | Evaluate sparse retrieval for exact system names; inspect candidate ranking | No baseline-changing retest |
| P1 | Do not leave devices unattended in public | Gold passage absent from top five; gate returned fallback | Retrieval | Compare paraphrase retrieval and a future reranker | No baseline-changing retest |
| P2 | Do not accept gifts during contract negotiations | Gold passage present in top five, but gate rejected evidence | Evidence gate | Expand development calibration; test answer-coverage/safety trade-off | No baseline-changing retest |
| A1 | GSAT means General Security Awareness Training and is annual | Gold passage present in top five, but gate rejected evidence | Evidence gate | Evaluate acronym-aware retrieval and recalibration on development queries | No baseline-changing retest |
| M1 | Password classification and approved storage require two documents | Both labelled passages found in top five; gate returned fallback | Evidence gate | Check multi-passage selection and coverage separately from one similarity cutoff | No baseline-changing retest |
| U1 | Unsupported pet-adoption leave question should fall back | Evidence passed the gate; Gemini returned `gemini_provider_unavailable` after 48.2949 s | Gate allowed unsupported case; provider failure prevented final grounding decision | Keep service error separate; manually retest without rewriting baseline | Separate explicit UI retry returned `insufficient_evidence` fallback in 8.9907 s; original error preserved |

The gate threshold 0.7770809961 accepted only 2/3 positive development cases while rejecting all 3 negatives. On the final set it produced false refusals even when relevant evidence was retrieved. Lowering the threshold is not automatically safe: U1 already passed it despite lacking a supported entitlement. Similarity indicates topical proximity, not answerability.

The U1 manual retry retrieved a sick-leave passage with a score just above the threshold, but generation/citation validation returned insufficient evidence rather than inventing pet-adoption leave. This demonstrates a useful downstream fallback on one real case, not comprehensive detection of unsupported questions. `evaluation/results/ui_smoke.json` preserves that run; `dense_evaluation.json` retains the original provider error.

## Additional observed issues

Two saved policies contain different reporting-hotline details: the [Anti-Corruption Policy](https://handbook.gitlab.com/handbook/legal/anti-corruption-policy/) lists EthicsPoint at `1-833-756-0853`, while the [Ethics and Compliance Program](https://handbook.gitlab.com/handbook/legal/ethics-compliance-program/) lists Ethico at `1-888-854-1396`. The snapshot alone does not establish which is the currently applicable general number. A question asking for the current general hotline cannot safely be answered by selecting whichever passage ranks first. Preserve the conflict and direct the reader to verify the applicable current source; the baseline has no comprehensive policy-version conflict resolver.

Mocked UI tests exposed a form/session-state identifier collision: successful graph results were replaced by a generic error when the form and saved question shared `policy_question`. The form was renamed to `policy_question_form`; all six UI tests then passed, including result persistence without a second graph call. These mocked tests validate UI behavior, not model answer quality.

Response latency also varied: F2 took 33.6536 seconds and U1 took 48.2949 seconds. The all-outcome median of 0.156 seconds is dominated by quick fallbacks; answered questions had a 9.7756-second median. Report both populations rather than claiming generated answers typically take a fraction of a second.

## Risks to check

| Risk | Observable symptom | Diagnosis and candidate response |
|---|---|---|
| Navigation included in chunks | Unrelated handbook page names dominate retrieval | Inspect extracted article boundaries and remove page furniture. |
| Exact policy name or acronym missed | Semantically related but wrong document ranks first | Compare dense/BM25 ranks and inspect whether RRF retrieves the relevant source. |
| Exception split from rule | Answer states a general rule without its condition | Inspect heading boundaries and chunk overlap; keep exceptions nearby. |
| Jurisdiction mismatch | A US rule is applied to a non-US question | Inspect heading metadata; clarify jurisdiction or fall back. |
| Evidence gate too strict | Relevant passages appear, but the system abstains | Tune only on the development set; report the trade-off in missed answers. |
| Evidence gate too permissive | Irrelevant passage reaches generation | Inspect score distribution and deliberately unsupported queries. |
| Genuine quote, unsupported inference | Citation text exists, but the answer misinterprets it | Human semantic review; improve prompt or return a more constrained answer. |
| Private linked detail missing | The answer would require an internal handbook page | Keep the corpus boundary explicit; do not invent missing details. |
| API quota or credentials failure | Service error with no policy answer | Record as infrastructure failure and preserve the incomplete-run status. |
| Source updated after capture | Live page differs from the evaluation evidence | Compare capture metadata and checksum; keep evaluation on one snapshot. |

## How to report a correction

Save the original question, retrieved IDs, source passages and generated answer before changing the pipeline. Identify which stage failed. Change one variable, rerun the relevant development cases, and then run the frozen evaluation when quota permits. Report both improvements and regressions.

If the final evaluation set was used to select a change, disclose that it is no longer a clean held-out measurement. Do not fill in faithfulness or correctness scores using citation validity as a substitute.

## Known design limitations

The preserved P0 system is dense-only; delivered P1 adds local BM25/RRF and a second chunk profile. Both use a small, static public corpus. Neither can answer every GitLab policy question, act on behalf of an employee, access private tools, or guarantee that a cited passage logically supports every claim. Runtime gates and quotation validation reduce some errors but do not prove correctness.
