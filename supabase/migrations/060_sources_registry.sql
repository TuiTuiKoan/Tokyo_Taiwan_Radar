-- ============================================================
-- 060: sources registry table
-- Migrates web/lib/sources.ts SOURCES array to DB.
-- Public read via RLS USING (true). Writes via service_role.
-- Admin must run in Supabase Dashboard → SQL Editor
-- ============================================================

CREATE TABLE IF NOT EXISTS sources (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  type        TEXT NOT NULL CHECK (type IN ('government','official','ticketing','cinema','academic','news','creator','other')),
  frequency   TEXT NOT NULL DEFAULT 'daily' CHECK (frequency IN ('daily','weekly')),
  official_url TEXT NOT NULL,
  sort_order  INT NOT NULL DEFAULT 0,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sources_type_sort ON sources(type, sort_order) WHERE is_active = TRUE;

ALTER TABLE sources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sources_read ON sources;
CREATE POLICY sources_read ON sources FOR SELECT USING (true);

DROP TRIGGER IF EXISTS sources_updated_at ON sources;
CREATE TRIGGER sources_updated_at BEFORE UPDATE ON sources
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

GRANT SELECT ON sources TO anon, authenticated;

INSERT INTO sources (id, name, type, frequency, official_url, sort_order) VALUES
('taiwan_cultural_center','台湾文化センター','government','daily','https://jp.taiwan.culture.tw/', 10),
('koryu','公益財団法人 日本台湾交流協会','government','daily','https://www.koryu.or.jp/', 20),
('taipei_fukuoka','台北駐福岡経済文化弁事処','government','daily','https://www.roc-taiwan.org/jpfuk/', 30),
('taiwan_kyokai','台湾協会','government','daily','https://taiwankyokai.or.jp/', 40),
('taioan_dokyokai','台湾同郷会','government','daily','https://www.taioan.org/', 50),
('taiwanshi','台湾史研究会','academic','daily','https://taiwanshi.jp/', 60),
('peatix','Peatix','ticketing','daily','https://peatix.com/', 70),
('doorkeeper','Doorkeeper','ticketing','daily','https://www.doorkeeper.jp/', 80),
('connpass','connpass','ticketing','daily','https://connpass.com/', 90),
('eplus','イープラス','ticketing','daily','https://eplus.jp/', 100),
('livepocket','LivePocket','ticketing','daily','https://t.livepocket.jp/', 110),
('kokuchpro','こくちーずプロ','ticketing','daily','https://www.kokuchpro.com/', 120),
('taiwan_festa','Taiwan Festa','official','weekly','https://taiwanfesta.com/', 130),
('taiwan_festival_tokyo','東京台湾祭','official','weekly','https://taiwan-fes.com/', 140),
('taiwan_matsuri','台湾祭','official','weekly','https://taiwan-matsuri.com/', 150),
('taiwan_faasai','Taiwan FAASAI','official','weekly','https://www.taiwanfaasai.com/', 160),
('taiwan_prism','Taiwan Prism','official','weekly','https://taiwanprism.com/', 170),
('taiwanbunkasai','台湾文化祭','official','weekly','https://taiwanbunkasai.com/', 180),
('tiff','東京国際映画祭','official','weekly','https://2025.tiff-jp.net/', 190),
('tokyo_filmex','Tokyo FILMeX','official','weekly','https://filmex.jp/', 200),
('ssff','Short Shorts Film Festival & Asia','official','weekly','https://www.shortshorts.org/', 210),
('oaff','大阪アジアン映画祭','official','weekly','https://www.oaff.jp/', 220),
('yebizo','恵比寿映像祭','official','weekly','https://www.yebizo.com/', 230),
('kgplus_kyotographie','KYOTOGRAPHIE','official','weekly','https://www.kyotographie.jp/', 240),
('waseda_taiwan','早稲田大学台湾研究所','academic','daily','https://www.waseda.jp/inst/wirfs/', 250),
('waseda_icl','早稲田大学 ICL','academic','daily','https://www.waseda.jp/', 260),
('tuat_global','東京農工大学','academic','daily','https://www.tuat.ac.jp/', 270),
('jats','日本台湾学会 (JATS)','academic','daily','http://jats.gr.jp/', 280),
('jinf','国家基本問題研究所','academic','daily','https://jinf.jp/', 290),
('ide_jetro','アジア経済研究所','academic','daily','https://www.ide.go.jp/', 300),
('tobunken','東京文化財研究所','academic','daily','https://www.tobunken.go.jp/', 310),
('zinbun_kyoto','京都大学人文科学研究所','academic','daily','https://www.zinbun.kyoto-u.ac.jp/', 320),
('kawasaki_ac','川崎学術研究機関','academic','daily','https://www.kawasaki-ac.jp/', 330),
('ifi','国際交流基金','academic','daily','https://www.jpf.go.jp/', 340),
('nittai_toumonkai','日台同友会','academic','daily','https://nittai-toumonkai.org/', 350),
('ks_cinema','K''s cinema 新宿','cinema','daily','https://www.ks-cinema.com/', 360),
('cinemart_shinjuku','シネマート新宿','cinema','daily','https://www.cinemart.co.jp/theater/shinjuku/', 370),
('cineswitch_ginza','シネスイッチ銀座','cinema','daily','http://www.cineswitch.com/', 380),
('human_trust_cinema','ヒューマントラストシネマ','cinema','daily','https://ttcg.jp/', 390),
('ttcg_kansai','TTCG 関西','cinema','daily','https://ttcg.jp/', 400),
('uplink_cinema','アップリンク','cinema','daily','https://joji.uplink.co.jp/', 410),
('shin_bungeiza','新文芸坐','cinema','daily','https://www.shin-bungeiza.com/', 420),
('eurospace','ユーロスペース','cinema','daily','http://www.eurospace.co.jp/', 430),
('stranger','Stranger','cinema','daily','https://stranger.jp/', 440),
('sakurazaka','桜坂劇場','cinema','daily','https://sakura-zaka.com/', 450),
('kbc_cinema','KBC シネマ','cinema','daily','https://kbc-cinema.net/', 460),
('kino_shinsaibashi','シネ・リーブル心斎橋','cinema','daily','https://ttcg.jp/', 470),
('kyoto_cinema','京都シネマ','cinema','daily','https://www.kyotocinema.jp/', 480),
('midland_cinema','ミッドランドスクエアシネマ','cinema','daily','https://midland-sq-cinema.jp/', 490),
('starcat_cinema','シネマスコーレ','cinema','daily','https://cinema-skhole.jp/', 500),
('cine_gallery','シネ・ギャラリー','cinema','daily','https://www.cine-gallery.jp/', 510),
('cinemarine','シネマリン','cinema','daily','https://www.cinemarine.co.jp/', 520),
('cinewind','シネ・ウインド','cinema','daily','http://www.cinewind.com/', 530),
('ycam_cinema','YCAM 山口情報芸術センター','cinema','daily','https://www.ycam.jp/', 540),
('amayaza','雨宮座','cinema','daily','https://www.amayaza.com/', 550),
('theater_kino','シアターキノ','cinema','daily','https://theaterkino.net/', 560),
('theater_enya','シアターセンディアン','cinema','daily','https://theaterenya.com/', 570),
('ftip','FT inn','cinema','daily','https://www.ft-inn.com/', 580),
('ciema','シネマ','cinema','daily','https://ciema.info/', 590),
('cineplaza','シネプラザ','cinema','daily','https://cineplaza.jp/', 600),
('internet_museum','Internet Museum','cinema','daily','https://museum.or.jp/', 610),
('onariza','御成座','cinema','daily','https://onariza.com/', 620),
('us_cinema_chiba','USシネマ千葉ニュータウン劇場','cinema','daily','https://www.uscinemas.jp/', 630),
('united_cinemas','ユナイテッド・シネマ','cinema','daily','https://www.unitedcinemas.jp/', 640),
('nagano_aioiza','長野アイオイ座','cinema','daily','http://www.aioiza.com/', 650),
('cinemadict','Cinemadict','cinema','daily','https://cinemadict.jp/', 660),
('nhk_rss','NHK ニュース RSS','news','daily','https://www3.nhk.or.jp/', 670),
('google_news_rss','Google ニュース RSS','news','daily','https://news.google.com/', 680),
('prtimes','PR TIMES','news','daily','https://prtimes.jp/', 690),
('walkerplus','Walker+','news','daily','https://www.walkerplus.com/', 700),
('rti_jp','RTI 日本語','news','daily','https://jp.rti.org.tw/', 710),
('fukuoka_now','Fukuoka Now','news','daily','https://www.fukuoka-now.com/', 720),
('tokyonow','Tokyo Now','news','daily','https://tokyo-now.com/', 730),
('tokyocity_i','東京シティアイ','news','daily','https://www.tokyo-tourism.jp/', 740),
('tokyoartbeat','Tokyo Art Beat','news','daily','https://www.tokyoartbeat.com/', 750),
('tsutaya_portal','TSUTAYA Portal','news','daily','https://store-tsutaya.tsite.jp/', 760),
('iwafu','巖風','news','daily','https://www.iwafu.tw/', 770),
('arukikata','地球の歩き方','news','daily','https://www.arukikata.co.jp/', 780),
('go_taiwan','Go Taiwan','news','daily','https://www.go-taiwan.com/', 790),
('gguide_tv','G ガイド TV','news','daily','https://www.tvguide.or.jp/', 800),
('rightscube','Rights Cube','news','daily','https://rightscube.jp/', 810),
('jposa_ja','日本Posa','news','daily','https://www.jposa.jp/', 820),
('transit_store','Transit Store','news','daily','https://transit.ne.jp/', 830),
('eiga_com','映画.com','news','daily','https://eiga.com/', 840),
('acros_fukuoka','ACROS 福岡','official','daily','https://www.acros.or.jp/', 850),
('faam_fukuoka','福岡アジア美術館','official','daily','https://faam.city.fukuoka.lg.jp/', 860),
('mot','東京都現代美術館 (MOT)','official','daily','https://www.mot-art-museum.jp/', 870),
('whitestone_gallery','Whitestone Gallery','official','daily','https://www.whitestone-gallery.com/', 880),
('eslite_spectrum','誠品生活日本橋','official','daily','https://www.eslitespectrum.jp/', 890),
('hankyu_umeda','阪急うめだ本店','official','daily','https://www.hankyu-dept.co.jp/honten/', 900),
('daimaru_matsuzakaya','大丸松坂屋','official','daily','https://www.daimaru-matsuzakaya.com/', 910),
('maruhiro','マルヒロ','official','daily','https://www.hasamiyaki.jp/', 920),
('moonromantic','月見ル君想フ','official','daily','https://www.moonromantic.com/', 930),
('bigromanticrecords','Big Romantic Records','official','daily','https://www.bigromanticrecords.com/', 940),
('morc_asagaya','MORC 阿佐ヶ谷','official','daily','https://www.morc-asagaya.com/', 950),
('artistcafe','Artist Cafe','official','daily','https://www.artistcafe.jp/', 960),
('bookandbeer','本屋ビール','official','daily','https://www.bookandbeer.com/', 970),
('hakusuisha','白水社','official','daily','https://www.hakusuisha.co.jp/', 980),
('tsudoi_osaka','大阪集い','official','daily','https://www.tsudoi-osaka.jp/', 990),
('ginsee','銀座シャラララ','official','daily','https://www.ginsee.jp/', 1000),
('startup_terrace','Startup Terrace','official','daily','https://startupterrace.jp/', 1010),
('johakyu','Johakyu','official','daily','https://johakyu.com/', 1020),
('otto','OTTO Gallery','official','daily','https://otto-gallery.com/', 1030),
('note_creators','note クリエイター（手動キュレーション）','creator','daily','https://note.com/', 1040)
ON CONFLICT (id) DO UPDATE SET
  name         = EXCLUDED.name,
  type         = EXCLUDED.type,
  frequency    = EXCLUDED.frequency,
  official_url = EXCLUDED.official_url,
  sort_order   = EXCLUDED.sort_order,
  updated_at   = NOW();
