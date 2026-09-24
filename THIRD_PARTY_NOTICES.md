# Third-party notices

## GitLab public-handbook corpus

The policy source material is from GitLab and contributors, published in the [GitLab Handbook](https://handbook.gitlab.com/handbook/). GitLab’s [External use of the Handbook](https://handbook.gitlab.com/handbook/about/handbook-usage/#external-use-of-the-handbook) identifies the handbook license as [Creative Commons Attribution-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/).

Each selected source is linked in `README.md` and identified in `ingestion/sources.json`. Keep the original document titles, source URLs, relevant supplied notices, and capture metadata with redistributed corpus material. Public policy content is used for an educational RAG demonstration. GitLab does not endorse this project.

Changes made during ingestion: extract the article from HTML; remove navigation and repeated page furniture; normalize whitespace; preserve headings; repeat table headers where needed; divide text into overlapping chunks; attach provenance metadata; and compute local embeddings. The snapshot captured on 23 September 2026 contains 12 documents and 282 sections. The preserved 384 / 64 profile has 312 chunks; active 256 / 48 has 364. P1 additionally creates a local BM25 token index. These transformations preserve policy text for retrieval rather than intentionally rewriting its rules.

Redistributed extracts and adapted corpus text remain under CC BY-SA 4.0. Attribution must include the source and license, and changes must be identified. Share adapted corpus material under the same license without additional restrictions. The license summary does not grant rights to unrelated third-party attachments, trademarks or logos. This project does not recursively ingest linked private pages or third-party attachments.

The corpus license applies to the source-derived material. It is distinct from licensing for original application code; this notice does not purport to grant an open-source license for that code.

## Software and model dependencies

Python packages and the BGE embedding model remain subject to their respective upstream licenses. `requirements.txt` records direct package pins and `requirements-lock.txt` records the installed environment. The embedding model is `BAAI/bge-small-en-v1.5`, downloaded at revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`; the local model files total 134,505,940 bytes. Preserve upstream notices when redistributing bundled dependencies or model weights. The project uses Gemini through the user’s configured API project; it does not redistribute Gemini model weights.

Do not include `.env`, API keys, private account material, or credentials in a submission ZIP or Git repository.
