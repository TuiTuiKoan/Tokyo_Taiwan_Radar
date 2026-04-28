-- 022_line_subscribers.sql
-- LINE 公開訂閱者表
-- 儲存加好友的 LINE 用戶、語言偏好、分類偏好

CREATE TABLE IF NOT EXISTS line_subscribers (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  line_user_id         text NOT NULL UNIQUE,
  status               text NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active', 'blocked')),
  language_preference  text NOT NULL DEFAULT 'zh'
                         CHECK (language_preference IN ('zh', 'en', 'ja')),
  category_preferences text[] NOT NULL DEFAULT '{}',
  subscribed_at        timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE line_subscribers ENABLE ROW LEVEL SECURITY;
-- 僅 service_role 可存取，不開放前端
