# Delivery checkpoint — 24 September 2026

## Completed

- Public source: https://github.com/ASWATHHARISH/gen-academy-week2-policy-rag
- Full local hybrid RAG application and separately labelled saved-result mode.
- 110 offline tests passed in 11.49 seconds after cloud/replay additions.
- Narrated MP4: `artifacts/demo/enterprise-policy-rag-demo.mp4`.
- Video: 177.709 seconds, 1280 × 720, H.264/AAC, 3,341,002 bytes.
- Video SHA256: `57cd54db3572c5645b0915f402beca2bb7ca557b3d9b24fb97c820a64249c3ab`.
- Full audio/video decode and representative visual-frame checks passed.

The video uses actual local Streamlit screenshots of saved N1/U1 evaluation
results, readable policy evidence, and summaries drawn from recorded metrics.
The approved narration uses the locally installed Microsoft Zira synthetic
voice. Labels disclose synthetic narration and saved replay throughout. This
is not a newly recorded live Gemini interaction or the student's real voice.
The historical 90-test P1 checkpoint is intentionally preserved in its narration.

No further Gemini requests were used for deployment preparation or video.
The local ledger remains 23 of 30 attempts, with seven remaining.

## Hosting step still required

The repository is published; a Streamlit Cloud app URL is **not yet verified**.
The owner must sign in at https://share.streamlit.io and create an app with:

- Repository: `ASWATHHARISH/gen-academy-week2-policy-rag`
- Branch: `main`
- Main file: `deployment/replay/streamlit_app.py`
- Python: `3.12`
- Secrets: none for this public replay target

Choose **Deploy**, then verify the resulting `*.streamlit.app` page. See
[deployment details](deployment.md). The public target is an interactive saved
demonstration, not live arbitrary-question generation. The complete live source
and an optional protected-live entrypoint are included separately.

## Preserved and excluded

The original P0 and P1 source ZIPs and evaluation results remain unchanged.
The current source-plus-video package is `artifacts/enterprise-policy-rag-final-submission.zip`.
The publication copy has its own Git repository under `artifacts/publication/`;
the original local app keeps its private `.env` and loopback-only binding.
No `.env`, Gemini key, API ledger, model cache, Chroma data, or virtual environment
was published. No paid service or additional model was used.

The student should review the project and video before submitting them.
