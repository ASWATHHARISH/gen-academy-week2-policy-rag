# P1 retrieval comparison

This offline experiment compares two chunk profiles and two retrieval modes, without Gemini calls. Dense retrieval uses local BGE and Chroma. Hybrid combines dense top ten and BM25 top ten through equal-weight reciprocal-rank fusion (RRF, k=60), retaining ten candidates. Metrics examine the first five candidates.

## Development selection and delivered configuration

The six development questions are distinct from the fifteen evaluation questions. Three development questions have labelled answer passages; the other three are unsupported and excluded from retrieval-quality and context-token averages. The predeclared selector ranks configurations by development mean passage Recall@5, then Hit@5, then fewer mean top-five context tokens. Exact remaining ties prefer 384, then hybrid. It does not read final-test metrics or latency.

| Profile | Retrieval | Dev Recall@5 | Dev Hit@5 | Mean top-five context tokens |
|---|---|---|---|---|
| 384 / 64 | Dense | 100% | 3/3 | 720.0 |
| 384 / 64 | Hybrid | 100% | 3/3 | 849.3 |
| 256 / 48 | Dense | 100% | 3/3 | 660.3 |
| 256 / 48 | Hybrid | 100% | 3/3 | 734.3 |

The automatic selector chose **256 / 48 dense**: fewest context tokens at equal development quality. The delivered P1 configuration is **256 / 48 hybrid**, an explicit product-mode choice to deliver the approved hybrid feature, not the overall automatic winner. Within the hybrid family, 256 wins on development context cost at equal quality: 734.3 versus 849.3 tokens. It adds 74.0 development context tokens relative to 256 dense. This decision is saved in `evaluation/results/p1_active_configuration.json`.

## Diagnostic follow-up on the frozen fifteen questions

These questions were already inspected during P0 failure analysis. P1 results are diagnostic regression measurements, not a new held-out estimate. Nine questions are answerable; six expected-fallback questions have no retrieval-recall denominator.

| Profile | Retrieval | Hit@5 | Mean passage Recall@5 | Mean top-five context tokens | Warm retrieval median / maximum |
|---|---|---|---|---|---|
| 384 / 64 | Dense | 7/9 | 77.8% | 845.1 | 0.0666 / 0.0789 s |
| 384 / 64 | Hybrid | 8/9 | 88.9% | 879.7 | 0.0695 / 0.0797 s |
| 256 / 48 | Dense | 7/9 | 77.8% | 686.2 | 0.0499 / 0.0713 s |
| 256 / 48 | Hybrid | 8/9 | 88.9% | 807.3 | 0.0744 / 0.0871 s |

| Answerable question | Dense, either profile | Hybrid, either profile |
|---|---|---|
| F1 — time-away logging | Missed | Found |
| F2 — GREEN classification | Found | Found |
| F3 — contractor harassment coverage | Found | Found |
| P1 — unattended laptop in a cafe | Missed | Missed |
| P2 — gift during negotiations | Found | Found |
| N1 — password length | Found | Found |
| N2 — compliance training deadline | Found | Found |
| A1 — GSAT acronym and frequency | Found | Found |
| M1 — password classification and storage | Both gold passages found | Both gold passages found |

Hybrid recovered the Workday evidence for F1. Neither configuration recovered the labelled cafe/laptop passage in the top five. Changing chunk size alone did not change retrieval accuracy in this small set. Fusion improves one measured case, not every paraphrase.

## Timing and reproducibility

All configurations ran in one process with a shared BGE model. Initial shared model/index loading took 17.6072 seconds. Configuration initialization took 0.0617, 0.1685, 0.1090 and 0.1419 seconds in table order, excluded from warm timings. The fixed-order single run cannot reliably rank a few milliseconds of difference. Generation, gating and API waiting are excluded.

The 384 / 64 profile has 312 chunks and 50,801 total chunk tokens. The 256 / 48 profile has 364 chunks and 54,132 total chunk tokens. Totals include headings, special tokens and overlap. All thirteen development/final gold spans were verified in saved sources and complete indexed chunks for both profiles. Original processed baseline files were preserved byte-for-byte.

| Frozen input | SHA-256 |
|---|---|
| Development questions | `81d31dd8753580e9b3ca48afa73981fc6f8eb0e658783f103ee8545e59347810` |
| Final questions | `562edb6a339601eaeac5fbbac67bc6a46bfa5d9db7a7d3f4dd3c53ab9cd2e315` |
| 384-profile chunks | `95aec3f81837a20be1ae5d5940b9b2c6a2cf14cfd76f11b14feb7fe5255864f0` |
| 256-profile chunks | `2d8b12e5e6bae492536fe60be928fffa26cdb9e98a4b3096313274c0d4f2d697` |

Detailed rows are saved in `evaluation/results/p1_retrieval_comparison.json` and `.csv`. Reproduce after building both indexes with `python -m evaluation.compare_retrieval`. This makes no API calls and does not overwrite P0 generation or calibration artifacts. The separate generation run `p1_hybrid_256_evaluation.json` and post-evaluation scope guard are discussed in `project_report.md` and `failure_analysis.md`. Retrieval metrics do not establish correct answers, correct fallbacks or faithfulness.
