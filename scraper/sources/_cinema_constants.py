# ⚠️ 新增固定電影院 scraper 時，必須兩處同步更新：
#   1. main.py 的 SCRAPERS list（否則爬蟲不會被每日 CI 執行）
#   2. 下方 FIXED_CINEMA_SOURCES（否則 annotator 不會替該電影院的台灣片自動建 work）
# 呼應 SCRAPERS List Completeness Guard。
FIXED_CINEMA_SOURCES: frozenset[str] = frozenset({
    "kyoto_cinema",
    "ks_cinema",
    "shin_bungeiza",
    "cinemart_shinjuku",
    "eurospace",
    "cinemarine",
    "cineswitch_ginza",
    "human_trust_cinema",
    "morc_asagaya",
    "moonromantic",
    "uplink_cinema",
    # 補充實際在 main.py SCRAPERS 中的固定電影院 source_name
})
