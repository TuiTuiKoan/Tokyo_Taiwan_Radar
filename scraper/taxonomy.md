# TTR 活動分類定義（Category Taxonomy）

這個檔案是 annotator 分類定義的**單一來源**。`annotator.py` 在載入時讀取下方
`PROMPT:BEGIN` 與 `PROMPT:END` 之間的內容，接在「允許的分類清單」後面，組成 `SYSTEM_PROMPT`
的分類段落。修改分類定義只改這個檔案，不要再把定義寫回 `annotator.py`。

維護規則：

- 標記之間的內容會原樣送給模型，用英文撰寫，保留日文與中文關鍵詞。
- 每個分類都必須有一行 `- "<slug>" = …` 定義；`tests/test_taxonomy.py` 會檢查它與
  `VALID_CATEGORIES` 一致（不多不少）。
- 分類 slug 的權威清單仍是 `web/lib/types.ts`；新增分類請走 `/add-category` 流程，
  並在這裡補上定義。
- 修改後跑 `cd scraper && python -m pytest tests/test_taxonomy.py`。

<!-- PROMPT:BEGIN -->
   CATEGORY DEFINITIONS:
   - "movie" = film screenings, movie events, documentary showings, film festivals. IMPORTANT: any event with 上映, 映画, film, screening, cinema in its title or description MUST include "movie" as a category, even if it also involves talks or other elements.
   - "performing_arts" = LIVE stage performances ONLY: concerts, theater, dance, opera. NOT for film screenings. For Asia/Japan tour events (アジアツアー, 日本ツアー), only use if the Tokyo show is confirmed a live performance.
   - "senses" (台湾の感性・アイデンティティ) = NARROW, CONCEPT-LEVEL category. Use ONLY when the event or publication takes one of these concepts as its central subject of discussion:
       (a) Taiwanese identity as a concept — what it means to be Taiwanese, 台湾人意識 / アイデンティティ / 認同 discussed as an idea (symposiums, dialogues, essays). The POLITICAL HISTORY of identity formation is "history", not senses.
       (b) Taiwanese aesthetics and sensibility — 台湾美学, visual culture, design language, 感性 as a subject of discourse.
       (c) Locality / 地方性 / ローカリティ / 在地 — discourse on place, regionality, 地方創生 as culture (NOT tourism promotion).
       (d) Folk culture as a subject of study — 民俗, 常民文化, folk belief research and discussion.
       (e) Vernacular — 庶民建築, 鉄窓花, 看板, 市場, 街並み, everyday objects and street landscapes, discussed or documented as culture.
     Typical forms: symposiums, lectures, panels, books/publications, research exhibitions explicitly framed around the concepts above.
     NEVER use "senses" as a fallback or catch-all. Do NOT use it for: general art / photo / design exhibitions (→ art, photography, exhibition, design_craft); concerts, films, food, markets, tea, workshops or festivals merely because they feel "Taiwanese"; colonial / war / KMT / 湾生 / ethnic-political identity history (→ history); contemporary society, ethnic policy or elections (→ geopolitics).
   - "folklore" = folk customs and festivals as PRACTICE: temple events, 廟会, 祭典, 陣頭, folk religion rituals, seasonal observances (年中行事), traditional crafts rooted in folk traditions. A lecture or book that ANALYZES folk culture is "senses" (add folklore too only if the event also includes the practice itself).
   - "history" = the past of Taiwan, including political identity history:
       * Japanese colonial era (日本統治, 総督府, 植民地, 同化), WWII and war memory (戦没, 慰霊, 戦争, 戦前, 戦後)
       * postwar KMT rule, 二二八事件, White Terror (白色テロ), martial law (戒厳) — as historical experience
       * 湾生, 引揚者, family history, roots / origin
       * the historical formation of ethnic and political identities (本省人 / 外省人, the historical experience of indigenous peoples, Hakka migration)
       * cultural heritage, historic buildings, archives, museums, historical figures (李登輝, 蒋介石)
       * photo exhibitions of historical Taiwan; films/docs about colonial-era or war-era Taiwan (日本統治, 戦没者, 同化, 傷痕)
     ALSO MANDATORY when a featured author / artist / creator / performer is explicitly described as 台湾出身, 台湾生まれ, 台北市出身, Taiwan-born, or born in Taiwan. Do NOT use history merely because someone studied at a Taiwan university, studied abroad in Taiwan, or works in Taiwan. Keywords: 戦没, 植民地, 統治, 秘録, 同化, 傷痕, 歴史, 湾生, 国民党, 二二八, 白色テロ, 戒厳.
   - "geopolitics" (社会・政治・国際関係) = CONTEMPORARY Taiwan society and politics: current social and ethnic issues and policy, elections (総統選, 立法委員選挙, 地方選挙), parties, democratic institutions, cross-strait relations, Taiwan's international status / sovereignty, Taiwan Strait crisis, Japan-Taiwan national security strategy, government / public policy (移民政策, 給食政策, デジタル政府). Historical political experience belongs to "history"; add geopolitics as well only when the event ALSO discusses present-day politics. Trigger keywords: 危機, 海峡, 民主化, 移民政策, インド太平洋, 日台関係 (security/policy sense), 主権, 国際フォーラム, 選挙.
   - "human_rights" = human rights, democracy, civil liberties, judicial justice, transitional justice, political persecution memory, advocacy events. Use for events centered on rights discourse (言論自由, 司法正義, 轉型正義, 人權倡議).
   - "taiwan_japan" = Taiwan-Japan BILATERAL relations ONLY. Use for: formal diplomatic/exchange events; civil exchange and friendship events between Taiwan and Japan; Taiwanese diaspora in Japan (台湾系移住民); Taiwan veteran memorials (台湾出身戦没者); academic research on bilateral topics. DO NOT USE for: Taiwan food events, Taiwan concerts/tours, Taiwan children's books, Taiwan tourism promotion seminars, general Taiwan cultural events without explicit bilateral focus.
   - "indigenous" = events related to Taiwan's indigenous peoples (原住民族), tribal culture, indigenous arts or languages (アミ族, パイワン族, タイヤル族, etc.)
   - "art" = visual / fine art broadly: painting, sculpture, installation, contemporary art, illustration, manga art, art talks.
   - "exhibition" = museum exhibitions, gallery shows, permanent/special exhibitions at a specific venue with defined dates. Distinct from "art" (which covers visual art broadly).
   - "photography" = photograph exhibitions, photographer talks, photo workshops, photo books. Use for events where photography is the primary medium (e.g. 写真展, 写真家トーク, フォトワークショップ). Often co-occurs with art or exhibition; pair with history for archival/documentary photography of Taiwan.
   - "design_craft" = Taiwanese design, craft, handmade goods, product design, industrial design, traditional crafts (ceramics, weaving, lacquerware, metalwork, woodwork). Use for design exhibitions, craft markets, handmade workshops, product showcases. Distinct from "art" (fine art) and "folklore" (folk traditions, even if they include crafts).
   - "urban" = architecture, urban planning, まちづくり, public space, cityscape and built-environment events.
   - "books_media" = books, literature, publishing, authors, readings, book launch events, media, journalism. FORMULA: when title contains 著者名+『書名』 (author + book in 『』) OR ブックサロン/刊行記念/出版記念 → ALWAYS add books_media + lecture + academic. Then add geopolitics if contemporary political/policy content, history if historical content, senses if the book's subject is identity / aesthetics / locality / folk culture / vernacular as defined above, taiwan_japan ONLY if explicitly about Japan-Taiwan bilateral topic.
   - "literature" = literary events: poetry readings, literary salons, writer residencies, literary translation. Distinct from "books_media" (publishing/media industry)
   - "lecture" = talks, presentations, lectures, panels, Q&A sessions. MANDATORY when title/description contains any of: トークイベント, トークショー, 講演会, 講演, 講座, シンポジウム, 勉強会, 例会, 基調講演, 映後座談, セッション, 研究会. Also ALWAYS add lecture when movie + トーク/座談 co-occur.
   - "academic" = academic research, seminars, symposiums, papers, university events, scholarly conferences
   - "workshop" = hands-on workshops, experience classes, craft workshops, cooking classes, pottery, weaving, tea ceremony, atelier sessions (体験, ワークショップ, 手作り, クラフト)
   - "lifestyle_food" = food, cooking, tea ceremony, restaurants, cafes, lifestyle events. Do NOT add taiwan_japan just because the food is Taiwanese — use taiwan_japan only when the event emphasizes bilateral exchange.
   - "tea_alcohol" = tea culture, wine, sake, cocktail events, tasting events, tea ceremony workshops, bar/pub events featuring Taiwanese beverages
   - "herbal" = Taiwanese spices, herbs, herbal medicine, medicinal cuisine (薬膳/薬膵料理), Chinese herbal pharmacy, aromatherapy with Asian herbs, herbal tea workshops (distinct from tea_alcohol which focuses on tea ceremony/wine culture). Use for events about 中薬, 漢方, 薬膳, herbal cooking classes, spice tastings.
   - "market" = markets and pop-up sales events: マルシェ, 物産展, 夜市-style markets, POP UP stores, flea markets.
   - "retail" = brand launches, shops, product sales and shopping-oriented events.
   - "nature" = nature, climate, fruit and agriculture, ecology, sustainability / SDGs.
   - "tourism" = travel to Taiwan, tourism promotion, study tours and travel briefings.
   - "tech" = technology, IT, AI, semiconductors, startups with a technology focus.
   - "business" = business, investment, commerce, startups, corporate events, trade, entrepreneurship
   - "competition" = contests, competitions, awards, championships, sports events, public calls for entries (コンテスト, 大会, 選手権, 公募, コンクール)
   - "scholarship" = scholarships, grants, open calls, funding opportunities (NOT study-abroad programs — use study_abroad instead)
   - "study_abroad" = study abroad programs, exchange programs, overseas university application briefings, Taiwan-Japan cross-cultural study programs, international student exchange events
   - "taiwan_mandarin" = Mandarin/Taiwanese language learning events, Chinese language classes, language exchange
   - "gender" = gender, feminism, LGBTQ+, gender equality events.
   - "parenting" = parenting, childcare, family-oriented events, children's education, parent-child workshops
   - "healthcare" = health, medical, public health, wellness events
   - "tv_program" = TV broadcasts, television programs. MANDATORY for any event from a TV broadcast source (look for 放送: / ジャンル: markers in raw_description). A TV drama should have BOTH tv_program AND drama. A TV movie broadcast should have BOTH tv_program AND movie.
   - "radio_program" = radio broadcasts, radio programs, podcast-style radio content. MANDATORY for any event from a radio broadcast source (e.g. RTI / 中央廣播電台, NHK Radio, FM radio shows). Use radio_program instead of tv_program for radio-specific sources.
   - "drama" = serialized dramatic works: TV dramas, stage drama series, web dramas. For TV drama broadcasts, always pair with tv_program.
   - "documentary" = documentary films or TV documentary programs. For TV documentaries, pair with tv_program.
   - "report" = event reports/recaps (only if the text IS a report about a past event, not an upcoming event)

   DECISION ORDER for history / geopolitics / senses (apply in order; an event can still receive other content categories):
   1. Main topic is PRESENT-DAY politics, society, ethnic policy, elections or international relations → "geopolitics".
   2. Main topic is PAST political experience: colonial era, WWII, KMT rule, 228 / White Terror, 湾生, historical formation of ethnic or political identity → "history".
   3. Main topic is identity / aesthetics / locality / folk culture / vernacular discussed AS A CONCEPT → "senses".
   4. None of the above → choose content categories only (movie, art, lifestyle_food, …). Never add "senses" to fill a gap.

   BOUNDARY EXAMPLES:
   - 「台湾アイデンティティの形成：日本統治から解厳まで」講演 → ["history", "lecture"] (political identity history)
   - 「鉄窓花と台湾の街並みの美学」トーク → ["senses", "lecture", "urban"] (vernacular aesthetics)
   - 湾生をめぐるドキュメンタリー上映 → ["movie", "documentary", "history"]
   - 2028年台湾総統選挙の展望シンポジウム → ["geopolitics", "lecture", "academic"]
   - 台湾の廟宇・剪黏工芸展 → ["folklore", "design_craft", "exhibition"] (the craft itself; add senses only if framed as research on folk aesthetics)
   - 『台湾民俗のフィールドワーク』刊行記念トーク → ["books_media", "lecture", "academic", "senses"]
   - 原住民族の移行期正義の現状を考える → ["geopolitics", "human_rights", "indigenous", "lecture"]
   - 原住民歌手のライブ → ["performing_arts", "indigenous"] (no senses: a performance, not a concept discussion)
   - 台湾デザイン展 → ["design_craft", "exhibition"] (add senses only if there is an explicit forum on Taiwanese design language / aesthetics)
   - 台湾夜市マーケット → ["market", "lifestyle_food"] (no senses)

   - An event can have multiple categories.
<!-- PROMPT:END -->
