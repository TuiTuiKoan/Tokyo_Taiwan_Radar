"""Seed authoritative venues into venues table with pre-flight conflict checks.

Usage:
  python scraper/_oneoff_seed_authoritative_venues.py --dry-run
  python scraper/_oneoff_seed_authoritative_venues.py
"""

from __future__ import annotations

import argparse
import os
import re
import unicodedata
from collections import Counter
from typing import Any

from dotenv import load_dotenv

from database import _get_client


SEED_DATA: list[dict[str, Any]] = [
    {
        "canonical_name_ja": "台北駐日経済文化代表処 台湾文化センター",
        "canonical_name_zh": "台北駐日經濟文化代表處 台灣文化中心",
        "canonical_name_en": "Taiwan Cultural Center, Taipei Economic and Cultural Representative Office in Japan",
        "address": "東京都港区虎ノ門1-1-12 虎ノ門ビル2階",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "港区",
        "aliases": [
            "台湾文化センター",
            "台北駐日経済文化代表処台湾文化センター",
            "台湾文化中心",
        ],
        "homepage": "https://www.taiwanembassy.org/jp_ja/post/84095.html",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "平日 10:00〜17:00 / 土日祝休館",
    },
    {
        "canonical_name_ja": "ユーロライブ",
        "canonical_name_zh": "ユーロライブ",
        "canonical_name_en": "Euro Live",
        "address": "東京都渋谷区円山町1-5 KINOHAUS 2F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "渋谷区",
        "aliases": ["EURO LIVE", "ユーロライブ（渋谷）"],
        "homepage": "https://eurolive.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "シネ・ヌーヴォ",
        "canonical_name_zh": "シネ・ヌーヴォ",
        "canonical_name_en": "Cine Nouveau",
        "address": "大阪府大阪市西区九条1-20-24",
        "prefecture": "大阪府",
        "prefectures": ["大阪府"],
        "city": "大阪市",
        "aliases": ["シネヌーヴォ", "CINE NOUVEAU"],
        "homepage": "https://www.cinenouveau.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "新文芸坐",
        "canonical_name_zh": "新文藝坐",
        "canonical_name_en": "Shin-Bungeiza",
        "address": "東京都豊島区東池袋1-43-5 マルハン池袋ビル3F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "豊島区",
        "aliases": ["しんぶんげいざ"],
        "homepage": "https://www.shin-bungeiza.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "京都シネマ",
        "canonical_name_zh": "京都電影院",
        "canonical_name_en": "Kyoto Cinema",
        "address": "京都府京都市下京区烏丸通四条下ル水銀屋町620 COCON KARASUMA 3F",
        "prefecture": "京都府",
        "prefectures": ["京都府"],
        "city": "京都市",
        "aliases": ["KYOTO CINEMA"],
        "homepage": "https://www.kyotocinema.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "福岡アジア美術館",
        "canonical_name_zh": "福岡亞洲美術館",
        "canonical_name_en": "Fukuoka Asian Art Museum",
        "address": "福岡県福岡市博多区下川端町3-1 リバレインセンタービル7F",
        "prefecture": "福岡県",
        "prefectures": ["福岡県"],
        "city": "福岡市",
        "aliases": ["FAAM"],
        "homepage": "https://faam.city.fukuoka.lg.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "9:30〜19:30（金・土は20:00まで）/ 水曜休館",
    },
    {
        "canonical_name_ja": "東京都写真美術館",
        "canonical_name_zh": "東京都寫真美術館",
        "canonical_name_en": "Tokyo Photographic Art Museum",
        "address": "東京都目黒区三田1-13-3 恵比寿ガーデンプレイス内",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "目黒区",
        "aliases": ["TOP Museum"],
        "homepage": "https://topmuseum.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "10:00〜18:00（木・金曜日は20:00まで）/ 月曜休館",
    },
    {
        "canonical_name_ja": "東京国際映画祭",
        "canonical_name_zh": "東京國際影展",
        "canonical_name_en": "Tokyo International Film Festival",
        "address": None,
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "千代田区",
        "aliases": ["TIFF", "東京国際映画祭2026"],
        "homepage": "https://2025.tiff-jp.net/",
        "is_authoritative": True,
        "is_multi_venue": True,
    },
    {
        "canonical_name_ja": "大阪アジアン映画祭",
        "canonical_name_zh": "大阪亞洲電影節",
        "canonical_name_en": "Osaka Asian Film Festival",
        "address": None,
        "prefecture": "大阪府",
        "prefectures": ["大阪府"],
        "city": "大阪市",
        "aliases": ["OAFF"],
        "homepage": "https://oaff.jp/",
        "is_authoritative": True,
        "is_multi_venue": True,
    },
    {
        "canonical_name_ja": "横浜国際舞台芸術ミーティング",
        "canonical_name_zh": "橫濱國際表演藝術會議",
        "canonical_name_en": "Yokohama International Performing Arts Meeting",
        "address": None,
        "prefecture": "神奈川県",
        "prefectures": ["神奈川県"],
        "city": "横浜市",
        "aliases": ["YPAM"],
        "homepage": "https://ypam.jp/",
        "is_authoritative": True,
        "is_multi_venue": True,
    },
    {
        "canonical_name_ja": "台灣國際紀錄片影展",
        "canonical_name_zh": "台灣國際紀錄片影展",
        "canonical_name_en": "Taiwan International Documentary Festival",
        "address": None,
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": None,
        "aliases": ["TIDF"],
        "homepage": "https://www.tidf.org.tw/",
        "is_authoritative": True,
        "is_multi_venue": True,
    },
    {
        "canonical_name_ja": "道の駅まえばし赤城",
        "canonical_name_zh": "前橋赤城道路休息站",
        "canonical_name_en": "Roadside Station Maebashi Akagi",
        "address": "群馬県前橋市田口町36番地",
        "prefecture": "群馬県",
        "prefectures": ["群馬県"],
        "city": "前橋市",
        "aliases": ["道の駅 まえばし赤城", "まえばし赤城"],
        "homepage": "https://maebashi-akagi.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "あまや座",
        "canonical_name_zh": "あまや座",
        "canonical_name_en": "Amayaza",
        "address": "茨城県那珂市瓜連1724-2",
        "prefecture": "茨城県",
        "prefectures": ["茨城県"],
        "city": "那珂市",
        "aliases": ["あまや座", "amayaza"],
        "homepage": "https://amaya-za.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "ミッドランドシネマ 名古屋空港",
        "canonical_name_zh": "中部名古屋機場米德蘭影城",
        "canonical_name_en": "Midland Cinema Nagoya Airport",
        "address": "愛知県西春日井郡豊山町豊場南長廻間1 エアポートウォーク名古屋2F",
        "prefecture": "愛知県",
        "prefectures": ["愛知県"],
        "city": "西春日井郡豊山町",
        "aliases": ["ミッドランドシネマ名古屋空港", "ミッドランドシネマ 名古屋空港"],
        "homepage": "https://www.midland-cinema.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "劇場オープン時間等、日によって異なります",
    },
    {
        "canonical_name_ja": "御成座",
        "canonical_name_zh": "御成座",
        "canonical_name_en": "Onariza",
        "address": "秋田県大館市御成町1丁目11-22",
        "prefecture": "秋田県",
        "prefectures": ["秋田県"],
        "city": "大館市",
        "aliases": ["御成座", "Onariza"],
        "homepage": "http://onariza.oodate.or.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "高田世界館",
        "canonical_name_zh": "高田世界館",
        "canonical_name_en": "Takada Sekaikan",
        "address": "新潟県上越市本町6丁目4-21",
        "prefecture": "新潟県",
        "prefectures": ["新潟県"],
        "city": "上越市",
        "aliases": ["高田世界館", "Takada Sekaikan"],
        "homepage": "https://shintomiza.whitesnow.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "八丁座",
        "canonical_name_zh": "八丁座",
        "canonical_name_en": "Hatchobori",
        "address": "広島県広島市中区胡町6-26 福屋八丁堀本店8F",
        "prefecture": "広島県",
        "prefectures": ["広島県"],
        "city": "広島市",
        "aliases": ["八丁座", "Hatchobori", "サロンシネマ", "サロンシネマ1・2"],
        "homepage": "https://johakyu.co.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "サロンシネマ",
        "canonical_name_zh": "沙龍影城",
        "canonical_name_en": "Salon Cinema",
        "address": "広島県広島市中区八丁堀16-10 タカタビル8F",
        "prefecture": "広島県",
        "prefectures": ["広島県"],
        "city": "広島市",
        "aliases": ["サロンシネマ", "サロンシネマ1・2", "Salon Cinema"],
        "homepage": "https://johakyu.co.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "109シネマズ港北",
        "canonical_name_zh": "109影城港北",
        "canonical_name_en": "109 Cinemas Kohoku",
        "address": "神奈川県横浜市都筑区中川中央1-31-1 ノースポート・モール6F",
        "prefecture": "神奈川県",
        "prefectures": ["神奈川県"],
        "city": "横浜市",
        "aliases": ["109シネマズ港北", "109 Cinemas Kohoku"],
        "homepage": "https://109cinemas.net/kohoku/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "109シネマズ富谷",
        "canonical_name_zh": "109影城富谷",
        "canonical_name_en": "109 Cinemas Tomiya",
        "address": "宮城県富谷市大清水1丁目33-1 イオンモール富谷 別棟",
        "prefecture": "宮城県",
        "prefectures": ["宮城県"],
        "city": "富谷市",
        "aliases": ["109シネマズ富谷", "109 Cinemas Tomiya"],
        "homepage": "https://109cinemas.net/tomiya/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "松本シネマセレクト",
        "canonical_name_zh": "松本電影選",
        "canonical_name_en": "Matsumoto Cinema Select",
        "address": "長野県松本市深志3-10-18",
        "prefecture": "長野県",
        "prefectures": ["長野県"],
        "city": "松本市",
        "aliases": ["松本シネマセレクト", "松本シネマセレクト（長野）", "ＮＰＯ松本シネマセレクト"],
        "homepage": "https://www.cinema-select.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "ユナイテッドシネマつくば",
        "canonical_name_zh": "United Cinemas 筑波",
        "canonical_name_en": "United Cinemas Tsukuba",
        "address": "茨城県つくば市小野崎字177-1 iiasつくば3F",
        "prefecture": "茨城県",
        "prefectures": ["茨城県"],
        "city": "つくば市",
        "aliases": ["ユナイテッド・シネマつくば", "ユナイテッドシネマ つくば", "united_cinemas_tsukuba"],
        "homepage": "https://www.unitedcinemas.jp/tsukuba/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "ユナイテッドシネマ豊橋",
        "canonical_name_zh": "United Cinemas 豐橋",
        "canonical_name_en": "United Cinemas Toyohashi",
        "address": "愛知県豊橋市藤沢町141 ホリデイ・スクエア内",
        "prefecture": "愛知県",
        "prefectures": ["愛知県"],
        "city": "豊橋市",
        "aliases": ["ユナイテッド・シネマ豊橋", "ユナイテッドシネマ 豊橋", "united_cinemas_toyohashi"],
        "homepage": "https://www.unitedcinemas.jp/toyohashi/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "ユナイテッドシネマ橿原",
        "canonical_name_zh": "United Cinemas 橿原",
        "canonical_name_en": "United Cinemas Kashihara",
        "address": "奈良県橿原市十市町1222-1 ツインゲート橿原内",
        "prefecture": "奈良県",
        "prefectures": ["奈良県"],
        "city": "橿原市",
        "aliases": ["ユナイテッド・シネマ橿原", "ユナイテッドシネマ 橿原", "united_cinemas_kashihara"],
        "homepage": "https://www.unitedcinemas.jp/kashihara/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "上田映劇",
        "canonical_name_zh": "上田映劇",
        "canonical_name_en": "Ueda Eigeki",
        "address": "長野県上田市中央2丁目12-30",
        "prefecture": "長野県",
        "prefectures": ["長野県"],
        "city": "上田市",
        "aliases": ["上田映劇", "uedaeigeki", "UEDA EIGEKI"],
        "homepage": "https://www.uedaeigeki.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "シエマ",
        "canonical_name_zh": "シエマ",
        "canonical_name_en": "CIEMA",
        "address": "佐賀県佐賀市松原2丁目14-16 セントラルプラザ3F",
        "prefecture": "佐賀県",
        "prefectures": ["佐賀県"],
        "city": "佐賀市",
        "aliases": ["シエマ", "ciema", "CIEMA"],
        "homepage": "http://ciema.info",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "OYAMA Cinema ROBLE",
        "canonical_name_zh": "OYAMA Cinema ROBLE",
        "canonical_name_en": "OYAMA Cinema ROBLE",
        "address": "栃木県小山市中央町3-7-1 ロブレ7F",
        "prefecture": "栃木県",
        "prefectures": ["栃木県"],
        "city": "小山市",
        "aliases": ["OYAMA Cinema ROBLE", "ロブレ", "ロブレ5"],
        "homepage": "https://www.ginsee.jp/roble/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "宇都宮ヒカリ座",
        "canonical_name_zh": "宇都宮ヒカリ座",
        "canonical_name_en": "Utsunomiya Hikariza",
        "address": "栃木県宇都宮市江野町7-13 プラザヒカリビル5F",
        "prefecture": "栃木県",
        "prefectures": ["栃木県"],
        "city": "宇都宮市",
        "aliases": ["宇都宮ヒカリ座", "ヒカリ座"],
        "homepage": "https://www.ginsee.jp/hikariza/",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "シネプラザサントムーン",
        "canonical_name_zh": "Cineplaza Suntomoon",
        "canonical_name_en": "Cineplaza Suntomoon",
        "address": "静岡県駿東郡清水町伏見52-1 サントムーン柿田川内",
        "prefecture": "静岡県",
        "prefectures": ["静岡県"],
        "city": "駿東郡清水町",
        "aliases": ["シネプラザサントムーン", "シネプラザ サントムーン"],
        "homepage": "https://cineplaza.net",
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": "上映スケジュールによる",
    },
    {
        "canonical_name_ja": "国立台湾科技大学",
        "canonical_name_zh": "國立台灣科技大學",
        "canonical_name_en": "National Taiwan University of Science and Technology",
        "address": "台北市大安区基隆路四段43号",
        "prefecture": "台北市",
        "prefectures": None,
        "city": "台北市",
        "aliases": ["国立台湾科技大学", "國立台灣科技大學", "臺灣科技大學", "Taiwan Tech", "NTUST"],
        "homepage": "https://www.ntust.edu.tw",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "誠品生活日本橋",
        "canonical_name_zh": "誠品生活日本橋",
        "canonical_name_en": "Eslite Spectrum Nihonbashi",
        "address": "中央区日本橋室町３丁目２−１ COREDO室町テラス 2F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "中央区",
        "aliases": ["誠品生活", "eslite spectrum nihonbashi", "誠品生活日本橋"],
        "homepage": "https://www.eslite.co.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "ユーロスペース",
        "canonical_name_zh": "Eurospace",
        "canonical_name_en": "Eurospace",
        "address": "東京都渋谷区円山町1-5 KINOHAUS 3F・4F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "渋谷区",
        "aliases": ["EUROSPACE", "ユーロスペース（渋谷）", "ユーロスペース"],
        "homepage": "http://www.eurospace.co.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "K's cinema",
        "canonical_name_zh": "K's cinema",
        "canonical_name_en": "K's cinema",
        "address": "東京都新宿区新宿3丁目35-13 3F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "新宿区",
        "aliases": ["ケイズシネマ", "Ks cinema", "K's cinema"],
        "homepage": "https://www.ks-cinema.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "桜坂劇場",
        "canonical_name_zh": "櫻坂劇場",
        "canonical_name_en": "Sakurazaka Theater",
        "address": "沖縄県那覇市牧志3-6-10",
        "prefecture": "沖縄県",
        "prefectures": ["沖縄県"],
        "city": "那覇市",
        "aliases": ["さくらざかげきじょう", "Sakurazaka Theater", "桜坂劇場"],
        "homepage": "https://sakurazaka-theater.com/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "山口情報芸術センター YCAM",
        "canonical_name_zh": "山口情報藝術中心 YCAM",
        "canonical_name_en": "Yamaguchi Center for Arts and Media [YCAM]",
        "address": "山口県山口市中園町7-7",
        "prefecture": "山口県",
        "prefectures": ["山口県"],
        "city": "山口市",
        "aliases": ["YCAM", "山口情報芸術センター", "ycam_cinema"],
        "homepage": "https://www.ycam.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "紫明会館",
        "canonical_name_zh": "紫明會館",
        "canonical_name_en": "Shimei Kaikan",
        "address": "京都府京都市北区小山南大野町1",
        "prefecture": "京都府",
        "prefectures": ["京都府"],
        "city": "京都市",
        "aliases": ["紫明会館（京都）", "紫明会館"],
        "homepage": "https://shimeikaikan.org/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "シアター・イメージフォーラム",
        "canonical_name_zh": "Theater Image Forum",
        "canonical_name_en": "Theater Image Forum",
        "address": "東京都渋谷区渋谷2-10-2",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "渋谷区",
        "aliases": ["イメージフォーラム", "Image Forum", "シアター・イメージフォーラム"],
        "homepage": "http://www.imageforum.co.jp/theatre/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "東京芸術劇場",
        "canonical_name_zh": "東京藝術劇場",
        "canonical_name_en": "Tokyo Metropolitan Theatre",
        "address": "東京都豊島区西池袋1-8-1",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "豊島区",
        "aliases": ["東京芸術劇場（池袋）", "Geigeki", "東京芸術劇場"],
        "homepage": "https://www.geigeki.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "森美術館",
        "canonical_name_zh": "森美術館",
        "canonical_name_en": "Mori Art Museum",
        "address": "東京都港区六本木6-10-1 六本木ヒルズ森タワー53階",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "港区",
        "aliases": ["MAM", "森美術館"],
        "homepage": "https://www.mori.art.museum/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "東京都美術館",
        "canonical_name_zh": "東京都美術館",
        "canonical_name_en": "Tokyo Metropolitan Art Museum",
        "address": "東京都台東区上野公園8-36",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "台東区",
        "aliases": ["都美", "Tokyo Metropolitan Art Museum", "東京都美術館"],
        "homepage": "https://www.tobikan.jp/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "シネマート新宿",
        "canonical_name_zh": "シネマート新宿",
        "canonical_name_en": "Cinemart Shinjuku",
        "address": "東京都新宿区新宿3丁目13番3号 新宿文化ビル6F・7F",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "新宿区",
        "aliases": ["シネマート新宿", "cinemart shinjuku"],
        "homepage": "https://www.cinemart.co.jp/theater/shinjuku/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "シネスイッチ銀座",
        "canonical_name_zh": "シネスイッチ銀座",
        "canonical_name_en": "Cineswitch Ginza",
        "address": "東京都中央区銀座4-4-5 簱ビル",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "中央区",
        "aliases": ["シネスイッチ銀座", "Cineswitch Ginza"],
        "homepage": "https://cineswitch.com",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "ヒューマントラストシネマ有楽町",
        "canonical_name_zh": "ヒューマントラストシネマ有楽町",
        "canonical_name_en": "Human Trust Cinema Yurakucho",
        "address": "東京都千代田区有楽町1-5-1",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "千代田区",
        "aliases": ["ヒューマントラストシネマ有楽町", "human_yurakucho"],
        "homepage": "https://ttcg.jp/human_yurakucho/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "アップリンク吉祥寺",
        "canonical_name_zh": "アップリンク吉祥寺",
        "canonical_name_en": "Uplink Kichijoji",
        "address": "東京都武蔵野市吉祥寺本町1-5-1",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "武蔵野市",
        "aliases": ["アップリンク吉祥寺", "uplink joji"],
        "homepage": "https://joji.uplink.co.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "横浜シネマリン",
        "canonical_name_zh": "橫濱シネマリン",
        "canonical_name_en": "Yokohama Cinemarine",
        "address": "神奈川県横浜市中区花咲町1丁目1番地 横浜ニューテアトルビル",
        "prefecture": "神奈川県",
        "prefectures": ["神奈川県"],
        "city": "横浜市",
        "aliases": ["横浜シネマリン", "横濱シネマリン"],
        "homepage": "https://cinemarine.co.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "MORC阿佐ヶ谷",
        "canonical_name_zh": "MORC阿佐ヶ谷",
        "canonical_name_en": "MORC Asagaya",
        "address": "東京都杉並区阿佐谷北2-12-19",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "杉並区",
        "aliases": ["MORC阿佐ヶ谷", "モーク阿佐ヶ谷"],
        "homepage": "https://www.morc-asagaya.com",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "KBCシネマ1・2",
        "canonical_name_zh": "KBC影城1・2",
        "canonical_name_en": "KBC Cinema 1 & 2",
        "address": "福岡県福岡市中央区那の津1-3-21",
        "prefecture": "福岡県",
        "prefectures": ["福岡県"],
        "city": "福岡市",
        "aliases": ["KBCシネマ", "KBCシネマ1・2"],
        "homepage": "https://kbc-cinema.com",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "シアターキノ",
        "canonical_name_zh": "シアターキノ",
        "canonical_name_en": "Theater Kino",
        "address": "北海道札幌市中央区南3条西6丁目1番地 ゴトウビル地下2F",
        "prefecture": "北海道",
        "prefectures": ["北海道"],
        "city": "札幌市",
        "aliases": ["シアターキノ", "theater kino"],
        "homepage": "https://www.theaterekino.net",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "シネマ・クレール 丸の内1・2",
        "canonical_name_zh": "シネマ・クレール 丸の内1・2",
        "canonical_name_en": "Cinema Claire Marunouchi 1 & 2",
        "address": "岡山県岡山市北区丸の内1丁目5-1",
        "prefecture": "岡山県",
        "prefectures": ["岡山県"],
        "city": "岡山市",
        "aliases": ["シネマ・クレール", "シネマ・クレール 丸の内1・2"],
        "homepage": "http://www.cinemaclaire.com",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "長野相生座・ロキシー",
        "canonical_name_zh": "長野相生座・ロキシー",
        "canonical_name_en": "Nagano Aioiza Roxy",
        "address": "長野県長野市権堂町2255",
        "prefecture": "長野県",
        "prefectures": ["長野県"],
        "city": "長野市",
        "aliases": ["長野相生座・ロキシー", "長野相生座", "ロキシー"],
        "homepage": "https://www.aioiza.com",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "伏見ミリオン座",
        "canonical_name_zh": "伏見ミリオン座",
        "canonical_name_en": "Fushimi Millionza",
        "address": "愛知県名古屋市中区栄1-12-12",
        "prefecture": "愛知県",
        "prefectures": ["愛知県"],
        "city": "名古屋市",
        "aliases": ["伏見ミリオン座", "ミリオン座"],
        "homepage": "https://www.starcat.co.jp/cinema/million/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "センチュリーシネマ",
        "canonical_name_zh": "世紀影城",
        "canonical_name_en": "Century Cinema",
        "address": "愛知県名古屋市中区栄3-15-13 スカイルビル地下2F",
        "prefecture": "愛知県",
        "prefectures": ["愛知県"],
        "city": "名古屋市",
        "aliases": ["センチュリーシネマ"],
        "homepage": "https://www.starcat-ticket.com/cc/theater/century/schedule",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "静岡シネ・ギャラリー",
        "canonical_name_zh": "靜岡シネ・ギャラリー",
        "canonical_name_en": "Shizuoka Cine Gallery",
        "address": "静岡県静岡市葵区御幸町11-14 サールナートホール3階",
        "prefecture": "静岡県",
        "prefectures": ["静岡県"],
        "city": "静岡市",
        "aliases": ["静岡シネ・ギャラリー", "シネ・ギャラリー"],
        "homepage": "https://www.cine-gallery.jp",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "シネ・ウインド",
        "canonical_name_zh": "シネ・ウインド",
        "canonical_name_en": "Cine Wind",
        "address": "新潟県新潟市中央区八千代2-1-1 万代シテイ第2駐車場ビル1F",
        "prefecture": "新潟県",
        "prefectures": ["新潟県"],
        "city": "新潟市",
        "aliases": ["シネ・ウインド", "シネウインド", "新潟市民映画館"],
        "homepage": "https://www.cinewind.com",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "シアターエンヤ",
        "canonical_name_zh": "シアターエンヤ",
        "canonical_name_en": "Theater Enya",
        "address": "佐賀県唐津市呉服町1513-1",
        "prefecture": "佐賀県",
        "prefectures": ["佐賀県"],
        "city": "唐津市",
        "aliases": ["シアターエンヤ", "シアター・エンヤ"],
        "homepage": "https://theater-enya.com",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "テアトル梅田",
        "canonical_name_zh": "テアトル梅田",
        "canonical_name_en": "Theatre Umeda",
        "address": "大阪府大阪市北区角田町2-1 梅田ロフト7F",
        "prefecture": "大阪府",
        "prefectures": ["大阪府"],
        "city": "大阪市",
        "aliases": ["テアトル梅田"],
        "homepage": "https://ttcg.jp/ttcg_umeda/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
    {
        "canonical_name_ja": "シネ・リーブル神戸",
        "canonical_name_zh": "シネ・リーブル神戸",
        "canonical_name_en": "Cine Libre Kobe",
        "address": "兵庫県神戸市中央区小野柄通7-1-1 神戸阪急ビル東館8F",
        "prefecture": "兵庫県",
        "prefectures": ["兵庫県"],
        "city": "神戸市",
        "aliases": ["シネ・リーブル神戸", "シネリーブル神戸"],
        "homepage": "https://ttcg.jp/cinelibre_kobe/",
        "is_authoritative": True,
        "is_multi_venue": False,
    },
]

_AUTHORITY_COLUMNS = (
    "is_authoritative",
    "is_multi_venue",
    "homepage",
    "prefectures",
)


def _distinct_non_empty(values: list[str | None]) -> list[str]:
    return sorted({(v or "").strip() for v in values if (v or "").strip()})


# ── Address normalisation helpers ────────────────────────────────────────────

_STREET_NUM_RE = re.compile(r"\d+(?:-\d+)+")


def _normalize_addr(addr: str) -> str:
    """NFKC-normalise (collapses full-width spaces/digits) and strip."""
    a = unicodedata.normalize("NFKC", addr or "")
    return a.replace("−", "-").strip()


def _street_prefix(addr: str) -> str:
    """Return the address truncated at the end of the street number (番地),
    discarding building name / floor details.

    Examples:
      '東京都港区虎ノ門1-1-12 虎ノ門ビル2階'  →  '東京都港区虎ノ門1-1-12'
      '福岡県福岡市博多区下川端町3-1 リバレイン7F・8F'  →  '福岡県福岡市博多区下川端町3-1'
    """
    a = _normalize_addr(addr)
    m = _STREET_NUM_RE.search(a)
    return a[: m.end()].strip() if m else a


def _addresses_compatible(a: str, b: str) -> bool:
    """Return True when *a* and *b* describe the same physical location.

    Handles:
    - Full-width characters (\u3000, ２, etc.) via NFKC normalisation
    - Missing prefecture prefix (e.g. '港区虎ノ門1-1-12' vs '東京都港区虎ノ門1-1-12')
    - Differing building/floor detail (shorter = less detail is OK)
    - 7F vs 7F・8F (both truncated to same street prefix)
    """
    pa, pb = _street_prefix(a), _street_prefix(b)
    if not pa or not pb:
        return _normalize_addr(a) == _normalize_addr(b)
    # Exact street match, or one is a suffix of the other (missing prefecture prefix)
    return pa == pb or pa.endswith(pb) or pb.endswith(pa)


def _merge_aliases(existing: list[str] | None, incoming: list[str] | None, canonical: str) -> list[str]:
    merged = {(a or "").strip() for a in (existing or []) + (incoming or []) if (a or "").strip()}
    merged.discard(canonical)
    return sorted(merged)


def _get_event_rows_for_seed(sb, row: dict[str, Any]) -> list[dict[str, Any]]:
    names = [row["canonical_name_ja"]] + (row.get("aliases") or [])
    name_rows = (
        sb.table("events")
        .select("id,location_name,location_address,is_active")
        .in_("location_name", names)
        .execute()
        .data
        or []
    )
    return name_rows


def _has_conflict(seed_row: dict[str, Any], event_rows: list[dict[str, Any]]) -> tuple[bool, list[str], list[str]]:
    seed_address = (seed_row.get("address") or "").strip()
    # Only consider active events — inactive gnews/secondhand events often carry stale addresses
    active_rows = [r for r in event_rows if r.get("is_active", True)]
    db_addresses = _distinct_non_empty([r.get("location_address") for r in active_rows])
    if not db_addresses:
        return False, db_addresses, []
    if not seed_address:
        return False, db_addresses, []
    # Use street-level normalised comparison instead of exact string match
    conflicts = [a for a in db_addresses if not _addresses_compatible(a, seed_address)]
    return len(conflicts) > 0, db_addresses, conflicts


def _is_missing_authority_column_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return ("column" in msg or "schema cache" in msg) and "venues" in msg and any(c in msg for c in _AUTHORITY_COLUMNS)


def _assert_authority_columns_ready(sb) -> None:
    try:
        (
            sb.table("venues")
            .select("is_authoritative,is_multi_venue,homepage,prefectures")
            .limit(1)
            .execute()
        )
    except Exception as exc:
        if not _is_missing_authority_column_error(exc):
            raise
        print(
            "[ERROR] venues authority migration 未套用：缺少欄位 "
            "is_authoritative/is_multi_venue/homepage/prefectures。"
        )
        print("[ERROR] 請先套用 supabase/migrations/076_venues_authority.sql 後再重跑。")
        raise SystemExit(2)


def run(dry_run: bool) -> None:
    sb = _get_client()
    _assert_authority_columns_ready(sb)
    stats = Counter(insert=0, update=0, skip=0, conflict=0)

    skip_keys: set[str] = set()
    for row in SEED_DATA:
        matches = _get_event_rows_for_seed(sb, row)
        has_conflict, db_addresses, conflicts = _has_conflict(row, matches)
        if not has_conflict:
            continue
        stats["conflict"] += 1
        stats["skip"] += 1
        skip_keys.add(row["canonical_name_ja"])
        example_ids = [m["id"][:8] for m in matches if (m.get("location_address") or "").strip() in conflicts][:5]
        print(
            "[WARN conflict]",
            row["canonical_name_ja"],
            "seed=",
            row.get("address"),
            "db=",
            db_addresses,
            "event_ids=",
            example_ids,
        )

    for row in SEED_DATA:
        canonical = row["canonical_name_ja"]
        if canonical in skip_keys:
            print(f"[SKIP] {canonical} (pre-flight conflict)")
            continue

        existing = (
            sb.table("venues")
            .select("id,aliases")
            .eq("canonical_name_ja", canonical)
            .limit(1)
            .execute()
            .data
            or []
        )

        payload = dict(row)
        payload["aliases"] = _merge_aliases(
            existing[0].get("aliases") if existing else None,
            payload.get("aliases") or [],
            canonical,
        )

        action = "update" if existing else "insert"
        stats[action] += 1

        if dry_run:
            print(f"[DRY-RUN {action}] {canonical} aliases={len(payload['aliases'])}")
            continue

        sb.table("venues").upsert(payload, on_conflict="canonical_name_ja").execute()
        print(f"[APPLY {action}] {canonical}")

    mode = "DRY-RUN" if dry_run else "APPLY"
    print(
        f"[{mode}] done | insert={stats['insert']} update={stats['update']} "
        f"skip={stats['skip']} conflict={stats['conflict']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed authoritative venues with conflict-safe pre-flight check")
    parser.add_argument("--dry-run", action="store_true", help="Show planned writes without DB mutation")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run(args.dry_run)


if __name__ == "__main__":
    main()
