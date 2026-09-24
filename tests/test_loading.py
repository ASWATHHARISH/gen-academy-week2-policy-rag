import hashlib

import pytest

from ingestion.loaders import allowed_source_url, extract_document, load_manifest


SOURCE = {"id": "test-policy", "title": "Example Policy",
          "url": "https://handbook.gitlab.com/handbook/finance/expenses/", "category": "Travel"}


def extract(html: str):
    return extract_document(html, SOURCE, snapshot_date="2026-09-23T00:00:00+00:00",
                            sha256=hashlib.sha256(html.encode()).hexdigest())


def test_sections_keep_country_rules_and_real_anchors_separate():
    document = extract("""
    <nav>PRIVATE NAVIGATION CONTENT</nav><main><div class="td-content">
    <h1>Example Policy</h1><p>These rules apply to employee business travel expenses.</p>
    <nav id="TableOfContents">DUPLICATE TABLE OF CONTENTS</nav>
    <h2 id="us">United States</h2><p>The meal allowance is $30 per day.</p>
    <h2 id="uk">United Kingdom</h2><p>The meal allowance is £25 per day.</p>
    <footer>FOOTER CONTENT</footer></div></main>""")
    assert len(document["sections"]) == 3
    us, uk = document["sections"][1:]
    assert us["section"] == "Example Policy > United States"
    assert us["section_url"].endswith("#us")
    assert "$30" in us["text"] and "£25" not in us["text"]
    assert "£25" in uk["text"] and "$30" not in uk["text"]
    all_text = " ".join(section["text"] for section in document["sections"])
    assert "NAVIGATION" not in all_text and "FOOTER" not in all_text and "CONTENTS" not in all_text


def test_lists_are_not_duplicated_and_table_headers_follow_rows():
    document = extract("""
    <article><h2 id="requirements">Requirements</h2>
    <p>Everyone must follow these company asset requirements at all times.</p>
    <ul><li>Protect the laptop<ul><li>Lock the screen</li><li>Keep it attended</li></ul></li></ul>
    <table><tr><th>Role</th><th>Training</th></tr>
    <tr><td>New hire</td><td>30 days</td></tr><tr><td>Existing employee</td><td>Annual</td></tr></table>
    </article>""")
    text = document["sections"][0]["text"]
    assert text.count("Lock the screen") == 1
    assert text.count("Protect the laptop") == 1
    assert "Role: New hire | Training: 30 days" in text
    assert "Role: Existing employee | Training: Annual" in text


def test_never_falls_back_to_whole_page_or_invents_heading_anchor():
    with pytest.raises(ValueError, match="No article body"):
        extract("<html><body><nav>Navigation content is not a policy document.</nav></body></html>")
    document = extract("<article><h2>Missing anchor</h2><p>A complete policy sentence with enough text to be useful for testing.</p></article>")
    assert document["sections"][0]["anchor"] == ""
    assert document["sections"][0]["section_url"] == SOURCE["url"]


def test_manifest_is_exactly_twelve_allowlisted_documents():
    manifest = load_manifest()
    assert len(manifest["sources"]) == 12
    assert manifest["license"] == "CC BY-SA 4.0"
    assert all(allowed_source_url(source["url"]) for source in manifest["sources"])
    for bad in ("http://handbook.gitlab.com/handbook/finance/expenses/",
                "https://example.com/handbook/finance/expenses/",
                "https://handbook.gitlab.com/handbook/finance/expenses/?token=secret",
                "https://handbook.gitlab.com/handbook/unapproved/",
                "https://handbook.gitlab.com.evil.example/handbook/finance/expenses/"):
        assert not allowed_source_url(bad)
