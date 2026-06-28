from sources.prtimes import _extract_venue_from_body, _should_skip_taiwan_venue


def test_taiwan_parenthetical_venue_context_rejects_inbound_promotion():
    title = 'レンタル819、台湾最大級のバイク専門展示会「2026 國際重型機車展」に出展'
    body = (
        '会場：南港展覽館 二館（台湾・台北市）\n'
        '訪日台湾ライダーの受け入れ強化へ。日本ツーリングの新たな選択肢を提案。'
    )

    venue = _extract_venue_from_body(body)

    assert venue == '南港展覽館 二館'
    assert _should_skip_taiwan_venue(title, body, venue) is True


def test_taiwan_venue_with_japanese_participant_signal_is_kept():
    title = '台湾・台北で文化交流イベント開催、日本から参加できます'
    body = '会場：松山文創園区（台湾・台北市）\n日本人向けの交流ツアーとして実施します。'

    venue = _extract_venue_from_body(body)

    assert venue == '松山文創園区'
    assert _should_skip_taiwan_venue(title, body, venue) is False


def test_japan_venue_is_kept():
    title = '東京で台湾フェア開催'
    body = '会場：東京ビッグサイト\n台湾グルメと文化を紹介します。'

    venue = _extract_venue_from_body(body)

    assert venue == '東京ビッグサイト'
    assert _should_skip_taiwan_venue(title, body, venue) is False