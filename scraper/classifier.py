"""
Keyword-based semantic categoriser for Taiwan events.

Each event can receive multiple category tags. Categories match the
frontend CATEGORIES type in web/lib/types.ts:
  movie | performing_arts | senses | retail | nature | tech | tourism | lifestyle_food | books_media | gender | geopolitics
  | taiwan_japan | business | academic | competition | indigenous | art | lecture | urban | workshop | report
"""

from typing import Optional

# ---------------------------------------------------------------------------
# Keyword rules: (category, [keywords_in_any_language])
# Order matters — first match wins for primary category, but ALL rules are
# applied so an event can accumulate multiple tags.
# ---------------------------------------------------------------------------

_RULES: list[tuple[str, list[str]]] = [
    # "report" is handled specially in classify() — name-only matching
    ("movie", [
        "映画", "film", "cinema", "上映", "スクリーニング", "screening",
        "ドキュメンタリー", "documentary", "電影", "影展", "影片",
    ]),
    ("performing_arts", [
        "音楽", "music", "concert", "コンサート", "live", "ライブ", "演奏",
        "jazz", "ジャズ", "歌", "sing", "band", "バンド", "音樂", "演唱",
        "公演", "performance", "舞踊", "dance", "ダンス", "バレエ", "ballet",
        "演劇", "theater", "theatre", "舞台", "stage", "オペラ", "opera",
        "舞蹈", "表演", "劇場",
    ]),
    ("senses", [
        "展覧", "exhibition", "展示", "アート", "art", "絵", "painting",
        "写真", "photo", "gallery", "ギャラリー", "デザイン", "design",
        "漫画", "manga", "イラスト", "illustration",
        "文化体験",
        "展覧", "トレンド", "trend",
    ]),
    ("lifestyle_food", [
        "グルメ", "gourmet", "食", "food", "料理", "cuisine", "レストラン",
        "restaurant", "カフェ", "cafe", "茶", "tea", "酒", "sake", "beer",
        "ビール", "wine", "ワイン", "スイーツ", "sweets", "お菓子",
        "飲食", "餐廳", "肉まん", "点心", "給食", "ごはん",
        "ライフスタイル", "lifestyle", "生活",
    ]),
    ("books_media", [
        "文学", "literature", "本", "book", "書籍", "読書", "朗読",
        "作家", "author", "writer", "出版", "publishing", "刊行",
        "書", "文學", "繪本", "メディア", "media", "ジャーナリズム",
        "journalism", "雑誌", "magazine", "媒體",
    ]),
    ("retail", [
        "shop", "ショップ", "店", "brand", "ブランド", "マルシェ",
        "marché", "market", "マーケット", "物産", "フェア", "fair",
        "品牌",
    ]),
    ("nature", [
        "自然", "nature", "outdoor", "アウトドア", "hiking", "ハイキング",
        "植物", "plant", "花", "flower", "農業", "agriculture",
    ]),
    ("tech", [
        "tech", "テクノロジー", "technology", "IT", "AI", "startup",
        "スタートアップ", "半導体", "semiconductor", "innovation",
        "イノベーション", "digital", "デジタル", "科技",
    ]),
    ("tourism", [
        "旅行", "travel", "tourism", "観光", "trip", "旅遊",
        "ビザ", "visa", "留学", "study abroad",
        "ガイドブック", "guidebook", "guide book",
    ]),
    ("gender", [
        "lgbtq", "LGBT", "ジェンダー", "gender", "女性", "women",
        "フェミニズム", "feminism", "多様性", "diversity", "queer",
        "性別", "rainbow", "レインボー", "pride",
    ]),
    ("geopolitics", [
        "外交", "diplomacy", "政治", "politics",
        "国際", "international", "両岸", "cross-strait", "台海",
        "安全保障", "security", "民主", "democracy", "人権", "human rights",
        "選挙", "election", "独立", "independence",
    ]),
    ("taiwan_japan", [
        "台日", "日台", "台日関係", "日台関係", "台日交流", "日台交流",
        "台湾人会", "台湾祭", "台湾フェス", "台湾まつり",
    ]),
    ("business", [
        "ビジネス", "business", "投資", "investment", "貿易", "trade",
        "企業", "company", "スタートアップ", "startup", "起業", "創業",
        "経営", "management", "商務", "商業", "商談", "展示会",
    ]),
    ("competition", [
        "コンテスト", "contest", "コンペティション", "competition",
        "大会", "選手権", "championship", "コンクール", "concours",
        "公募", "応募", "賞", "award", "prize", "入賞",
        "ハッカソン", "hackathon", "ピッチコンテスト", "pitch",
        "競技", "競技会", "大賞",
    ]),
    ("academic", [
        "学術", "academic", "研究", "research", "論文", "paper", "thesis",
        "シンポジウム", "symposium", "学会", "conference",
        "大学", "university", "研究所", "institute", "PhD",
        "研究発表",
    ]),
    ("indigenous", [
        "原住民", "indigenous", "先住民", "アミ族", "パイワン族", "タイヤル族",
        "台湾原住民", "台灣原住民", "原住民族", "部落",
    ]),
    ("lecture", [
        "講座", "lecture", "トーク", "talk", "セミナー", "seminar",
        "勉強会", "説明会", "トークイベント", "トークセッション",
        "ワーク", "講演", "講義",
    ]),
    ("history", [
        "歴史", "history", "歷史", "史跡", "遗跡", "文化遣産", "heritage",
        "古代", "近代", "現代史", "資料館", "archive", "博物館", "museum",
        "記憶", "memory", "战争", "war", "猛哀", "歴史文化",
    ]),
    ("urban", [
        "建築", "architecture", "都市", "urban", "城市", "まちづくり",
        "街づくり", "街並み", "タウン", "town", "city design", "都市計画",
        "ランドスケープ", "landscape", "不動産", "空間デザイン",
    ]),
    ("workshop", [
        "workshop", "ワークショップ", "体験", "体験イベント",
        "料理教室", "cooking class", "手作り", "craft", "クラフト",
        "纖物", "weaving", "陽厄", "陪物", "陶芸", "pottery", "ceramics",
        "切り紙", "origami", "貢茶道", "tea ceremony", "体験クラス",
        "工作坊", "hands-on", "atelier", "アトリエ",
    ]),
]


def classify(
    name_ja: Optional[str],
    name_zh: Optional[str],
    name_en: Optional[str],
    description_ja: Optional[str],
    description_zh: Optional[str],
    description_en: Optional[str],
) -> list[str]:
    """
    Return a list of category tags for an event.
    Always returns at least ["culture"] as a fallback.
    """
    corpus = " ".join(
        filter(None, [name_ja, name_zh, name_en, description_ja, description_zh, description_en])
    ).lower()

    found: list[str] = []

    # "report" uses NAME-ONLY matching to avoid false positives from
    # common words like 報告/紀錄 that appear in many descriptions.
    _REPORT_KEYWORDS = [
        "レポート", "イベントレポート", "開催レポート", "開催報告",
        "実施報告", "活動紀錄", "活動報告",
    ]
    name_corpus = " ".join(filter(None, [name_ja, name_zh, name_en])).lower()
    if any(kw.lower() in name_corpus for kw in _REPORT_KEYWORDS):
        found.append("report")

    for category, keywords in _RULES:
        if any(kw.lower() in corpus for kw in keywords):
            if category not in found:
                found.append(category)

    # Always have at least one tag
    if not found:
        found = ["senses"]

    return found
