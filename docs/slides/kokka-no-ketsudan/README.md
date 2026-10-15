# 『国家の決断』読書会シリーズ (1) — 社群動畫與圖卡

《國家的決斷》（張國城 著）讀書會系列第 1 回的 Instagram / X 宣傳素材。
風格：手繪抖動線條（boiling line）＋ 專案 design system 色票（蓮霧紅 `#E84860`、抹茶深綠 `#1F5E2B`、亮綠 `#C4E86F`、紙色 `#FFFDF5`、抹茶白 `#F7FFE8`、腮紅 `#FFF1EE`）。

## 產出（`renders/`）

| 檔案 | 尺寸 | 用途 |
| --- | --- | --- |
| `kokka-no-ketsudan-01-feed.mp4` | 1080×1350（4:5），約 1 分 54 秒，30fps | IG 動態、X 貼文 |
| `kokka-no-ketsudan-01-story.mp4` | 1080×1920（9:16） | IG Reels / Stories（上下色帶避開 UI 遮擋） |
| `card-01.png` … `card-10.png` | 1080×1350 | IG 輪播 10 張靜態圖卡 |
| `story-01.png` … `story-10.png` | 1080×1920 | 限動用靜態版 |

影片內含無聲音軌（IG 上傳後可直接選用 App 內的音樂）。

## 預覽與重新算圖

```bash
# 預覽：直接用瀏覽器開 index.html（空白鍵暫停、←/→ 換頁、點擊畫面暫停）
#   index.html?static=3     第 3 張靜態卡
#   index.html?fmt=story    9:16 版

node render.js cards                 # 10 張 4:5 PNG
node render.js cards --fmt story     # 10 張 9:16 PNG
node render.js video                 # 4:5 MP4
node render.js video --fmt story     # 9:16 MP4
node render.js video --from 0 --to 10 --out test.mp4   # 只算片段
```

需要 Playwright（Chromium）與 ffmpeg。每秒約算 5–6 格，整支影片約 10 分鐘。

## 書封

目前 p.2 的書封是**手繪示意圖**（算圖環境無法連線 Amazon）。
把真實書封存成 `assets/cover.jpg`（建議直式約 600×900）後重新執行 `render.js`，會自動換成真封面並保留膠帶裝飾。

## QR code

`assets/qr.js` 由 `node make_qr.js` 產生，內容為 `https://www.amazon.co.jp/dp/B07ZPLQT14`（與原始長網址指向同一商品頁）。
發布前請用手機實際掃描確認一次。

## 字型

- 日文：優先 `Zen Maru Gothic`（本機有安裝時使用），否則退回 IPA P Gothic。
- 手寫英文：Nothing You Could Do；數字：Erica One（皆為 OFL，授權檔在 `assets/`）。

## 文字校正（相對原稿）

- 「一向的な思惑」→「一方的な思惑」
- 「10つの視点」→「10の視点」
- 「捲き込まれない」→「巻き込まれない」
- 「南ベベトナム」→「南ベトナム」
- P.4 結論「外援（韓戦）…自衛の意志（越戦）」→ 改為「朝鮮戦争の教訓／ベトナム戦争の教訓」並列
- Jennifer 發言「冒冷汗（ゾッと）します」→「ゾッとします」
- 原稿兩個 Page 6 → 第二個視為 Page 7（日本で暮らし、働く私たちの気づき）
- P.3「安保は永続的な『善意の保障』ではありません」改成印章式強調句

## 貼文文案草稿

**Instagram**

```
「台湾有事」は対岸の火事か？🔥🌊

在日台湾人の視線から読み解く『国家の決断』（張国城 著）全10回シリーズ、スタートです📖

朝鮮戦争とベトナム戦争という「歴史の鏡」から、
同盟・自衛・そして私たちがすでに生きている「グレーゾーン（準有事）」を考えます。

💬 あなたは A・B・C どれに近いですか？コメント欄で教えてください！
📌 保存・シェアで、一緒にこれからの安全と日常を考えましょう。

#国家の決断 #台湾有事 #超限戦 #認知戦 #日台交流 #読書会 #台湾 #安全保障 #TokyoTaiwanRadar
```

**X**

```
「台湾有事」は対岸の火事か？🔥
在日台湾人の視線で『国家の決断』（張国城 著）を読み解く全10回シリーズ、第1回。
朝鮮戦争・ベトナム戦争の教訓から「同盟」と「自衛の意志」を考えます。
あなたはA/B/Cどれ？👇
#国家の決断 #台湾有事 #日台
```
