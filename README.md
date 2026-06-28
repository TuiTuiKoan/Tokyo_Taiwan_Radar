# Tokyo Taiwan Radar 東京台灣雷達

🌐 Website: [tokyotaiwanradar.com](https://tokyotaiwanradar.com)

📅 An aggregator platform for Taiwan-related events across Japan (Movies, Exhibitions, Lectures, Food)

🇹🇼🇯🇵 Trilingual (Chinese / Japanese / English)

- 6/28 -
Preparing for round 2 weekly news upgrading, including cover visual style and template based on perfectures and categories.  Meanwhile, rebuilding the self-event publishing function with 2 methods, poster-oriented and full manual.  In parallel, a series of cyber security approach is introduced to guard prompt injecttion and other risks.

- 6/17 -
Delivered 3 sharings across Japan, US, and Taiwan on Tokyo Taiwan Radar around "Design Workflow in the Age of Agentic AI - A Practical Guide to Normativity Design".  Through preparation, I also get deeper understanding on the overall architecture.  As the speed to debug is slow down, I am also ruminating on the next step.

- 6/1 -
This is a learning and optimizing week.  Auto qa pipeline gradually assembled. Most importantly, I start collecting groundtruth table for venues, official urls, which I haven't thought before.  1 click to calendar is online. Source expands to book publishing.  Still don't have any idea on SNS.  Positioning carefully would be more important for managing energy.

- 5/25 -
This is a reflection week.  I try to start a new pipeline around evaluation and auto-QA.  After a month of debugging, I finally realized the complexity of flooding scraper and the untamed hallucination around annotation and polluted fields.  The system is evolving into something I need to digest codes and plan closely.  Time to slow down, though many exciting backlogs push me to move on.  Wish I can overcome this stage asap!

- 5/18 -
Teaching a Wax Apple to Drive

What would you do if your Tesla, mid-drive, insisted there was a giraffe in the road?

That's what every AI product developer wakes up to in 2026.

Old-school software was like building a car — finish it, ship it. AI changes the game. Now you build all of this at once:

🚙 The car — the website users see
🧭 Navigation — how the AI judges, translates, classifies
🏭 The factory — keeping the system stable, affordable, error-free
🔁 Driving school — daily exams to make the AI smarter
Fix one bug, and all four domains need attention. That's the real story behind 350+ updates this week — not more hours, just every fix splitting into four.

This week, our mascot "Miss Wax Apple" officially made her debut.

Why a wax apple? Like Taiwan's semiconductors, it's a product of high technology. Originally from Indonesia — where you can no longer find this variety; brought to Taiwan by Dutch traders during the Age of Sail; the name 蓮霧(Lianbu) is a Taiwanese phonetic adaptation of the Malay jambu; postwar Taiwanese agriculture transformed it into the crisp, sweet fruit it is today.

One fruit, four hundred years — Indonesian roots, Dutch trade routes, Taiwanese phonetics, modern agri-science. Not in Japan. Not in Korea. Only in Taiwan.

This week's visual overhaul orbited entirely around her: the antenna flickers, petals drift across the screen, share images auto-compose motifs based on event category. Open the site, and digital petals float past you.

📋 What We Fixed This Week

🚙 Visuals: mascot and animation effects upgraded; share images now include category illustrations; dark mode unified across the site
🧭 AI judgment: added movie-poster visual recognition; blocked AI from inventing non-existent organizers; automatic simplified-to-traditional Chinese correction
🏭 Stability: form writes hardened against silent failures; client-side permissions tightened; added an AI "plan reviewer" for cross-checking decisions
🔁 Continuous improvement: launched daily AI translation quality exams; monthly governance scanner; 70+ permanent guard rules accumulated
📡 Data: 4 new sources added (film festival, cinemas); 42 blocked events recovered
See you next week 👋🍎

- 5/11 -

Week 3 clashed right with Japan's Golden Week, but we were in no mood for a holiday. We were coding like crazy every single day—our keyboards were practically smoking! 🔥 But the hard work totally paid off. We smashed a bunch of amazing goals all at once:

📱 Social Media Matrix Fully Activated!
We've fully unlocked our social channels! Besides launching a super convenient weekly newsletter via LINE QR code, our X, Instagram, Threads, and Facebook are all officially live. Come hang out with us!

📊 All-around Dashboard Monitoring Upgrade!
To hit the Japanese market more precisely, we conducted several rounds of deep-dive research on our PMF (Product-Market Fit) in Japan. Meanwhile, our backend monitoring got a massive upgrade! The new Dashboard now covers everything from dev progress and business strategy to SEO/AEO, data governance, and source management. Multiple dimensions at a glance—we have our finger perfectly on the pulse of the site's health! 😎

🔍 Database Firepower & Precision Leveled Up!
Content depth has evolved again! We've expanded from secondary event info, digging deeper to acquire "first-hand data," fully stripping down organizer info and event details. And for those tricky movie titles and names, we went all out comparing them against official and formal names to ensure our Chinese-Japanese translations are spot on! 🎬

🎉 The Biggest Surprise Easter Egg of the Week!
The most thrilling news? The "Japan-Taiwan Tomonkai of Waseda University" and "Tokyo Taiwan no Kai" (a group formed by Wansei—Japanese born in Taiwan) actually reached out to us proactively for collaboration! This is an absolutely fantastic start, and we are beyond excited for what's coming next! 🤝✨

- 5/5 -

Entering Week 2, our database has exploded to 633 events and 163 sources! We aren't just sweeping through Tokyo anymore; we're scraping all Japan-Taiwan exchange and grant/scholarship info across the entire country!
Watching Google, Claude, and ChatGPT's crawlers roaming around "Tokyo Taiwan Radar" all day—how does it feel? It's like I threw a massive EDM rave, and watching all these AI VIPs getting wasted and dancing their heads off at my venue. One word: Awesome!

🔥 Nothing comes easy here—only hardcore dedication!
Battling through trilingual translations until our noses bleed. Even with AI bowing down to help us out, the workload of data cleaning is beyond imagination. From movie titles and personal names to professional academic publications, no matter how many "final bosses" stand in the way, I'm going to smash them all one by one!
Basic LINE integration is live, and we've successfully tested publishing one weekly newsletter. We've also started brainstorming MVP models for monetization and running market tests.

- 4/26 -

Starting from 4/19, in just one week: 87 sources, 41 crawlers, and 237 event records. The very first version of "Tokyo Taiwan Radar" is finally running relatively smoothly.
It all started from a personal desire to help out while living overseas. Whether it's for people who love Taiwan, those who want their next generation to stay connected to it, or even those who aren't super familiar but want to give their friends a chance to discover Taiwan—I wanted them to have a small gathering place. A place where they can bring their curiosity, or simply use it as a lifestyle option to take their Japanese, American, Filipino, or even Chinese friends along to check things out.
This radar is still faint, but it carries a lot of love from everyone. I hope you find it a bit useful, too.

從4/19開始，一個禮拜，87個來源，41個爬蟲，237筆活動紀錄，「東京台灣雷達」第一版終於比較安定運作了。
一切都起於自己希望能夠在海外幫上忙。喜歡台灣的人，希望讓下一代繼續親近台灣的人，或者自己不夠熟悉，但是希望能夠讓身旁朋友有機會認識台灣的人，都有機會有一個小小的聚集地，可以帶著好奇心，或者，作為生活中一個選項，帶著身旁的日本朋友，美國朋友，菲律賓朋友，甚至中國朋友一起去看看。
這個雷達還很微弱，但他帶著很多大家的愛。希望你也覺得他有點用處。也歡迎你一起來許願，讓他把台灣的訊號，傳到更遠的地方。

4/19から始まり、1週間で87のソース、41のクローラー、237件のイベント記録。「東京台湾レーダー」の初期バージョンが、ついに比較的安定して稼働するようになりました。
すべては、「海外にいる自分にも何か手助けができないか」という思いから始まりました。台湾が好きな人、次の世代にも台湾に親しみ続けてほしいと願う人、あるいは自分自身はそこまで詳しくないけれど、周りの友人に台湾を知ってもらうきっかけを作りたい人。そんな人たちが、好奇心を持って集まれる小さな場所になればと願っています。日常の選択肢の一つとして、日本人の友達、アメリカ人の友達、フィリピン人の友達、そして中国人の友達も誘って、一緒に見に行けるような場所です。
このレーダーの電波はまだ微弱ですが、そこには皆さんのたくさんの愛が詰まっています。少しでもお役に立てれば嬉しいです。台湾のシグナルをさらに遠くへ届けられるよう、ぜひ皆さんも一緒にこのレーダーに願いを込めてください。