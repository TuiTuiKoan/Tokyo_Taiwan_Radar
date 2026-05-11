// Source registry — manually curated metadata for the public /sources page.
// Source-of-truth for the scraper list lives in scraper/main.py SCRAPERS.
// Keep names lightweight; URLs link to each source's official site.
//
// Some entries use the source_id as a placeholder display name (TODO);
// translate or refine when the underlying source is verified.

export type SourceType =
  | "official"
  | "ticketing"
  | "cinema"
  | "academic"
  | "news"
  | "government"
  | "creator"
  | "other";

export interface SourceInfo {
  id: string;
  name: string;
  type: SourceType;
  frequency: "daily" | "weekly";
  officialUrl: string;
}

// Ordered loosely by visibility / strategic importance.
export const SOURCES: SourceInfo[] = [
  // ── Government & cultural institutions ──
  { id: "taiwan_cultural_center", name: "台湾文化センター", type: "government", frequency: "daily", officialUrl: "https://jp.taiwan.culture.tw/" },
  { id: "koryu", name: "公益財団法人 日本台湾交流協会", type: "government", frequency: "daily", officialUrl: "https://www.koryu.or.jp/" },
  { id: "taipei_fukuoka", name: "台北駐福岡経済文化弁事処", type: "government", frequency: "daily", officialUrl: "https://www.roc-taiwan.org/jpfuk/" },
  { id: "taiwan_kyokai", name: "台湾協会", type: "government", frequency: "daily", officialUrl: "https://taiwankyokai.or.jp/" },
  { id: "taioan_dokyokai", name: "台湾同郷会", type: "government", frequency: "daily", officialUrl: "https://www.taioan.org/" },
  { id: "taiwanshi", name: "台湾史研究会", type: "academic", frequency: "daily", officialUrl: "https://taiwanshi.jp/" },

  // ── Ticketing platforms ──
  { id: "peatix", name: "Peatix", type: "ticketing", frequency: "daily", officialUrl: "https://peatix.com/" },
  { id: "doorkeeper", name: "Doorkeeper", type: "ticketing", frequency: "daily", officialUrl: "https://www.doorkeeper.jp/" },
  { id: "connpass", name: "connpass", type: "ticketing", frequency: "daily", officialUrl: "https://connpass.com/" },
  { id: "eplus", name: "イープラス", type: "ticketing", frequency: "daily", officialUrl: "https://eplus.jp/" },
  { id: "livepocket", name: "LivePocket", type: "ticketing", frequency: "daily", officialUrl: "https://t.livepocket.jp/" },
  { id: "kokuchpro", name: "こくちーずプロ", type: "ticketing", frequency: "daily", officialUrl: "https://www.kokuchpro.com/" },

  // ── Festivals / annual events ──
  { id: "taiwan_festa", name: "Taiwan Festa", type: "official", frequency: "weekly", officialUrl: "https://taiwanfesta.com/" },
  { id: "taiwan_festival_tokyo", name: "東京台湾祭", type: "official", frequency: "weekly", officialUrl: "https://taiwan-fes.com/" },
  { id: "taiwan_matsuri", name: "台湾祭", type: "official", frequency: "weekly", officialUrl: "https://taiwan-matsuri.com/" },
  { id: "taiwan_faasai", name: "Taiwan FAASAI", type: "official", frequency: "weekly", officialUrl: "https://www.taiwanfaasai.com/" },
  { id: "taiwan_prism", name: "Taiwan Prism", type: "official", frequency: "weekly", officialUrl: "https://taiwanprism.com/" },
  { id: "taiwanbunkasai", name: "台湾文化祭", type: "official", frequency: "weekly", officialUrl: "https://taiwanbunkasai.com/" },
  { id: "tiff", name: "東京国際映画祭", type: "official", frequency: "weekly", officialUrl: "https://2025.tiff-jp.net/" },
  { id: "tokyo_filmex", name: "Tokyo FILMeX", type: "official", frequency: "weekly", officialUrl: "https://filmex.jp/" },
  { id: "ssff", name: "Short Shorts Film Festival & Asia", type: "official", frequency: "weekly", officialUrl: "https://www.shortshorts.org/" },
  { id: "oaff", name: "大阪アジアン映画祭", type: "official", frequency: "weekly", officialUrl: "https://www.oaff.jp/" },
  { id: "yebizo", name: "恵比寿映像祭", type: "official", frequency: "weekly", officialUrl: "https://www.yebizo.com/" },
  { id: "kgplus_kyotographie", name: "KYOTOGRAPHIE", type: "official", frequency: "weekly", officialUrl: "https://www.kyotographie.jp/" },

  // ── Academic / research ──
  { id: "waseda_taiwan", name: "早稲田大学台湾研究所", type: "academic", frequency: "daily", officialUrl: "https://www.waseda.jp/inst/wirfs/" },
  { id: "waseda_icl", name: "早稲田大学 ICL", type: "academic", frequency: "daily", officialUrl: "https://www.waseda.jp/" },
  { id: "tuat_global", name: "東京農工大学", type: "academic", frequency: "daily", officialUrl: "https://www.tuat.ac.jp/" },
  { id: "jats", name: "日本台湾学会 (JATS)", type: "academic", frequency: "daily", officialUrl: "http://jats.gr.jp/" },
  { id: "jinf", name: "国家基本問題研究所", type: "academic", frequency: "daily", officialUrl: "https://jinf.jp/" },
  { id: "ide_jetro", name: "アジア経済研究所", type: "academic", frequency: "daily", officialUrl: "https://www.ide.go.jp/" },
  { id: "tobunken", name: "東京文化財研究所", type: "academic", frequency: "daily", officialUrl: "https://www.tobunken.go.jp/" },
  { id: "zinbun_kyoto", name: "京都大学人文科学研究所", type: "academic", frequency: "daily", officialUrl: "https://www.zinbun.kyoto-u.ac.jp/" },
  { id: "kawasaki_ac", name: "川崎学術研究機関", type: "academic", frequency: "daily", officialUrl: "https://www.kawasaki-ac.jp/" },
  { id: "ifi", name: "国際交流基金", type: "academic", frequency: "daily", officialUrl: "https://www.jpf.go.jp/" },
  { id: "nittai_toumonkai", name: "日台同友会", type: "academic", frequency: "daily", officialUrl: "https://nittai-toumonkai.org/" },

  // ── Cinemas (independent / arthouse) ──
  { id: "ks_cinema", name: "K's cinema 新宿", type: "cinema", frequency: "daily", officialUrl: "https://www.ks-cinema.com/" },
  { id: "cinemart_shinjuku", name: "シネマート新宿", type: "cinema", frequency: "daily", officialUrl: "https://www.cinemart.co.jp/theater/shinjuku/" },
  { id: "cineswitch_ginza", name: "シネスイッチ銀座", type: "cinema", frequency: "daily", officialUrl: "http://www.cineswitch.com/" },
  { id: "human_trust_cinema", name: "ヒューマントラストシネマ", type: "cinema", frequency: "daily", officialUrl: "https://ttcg.jp/" },
  { id: "ttcg_kansai", name: "TTCG 関西", type: "cinema", frequency: "daily", officialUrl: "https://ttcg.jp/" },
  { id: "uplink_cinema", name: "アップリンク", type: "cinema", frequency: "daily", officialUrl: "https://joji.uplink.co.jp/" },
  { id: "shin_bungeiza", name: "新文芸坐", type: "cinema", frequency: "daily", officialUrl: "https://www.shin-bungeiza.com/" },
  { id: "eurospace", name: "ユーロスペース", type: "cinema", frequency: "daily", officialUrl: "http://www.eurospace.co.jp/" },
  { id: "stranger", name: "Stranger", type: "cinema", frequency: "daily", officialUrl: "https://stranger.jp/" },
  { id: "sakurazaka", name: "桜坂劇場", type: "cinema", frequency: "daily", officialUrl: "https://sakura-zaka.com/" },
  { id: "kbc_cinema", name: "KBC シネマ", type: "cinema", frequency: "daily", officialUrl: "https://kbc-cinema.net/" },
  { id: "kino_shinsaibashi", name: "シネ・リーブル心斎橋", type: "cinema", frequency: "daily", officialUrl: "https://ttcg.jp/" },
  { id: "kyoto_cinema", name: "京都シネマ", type: "cinema", frequency: "daily", officialUrl: "https://www.kyotocinema.jp/" },
  { id: "midland_cinema", name: "ミッドランドスクエアシネマ", type: "cinema", frequency: "daily", officialUrl: "https://midland-sq-cinema.jp/" },
  { id: "starcat_cinema", name: "シネマスコーレ", type: "cinema", frequency: "daily", officialUrl: "https://cinema-skhole.jp/" },
  { id: "cine_gallery", name: "シネ・ギャラリー", type: "cinema", frequency: "daily", officialUrl: "https://www.cine-gallery.jp/" },
  { id: "cinemarine", name: "シネマリン", type: "cinema", frequency: "daily", officialUrl: "https://www.cinemarine.co.jp/" },
  { id: "cinewind", name: "シネ・ウインド", type: "cinema", frequency: "daily", officialUrl: "http://www.cinewind.com/" },
  { id: "ycam_cinema", name: "YCAM 山口情報芸術センター", type: "cinema", frequency: "daily", officialUrl: "https://www.ycam.jp/" },
  { id: "amayaza", name: "雨宮座", type: "cinema", frequency: "daily", officialUrl: "https://www.amayaza.com/" },
  { id: "theater_kino", name: "シアターキノ", type: "cinema", frequency: "daily", officialUrl: "https://theaterkino.net/" },
  { id: "theater_enya", name: "シアターセンディアン", type: "cinema", frequency: "daily", officialUrl: "https://theaterenya.com/" },
  { id: "ftip", name: "FT inn", type: "cinema", frequency: "daily", officialUrl: "https://www.ft-inn.com/" },
  { id: "ciema", name: "シネマ", type: "cinema", frequency: "daily", officialUrl: "https://ciema.info/" },
  { id: "cineplaza", name: "シネプラザ", type: "cinema", frequency: "daily", officialUrl: "https://cineplaza.jp/" },
  { id: "internet_museum", name: "Internet Museum", type: "cinema", frequency: "daily", officialUrl: "https://museum.or.jp/" },
  { id: "onariza", name: "御成座", type: "cinema", frequency: "daily", officialUrl: "https://onariza.com/" },
  { id: "us_cinema_chiba", name: "USシネマ千葉ニュータウン劇場", type: "cinema", frequency: "daily", officialUrl: "https://www.uscinemas.jp/" },
  { id: "united_cinemas", name: "ユナイテッド・シネマ", type: "cinema", frequency: "daily", officialUrl: "https://www.unitedcinemas.jp/" },
  { id: "nagano_aioiza", name: "長野アイオイ座", type: "cinema", frequency: "daily", officialUrl: "http://www.aioiza.com/" },
  { id: "cinemadict", name: "Cinemadict", type: "cinema", frequency: "daily", officialUrl: "https://cinemadict.jp/" },

  // ── News / aggregators ──
  { id: "nhk_rss", name: "NHK ニュース RSS", type: "news", frequency: "daily", officialUrl: "https://www3.nhk.or.jp/" },
  { id: "google_news_rss", name: "Google ニュース RSS", type: "news", frequency: "daily", officialUrl: "https://news.google.com/" },
  { id: "prtimes", name: "PR TIMES", type: "news", frequency: "daily", officialUrl: "https://prtimes.jp/" },
  { id: "walkerplus", name: "Walker+", type: "news", frequency: "daily", officialUrl: "https://www.walkerplus.com/" },
  { id: "rti_jp", name: "RTI 日本語", type: "news", frequency: "daily", officialUrl: "https://jp.rti.org.tw/" },
  { id: "fukuoka_now", name: "Fukuoka Now", type: "news", frequency: "daily", officialUrl: "https://www.fukuoka-now.com/" },
  { id: "tokyonow", name: "Tokyo Now", type: "news", frequency: "daily", officialUrl: "https://tokyo-now.com/" },
  { id: "tokyocity_i", name: "東京シティアイ", type: "news", frequency: "daily", officialUrl: "https://www.tokyo-tourism.jp/" },
  { id: "tokyoartbeat", name: "Tokyo Art Beat", type: "news", frequency: "daily", officialUrl: "https://www.tokyoartbeat.com/" },
  { id: "tsutaya_portal", name: "TSUTAYA Portal", type: "news", frequency: "daily", officialUrl: "https://store-tsutaya.tsite.jp/" },
  { id: "iwafu", name: "巖風", type: "news", frequency: "daily", officialUrl: "https://www.iwafu.tw/" },
  { id: "arukikata", name: "地球の歩き方", type: "news", frequency: "daily", officialUrl: "https://www.arukikata.co.jp/" },
  { id: "go_taiwan", name: "Go Taiwan", type: "news", frequency: "daily", officialUrl: "https://www.go-taiwan.com/" },
  { id: "gguide_tv", name: "G ガイド TV", type: "news", frequency: "daily", officialUrl: "https://www.tvguide.or.jp/" },
  { id: "rightscube", name: "Rights Cube", type: "news", frequency: "daily", officialUrl: "https://rightscube.jp/" },
  { id: "jposa_ja", name: "日本Posa", type: "news", frequency: "daily", officialUrl: "https://www.jposa.jp/" },
  { id: "transit_store", name: "Transit Store", type: "news", frequency: "daily", officialUrl: "https://transit.ne.jp/" },

  // ── Cinemas / programmes — additional ──
  { id: "eiga_com", name: "映画.com", type: "news", frequency: "daily", officialUrl: "https://eiga.com/" },
  { id: "acros_fukuoka", name: "ACROS 福岡", type: "official", frequency: "daily", officialUrl: "https://www.acros.or.jp/" },
  { id: "faam_fukuoka", name: "福岡アジア美術館", type: "official", frequency: "daily", officialUrl: "https://faam.city.fukuoka.lg.jp/" },
  { id: "mot", name: "東京都現代美術館 (MOT)", type: "official", frequency: "daily", officialUrl: "https://www.mot-art-museum.jp/" },
  { id: "whitestone_gallery", name: "Whitestone Gallery", type: "official", frequency: "daily", officialUrl: "https://www.whitestone-gallery.com/" },
  { id: "eslite_spectrum", name: "誠品生活日本橋", type: "official", frequency: "daily", officialUrl: "https://www.eslitespectrum.jp/" },
  { id: "hankyu_umeda", name: "阪急うめだ本店", type: "official", frequency: "daily", officialUrl: "https://www.hankyu-dept.co.jp/honten/" },
  { id: "daimaru_matsuzakaya", name: "大丸松坂屋", type: "official", frequency: "daily", officialUrl: "https://www.daimaru-matsuzakaya.com/" },
  { id: "maruhiro", name: "マルヒロ", type: "official", frequency: "daily", officialUrl: "https://www.hasamiyaki.jp/" },
  { id: "moonromantic", name: "月見ル君想フ", type: "official", frequency: "daily", officialUrl: "https://www.moonromantic.com/" },
  { id: "bigromanticrecords", name: "Big Romantic Records", type: "official", frequency: "daily", officialUrl: "https://www.bigromanticrecords.com/" },
  { id: "morc_asagaya", name: "MORC 阿佐ヶ谷", type: "official", frequency: "daily", officialUrl: "https://www.morc-asagaya.com/" },
  { id: "artistcafe", name: "Artist Cafe", type: "official", frequency: "daily", officialUrl: "https://www.artistcafe.jp/" },
  { id: "bookandbeer", name: "本屋ビール", type: "official", frequency: "daily", officialUrl: "https://www.bookandbeer.com/" },
  { id: "hakusuisha", name: "白水社", type: "official", frequency: "daily", officialUrl: "https://www.hakusuisha.co.jp/" },
  { id: "tsudoi_osaka", name: "大阪集い", type: "official", frequency: "daily", officialUrl: "https://www.tsudoi-osaka.jp/" },
  { id: "ginsee", name: "銀座シャラララ", type: "official", frequency: "daily", officialUrl: "https://www.ginsee.jp/" },
  { id: "startup_terrace", name: "Startup Terrace", type: "official", frequency: "daily", officialUrl: "https://startupterrace.jp/" },
  { id: "johakyu", name: "Johakyu", type: "official", frequency: "daily", officialUrl: "https://johakyu.com/" },
  { id: "otto", name: "OTTO Gallery", type: "official", frequency: "daily", officialUrl: "https://otto-gallery.com/" },

  // ── Creators / individual channels ──
  { id: "note_creators", name: "note クリエイター（手動キュレーション）", type: "creator", frequency: "daily", officialUrl: "https://note.com/" },
];
