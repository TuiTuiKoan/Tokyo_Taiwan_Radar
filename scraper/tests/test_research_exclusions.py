from research_exclusions import excluded_reason, prompt_block


def test_excluded_domain_and_subdomains_match():
    assert excluded_reason("https://connpass.com/explore/")
    assert excluded_reason("https://taiwan-meetup.connpass.com/event/1/")
    assert excluded_reason("https://www.doorkeeper.jp/events")
    assert excluded_reason("https://example.doorkeeper.jp/events/123")


def test_lookalike_and_unrelated_domains_pass():
    assert excluded_reason("https://peatix.com/group/1") is None
    assert excluded_reason("https://notconnpass.com/") is None
    assert excluded_reason("https://doorkeeper.jp.example.com/") is None
    assert excluded_reason("") is None
    assert excluded_reason("not a url") is None


def test_prompt_block_lists_every_domain():
    block = prompt_block()
    assert "connpass.com" in block
    assert "doorkeeper.jp" in block
