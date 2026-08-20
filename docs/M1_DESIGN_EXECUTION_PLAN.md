# M1 Design / Execution Plan — Zero-to-First-Real-Revenue

**תאריך:** 2026-08-13
**מקור:** `docs/ROADMAP_PROPOSAL.md` (M1, קנוני ונעול).
**סטטוס:** **Design Plan לבדיקה בלבד.** לא בוצע שינוי קוד. לא בוצעה קריאת-API אמיתית (למעט בדיקת-קיום, לא ערך, של משתנה-סביבה אחד — ר' סעיף 2). **עודכן 2026-08-13** לאחר ביקורת-חיצונית-נוספת (4 נקודות: test-baseline, external-evidence, attribution, founder-intervention-list) — בוצעה הרצת `pytest -q` מקומית (ללא קריאה חיצונית) לאימות baseline מדויק. **עודכן שוב 2026-08-13**: קריאת `verify` בוצעה בהצלחה (§10 סעיף 2); נקבע Precondition מחייב ל-readonly API key לפני M1 Execution (§10 סעיף 7), טרם בוצע. **עודכן שוב 2026-08-13 (Marketplace Discovery Design)**: נמצא ש-`listMarketplaceEntries` אינו מוכח כמנגנון-גילוי-affiliate; נקבע Design חדש — Dedicated ATLAS browser profile + `cdp_url` attach + defense-in-depth wrapper (§2א) — כמסלול-הגילוי האמיתי ל-M1. **🔒 נעול מחדש** לאחר עדכון זה. M1 **לא נפתח**, שום browser/CDP action לא בוצעה. **עודכן 2026-08-14 (Autonomous Marketplace Traversal — Design בלבד, §2ב)**: לאחר Live Validation #3 המוכיח קריאת product cards אמיתיים + Extraction/Ranking Validation (`marketplace_extraction.py`/`marketplace_evaluation.py`, ממומשים ונבדקים, 1555 passed), נותח מנגנון-ההתקדמות של הדף (scroll-based, ראייה חזקה אך לא-מאומתת-בחיים — ר' §2ב) ותוכנן primitive צר (`ScrollEvent`-בלבד, לא `BrowserHands`) + מודל persistence/dedupe + stop conditions. **עודכן שוב 2026-08-14, סוף-יום (§2ג)**: Implementation מלא מומש+נבדק (`DiscoveryScrollAdvancer`/`MarketplaceCatalogStore`/`run_discovery()`, 1586 passed) ואומת בשני live runs אמיתיים (scroll יחיד, ואז Bounded Discovery Run של 3 cycles על scratch catalog). **ממצא קריטי מהפאונדר**: ל-Marketplace יש 10 מוצרים/page עם מעבר-page ידני, לא רשימת-גלילה-יחידה — `pages_below_indicates_end` שנצפה בריצה החיה מייצג כנראה סוף Page 1 בלבד, לא סוף כל 1352 המוצרים. **נקודת-המשך ל-2026-08-15**: M1 Autonomous Marketplace Pagination (Design ל-primitive "Next Page only"). **נעול, אין GO נוסף ב-2026-08-14.**

---

## 1. Exact Current Flow — מודולים/פונקציות אמיתיים, לפי שלב

| שלב | מודול/פונקציה אמיתיים | הערה |
|---|---|---|
| **Discovery** | **תוקן 2026-08-13**: `discover_and_rank_digistore24_opportunities()`/`listMarketplaceEntries` **אינם מוכחים** כמנגנון-גילוי-affiliate (ר' §2א) — לא בשימוש ב-M1. המסלול האמיתי: Marketplace Discovery דרך Dedicated Browser Profile + `cdp_url` (§2א) → `collect_evidence_from_source()`/`BrowserPlugin` → `Finding` → אותה שרשרת `confidence_score()`/`decide()`/`opportunity_ranking`/`advance_opportunities_from_findings` הקיימת, ללא חיווט נוסף | ר' §2א למפרט המלא |
| **Evaluation** | `atlas.brain.opportunity_evaluation.evaluate_opportunities()`, `atlas.brain.confidence.confidence_score()`, `atlas.brain.revenue_strategy.commit_ready_opportunities()` (נקרא כל tick, מוגבל ל-`"affiliate"`) | `ceo.py:209` |
| **Decision** | `atlas.brain.decision_engine.decide()`/`decide_all()`, `atlas.brain.decision_apply.apply_decision()` (יוצר Goal, `engine_id="intelligence_affiliate"`), `atlas.brain.business_plan_advance.advance_business_plan_generation()` (יוצר Task `affiliate_commercial_terms_needed`) | `ceo.py:188, 247` |
| **Governance** | `atlas.brain.risk.RiskPolicy.evaluate()` (דרך `_risk_gate_and_delegate`), `ALWAYS_REQUIRES_APPROVAL` (כולל `affiliate_commercial_terms_needed`), `Delegator._propose()` → `Proposal`, `CEOBrain.approve(task_id)` | `ceo.py:159` |
| **Terms supply (פאונדר)** | CLI: `atlas affiliate commercial-terms supply <task_id> --commission --link --provider` → `atlas.brain.business_plan_advance.create_affiliate_opportunity_from_terms()` — יוצר `AffiliateOpportunity` אמיתי ב-`selected_for_marketing` | `cli.py:1220-1233` |
| **Campaign/Execution** | `atlas.brain.campaign_advance.advance_decision_driven_campaigns()` → `atlas.campaign.registry.create_campaign()`+`set_status("active")`+`atlas.orchestrator.orchestrator.start_execution()`; המשך כל tick: `advance_content_factory`, `advance_editorial_review`, `advance_creative_agent`, `advance_publishing_gateway`, `advance_all_campaign_executions()` | `ceo.py:250-273` |
| **Founder-review handoff** | `atlas.assets.campaign_execution.agent.CampaignExecutionAgent.run()` — מוחזר אחרי אישור Task `request_founder_review` | קוד אמיתי, אומת ישירות |
| **External platform** | **אין קריאת-API. פעולה ידנית של הפאונדר** — `CampaignExecutionAgent.run()` מחזיר במפורש: *"No real publishing integration exists yet — post it to the target platform(s) yourself"* | ר' סעיף 5 |
| **Revenue signal** | CLI: `atlas campaign revenue record <campaign_id> <amount>` → `atlas.brain.kpi_intake.record_manual_revenue()` | `cli.py:1756-1763` |
| **Ledger/KPIRegistry** | `record_manual_revenue()` כותב ל-`KPIRegistry` (`revenue_<goal_id>`, accumulate) ו-`Ledger` (`LedgerEntry`, kind=`revenue_claimed`) | קיים ומאומת |
| **סגירת-לולאה** | ה-`check_measurement` step ב-`ExecutionPlan` קורא `cashflow.profit()`; ברגע שיש רווח אמיתי, `advance_all_campaign_executions()` בתיק הבא מסמן את השלב `done`, קורא `campaign.refresh_confidence()`, וסוגר Campaign+Plan ל-`completed` | live-verified בעבר בסביבת-scratch, per CLAUDE.md |

**מסקנה**: השרשרת המלאה **בנויה ומחווטת ל-tick() כבר היום** — אין קטע חסר בקוד עצמו.

---

## 2. What Requires Real-World Access

- **`DIGISTORE24_API_KEY`** — **בדיקה בוצעה כרגע (קיום בלבד, לא ערך, אין קריאת-API)**: `SET (length=48)`. **המפתח כבר מוגדר בסביבה הזו.** לא אומת שהוא תקף/נכון — זה דורש קריאת-`verify` אמיתית, שלא בוצעה כאן.
- **Read-only, ניתן לבדוק לפני כל מחויבות**: `atlas affiliate digistore24 verify` (`getUserInfo` — ללא נתונים כספיים; per הקוד עצמו: **כבר אומת בעבר, session קודם**, 2026-08-04/2026-08-06, מול חשבון אמיתי). `atlas affiliate digistore24 sales` (`listPurchases`, read-only; per הקוד: **כבר אומת, חשבון-ריק-אמיתי מאושר**) — **גם המקור ל-external revenue evidence, ר' סעיף 6**: מדובר בקריאה read-only אמיתית שיכולה לשמש כראיה-חיצונית שמכירה קרתה בפועל, **נפרד ולפני** הרישום הידני ב-Ledger. `marketplace` / `marketplace-entry` / `discover-opportunities` — probes read-only נוספים.
- **השלב היחיד שיוצר פעולה אמיתית בעולם החיצוני**: **פרסום הקישור/תוכן בפועל — פעולה ידנית של הפאונדר, מחוץ ל-ATLAS לחלוטין.** שום קריאת-קוד לא מפרסמת דבר.
- **תנאי-מקדים אמיתי, לא-טכני**: הסכם-affiliate אמיתי וקיים מול Digistore24 לפחות למוצר אחד (commission + קישור-אמיתי) — עובדה עסקית שהפאונדר צריך להביא, לא dependency בקוד.

---

## 2א. Marketplace Discovery — Browser/Senses Design Decision (הוכרע 2026-08-13)

**עיקרון-על**: **Founder access ≠ Founder selection.** הפאונדר מספק **גישה** בלבד. **ATLAS** הוא זה שרואה/זוכר/חוקר/מדרג/**בוחר** את המוצר. רק **לאחר** בחירת-ATLAS, פעולה שאינה זמינה לו טכנית (למשל "Promote now"/קבלת promolink) עולה לפאונדר — אותו דפוס-נעול-בקוד כבר ("M3 מחליט WHAT, M4 ממשיך HOW, never a re-choice") מוחל עכשיו גם על **בחירת-מוצר**, לא רק על אספקת-תנאים-מסחריים.

### Boundary עיקרי — מבני, לא קוד: Dedicated ATLAS Browser Profile

הפאונדר **לא** מחבר את ATLAS לדפדפן/פרופיל-האישי-שלו. פרופיל ייעודי, ריק מכל חשבון/טאב/מידע שאינו Digistore24. **זהו ה-security boundary הראשי** — נכון גם אם קוד מכיל באג, גם אם מתרחש redirect בלתי-צפוי, גם אם ניסיון-extract/prompt-injection מנסה לגרום ל-navigate לדומיין אחר — כי **פשוט אין מה לחשוף שם**.

### למה לא מספיק להסתמך על קוד/wrapper בלבד — פערים אמיתיים שנמצאו (2026-08-13, בקוד-המקור המותקן, `browser_use==0.13.7`)

- **CDP-attach נותן גישה לדפדפן שלם, לא ל-tab/context מסוים** — אין isolation מובנה בספרייה. `BrowserSession.agent_focus_target_id` הוא bookkeeping-פנימי ("איזה tab אני פועל עליו עכשיו"), **לא** security boundary — קיים enumeration/switching מלא בין targets (`session_manager.get_target()`, `SwitchTabEvent`, `TabCreatedEvent`) כחלק מהתכנון הרגיל של הספרייה.
- **`BrowserAllowlist` מגן רק על ה-`navigate()` הראשוני** — **לא** על: redirect לאחר-הניווט (`real_url` בפועל לא נבדק שוב), tabs שכבר פתוחים בזמן ה-attach, popups/tabs-חדשים שהעמוד-עצמו פותח, וקריאות `BrowserHands` (שאין בהן **שום** allowlist check — אומת ישירות בקוד).
- **מסקנה**: profile ייעודי הוא ה-**primary boundary** (מבני, לא-תלוי-נכונות-קוד עתידית); ה-wrapper הבא הוא **defense-in-depth בלבד**, לא תחליף לו.

### Defense-in-Depth Wrapper — **✅ מומש 2026-08-13, נבדק (1524 passed, אותם 6 known failures, 0 regressions)**

1. **`cdp_url`** — פרמטר-configuration אופציונלי ב-`BrowserUseObserver`, `None` כברירת-מחדל (זהה לברירת-המחדל האמיתית של `BrowserSession` עצמה). Backward-compat מלא מאומת ב-test.
2. **Allowlist re-check מול `real_url` בפועל** אחרי navigation/redirect, ב-`browser_research.collect_evidence_from_url()` וב-`browser_plugin.BrowserPlugin.observe()` — fail-closed.
3. **תוקן 2026-08-13 (Qualification חשפה שהמימוש-הראשוני היה מאוחר-מדי — ר' §2א1 למטה)**: **וידוא target/URL לפני שתוכן נקרא בכלל, לא רק לפני שהוא נשמר.** `BrowserObserver.observe()` (Protocol, `atlas/integrations/base.py`) ו-`BrowserUseObserver` קיבלו פרמטר `verify_target: Callable[[str], bool] | None`, אופציונלי, `None` כברירת-מחדל. כשסופק — נבדק **בתוך** `_observe_async()`, מיד אחרי שה-`real_url` האמיתי ידוע, **לפני** `get_state_as_text()`/`take_screenshot()`. `browser_research.py`/`browser_plugin.py` מעבירים `verify_target=allowlist.is_approved`. **מוכח ב-test ייעודי**: `take_screenshot`/`get_state_as_text` **לא נקראים כלל** כש-verify_target דוחה את היעד (`assert_not_called()`, לא רק "התוצאה לא נשמרה"). הבדיקה-הכפולה-בשכבה-העליונה (סעיף 2) נשארת כ-defense-in-depth נוסף, לא-תלות-יחידה, למקרה של observer-implementation עתידי שלא-מכבד `verify_target`.
4. **Observe-only, ללא יוצא-מן-הכלל**: M1 Marketplace Discovery **לא** משתמש ב-`BrowserHands` בכלל — אין click/input/submit/promote/שינוי-חשבון אוטומטי בזרימה הזו. `browser_hands.py` **לא נגע**. מאומת ב-test סטטי (`test_m1_marketplace_discovery_safety_wiring.py`) שאף אחד מהמודולים הרלוונטיים לא מכיל אזכור ל-`BrowserHands`. שימוש עתידי ב-`BrowserHands` (למשל ל-"Promote now" עצמו) הוא **החלטה נפרדת, לא חלק מ-M1** — ואותה פעולה ספציפית, גם אם תיבנה בעתיד, תישאר פעולת-הפאונדר (ר' עיקרון-העל למעלה).
5. **צמצום-נתונים ב-`Finding`**: כל Finding שנשמר מ-Marketplace Discovery מכיל **רק** שדות-עסקיים (שם-מוצר/vendor/קטגוריה/מחיר/עמלה/מטא-דאטה-רלוונטית) — לעולם לא cookies/session-identifiers/PII שאינם נדרשים ל-Discovery/Research. (עדיין נכון — לא שונה בסבב זה.)

**תיקון להערה הקודמת ("סבב-קודם" של המסמך הזה)**: אז דווח כפער-פתוח שייתכן ש-screenshot ייכתב-לדיסק לפני דחייה. **זה כבר לא נכון** — הסדר-בפועל בקוד הוא `navigate → real_url → verify_target-check → (רק אם עבר) get_state_as_text/take_screenshot`, ומאומת ישירות ב-test (`take_screenshot.assert_not_called()` כש-verify_target דוחה). אין עוד פער פתוח בנקודה הזו.

### Founder Setup Sequence — צעד-אחד-בכל-פעם (לא בוצע, לביצוע לפני GO ל-Implementation)

1. פתיחת פרופיל-דפדפן **חדש וייעודי** (Chrome/Edge), נפרד לחלוטין מהפרופיל-האישי.
2. הפעלת remote-debugging בפרופיל הזה בלבד (למשל `--remote-debugging-port=<port>`), לא בפרופיל-האישי.
3. Login ל-Digistore24 **בפרופיל הייעודי בלבד**, על-ידי הפאונדר עצמו — ATLAS לא מקבל/רואה username/password.
4. ניווט ל-Affiliate Marketplace באותו פרופיל.
5. אישור מפורש לפאונדר ש-**שום דבר רגיש אחר** לעולם לא ייפתח באותו פרופיל-ייעודי.
6. רק לאחר 1-5 — GO נפרד ל-`cdp_url` attach (עדיין לא ניתן; ר' §10).

**⚠️ תיקון קריטי, 2026-08-16 — ר' §2ה למטה במלואו לפני ביצוע הרצף הזה**: סעיף 2 כפי שנוסח כאן ("בפרופיל הזה", תוך שימוש ב-`--profile-directory` בתוך תיקיית ה-Chrome User Data **הרגילה**) **אינו מספיק ומטעה** — התגלה בפועל ש-Chrome 136+ חוסם remote-debugging על כל תיקיית-User-Data רגילה/ברירת-מחדל, ללא קשר לאיזה פרופיל-משנה נבחר בתוכה. נדרשת תיקיית `--user-data-dir` **נפרדת ולא-סטנדרטית לגמרי** (לא תת-תיקייה של Chrome User Data הרגילה). הטקסט המקורי כאן נשאר כפי שהוא (לא נמחק) — ר' §2ה לפקודה המתוקנת בפועל.

---

## 2ב. Autonomous Marketplace Traversal — Analysis/Design (2026-08-14, Design בלבד — אין GO ל-Implementation)

**מטרה**: ATLAS יוכל בסופו של דבר לסרוק בעצמו את כל ה-Marketplace (`observe → extract → persist/dedupe → advance → readiness → observe again → repeat → stop`), בלי שהפאונדר יגלול/ידפדף במקומו. הסבב הזה הוא **Analysis/Design בלבד** — לא בוצע browser action נוסף, לא בוצע implementation. כל הראיות למטה מבוססות על ה-snapshot האמיתי מ-Live Validation #3 (`tests/fixtures/browser_snapshots/digistore24_marketplace_sample.txt`) ועל בדיקה ישירה, offline, של קוד-המקור המותקן של `browser_use==0.13.7` — לא ניחוש.

### 1. מנגנון ההתקדמות האמיתי של הדף — evidence, לא ניחוש

מה שנמצא בפועל ב-snapshot (`tests/fixtures/browser_snapshots/digistore24_marketplace_sample.txt`, שורה 18):
```
|scroll element|<mat-sidenav-content /> (0.0 pages above, 2.7 pages below)
```
- `pages_above`/`pages_below` הם מדד **אמיתי** של `browser_use` עצמו (`dom/views.py:scroll_info`, מחושב ישירות מ-`scrollRects`/`clientRects`/`bounds` אמיתיים דרך CDP) — לא Digistore24-specific, אבל משקף מצב-גלילה אמיתי של אלמנט `mat-sidenav-content` (Angular Material scrollable container).
- **2.7 pages below כבר בטעינה הראשונה**, מול 1352 מוצרים תואמי-פילטר — כלומר תוכן רב מעבר-לוויופורט **כבר קיים בתוך אותו scroll container אחד**, לא מפוצל לעמודים נפרדים.
- **אין** בשום מקום ב-snapshot כפתור/טקסט "Next"/"Load more"/ווידג'ט-מספרי-עמודים. זו ראייה שלילית תומכת (לא הוכחה מוחלטת) נגד click-pagination קלאסי.
- **מסקנה, ברמת-ביטחון "ראייה חזקה אך לא-מאומתת-בחיים"**: ההתקדמות היא **scroll-based** בתוך `mat-sidenav-content` — ולא pagination מבוססת-קליק. **לא ניתן להכריע מה-snapshot בלבד** האם זו רשימה ארוכה-אך-מלאה-ב-DOM, או רשימה virtualized עם lazy-load-בזמן-גלילה (Angular CDK virtual scroll — נפוץ מאוד לרשימות בגודל הזה, עם ה-styling של `ds-`/Material שנצפה). **ההבחנה הזו דורשת מחזור-scroll-אמיתי-בודד לאימות — לא ניתן להכריע ללא GO נפרד ל-Live action.**

### 2-3. Primitive צר של Discovery-Navigation — היתכנות ותכנון

**נמצא ומאושר**: `browser_use` חושף `browser.events.ScrollEvent` (`direction: up|down|left|right`, `amount: int px`, `node: None`=scroll-the-page) כ-event **עצמאי**, מטופל ב-`default_action_watchdog.on_ScrollEvent`, **ללא כל תלות** ב-`Tools`/agent-action-registry המלא. דפוס-קריאה אמיתי, מאומת בקוד-המקור (`tools/service.py`):
```python
event = session.event_bus.dispatch(ScrollEvent(direction="down", amount=800, node=None))
await event
await event.event_result(raise_if_any=True, raise_if_none=False)
```
זהו **event יחיד, סגור-מבנית**: אין שום דרך לגרום לו לבצע click/input/submit/navigate — הוא לא מייבא/משתמש ב-`Tools.click`/`Tools.input`/`Tools.navigate` בכלל, בניגוד ל-`BrowserHands` (`src/atlas/hands/browser_hands.py`) שחושף `Tools` המלא (navigate/click/input_text/upload_file/send_keys/scroll/describe_page) על-גבי `BrowserSession()` **ללא** `cdp_url`/`verify_target`/`select_existing_target`/`page_ready_check` בכלל — כלומר גם ברמת-ה-scope וגם ברמת-הבטיחות-הקיימת, `BrowserHands` אינו מתאים למשימה הזו כפי-שהוא.

**תכנון-primitive מומלץ**: מחלקה חדשה, נפרדת מ-`BrowserUseObserver` (לא הרחבה שלה) — `BrowserObserver.observe()` נשאר read-only ללא-יוצא-מן-הכלל, זו הבטחה ארכיטקטונית שקוד אחר עשוי להסתמך עליה. מוצע: `src/atlas/integrations/browser_scroll_advancer.py` → מחלקה בשם עבודה `DiscoveryScrollAdvancer`, עם **בדיוק אותו** מנגנון-חיים ואותם safety gates כמו `BrowserUseObserver` (אותו `cdp_url`, אותו `select_existing_target`/`verify_target`/timeout), ופעולה יחידה בלבד: `ScrollEvent`. שום `Tools`, שום click/input/upload/send_keys/navigate — לא רק מדיניות אלא **בלתי-אפשרי מבנית** (לא מיובא כלל).

**סדר-הפעולות בתוך cycle יחיד (מראה במדויק את סדר-ה-gates הקיים ב-`observe()`, לא ממציא סדר חדש)**:
1. `select_existing_target` (fail-closed, exact-match) — כל cycle מתחבר-מחדש במפורש, אף פעם לא סומך על state בין-cycles.
2. `verify_target` (בדיקה 1) — נגד `real_url` טרי, **לפני** כל scroll.
3. `ScrollEvent(direction="down", amount=<bounded>, node=None)` — **הפעולה היחידה שמבוצעת**.
4. Readiness-poll (ר' סעיף הבא — עיצוב-מחדש, לא spinner-check נאיבי).
5. `verify_target` (בדיקה 2, `real_url` **טרי שוב**) — אותו דפוס-כפול-בדיוק שכבר מוכח ב-`observe()`.
6. מחזיר רק את הרשומות **החדשות** שחולצו (dedupe נגד מפתחות ידועים) — **לא כותב לדיסק בעצמו**; persistence היא שכבה נפרדת (ר' סעיף 5).

**עיצוב-Readiness משופר, לא spinner-check**: ה-`not_loading` (העדר `ds-spinner`) ששימש לטעינה-ראשונית **לא בהכרח רלוונטי** לגלילה — ייתכן שאין spinner-ייעודי-לגלילה בכלל, וייתכן שהתופעה היא virtualization (node-recycling), לא loading אמיתי. **מוצע content-based readiness**: פונקציית-ה-extraction הקיימת (`extract_marketplace_products`) **עצמה** משמשת כ-readiness oracle — poll חוזר עד ש-set-המוצרים-המחולץ משתנה ביחס למצב-שלפני-הגלילה, חסום ב-`page_ready_timeout`. זה נמנע מהצורך לנחש UI-חדש (spinner/loader) שטרם נצפה בפועל, ומשתמש-חוזר בקוד קיים ונבדק. **אם הזמן-הבחור עובר בלי שינוי — זו לא בהכרח כשל**: ייתכן שזה בדיוק סימן "הגענו לסוף" (ר' Stop Conditions).

### 4. מודל Persistence / Dedupe

**זהות-מוצר**: אין מזהה-Digistore24-אמיתי (product ID) גלוי ב-`text_content` כפי שהוא נקרא היום — הקישורים ("Sales page"/"Affiliate support page") מוצגים כטקסט בלבד, ללא `href`. **ממצא אמיתי, לא הוסתר**: המפתח היציב-ביותר-שזמין-כיום הוא **מפתח מורכב** `(vendor, product_name)` מנורמל (strip + casefold). שיפור עתידי אמיתי (לא נבנה עכשיו): קריאת `href` מתוך `selector_map`/ה-DOM-node עצמו (לא רק ה-text serialization) לחילוץ product-ID אמיתי — הרחבה נפרדת, לא נדרשת ל-Design הנוכחי.

**Store חדש, נפרד מ-`KnowledgeBase`**: `src/atlas/brain/marketplace_catalog.py` (עיצוב) → `MarketplaceCatalogStore`, אותו דפוס `BrainStore`/`JSONFileStore` בדיוק כמו כל store אחר בקוד-הבסיס, קובץ נפרד (`.atlas/marketplace_catalog.json`). **בכוונה נפרד מ-`Finding`** — Marketplace catalog הוא רשומת-קטלוג-גולמית, לא evidence-grade Finding ולא Opportunity/Decision (בדיוק כמו ש-`AffiliateStore` כבר נפרד מ-`KnowledgeBase` היום). `save_records()` דוחה כפילויות לפי מפתח-הזהות; רשומה קיימת מתעדכנת בשדות-משתנים (מחיר/עמלה/conversion עשויים להשתנות עם הזמן) תוך שמירת `first_observed_at` המקורי.

### 5. Stop Conditions

1. **שני cycles רצופים** ללא אף מפתח-זהות חדש → עצירה, `no_new_products` (סף-2, לא-1, כדי לא לעצור-מוקדם-מדי על delay רגעי חד-פעמי).
2. `pages_below` (מ-`scroll_info`, אם/כאשר יילקח מהיר-דרך-אמיתי בעתיד) קרוב-ל-0 אחרי scroll — סימן תומך נוסף ל"הגענו לתחתית".
3. **`MAX_DISCOVERY_CYCLES`** (קבוע מוצהר-ועריך, למשל 50) — עצירה בכל מקרה, עם דיווח מפורש "ייתכן שלא מוצה".
4. **Wall-clock timeout** נפרד מ-`page_ready_timeout` הפר-cycle — כדי שרצף איטי-אך-תקין לא יחרוג מתקציב-זמן כולל.
5. **Fail-closed על target/domain mismatch** — אותו `verify_target` בדיוק, נבדק פעמיים בכל cycle (ר' סעיף 2-3) — לא מנגנון חדש.

### 6. איך ה-Ranking הקיים משתלב

שכבות נפרדות, לא שינוי ל-`marketplace_evaluation.py` הקיים:
- **Catalog ingestion** (הסבב הזה, מתוכנן) — persist גולמי, בלי שיפוט.
- **Preliminary research-priority ranking** — `rank_marketplace_products()` **הקיים כבר, ללא שינוי**, מופעל על כל הקטלוג המצטבר (בסיום traversal, או אינקרementally) — פונקציה טהורה, idempotent, מתאימה כמו-שהיא.
- **Deep research** — **לא קיים היום**. הרחבה עתידית סבירה: `browser_research.collect_evidence_from_url()` הקיים, מופעל per-shortlisted-product על עמוד-הפרטים/ה-sales-page שלו — לא נבנה בסבב הזה.
- **Selection for execution** — נשאר **לגמרי נפרד ולא-נגוע**: שום קטלוג/דירוג לא הופך אוטומטית ל-Opportunity/Task/Decision. Marketplace catalog ≠ recommendation — עיקרון מובנה, לא רק מדיניות.

### 7. גבולות M1 — נשמרים, checklist

| גבול | נשמר איך |
|---|---|
| Dedicated profile | ללא שינוי — `cdp_url` מצביע לאותו profile ייעודי בלבד |
| Explicit target selection | `select_existing_target` בכל cycle, ללא fallback ל-index |
| Allowlist | `verify_target=allowlist.is_approved`, ללא שינוי |
| Readiness | מחליף spinner-check ב-content-based poll, עדיין בלתי-fixed-sleep, עדיין bounded |
| Target re-verification | פעמיים בכל cycle (לפני+אחרי scroll), כמו ב-`observe()` |
| No unrestricted BrowserHands | `browser_hands.py` לא נגע; ה-advancer החדש לא מייבא `Tools` בכלל |
| No Promote/link retrieval/publishing | לא נבנה, לא נגזר במרומז מהקטלוג |

### 8. Tests — מתוכננים, טרם נכתבו (Design בלבד)

- Parser/dedupe: פונקציית `dedupe_key(record)` טהורה — קלה לבדיקה.
- `MarketplaceCatalogStore`: לוגיקת JSON-store טהורה, ללא דפדפן, אותו דפוס כמו `tests/brain/test_knowledge.py`.
- לולאת ה-stop-conditions: ניתנת לבדיקה **מלאה בלי דפדפן אמיתי** — הזנת רצפי-טקסט מדומים (0/N רשומות-חדשות) ואימות שהלולאה עוצרת בדיוק לפי כל תנאי בנפרד.
- ה-scroll primitive עצמו: mock-בלבד על `session.event_bus.dispatch`/`ScrollEvent`, באותו דפוס בדיוק כמו `tests/integrations/test_browser_use_observer.py` הקיים.

### מסקנה — האם ניתן להגיע לסריקה אוטונומית מלאה בלי BrowserHands כללי

**כן, ארכיטקטונית**: `ScrollEvent` הוא primitive צר-מבנית, מספיק לצורך הזה, ולא דורש פתיחת `Tools`/click/input/submit/navigate כלליים. **אך יש פער-ידע אמיתי אחד שנותר פתוח, ולא ניתן לסגור אותו ב-Design בלבד**: האם ההתקדמות היא רשימה-ארוכה-אך-מלאה או virtualized-lazy-load — משפיע ישירות על עיצוב ה-readiness-poll (מס' cycles צפוי, timeout סביר). **מומלץ**: GO נפרד וצר ל-**מחזור scroll-אמיתי בודד** (scroll יחיד + readiness-poll יחיד + observe יחיד, ללא persistence, ללא loop מלא) כצעד-האימות-הבא — לפני GO ל-Implementation המלא של הלולאה.

---

## 2ג. סיכום סוף-יום 2026-08-14 — Implementation מומש + תיקון-ממצא קריטי + נקודת-המשך ל-2026-08-15

**Implementation מומש ונבדק במלואו** (GO נפרד, אחרי §2ב): `DiscoveryScrollAdvancer` (`src/atlas/integrations/browser_scroll_advancer.py`, `ScrollEvent`-בלבד, ללא `Tools`/click/input/submit/navigate), `MarketplaceCatalogStore` (`src/atlas/brain/marketplace_catalog.py`, cumulative/union-based, נפרד מ-`KnowledgeBase`), `run_discovery()` (`src/atlas/brain/marketplace_discovery.py`, שישה stop conditions — חמישה כ-`stop_reason` מוחזר, target/domain mismatch כ-`BrowserUseError` שמתפשט, fail-closed בקול). 25 tests חדשים, Full Suite: 1586 passed, 6 כשלים ידועים קיימים, 0 regressions.

**Live-verified פעמיים**: Single Live Scroll Validation (scroll יחיד) ואחריו Bounded Live Discovery Run (`max_cycles=3`, scratch catalog בלבד — **לא** production). שלושה cycles אמיתיים: 6 → 9 (4 חדשים) → 6 (0 חדשים) records, `pages_below` ירד 2.7 → 1.0 → 0.0, עצר ב-`pages_below_indicates_end`. Cumulative persistence מאומת ישירות בחיים: `megadrought::Joseph's Well...` נעלם מה-snapshot מ-cycle 2 ואילך ונשאר בקטלוג הסופי, לא נמחק.

**תיקון-ממצא קריטי מהפאונדר (2026-08-14, סוף-יום)**: ל-Marketplace יש בדיוק **10 מוצרים בכל page**, עם מעבר-ידני ל-Page 2/3/... — **לא** רשימת-גלילה-אחת-ארוכה כפי שהונח. המשמעות: `pages_below = 0.0` שהתקבל בסוף ה-Bounded Live Discovery Run מייצג ככל-הנראה **סוף ה-scroll בתוך Page 1 בלבד**, לא סוף כל 1352 המוצרים ב-Marketplace. זה **מאשר ומחדד** את ה-gap שכבר סומן בדוח אותו ריצה (סעיף 9: "`pages_below_indicates_end` עלול להיות stop-condition מוקדם-מדי") — עכשיו עם הסבר-שורש אמיתי, לא רק חשד. **לא תוקן היום** — הפאונדר הבהיר שאין GO לשום שינוי/פעולה נוספת ב-2026-08-14; זהו הממצא שנועל את היום ומתעד את הכיוון למחר.

**נקודת-המשך מאושרת ל-2026-08-15 — M1 Autonomous Marketplace Pagination**: תכנון (Analysis/Design, לא Implementation, כפי שכל milestone קודם נפתח) של primitive צר ובטוח נוסף — **"Next Page only"** — מקביל מבנית ל-`DiscoveryScrollAdvancer` (אותם safety gates: dedicated profile, explicit target selection, allowlist+verify_target לפני/אחרי, readiness bounded, ללא `BrowserHands` כללי, ללא Promote/Copy promo link/פעולה מסחרית). ה-flow המתוכנן:
```
read current page → extract → persist/dedupe → finish scrolling current page
→ safely advance to next Marketplace page → wait for readiness
→ verify target/domain → read next page → repeat
```
**אין GO לביצוע/שינוי נוסף ב-2026-08-14.** נקודת-המצב נעולה כאן.

---

## 2ד. Checkpoint 2026-08-16 — Session Handoff, Root-Cause Review, ותיקון Orientation + Completeness

**הערה מתודולוגית**: הסעיפים 2ג ומעלה תיעדו רק עד 2026-08-14 — כל העבודה האמיתית מ-2026-08-15/16/17 (ר' `project_atlas_m1_marketplace_discovery` ו-`feedback_screenshot_ground_truth_validation` ב-memory) בוצעה בקוד בפועל אך מעולם לא שוקפה לכאן. סעיף זה סוגר את הפער — מסמך זה חוזר להיות מקור-האמת האמיתי והמעודכן.

**Checkpoint של מצב ה-worktree, לפני כל שינוי בסבב הזה (2026-08-16)**: כל עבודת M1 — כולל Semantic Grounding, MarketplaceCatalogStore, marketplace_extraction, ה-Digital Body Foundation (`browser_scroll_advancer.py`, `browser_click_advancer.py`, `traversal_completion.py`) וה-Cognitive Foundation (`claims.py`, `reasoning_claims.py`) — **עדיין uncommitted**, קיימת רק על ה-disk. `git log -- <כל קובץ מה-workstream הזה>` ריק — אין היסטוריית commits לגביהם. ~35 קבצי tracked מתוקנים + ~90 קבצים/תיקיות untracked. שום פעולת git הרסנית (reset/stash/checkout) לא בוצעה — התיעוד הזה הוא ה-checkpoint, לא commit.

**סיכום מאושר של מה שהושג (2026-08-15/16/17, לפי memory + אימות ישיר בקוד היום)**:
- **Page 1 ו-Page 2 — COMPLETE אמיתי** (4-תנאים: Traversal/Perception/Reconciliation/Data-Stability), מאומת גם דרך audit גולמי בלתי-תלוי ב-extractor (`dom_state._root`).
- **שני באגים אמיתיים בשלמות-נתונים תוקנו** ב-`MarketplaceCatalogStore.save_records()`: זיהוי-vendor-חסר, ו-preserve-on-`None` למחיר/עמלה (מאומת שוב היום, קיים בקוד).
- **Semantic Grounding Wiring** — `Claim.claim_type` (ציר אורתוגונלי ל-`claim_status()`), `marketplace_semantic_grounding.py`, מחובר בפועל בתוך `run_discovery()` (מאומת היום).
- **Screenshot Cross-Validation: PASS**, 24/24 MATCH, 0 mismatch — הפרש-לכאורה יחיד היה טעות-תמלול של הפאונדר, לא באג.
- **Page 3 Navigation: PASS** (מאושר חיצונית ע"י הפאונדר; לא נמצא artifact בקוד/repo שמוכיח זאת עצמאית — מדווח כעובדה מאושרת-ע"י-הפאונדר, לא כמאומת-על-ידי מחדש).
- **הבעיה שהתגלתה**: לאחר ה-click האמיתי ל-Page 3, הדפדפן נשאר קרוב לתחתית (תוצר-לוואי של מיקום ה-scroll ב-Page 2 בזמן ה-click). `run_discovery()` — production entry point אמיתי, ללא שינוי — התחיל משם, תפס 7 מוצרים אמיתיים, ועצר ב-`pages_below_indicates_end` **בלי לבסס orientation** לפני שהתחיל. Page 3 Coverage נשאר **PARTIAL**, לא אושר.

**ההחלטה הנוכחית (2026-08-16)**: לא Page 4, לא תיקון-מקומי ל-Page 3. בוצעה סקירת-שורש (Navigate → Orient → Traverse → Reconcile → Complete) — נמצא: לא כפילות, אלא **ניתוק** — שלושה רכיבים אמיתיים, בטוחים, בדוקים (`scroll_pages_above()`, `PageCompletionTracker`, `VerifiedClickAdvancer`) נבנו ומעולם לא חוברו ל-`run_discovery()`, ה-entry point האמיתי היחיד. אושר תיקון-שורש **מצומצם בלבד**: Orientation Precondition + Completeness Wiring. Navigation בין-עמודים (`VerifiedClickAdvancer`) **נשאר מחוץ ל-scope** במכוון.

**מומש** (`src/atlas/brain/marketplace_discovery.py`): (1) **Orientation Precondition** — לפני traversal רגיל, `scroll_pages_above()` נקרא על ה-state האמיתי; אם לא near-zero, מבוצע reverse-climb מוגבל (`DiscoveryScrollAdvancer(direction="up")` הקיים, ללא שינוי) עד orientation או `MAX_ORIENTATION_SCROLLS=20`/no-progress — ואז **עוצר עם `orientation_failed`, לא ממשיך forward בהנחה שגויה**. רשומות אמיתיות שנצפו תוך-כדי הטיפוס נשמרות תמיד (לא מומצא, לא נזרק). (2) **Completeness Wiring** — `PageCompletionTracker` אופציונלי (`tracker=None` ברירת-מחדל, backward-compatible מלא), מוזן מכל רשומה שנחלצת (גם ב-orientation, גם ב-traversal רגיל). **`resolve()` לא נקרא בסבב הזה בכוונה** — אין מנגנון-inspection אמיתי מחובר עדיין, אז `is_inspection_complete()`/`is_page_complete()` יחזירו `False` באופן כן, לא מזויף. `pages_below_indicates_end` נשאר תנאי content-completeness בלבד; page-completeness דורש גם inspection-completeness מה-tracker, נבדק ע"י הקורא, לא ע"י `run_discovery()` עצמו.

**Tests**: 11 טסטים חדשים ב-`test_marketplace_discovery.py` (orientation מכל 3 מצבי-פתיחה, כישלון-orientation מוגבל, שימור-evidence-בכישלון, tracker wiring, UNKNOWN-נשאר-UNKNOWN, אי-שבירת Semantic Grounding). Focused: 142/142. Full Suite: 1776 passed, 6 כשלים ידועים (זהים-בשם, בלתי-קשורים), 0 regressions.

**הבא**: Live Production Validation יחיד, מ-Page 3 בדיוק במצב שבו נעצרנו (תחתית/קרוב-לתחתית) — ללא סיוע ידני. פרטים מלאים ב-memory לאחר הריצה.

---

## 2ה. Root Cause אמיתי ל-CDP Attach Failure (2026-08-16) — Chrome 136+ Security Change

**ממצא, מאומת מול תיעוד רשמי, לא הנחה**: Chrome גרסה 151.0.7922.138 (הגרסה המותקנת בפועל, נבדק ישירות: `(Get-Item chrome.exe).VersionInfo.ProductVersion`) — הרבה מעבר לסף הרלוונטי. אומת מול [Chrome for Developers — Changes to remote debugging switches to improve security](https://developer.chrome.com/blog/remote-debugging-port): **החל מ-Chrome 136**, הדגלים `--remote-debugging-port`/`--remote-debugging-pipe` **מפסיקים להיות מכובדים** כאשר Chrome מופעל מול תיקיית ה-User Data **הרגילה/ברירת-המחדל** — ללא קשר לאיזה `--profile-directory` (תת-פרופיל) נבחר בתוכה. הסיבה: תיקייה לא-סטנדרטית משתמשת ב-encryption key נפרד, כך שנתוני-הפרופיל-הראשי מוגנים מפני ניצול-remote-debugging לגניבת cookies.

**זה מסביר באופן ישיר וממצה את כל מה שנצפה**: הפקודה שהופעלה קודם (`--user-data-dir="C:\Users\User\AppData\Local\Google\Chrome\User Data" --profile-directory="Profile 4"`) עדיין הצביעה על **תיקיית ה-User Data הרגילה עצמה** — בחירת תת-פרופיל בתוכה לא רלוונטית לבדיקת Chrome. זה גם מסביר למה restart מלא לא פתר את הבעיה — הבעיה לא הייתה session תקוע, אלא חסימת-אבטחה מובנית, תמיד-נכשלת, ללא קשר להיסטוריית-התהליכים.

**התיקון — Founder Setup Sequence מתוקן, מחליף בפועל את §2א-סעיף-2 לעיל**:

```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\User\AppData\Local\ATLAS\ChromeProfile"
```

- `C:\Users\User\AppData\Local\ATLAS\ChromeProfile` — תיקייה **חדשה, לא-סטנדרטית לגמרי**, מחוץ לכל מבנה Chrome/Edge קיים. נבדק ישירות (read-only): התיקייה **אינה קיימת עדיין** — Chrome ייצור אותה אוטומטית, נקייה, בפעלה הראשונה.
- **אין `--profile-directory`** — מיותר ומטעה כאן: תיקייה ייעודית חדשה משתמשת אוטומטית בפרופיל "Default" הפנימי שלה, שהוא ממילא ייחודי ל-ATLAS. השימוש הקודם ב-`--profile-directory="Profile 4"` היה ניסיון-לתקן-את-הבעיה-הלא-נכונה.
- Login ל-Digistore24 יידרש **מחדש**, בתוך התיקייה-הייעודית-החדשה הזו בלבד (Cookies/session לא עוברים מהפרופיל הישן) — פעולה ידנית של הפאונדר, כפי שתמיד היה.

**כלל קבוע מעכשיו, למניעת חזרה על התקלה**: **Chrome User Data directory הרגיל/ברירת-המחדל (`...\Google\Chrome\User Data`) לעולם לא ישמש שוב ל-remote-debugging/CDP attach** — רק תיקייה ייעודית, נפרדת, לא-סטנדרטית (כמו `ATLAS\ChromeProfile` לעיל). §2א-סעיף-2 המקורי לעיל תוקן בהערה מפנה, לא נמחק.

---

## 3. Minimal Implementation Delta

**ליבת לולאת-ההכנסה (Discovery-הישן-דרך-Digistore24-API ועד Ledger) עדיין דורשת אפס שינויי-קוד** — כפי שכבר תועד: השרשרת המלאה קיימת, מחווטת, ונבדקה עם mocks; שכבת ה-API של Digistore24 עצמה כבר אומתה מול חשבון-אמיתי (base-URL ומעטפת-JSON, מאומתים-בפועל).

**עודכן 2026-08-13, מומש ונבדק (✅)**: Marketplace Discovery דרש delta-קוד קטן ואמיתי, לא אפס (ר' §2א למפרט המלא) — בוצע:
1. `cdp_url` — פרמטר חדש ב-`BrowserUseObserver.__init__`, מועבר ל-`BrowserSession(cdp_url=...)`. `src/atlas/integrations/browser_use_observer.py`.
2. `verify_target` — פרמטר Protocol חדש ב-`atlas/integrations/base.py` (`BrowserObserver.observe`), ממומש ב-`BrowserUseObserver`: נבדק **בתוך** `_observe_async()` מיד אחרי `real_url`, **לפני** קריאת-תוכן. `browser_research.collect_evidence_from_url()` ו-`browser_plugin.BrowserPlugin.observe()` מעבירים `verify_target=allowlist.is_approved`, **וגם** שומרים בדיקה-כפולה אחרי `observe()` כ-defense-in-depth. `knowledge_source_research.py` **לא נגע** — מגן טרנזיטיבית דרך `BrowserPlugin`.
3. Observe-only מאומת ב-test סטטי (`test_m1_marketplace_discovery_safety_wiring.py`) — `browser_hands.py` לא נגע.

**עדיין תקף**: (א) קריאת `verify` אמיתית — כבר בוצעה בהצלחה. (ב) הסכם-affiliate אמיתי + פרסום ידני + מכירה אמיתית — פעולות-עולם-אמיתי, לא קוד. אם קריאת `sales`/Marketplace-observation תחשוף סכימה בלתי-צפויה — זה ממצא, לא כשל-תכנון; אינו חוסם את M1's DoD.

---

## 4. Safe Validation Sequence

1. **local/tests**: `python -m pytest -q` — סיכון חיצוני אפס. דורש **test baseline unchanged** (ר' סעיף 8), לא "ירוק מוחלט".
2. **authenticated read-only external call**: `atlas affiliate digistore24 verify` — הקריאה-האמיתית-הראשונה בכל הרצף. דורשת GO נפרד ומפורש (ר' סעיף 8/10).
3. **validate real response/schema**: בדיקת ה-JSON הגולמי מול `verify`/`sales` — GET בלבד, ללא מחויבות/שינוי-חשבון.
4. **dry/safe campaign path**: **אין sandbox אמיתי מתועד ב-Digistore24 — לא הומצא כאן.** השווה-ל-dry-run בפועל: כל השרשרת הפנימית (Discovery→Decision→Governance→Campaign→ExecutionPlan→`CampaignExecutionAgent`) היא **בעצמה בטוחה-לחלוטין** — לא נוגעת בעולם החיצוני בשום שלב, כי היא **עוצרת מבנית** ב-`request_founder_review`/handoff, לפני כל פרסום. זה ה-dry-run האמיתי, לא המצאה.
5. **controlled real execution**: הפאונדר מפרסם ידנית, פלטפורמה-אחת-נבחרת, תוכן-מאושר-אחד — **הפעולה החיצונית היחידה בכל הרצף, ומחוץ לקוד ATLAS לחלוטין.**
6. **external evidence check (read-only, לפני רישום)**: הרצה חוזרת של `atlas affiliate digistore24 sales` (`listPurchases`) — בדיקה **חיצונית, read-only** אם רשומת-רכישה אמיתית חדשה מופיעה בחשבון. זו ראייה **חיצונית** שמכירה קרתה — נפרדת ושלב-לפני רישום ידני.
7. **revenue observation + recording**: לאחר ראיית ה-listPurchases (או אישור-ישיר של הפאונדר על מכירה שראה בדשבורד/התראה), הפאונדר מדווח דרך `atlas campaign revenue record`.

---

## 5. Spending / External-Action Boundary

| פעולה | קיימת ב-M1? |
|---|---|
| הוצאה כספית | **לא, מבנית** — `amount_threshold` ברירת-מחדל `0.0`; אין Task ב-שרשרת-M1 עם עלות-לא-אפס; Autonomous Reinvestment Budget (M2) **עדיין לא בנוי**. |
| פרסום חיצוני | **לא ע"י ATLAS** — `CampaignExecutionAgent.run()` מחזיר במפורש בקשה לפעולה-ידנית. אין `ContentPublisher` ממומש בשום מקום. |
| Commitment | רק דרך הפאונדר: הסכם-affiliate שהוא **כבר** מביא מבחוץ — ATLAS לא יוזם/מנהל משא-ומתן. |
| שינוי-חשבון | **לא קיים בקוד כלל** — כל מתודות ה-Provider הן GET בלבד (`getUserInfo`/`listPurchases`/`listMarketplaceEntries`/`getMarketplaceEntry`/`listProductTypes`) — אין create/update/delete. |
| פעולה בלתי-הפיכה | הפוסט-הידני-של-הפאונדר בלבד — **מחוץ לגבול-הפעולה של Design Plan זה**, לא מאושר/מבוצע-אוטומטית כאן. |
| Marketplace observation (CDP) | **Observe-only, לא-משנה-state** — ר' §2א. `cdp_url` attach לפרופיל-ייעודי-בלבד; אין click/input/submit/promote/שינוי-חשבון בזרימה הזו; `BrowserHands` לא בשימוש. |

**שום פעולה מהטבלה אינה מאושרת במסגרת Design Plan זה.** כל מה ש-ATLAS מבצע אוטומטית ב-M1 נשאר פנימי, הפיך, וללא-עלות.

---

## 6. Definition of Done

1. **Opportunity/Campaign עברו בשרשרת** — `AffiliateOpportunity` אמיתי ב-`selected_for_marketing`, `Campaign` אמיתי (`atlas campaign show <id>`), `ExecutionPlan` שהגיע ל-`request_founder_review`→approved→dispatch ל-`CampaignExecutionAgent` (`atlas campaign execution show <plan_id>`).
2. **פעולה חיצונית אמיתית התרחשה — שני evidence-types נפרדים, לא אחד**:
   **א. External evidence שהמכירה קרתה בפועל** — רשומה חדשה, אמיתית, ב-`atlas affiliate digistore24 sales` (`listPurchases`, read-only) **ו/או** התראה/דשבורד אמיתיים מ-Digistore24 עצמה. זו ראייה **חיצונית, בלתי-תלויה ברישום הידני**.
   **ב. Manual recording לתוך ATLAS** — `atlas campaign revenue record` (סעיף 3 למטה). **זו לא אותה ראייה** — M1 לא "מוכיח Revenue Loop" רק כי מספר הוזן ידנית; שני הרכיבים נדרשים יחד.
3. **₪1+/שווה-ערך הכנסה אמיתית** — `atlas campaign revenue record <campaign_id> <amount>` עם סכום **אמיתי**, לא בדיקה, **לאחר** ראיית ה-external evidence מסעיף 2א.
4. **נקלט במנגנוני המדידה** — `revenue_<goal_id>` ב-`KPIRegistry` (`atlas brain kpi list`) **וגם** `LedgerEntry` אמיתי (`kind=revenue_claimed`) ב-`Ledger`.
5. **Traceability — internal מול external, מובחן במפורש**:
   - **Internal linkage (קיים, מספיק ל-DoD הקנוני)**: אותו `goal_id` מקשר Campaign→Ledger לאורך כל השרשרת, נפתר אוטומטית דרך `_resolve_campaign_goal_id` — bookkeeping פנימי תקין, לא override ידני.
   - **External campaign-level attribution — נבדק בקוד, המסקנה: אינו קיים כרגע.** `validate_link()`/`create_affiliate_opportunity_from_terms()` מקבלים `real_affiliate_link` כמחרוזת שהפאונדר מספק ידנית — שום קוד ב-ATLAS לא מייצר/מוסיף sub-id/tracking-parameter/campaign-id ייחודי לקישור, ואין מימוש ל-`createBuyUrl` (המתועד כשם-מתודה אמיתי ב-Digistore24, אך **לא ממומש כאן**). `fetch_recent_sales()`/`listPurchases()` מחזירה רשומות-גולמיות שהשדות המדויקים שלהן **מעולם לא נצפו** (חשבון ריק עד כה) — לא ניתן להניח מראש שהן כוללות שדה-ייחוס-קמפיין.
   - **המשמעות ל-DoD**: M1 יכול **ביושר** להוכיח *"real revenue exists, real-world-verified"* — אך **לא** *"this specific revenue came, verifiably, from this specific ATLAS campaign"* מעבר לטענת-הפאונדר עצמו (מי שמזין את `campaign_id` ב-`revenue record`). **ה-DoD הקנוני (`ROADMAP_PROPOSAL.md`) אינו דורש אימות-חיצוני-קריפטוגרפי לקישור** — רק "ניתן לקישור לפעולה/קמפיין", המתקיים כבר ברמה-הפנימית. **לכן: אין צורך בתיקון-Design לפני GO** — אך זו מגבלה אמיתית שיש לתעד במפורש, לא להניח שהיא חזקה יותר משהיא. **מיטיגציה תפעולית מומלצת (לא Design, לא קוד)**: להריץ קמפיין-אמיתי-פעיל יחיד בלבד בזמן הוכחת-M1, כך שכל מכירה אמיתית בחשבון בתקופה הזו ניתנת-לייחוס-בוודאות-גבוהה בהיסק-שלילה (elimination), לא רק בהצהרה.
6. **Founder-intervention baseline — תוקן מול ה-flow האמיתי בקוד** (M3/`revenue_strategy.commit_ready_opportunities()` **מחייב במפורש** commit אוטומטי, ללא בחירת-הזדמנות אנושית — "never a re-choice", per `business_plan_advance.py`'s own docstring). **הרשימה המדויקת, לפי ה-flow בפועל**:
   1. `atlas brain approve <terms_task_id>` — אישור הבקשה לספק תנאים מסחריים (`affiliate_commercial_terms_needed`, ב-`ALWAYS_REQUIRES_APPROVAL`).
   2. `atlas affiliate commercial-terms supply <task_id> --commission --link --provider` — אספקת התנאים האמיתיים בפועל.
   3. `atlas brain approve <request_founder_review_task_id>` — אישור-תוכן-הקמפיין לשחרור (השלב `request_founder_review` ב-`ExecutionPlan`).
   4. פרסום-ידני אמיתי (לא CLI — פעולה בעולם האמיתי).
   5. `atlas campaign revenue record <campaign_id> <amount>` — רישום ההכנסה האמיתית.
   **"בחירת-הזדמנות" אינה מתרחשת בפועל ב-M1 — הוסרה מהרשימה.** יצירת/הפעלת ה-Campaign עצמו (בין שלב 2 ל-3) היא **אוטומטית**, לא פעולת-פאונדר (per `campaign_advance.py`: "internal, reversible, zero-cost workflow transition... never routed through RiskPolicy").

**ראיה נוספת, לא-טריוויאלית**: ה-`check_measurement` step מגיע ל-`done` וה-Campaign ל-`status="completed"` **אוטומטית**, בתיק הבא אחרי הרישום — זו ההוכחה שהלולאה **נסגרה**, לא רק שמספר הופיע איפשהו.

---

## 7. Failure Modes

| שלב | כשל אפשרי | סיווג | תגובת ATLAS |
|---|---|---|---|
| Verify | credential לא-תקף/פג | External credential issue, **לא** כשל-ATLAS | `Digistore24APIError` נזרקת בקול, לא נבלעת |
| Verify/Sales | endpoint/schema השתנו מאז שנכתב | External API drift | `Digistore24APIError` עם רמז ("אם 404, נתיב אולי השתנה") |
| Discovery | `listMarketplaceEntries` מחזיר 0 | **תקין, לא כשל** | הודעה מפורשת: "צפוי לחשבון-affiliate-בלבד" |
| Terms | אין הסכם/מוצר אמיתי מאושר | External approval pending | חוסם רק את שלב-הפאונדר; לא כשל-קוד |
| Publishing | הפאונדר לא מפרסם | Awaiting founder action | הקמפיין נשאר לא-completed, נראה בבירור |
| Sale | אין מכירה אמיתית | **תוצאה אמיתית ותקינה**, לא כשל | `check_measurement` נשאר blocked עם סיבה-מוסברת, לא "נכשל" |
| Recording | מכירה קרתה, הפאונדר שכח לרשום | Process gap, לא Code bug | Ledger/KPI לא-מעודכנים עד לרישום ידני |
| Attribution | מכירה משויכת בטעות | Founder-input error, לא שחיתות-שקטה | `goal_id`/`campaign_id` נדרשים במפורש, לא מנוחשים |
| CDP Attach | הפרופיל-הייעודי לא זמין/remote-debugging לא מופעל | External setup issue, לא כשל-ATLAS | חיבור נכשל בקול; אין fallback לפרופיל-אחר |
| Redirect | ניווט מוביל לדומיין לא-מאושר | **תפוס ע"י ה-wrapper — fail-closed** | עצירה מיידית, לא ממשיך עם תוכן-לא-מאושר |
| Target mismatch | ה-target הפעיל בפועל שונה מהצפוי | Safety-check תפס פער אמיתי | אין extraction/screenshot — עצירה, לא ניחוש |

---

## 8. Stop Conditions

- לפני כל קריאה חיצונית: **test baseline unchanged / no new regressions** — לא "pytest -q ירוק" (זו דרישה שגויה: יש 6 כשלים ידועים, קיימים-מראש, לא-קשורים ל-M1). **Baseline מאומת כרגע (2026-08-13, הרצה מקומית, ללא שינוי-קוד)**: `1515 passed, 6 failed (test_affiliate_intelligence_agent.py×4, test_ceo.py×2 — אותם כשלים ידועים), 68.74s`. M1 חסום רק אם המספר חורג מ-baseline זה (פחות passed, יותר failed, או כשל חדש שאינו אחד מששת הידועים) — לא בגלל ששת הכשלים עצמם.
- לפני `verify`: GO מפורש **נפרד**, לא חלק מ-"אישור M1 הכללי" — זו הקריאה-האמיתית-הראשונה.
- אם `verify_connection()` זורקת `Digistore24APIError`: עצירה, דיווח, **לא** ניסיון-חוזר-עיוור.
- לפני הפרסום-הידני: אימות ש-`request_founder_review` אושר בפועל (`atlas campaign execution show`), לא הנחה.
- שום מספר-הכנסה לא נרשם ללא אישור-אמיתי-מפורש של הפאונדר על מכירה שקרתה בפועל.
- כל שלב עוצר אם ה-GO נשלל — אין המשך-אוטומטי בין שלבים.

---

## 9. Rollback / Cleanup

- קריאות read-only (`verify`/`sales`/`marketplace`) — **לא יוצרות state חיצוני כלל.** אין מה לנקות.
- State פנימי (`.atlas/*.json`) — הפיך: מחיקת-רשומות ידנית, או (מומלץ) הרצת-הבדיקה כולה בתיקיית-`.atlas` מבודדת תחילה — אותו משמעת שכבר קיימת בפרויקט (landing_page_dir injection, test-isolation ל-CampaignRegistry).
- הפעולה החיצונית היחידה (הפוסט-הידני) — rollback דרך הפאונדר עצמו על הפלטפורמה שבחר; ATLAS לא מתווך ולא אחראי על ניקוי כאן.
- Campaign שנוצר בטעות — `set_status("cancelled")` הקיים, לא מחיקה-הרסנית.
- **Marketplace observation (CDP)** — `cdp_url` attach לא יוצר/משנה שום state בצד-Digistore24 (observe-only). הפרופיל-הייעודי עצמו הוא נכס-של-הפאונדר, לא של ATLAS — ניקוי/סגירה שלו (אם בכלל נדרש) בשליטת-הפאונדר בלבד, לא באחריות-ATLAS.

---

## 10. Founder Checklist — לפני GO נפרד ל-M1 Implementation

1. אישור שה-`DIGISTORE24_API_KEY` הקיים בסביבה הוא המפתח **הנכון והעדכני** (אומת קיום בלבד כאן, לא תוקף).
2. GO מפורש ונפרד לקריאת ה-`verify` הראשונה (הפעולה-החיצונית-הראשונה בפועל). **בוצע 2026-08-13 — הצליח.**
3. הסכם-affiliate אמיתי, קיים ומאושר מול Digistore24, לפחות למוצר אחד.
4. אישור-נכונות לבצע את הפעולה הידנית היחידה ש-ATLAS לא יכול: פרסום בפועל.
5. החלטה על ערוץ-הפרסום הריאלי (איפה בדיוק יפורסם).
6. התחייבות לדווח (דרך CLI) את התוצאה האמיתית — מכירה או אי-מכירה — ביושר.
7. **Precondition מחייב, נקבע 2026-08-13 — Least Privilege**: `verify` (2026-08-13) חשף `api_key_permissions: "writable"` — היקף רחב-יותר-ממה-ש-ATLAS-משתמש-בו-בפועל (כל מתודות `Digistore24Provider` הן GET/retrieval בלבד, אין נתיב-כתיבה אחד בקוד). עקרון-הכרעה: **"Technical capability ≠ granted authority"** — ATLAS צריך את ה-least-privilege הדרוש למשימה, לא את המקסימום שהמפתח מאפשר. **לפני GO ל-M1 Execution המלא (לא לפני קריאות read-only בודדות נוספות מאותה מחלקה)**: יש להחליף את `DIGISTORE24_API_KEY` ל-**API key חדש בהרשאת `readonly`** (Digistore24 תומך בכך במפורש — `readonly`/`writable`/`developer`, מאומת חיצונית 2026-08-13), ולאמת מחדש עם קריאת `verify` יחידה. **טרם בוצע** — יצירה/החלפה/ביטול/rotation של key **לא אושרו** בשום שלב עד כה; זו פעולה נפרדת, ממתינה לביצוע-הפאונדר, לפני (לא כחלק מ-) שלב-ה-validation הנוכחי.
8. **Precondition מחייב נוסף, נקבע 2026-08-13 — Marketplace Discovery (ר' §2א)**: ביצוע Founder Setup Sequence המלא (§2א) — פרופיל-דפדפן ייעודי, remote-debugging, login עצמאי, ניווט ל-Marketplace, אישור שהפרופיל ריק-מכל-דבר-אחר. **טרם בוצע** — שום `cdp_url`/browser action לא אושרו/בוצעו עד כה.
9. GO נפרד וסופי ל-M1 Implementation/Execution, אחרי כל הנ"ל **וכולל** סעיפים 7-8.

---

**סטטוס:** Design Plan לבדיקה. שום קוד לא נכתב. שום קריאת-API אמיתית לא בוצעה. M1 לא נפתח.
