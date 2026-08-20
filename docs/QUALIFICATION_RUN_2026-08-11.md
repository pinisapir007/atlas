# ATLAS Qualification Run #1 — 2026-08-11

**מסגרת:** `docs/ATLAS_QUALIFICATION_FRAMEWORK.md`
**מטרה:** לא להוכיח ש-ATLAS מושלם. לחשוף את האמת — מה עובד, מה חסר, ולמה.
**תוצאה:** הצלחה מתודולוגית מלאה. ההרצה הבחינה בבירור בין כשל תשתיתי לכשל קוגניטיבי — ATLAS חקר, אסף ראיות, ויצר מאות Findings אמיתיים; שכבת החיבור בין המחקר ל-Brain לא הייתה עקבית. זו בעיית ארכיטקטורה, לא בעיית חשיבה.

---

## הרצה בפועל

Goal אמיתי אחד: *"אתה המנכ"ל של החברה. המטרה שלך היא לבנות דרך אמיתית להגיע להכנסה של $100,000..."* — `CEOBrain` אמיתי, `Registry` אמיתי (כולל `research_discovery`), בתיקיית scratch מבודדת. 25 `tick()` אמיתיים, 680.8 שניות, ללא קריסה. ללא התערבות ידנית באמצע (Principle of Honest Evaluation).

## Qualification Report — טבלה מובנית

| # | יכולת/קריטריון | תוצאה | מקור | הפניה לקוד |
|---|---|---|---|---|
| 1 | חיפוש אמיתי מוצא מקורות אמיתיים | ✓ עבר — 260 Findings אמיתיים, ממוקורים, על פני קטגוריות מרובות | מנגנון מערכת אמיתי | `assets/research_discovery/agent.py` |
| 2 | שער איכות ראיות (fact vs. opinion) פעיל תחת עומס | ✓ עבר — `evidence_validation` שער כל דיווקה בפועל | מנגנון מערכת אמיתי (Milestone 0 legacy, מחובר היום) | `brain/evidence_validation.py` |
| 3 | Exploration Gate מונע נעילה מוקדמת | ✓ עבר — לא נבדק verdict "invest" בטרם רוחב מספק (לא הגענו לזה כלל בגלל #7) | מנגנון מערכת אמיתי | `brain/discovery/exploration_gate.py` |
| 4 | Research Trigger יוזם מחקר ביקוש | ✓ עבר — 42 משימות `request_research` אמיתיות נוצרו ונשלחו | מנגנון מערכת אמיתי | `brain/discovery/research_request.py` |
| 5 | יציבות תשתיתית לאורך זמן | ✓ עבר — 25 ticks רצופים, ללא קריסה, ללא תקיעה | תצפית ישירה | — |
| 6 | דירוג משווה בין קטגוריות + נימוק ("Business Standings Map") | **Backlog — אינו קיים כיום** | לא נבדק (מעולם לא נבנה) | פער ידוע מראש |
| 7 | חיבור בין Task דרך Registry.dispatch() ל-KnowledgeBase האמיתי שהמוח קורא ממנו | **Backlog — פער אמיתי, לא ידוע מראש; התגלה בהרצה** | — | `core/registry.py` (lazy instantiation, ללא DI) |
| 8 | סטטוס "done" משקף תוצאה אמיתית ברמת המשימה הבודדת | **Backlog — פער אמיתי, קיים בכל המערכת (לא ייחודי ל-Milestone 1)** | — | `brain/monitor.py` (`report()` הוא אגרגטיבי, לא per-task) |
| 9 | Planner לא יוצר משימות כפולות ללא הגבלה | **Backlog — פער אמיתי, קיים מראש** | — | `brain/planner.py` |
| 10 | Decision Engine מגיע לverdict אמיתי (invest/propose_capability/וכו') | **לא נבדק בפועל** — נחסם על ידי #7 (ה-KnowledgeBase שה-Brain קרא ממנו נשאר ריק) | — | תלוי בסגירת #7 |

## הממצא המרכזי

ההבחנה בין **כשל תשתיתי** (#7, #8, #9 — "צנרת" שלא מחוברת נכון) לבין **כשל קוגניטיבי** (שאלה שלא נבדקה כי לא הגענו אליה) — היא-היא התוצר המרכזי של ההרצה. בלי הרצת Qualification אמיתית, ההבחנה הזו לא הייתה אפשרית.

## תקרית נתוני ייצור — נמצאה, טופלה, מתועדת

260 Findings אמיתיים נכתבו בטעות ל-`.atlas/knowledge.json` הייצורי (ראה סעיף #7 למעלה — הסיבה המדויקת). זוהה, נחקר, ותוקן באותו יום:
- הרשומות המלאות נשמרו לצמיתות: [`docs/qualification_runs/run_2026-08-11_research_discovery_findings.json`](qualification_runs/run_2026-08-11_research_discovery_findings.json) (260 Findings, בדיוק כפי שנוצרו).
- `.atlas/knowledge.json` הייצורי נוקה — הוחזר ל-41 ה-Findings המקוריים בלבד, `success_laws` לא נגע.
- אומת: 0 רשומות `research_discovery` בייצור, 41 Findings + 3 SuccessLaws תקינים.

## Backlog — ארבעה פערים, לתעדוף משותף (לא תוקנו)

1. **Dependency Injection דרך Registry** — הגורם השורשי הסביר ביותר, כי הוא זה שיצר גם את #2 (תקרית הנתונים) וגם חוסם את #10 (Decision Engine מעולם לא נבדק בפועל).
2. **Task Result Propagation אמיתי** — `report()` אגרגטיבי, לא per-task, בכל המערכת.
3. **Business Standings Map** — לא נבנה, לא נבדק כי לא הגענו לשלב Decision.
4. **Planner Deduplication** — גדילה בלתי-חסומה של משימות לאורך ticks.

**סטטוס Run #1:** נותח. Root Cause Analysis זיהה קשר סיבתי אמיתי אחד בלבד: #7 → #10. #2, #6, #9 עצמאיים, לא תלויים ב-#7.

---

## Qualification Run #2 — 2026-08-11 (אותו יום), השערה מבודדת אחת בלבד

**תיקון שבוצע לפני ההרצה (רק #7, שום דבר נוסף):** `Registry` קיבל פרמטר `instances` חדש המאפשר לזרוע מופע Asset מוכן מראש, במקום בנייה עם ברירות מחדל. `CEOBrain` נבנה מחדש כך שכאשר `registry` לא מסופק במפורש, הוא בונה `Registry` שזורע את `research_discovery` עם `self.knowledge` שלו עצמו — לראשונה, ה-Agent וה-Brain חולקים בפועל את אותו KnowledgeBase. 1440/1440 בדיקות עוברות. (תוקנה גם, בנפרד, טעות encoding שלי מהניקוי אתמול — `ensure_ascii=False` שברה קריאה בקידוד ברירת המחדל של המערכת; תוקן לעקוב אחר `write_json_atomic()` המקורי.)

**השאלה היחידה שההרצה הזו נועדה לענות עליה:** האם Decision Engine מנמק נכון כשהוא באמת מקבל ראיות אמיתיות — שאלה שמעולם לא נבדקה ב-Run #1.

**תוצאה: כן, באופן ברור ועקבי.**

- 65 Findings אמיתיים (5 לכל אחת מ-13 קטגוריות) הופיעו הפעם ב-KnowledgeBase **שה-CEOBrain בפועל קורא ממנו** — התיקון עבד.
- שער הרוחב עבר (13 ≥ 5), Decision Engine קיבל verdicts אמיתיים על פני כל 13 הקטגוריות.
- **4 קטגוריות עם ערוץ אמיתי** (affiliate, content, digital_product, recruitment) → `invest` בסבב הראשון (Goal+Task אמיתיים נוצרו, כולל דלגציה אמיתית ל-`affiliate_pipeline`/`revenue_content_assets`/`revenue_digital_product`/`revenue_recruitment_leads`), ואז **נכון** `already_invested` בסבבים הבאים — לא נוצרה כפילות.
- **9 קטגוריות ללא ערוץ אמיתי** (community, ecommerce, email_marketing, instagram, marketplace, saas, tiktok, ugc, youtube) → `propose_capability` בסבב הראשון (9 Proposals אמיתיים, `pending_approval`, נכון גם שער הסיכון החל אוטומטית), ואז **נכון** `already_proposed` בסבבים הבאים — שוב, ללא כפילות.
- 25 ticks, 332.4 שניות, ללא קריסה.

**המשמעות:** לא רק ש-Decision Engine "עבד" — הוא הפגין את בדיוק ההתנהגות שתוארה בקוד אך מעולם לא אומתה חי: אנטי-כפילות (`already_invested`/`already_proposed`), הבחנה נכונה בין קטגוריות עם/בלי ערוץ ביצוע אמיתי, ושער סיכון אוטומטי על `create_asset`. #10 עובר מ"לא נבדק" ל**"נבדק, ועבר."**

**תצפית צדדית, לא ההשערה של ההרצה הזו, לא "מתוקנת" כעת:** `general: 109` משימות — #9 (Planner Deduplication) עדיין קיים, אף חמור יותר (יותר Goals פעילים = יותר משימות כפולות לכל tick), בדיוק כפי שחזתה מפת התלות: אינו תלוי ב-#7, לא נפתר על ידי תיקונו.

**סטטוס: #7 סגור ומאומת. #10 נבדק לראשונה ועבר. #2, #6, #9 נשארים כפי שהיו — לא תוקנו, לא ייעלמו מעצמם.**
