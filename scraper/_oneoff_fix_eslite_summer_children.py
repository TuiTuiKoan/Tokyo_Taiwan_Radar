"""Repair the 2026 Eslite summer umbrella event and its child activities.

The public ``eslite Collection`` row incorrectly treated a 6,980 JPY tea gift
as the admission price for the whole summer campaign. The official umbrella
page already belongs to the canonical IWAFU event, so this repair:

1. clears nested hours from the canonical parent and pins its official URL;
2. repairs the existing Starry Sky Taiwan Night Market row and attaches it;
3. inserts the six other first-level items listed by the official umbrella;
4. merges the incorrect Collection row into the canonical parent last.

Usage:
    ../.venv/bin/python _oneoff_fix_eslite_summer_children.py --dry-run
    ../.venv/bin/python _oneoff_fix_eslite_summer_children.py --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

from merger import apply_targeted_merge
from qa_auto_fix import unlock_and_write


PARENT_ID = "074ec240-3463-4c42-8cab-2ea348b93f5c"
COLLECTION_ID = "c1eb5e53-6779-4379-ba2a-95e8ae8e8255"
OVERVIEW_SECONDARY_ID = "17cdd2b3-eb7b-43c8-b413-c77cca19067f"
NIGHT_MARKET_ID = "f573eb8b-665e-4158-a4ef-b94c92d81fcc"

MAIN_URL = "https://www.eslitespectrum.jp/news/85683cc0-cbde-4cfe-bc7e-d46468d7a998"
COLLECTION_URL = "https://www.eslitespectrum.jp/news/4b78600a-8404-4286-878e-bc3463f5d66c"
NIGHT_MARKET_URL = "https://www.eslitespectrum.jp/news/57f8e77e-29dc-4c02-88c2-5b06e281db66"
VENUE_URL = "https://www.eslitespectrum.jp/about/store/9cd1340f-26b6-4f55-9c33-d0487d7ac01d"

COMMON_ADDRESS = "東京都中央区日本橋室町3-2-1 COREDO室町テラス2F"
COMMON_ADDRESS_ZH = "東京都中央區日本橋室町3-2-1 COREDO室町TERRACE 2樓"
COMMON_ADDRESS_EN = "COREDO Muromachi Terrace 2F, 3-2-1 Nihonbashi-Muromachi, Chuo City, Tokyo"

PARENT_EXPECTED = {
    "source_name": "iwafu",
    "source_id": "iwafu_1150119",
    "source_url": "https://www.iwafu.com/jp/events/1150119",
    "official_url": "https://www.eslitespectrum.jp",
    "name_ja": "夏日の奇幻旅程～夏休みのファンタジック・ジャーニー～",
    "start_date": "2026-07-18T00:00:00+00:00",
    "end_date": "2026-08-31T00:00:00+00:00",
    "business_hours": "12:00〜20:00",
    "business_hours_zh": "10:00～19:00",
    "business_hours_en": "10:00 AM - 7:00 PM",
    "is_paid": False,
    "price_info": None,
    "is_active": True,
    "parent_event_id": None,
    "merged_into_event_id": None,
    "secondary_source_urls": [MAIN_URL],
}

COLLECTION_EXPECTED = {
    "source_name": "eslite_spectrum",
    "source_id": "eslite_spectrum_4b78600a-8404-4286-878e-bc3463f5d66c",
    "source_url": COLLECTION_URL,
    "name_ja": "eslite Collection -夏日の奇幻旅程-",
    "start_date": "2026-07-18T00:00:00+00:00",
    "end_date": "2026-08-31T00:00:00+00:00",
    "is_paid": True,
    "price_info": "6980円(税込)",
    "is_active": True,
    "parent_event_id": None,
    "merged_into_event_id": None,
}

OVERVIEW_EXPECTED = {
    "source_name": "eslite_spectrum",
    "source_id": "eslite_spectrum_85683cc0-cbde-4cfe-bc7e-d46468d7a998",
    "source_url": MAIN_URL,
    "is_active": False,
    "parent_event_id": None,
    "merged_into_event_id": PARENT_ID,
}

NIGHT_MARKET_EXPECTED = {
    "source_name": "eslite_spectrum",
    "source_id": "eslite_spectrum_57f8e77e-29dc-4c02-88c2-5b06e281db66",
    "source_url": NIGHT_MARKET_URL,
    "start_date": "2026-07-18T00:00:00+00:00",
    "end_date": "2026-07-18T00:00:00+00:00",
    "business_hours": "12:00〜20:00",
    "business_hours_zh": "12:00～20:00",
    "business_hours_en": "12:00 PM - 8:00 PM",
    "location_name": "誠品生活日本橋",
    "location_name_zh": "誠品生活日本橋",
    "location_name_en": "Eslite Spectrum Nihonbashi",
    "location_address": COMMON_ADDRESS,
    "location_address_zh": "東京都中央區日本橋室町3-2-1",
    "location_address_en": "3-2-1 Nihonbashi Muromachi, Chuo City, Tokyo",
    "category": ["lifestyle_food", "market"],
    "event_form": ["networking"],
    "is_paid": True,
    "price_info": "B：2F誠品生活日本橋フロアでのお買い物、レシート合計5,000円(税込)ごとに、抽選券Bを1枚お渡しいたします。",
    "parent_event_id": None,
    "is_active": True,
    "merged_into_event_id": None,
}

PARENT_CHANGES = {
    "official_url": MAIN_URL,
    "business_hours": None,
    "business_hours_zh": None,
    "business_hours_en": None,
}

NIGHT_MARKET_CHANGES = {
    "start_date": "2026-08-22T00:00:00+00:00",
    "end_date": "2026-08-23T00:00:00+00:00",
    "business_hours": "8/22 12:00～20:00、8/23 12:00～19:00",
    "business_hours_zh": "8/22 12:00～20:00、8/23 12:00～19:00",
    "business_hours_en": "Aug 22 12:00 PM–8:00 PM; Aug 23 12:00 PM–7:00 PM",
    "location_name": "コレド室町テラス1F 大屋根広場",
    "location_name_zh": "COREDO室町TERRACE 1樓 大屋頂廣場",
    "location_name_en": "COREDO Muromachi Terrace 1F Grand Roof Plaza",
    "location_address": "東京都中央区日本橋室町3-2-1 COREDO室町テラス1F 大屋根広場",
    "location_address_zh": "東京都中央區日本橋室町3-2-1 COREDO室町TERRACE 1樓 大屋頂廣場",
    "location_address_en": "COREDO Muromachi Terrace 1F Grand Roof Plaza, 3-2-1 Nihonbashi-Muromachi, Chuo City, Tokyo",
    "category": ["lifestyle_food", "taiwan_japan"],
    "event_form": ["market"],
    "is_paid": False,
    "price_info": "入場料の記載なし（飲食・物販は各ブース別料金、抽選会は別途参加条件あり）",
    "description_ja": "2026年8月22日・23日、コレド室町テラス1F大屋根広場で、台湾屋台グルメ、キッチンカー、日台の縁日、プラネタリウム、星引きくじを楽しめる「星空台湾夜市」を開催します。各ブースの開始・終了時間は異なります。",
    "description_zh": "2026年8月22日至23日，COREDO室町TERRACE 1樓大屋頂廣場將舉辦「星空台灣夜市」，可體驗台灣攤販美食、餐車、日台廟會遊戲、天文館與星空抽籤。各攤位的開始與結束時間不同。",
    "description_en": "The Starry Sky Taiwan Night Market takes place on August 22–23, 2026 at COREDO Muromachi Terrace's 1F Grand Roof Plaza, with Taiwanese street food, food trucks, Japanese and Taiwanese festival games, a planetarium, and star-themed draws. Booth hours vary.",
    "parent_event_id": PARENT_ID,
}

EXPECTED_TARGET_LOCKS = {
    PARENT_ID: {},
    NIGHT_MARKET_ID: {
        "location_name": ("4a9e15a9-b733-4dab-916e-f73e10bc1c6f", "誠品生活日本橋"),
        "location_address": (
            "4cec29e7-636d-4481-8d5b-80f6d010c57c",
            COMMON_ADDRESS,
        ),
    },
}


def _localized_selection_reason(ja: str, zh: str, en: str) -> str:
    return json.dumps({"ja": ja, "zh": zh, "en": en}, ensure_ascii=False)


def _child(
    *,
    suffix: int,
    source_url: str,
    name_ja: str,
    name_zh: str,
    name_en: str,
    description_ja: str,
    description_zh: str,
    description_en: str,
    raw_description: str,
    start_date: str,
    end_date: str,
    category: list[str],
    event_form: list[str],
    location_name: str,
    location_name_zh: str,
    location_name_en: str,
    business_hours: str | None,
    business_hours_zh: str | None,
    business_hours_en: str | None,
    is_paid: bool,
    price_info: str,
    reason_ja: str,
    reason_zh: str,
    reason_en: str,
) -> dict[str, Any]:
    return {
        "source_name": "eslite_spectrum",
        "source_id": f"eslite_spectrum_85683cc0-cbde-4cfe-bc7e-d46468d7a998_sub{suffix}",
        "source_url": source_url,
        "official_url": source_url,
        "original_language": "ja",
        "raw_title": name_ja,
        "raw_description": raw_description,
        "name_ja": name_ja,
        "name_zh": name_zh,
        "name_en": name_en,
        "description_ja": description_ja,
        "description_zh": description_zh,
        "description_en": description_en,
        "start_date": start_date,
        "end_date": end_date,
        "category": category,
        "event_form": event_form,
        "location_name": location_name,
        "location_name_zh": location_name_zh,
        "location_name_en": location_name_en,
        "location_address": COMMON_ADDRESS,
        "location_address_zh": COMMON_ADDRESS_ZH,
        "location_address_en": COMMON_ADDRESS_EN,
        "location_prefectures": ["東京都"],
        "location_url": VENUE_URL,
        "business_hours": business_hours,
        "business_hours_zh": business_hours_zh,
        "business_hours_en": business_hours_en,
        "is_paid": is_paid,
        "price_info": price_info,
        "price_amount": None,
        "price_currency": "JPY",
        "organizer": "誠品生活日本橋",
        "organizer_zh": "誠品生活日本橋",
        "organizer_en": "Eslite Spectrum Nihonbashi",
        "organizer_type": ["commercial_brand"],
        "selection_reason": _localized_selection_reason(reason_ja, reason_zh, reason_en),
        "annotation_status": "annotated",
        "is_active": True,
        "parent_event_id": PARENT_ID,
    }


NEW_CHILDREN = [
    _child(
        suffix=1,
        source_url=NIGHT_MARKET_URL,
        name_ja="星空抽選会",
        name_zh="星空抽獎會",
        name_en="Starry Sky Prize Draw",
        description_ja="星空台湾夜市で受け取る抽選券Aと、誠品生活日本橋2Fで税込5,000円の買い物ごとに受け取る抽選券Bを1組にして参加するガラポン抽選会です。特賞はSTARLUX航空の東京・台中往復航空券です。",
        description_zh="將星空台灣夜市取得的抽獎券A，與在誠品生活日本橋2樓每消費滿5,000日圓（含稅）取得的抽獎券B配成一組，即可參加轉盤抽獎。特獎為星宇航空東京往返台中的機票。",
        description_en="Pair ticket A from the Starry Sky Taiwan Night Market with ticket B, issued for every JPY 5,000 spent on Eslite Spectrum Nihonbashi's 2F, to enter the prize draw. The grand prize is a STARLUX round trip between Tokyo and Taichung.",
        raw_description="抽選券AとBのセットで参加。Aは星空台湾夜市で一会計につき1枚、Bは2Fでレシート合計5,000円(税込)ごとに1枚。期間中のレシート合算可。",
        start_date="2026-08-22T00:00:00+00:00",
        end_date="2026-08-23T00:00:00+00:00",
        category=["taiwan_japan", "competition"],
        event_form=["competition"],
        location_name="コレド室町テラス1F 大屋根広場・誠品生活日本橋 expo",
        location_name_zh="COREDO室町TERRACE 1樓大屋頂廣場・誠品生活日本橋 expo",
        location_name_en="COREDO Muromachi Terrace 1F Grand Roof Plaza and Eslite Spectrum expo",
        business_hours="8/22 12:00～20:00、8/23 12:00～19:00",
        business_hours_zh="8/22 12:00～20:00、8/23 12:00～19:00",
        business_hours_en="Aug 22 12:00 PM–8:00 PM; Aug 23 12:00 PM–7:00 PM",
        is_paid=True,
        price_info="抽選券A（夜市で一会計につき1枚）と抽選券B（2Fで税込5,000円購入ごとに1枚）が必要",
        reason_ja="台湾夜市への来場と館内購入を組み合わせた、公式サマー企画の抽選会です。",
        reason_zh="這是結合台灣夜市到場與館內消費的官方夏季抽獎活動。",
        reason_en="This official summer prize draw connects the Taiwan night market with purchases inside Eslite Spectrum.",
    ),
    _child(
        suffix=2,
        source_url=MAIN_URL,
        name_ja="普段使いの魔法道具マーケット『まいにち魔法』",
        name_zh="日常魔法道具市集「每日魔法」",
        name_en="Everyday Magic Tools Market",
        description_ja="コンパクトミラー、鉱石の耳飾り、魔導書のようなノートや文具など、人気クリエイターが手がけるアクセサリーや雑貨を集めたマーケットです。",
        description_zh="集結人氣創作者製作的飾品與雜貨，包括化妝鏡、礦石耳飾，以及宛如魔法書的筆記本與文具。",
        description_en="A market of accessories and goods by popular creators, including compact mirrors, mineral earrings, and notebooks and stationery styled like spellbooks.",
        raw_description="期間｜8/1(土)～8/31(月)\n場所｜expo\n人気クリエイターが手がけるアクセサリーや雑貨を集めた魔法道具マーケット。",
        start_date="2026-08-01T00:00:00+00:00",
        end_date="2026-08-31T00:00:00+00:00",
        category=["retail", "art"],
        event_form=["market"],
        location_name="誠品生活日本橋 expo",
        location_name_zh="誠品生活日本橋 expo",
        location_name_en="Eslite Spectrum Nihonbashi expo",
        business_hours=None,
        business_hours_zh=None,
        business_hours_en=None,
        is_paid=False,
        price_info="入場無料（商品は個別販売）",
        reason_ja="公式サマー企画の中で独立した期間と会場を持つマーケットです。",
        reason_zh="這是官方夏季企劃中具有獨立期間與會場的市集。",
        reason_en="This is a separately dated and located market within the official summer program.",
    ),
    _child(
        suffix=3,
        source_url=MAIN_URL,
        name_ja="夏だ‼ 黒橋牌台湾ソーセージだ‼",
        name_zh="夏天就是要吃黑橋牌台灣香腸‼",
        name_en="Summer Black Bridge Taiwanese Sausage Campaign",
        description_ja="食料品購入者向けの三角くじ、無料試食会、焼きたて黒橋牌台湾ソーセージの限定販売を行います。試食は各実施日11:30～16:00、限定販売は7月25日・26日です。",
        description_zh="舉辦食品購買者限定抽籤、免費試吃，以及現烤黑橋牌台灣香腸限定販售。試吃於各活動日11:30～16:00，限定販售為7月25日至26日。",
        description_en="The campaign includes a prize draw for grocery shoppers, free tastings, and limited sales of freshly grilled Black Bridge Taiwanese sausages. Tastings run 11:30 AM–4:00 PM on event days; sales are July 25–26.",
        raw_description="実施日：7/18・19・20・25・26 各日10:00～19:00。無料試食会は各日11:30～16:00。限定販売は7/25・26 11:30～16:00、1本500円(税込)。",
        start_date="2026-07-18T00:00:00+00:00",
        end_date="2026-07-26T00:00:00+00:00",
        category=["lifestyle_food", "taiwan_japan"],
        event_form=["tasting"],
        location_name="誠品生活日本橋 誠品生活市集",
        location_name_zh="誠品生活日本橋 誠品生活市集",
        location_name_en="Eslite Spectrum Nihonbashi Market",
        business_hours="実施日：7/18・19・20・25・26 10:00～19:00（試食 11:30～16:00、限定販売 7/25・26 11:30～16:00）",
        business_hours_zh="活動日：7/18・19・20・25・26 10:00～19:00（試吃 11:30～16:00，限定販售 7/25・26 11:30～16:00）",
        business_hours_en="Jul 18, 19, 20, 25 and 26, 10:00 AM–7:00 PM (tasting 11:30 AM–4:00 PM; sales Jul 25–26 11:30 AM–4:00 PM)",
        is_paid=False,
        price_info="無料試食あり。三角くじは食料品購入者対象。限定販売は1本500円(税込)",
        reason_ja="台湾の定番食品を試食・購入できる公式キャンペーンです。",
        reason_zh="這是可試吃與購買台灣經典食品的官方活動。",
        reason_en="This official campaign offers tastings and sales of a classic Taiwanese food.",
    ),
    _child(
        suffix=4,
        source_url=MAIN_URL,
        name_ja="アート＆シネマ抽選会",
        name_zh="藝術與電影抽獎會",
        name_en="Art and Cinema Prize Draw",
        description_ja="コレド室町テラス2Fで税込5,000円の買い物ごとに1回参加できる、ハズレなしの抽選会です。映画鑑賞券、美術展招待券、夏のセレクトアイテムなどが当たります。",
        description_zh="於COREDO室町TERRACE 2樓每消費滿5,000日圓（含稅）可參加一次、人人有獎的抽獎活動。獎品包括電影票、美術展邀請券與夏季精選商品。",
        description_en="A guaranteed-win draw on COREDO Muromachi Terrace's 2F, with one entry for every JPY 5,000 spent. Prizes include cinema tickets, art exhibition invitations, and selected summer items.",
        raw_description="期間：8/8(土)～8/16(日) 各日12:00～19:00。2Fフロアで5,000円(税込)お買い上げごとに1回。期間中レシート合算可、1人最大5回。",
        start_date="2026-08-08T00:00:00+00:00",
        end_date="2026-08-16T00:00:00+00:00",
        category=["art", "competition"],
        event_form=["competition"],
        location_name="コレド室町テラス2F フロア",
        location_name_zh="COREDO室町TERRACE 2樓",
        location_name_en="COREDO Muromachi Terrace 2F",
        business_hours="12:00～19:00",
        business_hours_zh="12:00～19:00",
        business_hours_en="12:00 PM–7:00 PM",
        is_paid=True,
        price_info="税込5,000円の購入ごとに1回（期間中レシート合算可、1人最大5回）",
        reason_ja="公式サマー企画内の、独立した開催期間と参加条件を持つ抽選会です。",
        reason_zh="這是官方夏季企劃中具有獨立期間與參加條件的抽獎活動。",
        reason_en="This prize draw has its own dates and participation terms within the official summer program.",
    ),
    _child(
        suffix=5,
        source_url=MAIN_URL,
        name_ja="eslite welcome weekend! 誠品会員限定抽選会",
        name_zh="eslite welcome weekend! 誠品會員限定抽獎會",
        name_en="Eslite Welcome Weekend Members-Only Prize Draw",
        description_ja="誠品生活日本橋メンバーズ会員を対象に、2Fフロアで税込5,000円の買い物ごとに1回参加できる抽選会です。当日の会員申込みも対象です。",
        description_zh="誠品生活日本橋會員於2樓每消費滿5,000日圓（含稅）可參加一次抽獎，當日申辦會員亦可參加。",
        description_en="Eslite Spectrum Nihonbashi members receive one draw entry for every JPY 5,000 spent on the 2F. Same-day membership applications are eligible.",
        raw_description="期間：8/21(金)～8/23(日)。場所：誠品生活日本橋書籍レジ。会員限定、税込5,000円ごとに1回。当日会員申込み・フロア合算可、当日限り有効。",
        start_date="2026-08-21T00:00:00+00:00",
        end_date="2026-08-23T00:00:00+00:00",
        category=["retail", "competition"],
        event_form=["competition"],
        location_name="誠品生活日本橋 書籍レジ",
        location_name_zh="誠品生活日本橋 書籍櫃檯",
        location_name_en="Eslite Spectrum Nihonbashi Book Register",
        business_hours=None,
        business_hours_zh=None,
        business_hours_en=None,
        is_paid=True,
        price_info="誠品会員限定。税込5,000円の購入ごとに1回（当日入会・フロア合算可）",
        reason_ja="誠品生活日本橋の会員向けに独立した日程で行われる公式抽選会です。",
        reason_zh="這是誠品生活日本橋於獨立日期舉辦的會員限定官方抽獎活動。",
        reason_en="This is an official members-only draw held on separate dates by Eslite Spectrum Nihonbashi.",
    ),
    _child(
        suffix=6,
        source_url=COLLECTION_URL,
        name_ja="eslite Collection -夏日の奇幻旅程-",
        name_zh="eslite Collection -夏日奇幻旅程-",
        name_en="Eslite Collection - Summer's Fantastical Journey",
        description_ja="夏をテーマに、台湾茶のギフト、季節のメニュー、台湾仙草茶、香水、雑貨、鋳造ワークショップなどを紹介する商品・体験コレクションです。6,980円は王徳傅の台湾茶ギフト1商品の価格で、企画全体の料金ではありません。",
        description_zh="以夏季為主題，介紹台灣茶禮盒、季節限定餐點、台灣仙草茶、香水、雜貨與鑄造工作坊等商品及體驗。6,980日圓是王德傳台灣茶禮盒單一商品的價格，並非整體企劃費用。",
        description_en="A summer collection of products and experiences including a Taiwanese tea gift, seasonal food, Taiwanese grass-jelly tea, fragrance, goods, and a casting workshop. JPY 6,980 is the price of one Wang De Chuan tea gift, not admission to the overall program.",
        raw_description="王徳傅の金萱ウーロン茶と桂花プーアール茶ギフトセット6,980円(税込)を含む複数の商品・メニューと、metamate錫の鋳造ワークショップ（3,300円）を紹介。",
        start_date="2026-07-18T00:00:00+00:00",
        end_date="2026-08-31T00:00:00+00:00",
        category=["retail", "lifestyle_food"],
        event_form=["market"],
        location_name="誠品生活日本橋 各ショップ",
        location_name_zh="誠品生活日本橋 各店舖",
        location_name_en="Participating shops at Eslite Spectrum Nihonbashi",
        business_hours=None,
        business_hours_zh=None,
        business_hours_en=None,
        is_paid=False,
        price_info="入場無料。商品・メニュー・ワークショップは各項目ごとに料金が異なります",
        reason_ja="台湾ブランドの商品を含む、親企画内の商品・体験コレクションです。",
        reason_zh="這是母企劃中的商品與體驗集錦，包含台灣品牌商品。",
        reason_en="This product and experience collection within the parent program includes goods from Taiwanese brands.",
    ),
]


def _client():
    local_env = Path(__file__).with_name(".env")
    shared_env = Path(__file__).resolve().parents[2] / "scraper" / ".env"
    load_dotenv(local_env if local_env.exists() else shared_env, override=False)
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _event(sb, event_id: str) -> dict[str, Any]:
    return sb.table("events").select("*").eq("id", event_id).single().execute().data


def _locks(sb, event_id: str) -> dict[str, dict[str, Any]]:
    rows = sb.table("field_corrections").select("*").eq("event_id", event_id).execute().data or []
    return {row["field_name"]: row for row in rows}


def _assert_subset(label: str, actual: dict[str, Any], expected: dict[str, Any]) -> None:
    mismatches = [
        f"{field}: expected={value!r} actual={actual.get(field)!r}"
        for field, value in expected.items()
        if actual.get(field) != value
    ]
    if mismatches:
        raise RuntimeError(f"{label} drift:\n  " + "\n  ".join(mismatches))


def _preflight(sb) -> dict[str, Any]:
    rows = {
        "parent": _event(sb, PARENT_ID),
        "collection": _event(sb, COLLECTION_ID),
        "overview": _event(sb, OVERVIEW_SECONDARY_ID),
        "night_market": _event(sb, NIGHT_MARKET_ID),
    }
    _assert_subset("parent", rows["parent"], PARENT_EXPECTED)
    _assert_subset("collection", rows["collection"], COLLECTION_EXPECTED)
    _assert_subset("overview", rows["overview"], OVERVIEW_EXPECTED)
    _assert_subset("night_market", rows["night_market"], NIGHT_MARKET_EXPECTED)

    existing_children = (
        sb.table("events").select("id,source_id,name_ja").eq("parent_event_id", PARENT_ID).execute().data
        or []
    )
    if existing_children:
        raise RuntimeError(f"parent already has children: {existing_children}")

    child_source_ids = [row["source_id"] for row in NEW_CHILDREN]
    existing_sources = (
        sb.table("events")
        .select("id,source_name,source_id,parent_event_id")
        .eq("source_name", "eslite_spectrum")
        .in_("source_id", child_source_ids)
        .execute()
        .data
        or []
    )
    if existing_sources:
        raise RuntimeError(f"planned child source IDs already exist: {existing_sources}")

    target_fields = {
        PARENT_ID: set(PARENT_CHANGES),
        NIGHT_MARKET_ID: set(NIGHT_MARKET_CHANGES),
    }
    lock_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for event_id, fields in target_fields.items():
        lock_map = _locks(sb, event_id)
        lock_maps[event_id] = lock_map
        actual_target_locks = {field: lock_map[field] for field in fields if field in lock_map}
        expected_target_locks = EXPECTED_TARGET_LOCKS[event_id]
        if set(actual_target_locks) != set(expected_target_locks):
            raise RuntimeError(
                f"target FC field drift for {event_id}: "
                f"expected={sorted(expected_target_locks)} actual={sorted(actual_target_locks)}"
            )
        for field, (expected_id, expected_value) in expected_target_locks.items():
            actual = actual_target_locks[field]
            if actual.get("id") != expected_id or actual.get("corrected_value") != expected_value:
                raise RuntimeError(f"target FC row drift for {event_id}.{field}: {actual}")

    return {"rows": rows, "locks": lock_maps}


def _apply_field_changes(
    sb,
    *,
    event_id: str,
    before: dict[str, Any],
    changes: dict[str, Any],
    locks: dict[str, dict[str, Any]],
    reason: str,
) -> None:
    for field, new_value in changes.items():
        mode = "lock_empty" if new_value is None else "lock_clean"
        ok = unlock_and_write(
            sb,
            event_id=event_id,
            field_name=field,
            new_value=new_value,
            mode=mode,
            unlock_reason=reason,
            expected_fc=locks.get(field),
            expected_event_value=before.get(field),
        )
        if not ok:
            raise RuntimeError(f"field correction failed: {event_id}.{field}; stop and inspect audit")


def _insert_children(sb) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        {**row, "scraped_at": now, "annotated_at": now}
        for row in NEW_CHILDREN
    ]
    inserted = sb.table("events").insert(rows).execute().data or []
    if len(inserted) != len(rows):
        raise RuntimeError(f"child insert count mismatch: expected={len(rows)} actual={len(inserted)}")
    return inserted


def _apply_merge(sb, parent: dict[str, Any], collection: dict[str, Any]) -> None:
    fresh_parent = _event(sb, PARENT_ID)
    fresh_collection = _event(sb, COLLECTION_ID)
    if fresh_parent.get("secondary_source_urls") != [MAIN_URL]:
        raise RuntimeError("parent secondary_source_urls drifted before merge")
    if fresh_collection.get("is_active") is not True or fresh_collection.get("merged_into_event_id") is not None:
        raise RuntimeError("collection merge state drifted before merge")

    result = apply_targeted_merge(
        sb,
        fresh_parent,
        fresh_collection,
        reason=(
            "manual correction: eslite Collection is a child merchandise topic; "
            "6,980 JPY is one tea gift price, not umbrella admission"
        ),
        pass_id="admin_manual",
        primary_update={"secondary_source_urls": [MAIN_URL, COLLECTION_URL]},
        repair_children=True,
    )
    if not result.get("deactivated"):
        raise RuntimeError(f"collection merge was not applied: {result}")


def _verify(sb) -> list[dict[str, Any]]:
    parent = _event(sb, PARENT_ID)
    _assert_subset(
        "parent after",
        parent,
        {
            **PARENT_CHANGES,
            "secondary_source_urls": [MAIN_URL, COLLECTION_URL],
            "is_active": True,
            "merged_into_event_id": None,
        },
    )
    collection = _event(sb, COLLECTION_ID)
    _assert_subset(
        "collection after",
        collection,
        {"is_active": False, "merged_into_event_id": PARENT_ID, "deactivated_by_pass": "admin_manual"},
    )
    overview = _event(sb, OVERVIEW_SECONDARY_ID)
    _assert_subset("overview after", overview, OVERVIEW_EXPECTED)

    night_market = _event(sb, NIGHT_MARKET_ID)
    _assert_subset("night market after", night_market, NIGHT_MARKET_CHANGES)

    children = (
        sb.table("events")
        .select("id,source_id,name_ja,start_date,end_date,is_paid,price_info,parent_event_id,is_active,annotation_status")
        .eq("parent_event_id", PARENT_ID)
        .order("start_date")
        .order("source_id")
        .execute()
        .data
        or []
    )
    if len(children) != 7:
        raise RuntimeError(f"expected 7 direct children, found {len(children)}")
    if any(not row.get("is_active") or row.get("annotation_status") != "annotated" for row in children):
        raise RuntimeError(f"child publication state mismatch: {children}")

    expected_source_ids = {NIGHT_MARKET_EXPECTED["source_id"], *(row["source_id"] for row in NEW_CHILDREN)}
    actual_source_ids = {row["source_id"] for row in children}
    if actual_source_ids != expected_source_ids:
        raise RuntimeError(
            f"child source ID mismatch: expected={sorted(expected_source_ids)} actual={sorted(actual_source_ids)}"
        )

    for event_id, changes in ((PARENT_ID, PARENT_CHANGES), (NIGHT_MARKET_ID, NIGHT_MARKET_CHANGES)):
        lock_map = _locks(sb, event_id)
        for field, value in changes.items():
            expected_fc_value = "" if value is None else (
                json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value)
            )
            actual_fc_value = (lock_map.get(field) or {}).get("corrected_value")
            if actual_fc_value != expected_fc_value:
                raise RuntimeError(
                    f"FC verify failed {event_id}.{field}: expected={expected_fc_value!r} actual={actual_fc_value!r}"
                )
    return children


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    sb = _client()
    snapshot = _preflight(sb)
    manifest = {
        "parent_id": PARENT_ID,
        "collection_id": COLLECTION_ID,
        "night_market_id": NIGHT_MARKET_ID,
        "child_source_ids": [row["source_id"] for row in NEW_CHILDREN],
        "parent_changes": PARENT_CHANGES,
        "night_market_changes": NIGHT_MARKET_CHANGES,
    }
    digest = hashlib.sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()[:12]
    print(f"preflight PASS manifest={digest}")
    print("canonical parent:", PARENT_ID)
    print("planned direct children: 7 (1 repair + 6 inserts)")
    print("final merge redirect:", COLLECTION_ID, "->", PARENT_ID)

    if args.dry_run:
        print("DRY RUN: no writes")
        return 0

    _apply_field_changes(
        sb,
        event_id=PARENT_ID,
        before=snapshot["rows"]["parent"],
        changes=PARENT_CHANGES,
        locks=snapshot["locks"][PARENT_ID],
        reason=f"Eslite summer umbrella correction manifest={digest}",
    )
    _apply_field_changes(
        sb,
        event_id=NIGHT_MARKET_ID,
        before=snapshot["rows"]["night_market"],
        changes=NIGHT_MARKET_CHANGES,
        locks=snapshot["locks"][NIGHT_MARKET_ID],
        reason=f"Eslite summer child correction manifest={digest}",
    )
    inserted = _insert_children(sb)
    print(f"inserted children: {len(inserted)}")
    _apply_merge(
        sb,
        snapshot["rows"]["parent"],
        snapshot["rows"]["collection"],
    )

    children = _verify(sb)
    print("verification PASS")
    for child in children:
        print(f"  {child['name_ja']}: https://tokyotaiwanradar.com/ja/events/{child['id']}")
    print(f"  canonical: https://tokyotaiwanradar.com/ja/events/{PARENT_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
