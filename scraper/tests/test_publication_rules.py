from publication_rules import (
    PUBLICATION_NULL_FIELDS,
    canonicalize_publisher_url,
    is_ndl_periodical_article,
    is_pure_publication_record,
    normalize_event_forms,
    normalize_publisher_name,
    validate_publisher_homepage,
)


def test_normalize_event_forms_removes_blanks_and_duplicates():
    assert normalize_event_forms([" publication ", "", None, "publication"]) == ["publication"]


def test_only_exact_normalized_publication_form_is_pure():
    assert is_pure_publication_record({"event_form": ["publication"]})
    assert is_pure_publication_record({"event_form": [" publication ", "publication"]})
    assert not is_pure_publication_record({"event_form": ["publication", "lecture"]})
    assert not is_pure_publication_record({"event_form": ["lecture"]})


def test_source_category_and_title_do_not_make_record_pure():
    record = {
        "source_name": "hanmoto",
        "category": ["books_media"],
        "name_ja": "[新刊出版] 実体トーク",
        "event_form": ["lecture"],
    }
    assert not is_pure_publication_record(record)


def test_hanmoto_missing_form_is_not_pure():
    assert not is_pure_publication_record({"source_name": "hanmoto", "event_form": None})


def test_ndl_periodical_requires_pure_form_and_record_family_evidence():
    periodical = {
        "source_name": "ndl_opensearch",
        "event_form": ["publication"],
        "source_url": "https://ndlsearch.ndl.go.jp/books/R100000002-I123?recordFamily=R000000004",
    }
    assert is_ndl_periodical_article(periodical)
    assert not is_ndl_periodical_article({**periodical, "event_form": ["lecture"]})
    assert not is_ndl_periodical_article({**periodical, "source_name": "hanmoto"})
    assert not is_ndl_periodical_article({**periodical, "source_url": "https://ndlsearch.ndl.go.jp/books/R100000002-I123"})


def test_ndl_periodical_accepts_verified_record_family_metadata():
    assert is_ndl_periodical_article({
        "source_name": "ndl_opensearch",
        "event_form": ["publication"],
        "ndl_record_family": "R000000004",
    })


def test_publication_null_fields_are_the_seven_policy_fields():
    assert PUBLICATION_NULL_FIELDS == (
        "location_address",
        "location_address_zh",
        "location_address_en",
        "business_hours",
        "business_hours_zh",
        "business_hours_en",
        "location_prefectures",
    )


def test_publisher_name_and_url_normalization():
    assert normalize_publisher_name(" 株式会社 河出書房新社 ") == "河出書房新社"
    assert canonicalize_publisher_url("HTTPS://WWW.Example.JP:443/books/?utm_source=x#top") == "https://www.example.jp/books"


def test_publisher_validator_accepts_identity_evidence():
    result = validate_publisher_homepage(
        "https://www.kawade.co.jp/",
        "河出書房新社",
        page_title="河出書房新社 公式サイト",
    )
    assert result.accepted
    assert result.canonical_url == "https://www.kawade.co.jp/"
    assert result.evidence == ("title",)


def test_publisher_validator_accepts_trusted_alias_domain_identity():
    result = validate_publisher_homepage(
        "kawade.co.jp",
        "河出書房新社",
        aliases=["kawade"],
    )
    assert result.accepted
    assert result.evidence == ("domain",)


def test_publisher_validator_rejects_provenance_commerce_and_documents():
    assert validate_publisher_homepage(
        "https://ndlsearch.ndl.go.jp/books/123", "河出書房新社", page_text="河出書房新社"
    ).reason == "denied-host"
    assert validate_publisher_homepage(
        "https://www.amazon.co.jp/example", "河出書房新社", page_text="河出書房新社"
    ).reason == "denied-host"
    assert validate_publisher_homepage(
        "https://publisher.example.jp/catalog.pdf", "出版社", page_text="出版社"
    ).reason == "document-url"


def test_publisher_validator_rejects_unverified_identity():
    result = validate_publisher_homepage(
        "https://unrelated.example.jp/",
        "河出書房新社",
        page_title="書籍情報",
        page_text="一般的な紹介ページ",
    )
    assert not result.accepted
    assert result.reason == "publisher-identity-unverified"
