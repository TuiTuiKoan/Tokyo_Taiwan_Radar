-- Add Japanese distributor fields to works table
-- distributor = company responsible for releasing the work in Japan (e.g. 株式会社ライツキューブ)
ALTER TABLE works ADD COLUMN IF NOT EXISTS distributor_ja TEXT;
ALTER TABLE works ADD COLUMN IF NOT EXISTS distributor_zh TEXT;
ALTER TABLE works ADD COLUMN IF NOT EXISTS distributor_en TEXT;
ALTER TABLE works ADD COLUMN IF NOT EXISTS distributor_url TEXT;

COMMENT ON COLUMN works.distributor_ja IS '日本での配給会社名（日本語）';
COMMENT ON COLUMN works.distributor_zh IS '配給会社名（繁體中文）';
COMMENT ON COLUMN works.distributor_en IS '配給会社名（English）';
COMMENT ON COLUMN works.distributor_url IS '配給会社の公式サイトまたは作品紹介ページ';
