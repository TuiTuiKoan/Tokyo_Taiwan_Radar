-- 023_source_scraper_config.sql
-- Adds scraper pipeline config columns to research_sources:
--   scraper_source_name : matches _scraper_key() output in main.py (e.g. "peatix")
--   scrape_times_per_day: preferred daily run count, 1–8 (default 1)
--   scrape_hours_jst    : preferred JST hours array (default [9] = 09:00 JST)
-- These columns power the admin UI immediate-rescrape and schedule features.

ALTER TABLE research_sources
  ADD COLUMN IF NOT EXISTS scraper_source_name  TEXT,
  ADD COLUMN IF NOT EXISTS scrape_times_per_day INT  NOT NULL DEFAULT 1
    CHECK (scrape_times_per_day BETWEEN 1 AND 8),
  ADD COLUMN IF NOT EXISTS scrape_hours_jst     INT[] NOT NULL DEFAULT '{9}';

-- Populate scraper_source_name for all currently-implemented sources.
-- Mapping: research_sources.id → _scraper_key() in scraper/main.py
UPDATE research_sources SET scraper_source_name = 'iwafu'                  WHERE id = 4;
UPDATE research_sources SET scraper_source_name = 'tokyo_city_i'           WHERE id = 5;
UPDATE research_sources SET scraper_source_name = 'arukikata'              WHERE id = 6;
UPDATE research_sources SET scraper_source_name = 'taiwan_kyokai'          WHERE id = 7;
UPDATE research_sources SET scraper_source_name = 'koryu'                  WHERE id = 8;
UPDATE research_sources SET scraper_source_name = 'taiwan_festival_tokyo'  WHERE id = 9;
UPDATE research_sources SET scraper_source_name = 'ide_jetro'              WHERE id = 10;
UPDATE research_sources SET scraper_source_name = 'taiwan_cultural_center' WHERE id = 13;
UPDATE research_sources SET scraper_source_name = 'peatix'                 WHERE id = 14;
UPDATE research_sources SET scraper_source_name = 'eplus'                  WHERE id = 17;
UPDATE research_sources SET scraper_source_name = 'taioan_dokyokai'        WHERE id = 18;
UPDATE research_sources SET scraper_source_name = 'doorkeeper'             WHERE id = 19;
UPDATE research_sources SET scraper_source_name = 'connpass'               WHERE id = 20;
UPDATE research_sources SET scraper_source_name = 'taiwan_matsuri'         WHERE id = 21;
UPDATE research_sources SET scraper_source_name = 'tokyo_now'              WHERE id = 23;
UPDATE research_sources SET scraper_source_name = 'ifi'                    WHERE id = 24;
UPDATE research_sources SET scraper_source_name = 'tuat_global'            WHERE id = 25;
UPDATE research_sources SET scraper_source_name = 'jinf'                   WHERE id = 26;
UPDATE research_sources SET scraper_source_name = 'zinbun_kyoto'           WHERE id = 27;
UPDATE research_sources SET scraper_source_name = 'jats'                   WHERE id = 28;
UPDATE research_sources SET scraper_source_name = 'waseda_taiwan'          WHERE id = 29;
UPDATE research_sources SET scraper_source_name = 'taiwanshi'              WHERE id = 30;
UPDATE research_sources SET scraper_source_name = 'tobunken'               WHERE id = 31;
UPDATE research_sources SET scraper_source_name = 'kokuchpro'              WHERE id = 32;
UPDATE research_sources SET scraper_source_name = 'ks_cinema'              WHERE id = 33;
UPDATE research_sources SET scraper_source_name = 'cinemart_shinjuku'      WHERE id = 34;
UPDATE research_sources SET scraper_source_name = 'human_trust_cinema'     WHERE id = 35;
UPDATE research_sources SET scraper_source_name = 'eurospace'              WHERE id = 36;
UPDATE research_sources SET scraper_source_name = 'uplink_cinema'          WHERE id = 38;
UPDATE research_sources SET scraper_source_name = 'cineswitch_ginza'       WHERE id = 41;
UPDATE research_sources SET scraper_source_name = 'kokuchpro'              WHERE id = 45;
UPDATE research_sources SET scraper_source_name = 'eslite_spectrum'        WHERE id = 46;
UPDATE research_sources SET scraper_source_name = 'peatix'                 WHERE id = 47;
UPDATE research_sources SET scraper_source_name = 'moon_romantic'          WHERE id = 48;
UPDATE research_sources SET scraper_source_name = 'tokyo_art_beat'         WHERE id = 49;
UPDATE research_sources SET scraper_source_name = 'shin_bungeiza'          WHERE id = 50;
UPDATE research_sources SET scraper_source_name = 'morc_asagaya'           WHERE id = 51;
UPDATE research_sources SET scraper_source_name = 'cine_marine'            WHERE id = 56;
UPDATE research_sources SET scraper_source_name = 'taiwan_faasai'          WHERE id = 57;
UPDATE research_sources SET scraper_source_name = 'ssff'                   WHERE id = 58;
UPDATE research_sources SET scraper_source_name = 'tokyo_filmex'           WHERE id = 59;
UPDATE research_sources SET scraper_source_name = 'eiga_com'               WHERE id = 70;
UPDATE research_sources SET scraper_source_name = 'yebizo'                 WHERE id = 76;
UPDATE research_sources SET scraper_source_name = 'note_creators'          WHERE id = 78;
UPDATE research_sources SET scraper_source_name = 'taipei_fukuoka'         WHERE id = 80;
UPDATE research_sources SET scraper_source_name = 'faam_fukuoka'           WHERE id = 81;
UPDATE research_sources SET scraper_source_name = 'oaff'                   WHERE id = 86;
UPDATE research_sources SET scraper_source_name = 'jposa_ja'               WHERE id = 87;
UPDATE research_sources SET scraper_source_name = 'taiwanbunkasai'         WHERE id = 91;
UPDATE research_sources SET scraper_source_name = 'gguide_tv'              WHERE id = 95;
