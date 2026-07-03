from sources.prtimes import (
    _TAIWAN_BASED_TITLE_RE,
    _extract_venue_from_body,
    _should_skip_taiwan_venue,
)


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


# --- Title guard (_TAIWAN_BASED_TITLE_RE, used standalone at L402) ---------


def test_title_taiwan_nite_held_is_skipped():
    # Japan brand running an overseas program IN Taiwan (event b90f0b77 type).
    title = '株式会社ハミガキドッグ、台湾にて海外初となる「OraBio認定歯みがきサロン合宿講座」を開催'
    assert _TAIWAN_BASED_TITLE_RE.search(title) is not None


def test_title_taiwan_nioite_held_is_skipped():
    title = 'あるペットブランド、台湾において新プログラムを開催'
    assert _TAIWAN_BASED_TITLE_RE.search(title) is not None


def test_title_japan_held_taiwan_festival_is_kept():
    assert _TAIWAN_BASED_TITLE_RE.search('台湾フェスティバル2026を東京で開催') is None


def test_title_taiwan_night_market_in_odaiba_is_kept():
    assert _TAIWAN_BASED_TITLE_RE.search('台湾夜市 in お台場') is None


def test_title_taiwan_film_screening_is_kept():
    assert _TAIWAN_BASED_TITLE_RE.search('台湾映画上映会') is None


def test_title_taiwan_popular_sweets_japan_debut_is_kept():
    # 台湾で人気→日本初上陸: negative lookahead (?!日本) must prevent a false skip.
    assert _TAIWAN_BASED_TITLE_RE.search('台湾で人気のスイーツ、日本初上陸イベント開催') is None


# --- Title guard 漏洞 C: 台湾 + place quantifier + で/にて + verb (event 4e558c1c) --


def test_title_taiwan_3_cities_sake_overseas_expansion_is_skipped():
    # Target event 4e558c1c: Japan sake brand HENGE running overseas-expansion
    # dinner events in Taipei/Taichung/Kaohsiung — held in Taiwan, out of scope.
    title = '台湾3都市で日本酒イベントを開催。高級日本酒ブランド「HENGE」、初の海外進出へ。'
    assert _TAIWAN_BASED_TITLE_RE.search(title) is not None


def test_title_taiwan_everywhere_fair_is_skipped():
    assert _TAIWAN_BASED_TITLE_RE.search('台湾各地でフェアを実施') is not None


def test_title_taiwan_major_3_cities_briefing_is_skipped():
    assert _TAIWAN_BASED_TITLE_RE.search('台湾主要3都市で説明会を開催') is not None


def test_title_japan_3_cities_taiwan_fair_is_kept():
    # Quantifier is preceded by 日本, not 台湾 — Japan-held Taiwan fair.
    assert _TAIWAN_BASED_TITLE_RE.search('日本3都市で台湾フェアを開催') is None


def test_title_taiwan_everywhere_popular_gourmet_japan_nationwide_is_kept():
    # Japan-pivot: 台湾各地で人気 → 日本各地で開催 (held across Japan).
    assert _TAIWAN_BASED_TITLE_RE.search('台湾各地で人気のグルメ、日本各地で開催') is None


def test_title_taiwan_fair_in_tokyo_is_kept():
    # 台湾 not directly followed by a place quantifier — Japan-held.
    assert _TAIWAN_BASED_TITLE_RE.search('台湾フェアを東京で開催') is None


def test_title_taiwan_3_cities_popular_gourmet_held_in_tokyo_is_kept():
    # Japan-venue: quantifier present but event 東京で開催 — must NOT skip.
    assert _TAIWAN_BASED_TITLE_RE.search('台湾3都市で人気のグルメを東京で開催') is None


def test_title_taiwan_major_3_cities_brand_held_in_osaka_is_kept():
    # Japan-venue: quantifier present but event 大阪でイベント開催 — must NOT skip.
    assert _TAIWAN_BASED_TITLE_RE.search('台湾主要3都市で話題のブランドが大阪でイベント開催') is None


# --- Body guard (_TAIWAN_HELD_BODY_RE via _should_skip_taiwan_venue, L427) --


def test_body_held_in_taiwan_country_only_is_skipped():
    title = '株式会社ハミガキドッグ、海外初の合宿講座を開催'
    for body in ('開催地：台湾', '場所：台湾', '会場名：台湾'):
        venue = _extract_venue_from_body(body)
        assert _should_skip_taiwan_venue(title, body, venue) is True, body


def test_body_held_in_taiwan_country_with_parenthetical_venue_is_skipped():
    title = '株式会社ハミガキドッグ、海外初の合宿講座を開催'
    body = '開催地：台湾（新北市）'
    venue = _extract_venue_from_body(body)
    assert _should_skip_taiwan_venue(title, body, venue) is True


def test_body_taiwan_night_market_in_tokyo_is_kept():
    # Venue name starts with 台湾 but the event is in Tokyo — must NOT be skipped.
    title = '台湾夜市を東京で開催'
    body = '会場：台湾夜市（東京・お台場）\n台湾グルメを紹介します。'
    venue = _extract_venue_from_body(body)
    assert _should_skip_taiwan_venue(title, body, venue) is False