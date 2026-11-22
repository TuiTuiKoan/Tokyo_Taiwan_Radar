"""Address grader (spec venue-ground-truth, Phase A).

Every address below is a value seen in production on 2026-11-22, or a spelling the
plan review asked to pin down.
"""

import pytest

from address_quality import (
    EMPTY,
    NON_JAPAN,
    NOT_ADDRESS,
    REGION,
    STREET,
    TOWN,
    grade_address,
    is_street_level,
    normalize_address,
)


@pytest.mark.parametrize("address", [
    "東京都港区虎ノ門1-1-12 虎ノ門ビル2階",
    "東京都新宿区新宿3丁目35-13 3F",
    "東京都中央区日本橋室町３丁目２−１ COREDO室町テラス 2F",       # full-width digits and minus
    "神奈川県横浜市中区花咲町1丁目1番地 横浜ニューテアトルビル",
    "東京都新宿区新宿3丁目13番3号 新宿文化ビル6F・7F",
    "〒163-0210 東京都新宿区西新宿2-6-1 新宿住友ビル10階",
    "港区虎ノ門1-1-12 虎ノ門ビル2階",                               # no prefecture
    "東京都千代田区神田司町二丁目10番地4階",                         # kanji chome
    "東京都墨田区押上一丁目1-2",
    "名取市閖上中央一丁目6番地",
    "東京都台東区上野公園8番",
    "山梨県甲府市北口2丁目2",
    "東京都新宿区西新宿１―５",                                       # horizontal bar as dash
    "多摩市永山1ｰ5 ベルブ永山5F（多摩市永山公民館）",                 # half-width long vowel as dash
    "長野県長野市権堂町2255",                                        # lot number right after the town
    "〒192-0395 東京都八王子市大塚359",
    "〒595-0056 大阪府泉大津市夕凪町6",
    "神奈川県横須賀市新港町 6",
    "愛知県常滑市金山字上砂原100",                                   # 字
    "大分県竹田市大字玉来1番地1",                                    # 大字
    "石川県加賀市山中温泉南町ロ87番地1",
    "京都府京都市下京区烏丸通四条下ル水銀屋町620 COCON KARASUMA 3F",  # Kyoto street-name style
    "京都府京都市中京区木屋町通三条下ル大黒町71",
    "北海道札幌市中央区北1条西3丁目3-8",                             # Sapporo 条丁目 with a lot
    "北海道札幌市中央区南1条西19丁目291番地山晃ハイツB1F",
    "2F, 12-8 Sarugaku-cho, Shibuya-ku, Tokyo 150-0033",            # romanised
    "166, Hamacho, Naka-ku, Hamamatsu-shi, Shizuoka 430-0942",
    "494 Iwaki, Tsunagimachi, Ashikitagun, Kumamoto 869-5603",
    "2 Chome-6-1 Nishishinjuku, Shinjuku City, Tokyo 160-0023 日本",
    "日本、〒106-0045 東京都港区麻布十番２丁目１４−９ 2f",
    '"東京都品川区上大崎3丁目1番1号 目黒セントラルスクエア"',          # stray quotes
    "住所：東京都練馬区田柄5-27-25",                                 # label left in by extraction
    # Plan review (plan-critique-1.md): Japanese addresses that mention Taiwan.
    "東京都港区虎ノ門1-1-12 台湾文化センター",
    "東京都港区白金台5-20-2 台北駐日経済文化代表処",
    "東京都豊島区西池袋1-8-26 台湾料理 新竹",
    "京都市右京区梅ケ畑高雄町5",                                     # 高雄町 is in Kyoto
    "東京都港区六本木6-10-1（オンライン配信あり）",                   # hybrid event keeps its address
    "東京都千代田区丸の内三丁目五番一号",
    "東京都渋谷区神宮前1の14の30",
    "大阪市北区角田町8番7号",
    "仙台市青葉区一番町3-11-15",                                     # 一番町 is a town name
    "北海道札幌市中央区北1条西2丁目1",
    "京都市中京区寺町通三条上る天性寺前町523",
    "茨城県つくば市大字小野川16番地2",
    "長野県北佐久郡軽井沢町大字長倉字横吹2140",
    "6-10-1 Roppongi, Minato-ku, Tokyo",
])
def test_street(address):
    assert grade_address(address) == STREET
    assert is_street_level(address)


@pytest.mark.parametrize("address", [
    "東京都台東区上野公園",
    "東京都港区六本木",
    "福岡市中央区天神",
    "大阪市港区弁天町",                       # town inside a ward of a designated city
    "滋賀県長浜市元浜町",                     # town inside a city
    "東京都中野区中野4丁目",                   # chome only
    "愛知県名古屋市中村区名駅南1丁目",
    "東京都台東区上野公園・池之端三丁目",
    "北海道札幌市北区北8条西5丁目",            # 条丁目 without a lot
    "京都府京都市中京区烏丸通四条上ル",        # Kyoto crossing without a lot
    "岩手県盛岡市内丸",
    "東京都墨田区蔦屋書店 1号館1階 レジ前スぺース",  # 1号館 and 1階 are not lot numbers
    # Plan review: numbers that are not lot numbers.
    "東京都千代田区三番町",                    # the town is called 三番町
    "宮城県仙台市青葉区一番町",
    "東京都港区麻布十番",
    "愛知県名古屋市中区栄3",                   # chome written short
    "東京都港区南青山5",
    "東京都渋谷区道玄坂 第2会場",
    "東京都江東区有明 東京ビッグサイト 東1ホール",
    "東京都新宿区戸山 早稲田大学戸山キャンパス33号館3階第1会議室",
    "東京都目黒区駒場 東京大学駒場キャンパス18号館",
    "東京都千代田区丸の内三丁目",
    "東京都新宿区新宿3丁目",
    "北海道札幌市中央区北1条西2丁目",          # Sapporo block without a lot: TOWN by definition
    "札幌市中央区南1条西",
    "長野県北佐久郡軽井沢町大字長倉",
    "岐阜県高山市上三之町",                    # a town inside a city, not a municipality
    "神奈川県横浜市中区山下町 横浜中華街 香港路",
    "銀座4-6-16",                              # lot number without its city: incomplete
])
def test_town(address):
    assert grade_address(address) == TOWN


@pytest.mark.parametrize("address", [
    "東京都", "東京", "埼玉県", "福岡", "沖縄",
    "大阪府大阪市西区",
    "秋田県大館市",
    "福岡市",
    "広島市中区",
    "北九州市門司区",
    "東京都八王子市",
    "和歌山県西牟婁郡白浜町",                 # 郡 + 町 is a municipality, not a town in it
    "熊本県上益城郡嘉島町",
    "北海道, 東京, 神奈川, 京都, 大阪",       # list of regions
    "東京｜Tokyo",
    "名古屋", "渋谷", "東北",
    "東京都内", "東京都内各所", "全国", "日本・東京", "東京・大阪・福岡",
    "〒105-0001 東京都港区",
    "神奈川県足柄下郡箱根町",
    "千葉県市川市", "広島県廿日市市",          # city names that contain 市
    "東京都千代田区 3331 Arts Chiyoda",        # a number in a building name
    "東京都渋谷区 14:00-16:00",                # a time range is not a lot number
    "東京都渋谷区 11/22-11/24",
])
def test_region(address):
    assert grade_address(address) == REGION


@pytest.mark.parametrize("address", ["", "   ", None, "null", "NULL", "—"])
def test_empty(address):
    assert grade_address(address) == EMPTY


@pytest.mark.parametrize("address", [
    "台北",
    "台湾",
    "台北市信義區信義路五段1號",
    "台北市中山区北安路55号",                 # Japanese-style 号 on a Taipei address
    "南投県魚池郡",
    "高雄市前鎮區中華五路789號3樓",
    "台湾 国立清華大学",
    "Lot No. 2-02 - 2-06, Fahrenheit88, 179, Jln Gading, Bukit Bintang, Kuala Lumpur, Malaysia",
])
def test_non_japan(address):
    assert grade_address(address) == NON_JAPAN


def test_taito_ward_is_japan_not_taiwan():
    """台東区 is a Tokyo ward; 台東 must not be read as Taitung."""
    assert grade_address("東京都台東区上野公園5-20") == STREET
    assert grade_address("〒110-0005　東京都台東区上野1-13-16") == STREET


@pytest.mark.parametrize("address", [
    "オンライン",
    "https://example.com/access",
    "福岡アジア美術館",                       # a venue name
    "甲子園球場",
    "京王プラザホテル（新宿）",
    "早稲田大学3号館3階305教室",              # 3号館 / 3階 / 305教室 are not lot numbers
    "目白大学新宿キャンパス10号館9階（予定）",
    "2階 SHARE LOUNGEストリート",
    "、その都度メールでお知らせいたします",
    "熊本県重要無形文化財「清和文楽」。日本と台湾の人形劇を、清和文楽館で上演します。"
    "台北木偶劇団と清和文楽が、それぞれの文化に育まれた人形劇の魅力をお届けします。",
    "東京都千代田区、代表取締役 関谷有三）が運営する、タピオカミルクティー発祥の台湾カフェ"
    "「春水堂（チュンスイタン）」は、2026年8月4日（火）より、台湾料理とスイーツ",   # dates are not lots
    "東京都現代美術館で、映画を起点に約200点展示 リンクをコピー 記事のURLをコピーしました",  # 200点
    "東京・横浜・大阪・名古屋・福岡 他全国30店舗",                                       # 30店舗
    "The atmosphere of a Taiwanese night market returns to central Tenjin for around three weeks",
    "ジョグジャカルタ",
    "〒105-0001",
    "渋谷ヒカリエ 8F",
    "東京大学駒場キャンパス18号館",
    "JR新宿駅東口徒歩5分",
    "090-1234-5678",
    "未定", "調整中",
])
def test_not_address(address):
    assert grade_address(address) == NOT_ADDRESS


def test_phone_and_postal_code_are_not_lot_numbers():
    assert grade_address("姫路市観光コンベンション室：079-221-1520") != STREET
    assert grade_address("〒600-8176 京都府京都市下京区烏丸通七条上る") == TOWN


def test_address_repeating_the_venue_name():
    assert grade_address("長野", location_name="長野") == NOT_ADDRESS
    assert grade_address("東京都台東区上野公園", location_name="東京都台東区上野公園") == NOT_ADDRESS
    # A lot number still counts when the same text was also stored as the venue name.
    text = "〒150-0033 東京都千代田区神田司町二丁目10番地 ザ・フェロー神田4階"
    assert grade_address(text, location_name=text) == STREET


def test_normalize_address():
    assert normalize_address("東京都中央区日本橋室町３丁目２−１") == "東京都中央区日本橋室町3丁目2−1"
    assert normalize_address("東京都千代田区神田司町二丁目10番地") == "東京都千代田区神田司町2丁目10番地"
    assert normalize_address("名取市閖上中央十二丁目") == "名取市閖上中央12丁目"
    # Numerals that belong to a place name stay as written.
    assert normalize_address("東京都港区麻布十番２丁目１４−９") == "東京都港区麻布十番2丁目14−9"
    assert normalize_address("大阪府大阪市西区九条1-20-24") == "大阪府大阪市西区九条1-20-24"
    assert normalize_address("京都市中京区木屋町通三条下ル大黒町71") == "京都市中京区木屋町通三条下ル大黒町71"
    assert normalize_address(' "東京都港区" ') == "東京都港区"
    assert normalize_address("null") == ""


def test_known_limits():
    """Cases the text-only grader cannot settle; they err toward "needs a look".

    - 京都大学's official address is 吉田本町 with no lot number: TOWN.
    - A real one-digit lot that does not follow 町 reads like a short chome: TOWN.
    - Two addresses in one value grade by the more specific one. Such a value must
      not be used as evidence for a single venue (spec Phase D).
    """
    assert grade_address("京都府京都市左京区吉田本町") == TOWN
    assert grade_address("秋田市中通1") == TOWN
    assert grade_address("愛知県西春日井郡豊山町豊場南長廻間1 エアポートウォーク名古屋2F") == TOWN
    assert grade_address("東京都港区六本木6-10-1 / 大阪府大阪市北区梅田1-1-3") == STREET


def test_is_vague_and_the_grader_disagree_on_town_level_addresses():
    """Until Phase B, enrich_addresses.is_vague() and grade_address() coexist.

    is_vague() treats a town-level address as specific, so enrich_addresses never
    tries to improve it. The audit reports how many events fall in this gap.
    """
    from enrich_addresses import is_vague

    for address in ("東京都港区六本木", "東京都千代田区神田神保町", "東京都中野区中野4丁目"):
        assert not is_vague(address)
        assert grade_address(address) == TOWN
    for address in ("東京都", "福岡県福岡市", None):
        assert is_vague(address)
        assert grade_address(address) in (REGION, EMPTY)


def test_address_key_merges_spellings_of_one_address():
    from address_quality import address_key

    same = [
        "東京都中央区日本橋室町3-2-1 COREDO室町テラス2F",
        "東京都中央区日本橋室町３丁目２−１ COREDO室町テラス 2F",
        "〒103-0022 東京都中央区日本橋室町3-2-1",
        "中央区日本橋室町３丁目２−１ COREDO室町テラス 2F",
        "東京都中央区日本橋室町3丁目2番1号",
        "東京都中央区日本橋室町3-2-1 COREDO室町テラス1F 大屋根広場",
    ]
    assert {address_key(a) for a in same} == {"中央区日本橋室町3-2-1"}
    assert address_key("東京都新宿区新宿3丁目35-13 3F") == address_key("東京都新宿区新宿3-35-13")
    assert address_key("北海道札幌市中央区北1条西3丁目3-8") == "札幌市中央区北1条西3-3-8"
    assert address_key("長野県長野市権堂町2255") == address_key("〒380-0833 長野県長野市権堂町2255")
    assert address_key("東京都渋谷区神宮前1の14の30") == "渋谷区神宮前1-14-30"


def test_address_key_keeps_different_addresses_apart():
    from address_quality import address_key

    assert address_key("東京都新宿区西早稲田1-6-1") != address_key("東京都新宿区戸山1-24-1")
    assert address_key("東京都港区三田2-15-45") != address_key("東京都港区三田3-16-1")
    assert address_key("東京都港区虎ノ門1-1-12") != address_key("東京都港区虎ノ門1-1-1")


def test_address_key_is_none_for_addresses_that_are_not_street_level():
    from address_quality import address_key

    for value in (None, "", "東京都港区", "東京都港区六本木", "台北市信義區信義路五段7號", "オンライン"):
        assert address_key(value) is None, value


def test_address_key_leaves_town_names_with_numerals_alone():
    """plan-critique-2 M8: 丸の内, 三番町, 一番町 and 麻布十番 are town names."""
    from address_quality import address_key

    assert address_key("東京都千代田区丸の内三丁目5番1号") == "千代田区丸の内3-5-1"
    assert address_key("東京都千代田区丸の内3-5-1 東京国際フォーラム") == "千代田区丸の内3-5-1"
    assert address_key("宮城県仙台市青葉区一番町3-11-15") == "仙台市青葉区一番町3-11-15"
    assert address_key("東京都千代田区三番町6-14") == "千代田区三番町6-14"
    assert address_key("東京都港区麻布十番２丁目１４−９ 2f") == "港区麻布十番2-14-9"
    assert address_key("東京都港区三田3-1-1") == address_key("東京都港区三田3丁目1-1")
