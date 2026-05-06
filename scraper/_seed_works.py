"""One-off: seed works records for TV dramas and films."""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
from supabase import create_client

sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])

works_data = [
    {
        "work_type": "tv_drama",
        "original_title": "螺絲小姐要出嫁",
        "title_ja": "スクリュー・ガール\u3000一発逆転婚！！",
        "title_zh": "螺絲小姐要出嫁",
        "title_en": "Miss Rose",
        "country": "TW",
        "release_year": 2012,
    },
    {
        "work_type": "film",
        "original_title": "最親愛的陌生人",
        "title_ja": "Dear Stranger／ディア・ストレンジャー",
        "title_zh": "最親愛的陌生人",
        "title_en": "Dear Stranger",
        "country": "TW",
        "release_year": 2025,
        "cast_summary": "桂綸鎂",
    },
    {
        "work_type": "tv_drama",
        "original_title": "但願人長久",
        "title_ja": "テレサ・テン 歌姫を愛した人々",
        "title_zh": "但願人長久",
        "title_en": None,
        "country": "TW",
        "release_year": 2024,
        "cast_summary": "陳妍希、何潤東",
    },
    {
        "work_type": "film",
        "original_title": "一秒之前的他",
        "title_ja": "1秒先の彼",
        "title_zh": "一秒之前的他（改編自台灣電影《消失的情人節》）",
        "title_en": "One Second Ahead of Him",
        "country": "JP",
        "release_year": 2023,
        "cast_summary": "岡田將生、清原果耶",
    },
    {
        "work_type": "film",
        "original_title": "那年夏天，我們喜歡的素娜",
        "title_ja": "あの夏、僕たちが好きだったソナへ",
        "title_zh": "那年夏天，我們喜歡的素娜（改編自台灣電影《那些年，我們一起追的女孩》）",
        "title_en": "That Summer We Loved Sona",
        "country": "KR",
        "release_year": 2025,
        "cast_summary": "朴珍榮、金多賢",
    },
    {
        "work_type": "film",
        "original_title": "新精武門",
        "title_ja": "レッド・ドラゴン／新・怒りの鉄拳",
        "title_zh": "新精武門",
        "title_en": "New Fist of Fury",
        "country": "HK",
        "release_year": 1976,
        "cast_summary": "成龍",
    },
]

print("=== Seeding works records ===")
for w in works_data:
    try:
        sb.table('works').upsert(w, on_conflict='original_title').execute()
        print(f"  ✓ {w['original_title']}")
    except Exception as e:
        print(f"  ✗ {w['original_title']}: {e}")

# Verify
result = sb.table('works').select('id,work_type,original_title,title_ja,title_zh,country').in_(
    'original_title', [w['original_title'] for w in works_data]
).execute()
print(f"\nVerified {len(result.data)} works in DB:")
works_by_ja = {}
for r in result.data:
    print(f"  {r['work_type']:10} | {r['original_title'][:25]:25} | ja: {(r.get('title_ja') or '')[:35]} | {r.get('country','?')}")
    if r.get('title_ja'):
        works_by_ja[r['title_ja']] = r

# Link existing gguide_tv events to their works
print("\n=== Linking gguide_tv events to works ===")
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sources'))
from gguide_tv import _extract_show_title

events = sb.table('events').select('id,name_ja').eq('source_name', 'gguide_tv').eq('is_active', True).execute()
linked = 0
for evt in events.data:
    show = _extract_show_title(evt['name_ja'])
    work = works_by_ja.get(show)
    if not work:
        for ja, w in works_by_ja.items():
            if ja in evt['name_ja'] or evt['name_ja'].startswith(ja):
                work = w
                break
    if work:
        sb.table('events').update({'work_id': work['id']}).eq('id', evt['id']).execute()
        linked += 1
        print(f"  Linked {evt['id'][:8]} → {work['original_title']}")
print(f"\nLinked {linked} events to works")
