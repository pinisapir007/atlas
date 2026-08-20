# Roadmap — M1–M10 (Canonical, Approved)

**תאריך אישור סופי:** 2026-08-13
**מקור בלעדי:** `docs/CAPABILITY_CONSOLIDATION.md` (נעול 2026-08-13, Approved Baseline — 11 יכולות-על A-K, ASIF, Governance, Autonomous Reinvestment Budget, Debt Ownership Workflow — 8/8 שאלות הוכרעו, Final Coherence Review PASS).
**שרשרת-הרחבה (traceability מלאה)**: המסמך הזה עבר שני סבבים: (1) הצעה ראשונית של 7 Milestones, מבוססת-קוד-וארכיטקטורה בלבד. (2) `docs/PRE_ROADMAP_BUSINESS_ARCHITECTURE_RESEARCH.md` (מחקר חיצוני, 12 משפחות revenue-engine, ניתוח Digital Influencer ייעודי, source-quality check) + `docs/ROADMAP_RECONCILIATION_M4_M7.md` (reconciliation מלא, כולל M7's Trust/Integrity-Tests/Audience-Listening) — שניהם הרחיבו את M4-M7 המקוריים ל-M4-M10 הנוכחיים. שני המסמכים **נשארים, לא נמחקים** — הם ההיסטוריה/הנימוקים המלאים מאחורי הצורה הנוכחית.

**🔒 סטטוס: נעול 2026-08-13 — Roadmap מאושר.** M1–M10, כולל dependencies ו-parallelism, אושרו ע"י הפאונדר. **אישור ה-Roadmap אינו אישור להתחיל Implementation.** שום קוד לא נכתב. M1 לא נפתח.

**⚠️ הצלבה קריטית עם מסלול-תכנון שני (נוספה 2026-08-17, ONE BRAIN Root Implementation Audit)**: קיים Roadmap שני, נפרד, `docs/BUSINESSMAN_V1_SOURCE_OF_TRUTH.md` (מספור **Milestone 1-7**, שונה לגמרי מ-**M1-M10** כאן), ננעל יום קודם (2026-08-12). שני המסמכים **לא מאוחדים**. עבודת "M1 Marketplace Discovery" (Digistore24/Marketplace, כולל Cognitive State Wiring וה-ONE BRAIN implementation) שייכת למסלול **הזה (M1-M10)**, לא ל-Milestone-1-7 של המסמך השני. `atlas.brain.opportunity_advance.advance_opportunities_from_findings()` (Bridge 1) הוא הצינור-הכתיבה-היחיד המאושר ל-`atlas.brain.models.Opportunity` בשני המסלולים גם יחד.

**המטרה של ה-Roadmap הזה אינה "לסיים את כל הרשימה".** המטרה: להביא את ATLAS בהדרגה למצב שבו הוא **discovers → evaluates → experiments → decides → executes → earns → measures → learns → reinvests → scales**, עם מעורבות-פאונדר שקטנה בהדרגה בפעולות השגרתיות ככל שהמערכת מוכיחה את עצמה.

**עקרונות-סדר שהופעלו** (לא A→K, לא רשימתי): dependencies אמיתיים, ערך-עסקי (מאומת גם במחקר-חיצוני), דרישת-bootstrap, סיכון, ומהירות-הגעה ללולאה עסקית עובדת. הרחבת-תשתית-קיימת הועדפה על מערכת-מקבילה בכל מקום. I גדלה רק כשמורכבות אמיתית מצדיקה. J אינו Milestone — נשאר Debt Track עם Debt Alarm בכל שער-Milestone (per §6א). Evidence→hypothesis→proof ו-Governance נשמרים כתביעה חוצה בכל Milestone.

---

## Milestone 1 — Close the Bootstrap Loop: Zero-to-First-Revenue, Founder-Minimal

**1. מטרה עסקית**: להוכיח, בפעם הראשונה מקצה-לקצה עם כסף אמיתי, ש-ATLAS יכול לזהות → להעריך → להחליט → לבצע → **להרוויח בפועל** הזדמנות existing-market, כמעט-בלי-הון, עם מעורבות-פאונדר מצומצמת לשערי-מבנה בלבד (לא ניהול-שוטף).

**2. Capabilities מקודמות**: **F** (בעיקר — Cashflow & Monetization), **C** (צד-השוק-הקיים, כבר מוכח), **D** (הערכה, כבר קיים), **G** (ביצוע, כבר קיים), **H** (במצבו הבסיסי הקיים — לא ההרחבה, זו M2).

**3. למה כאן ולא מוקדם/מאוחר יותר**: זה כבר **הכי-קרוב-לגמור** מכל היכולות (F "קיים ברובו" per §2F) — כל שרשרת ה-affiliate/Campaign/Orchestrator/Ledger בנויה ונבדקה. מאומת גם חיצונית: Affiliate הוא היחיד (עם Digital Products) המשיג ציון-גבוה בו-זמנית על הון-נמוך+מהירות+autonomous-fit+parallel-fit. דחיית זה למאוחר-יותר הייתה דוחה את הרגע שבו ATLAS בכלל מוכיח שהוא עסק עם כסף אמיתי. זה חייב לבוא **ראשון**.

**4. מה כבר קיים**: שרשרת ה-affiliate המלאה (`affiliate_department`/`affiliate_intelligence` → `content_factory` → `editorial_review` → `publishing_gateway`/`creative_agent`), `Campaign`/`atlas.orchestrator`, `Ledger`/`KPIRegistry`, `atlas affiliate revenue/cost/settlement record`, אינטגרציית Digistore24 (`verify_connection()`, `fetch_recent_sales()`) — בנויה, נבדקה עם mocks, **טרם אומתה עם קריאה אמיתית אחת**.

**5. מה באמת חסר**: **לא בנייה — אימות אמיתי**. (א) קריאה אמיתית אחת ל-`atlas affiliate digistore24 verify` עם credential אמיתי. (ב) הרצת מחזור-קמפיין מלא אחד עד סוף אמיתי — כולל מכירה אמיתית ורישום-הכנסה אמיתי. (ג) ספירת-פעולות-פאונדר אמיתית לאורך המחזור, כ-baseline.

**6. Definition of Done (observable)**: לפחות ₪1 הכנסה אמיתית, מפלטפורמה חיצונית אמיתית, רשומה ב-`Ledger` דרך השרשרת המלאה הקיימת — לא הדגמה, לא mock. **המחזור מוכיח את הדפוס הגנרי (discover→evaluate→decide→execute→earn→record) עם ספק-אמיתי-ראשון אחד — Digistore24 אינו התקרה הקבועה, רק ההוכחה הראשונה.** מספר-אישורי-הפאונדר לאורך המחזור המלא מתועד ומפורסם כ-baseline.

**7. Dependencies**: אין — משתמש רק בתשתית קיימת.

**8. סיכונים עיקריים**: הנחות ה-API של Digistore24 (header/base-URL) לא מאומתות — כשל כאן הוא מידע (`Digistore24APIError` בנוי לכשל-רועש), לא אסון.

**9. מה במפורש אינו נבנה כאן**: שום capability חדשה. לא E, לא C-extension, לא K, לא H-הרחבה. זה verification+hardening טהור.

---

## Milestone 2 — Governance Economic Proportionality + Autonomous Reinvestment Budget

**1. מטרה עסקית**: לתת ל-ATLAS יכולת **לבצע השקעה-חוזרת אוטונומית אמיתית** מתוך כסף שהוא עצמו הרוויח (M1), בתוך מסגרת-מדיניות שהפאונדר קבע — בלי שכל פעולה כספית תעצור אצל הפאונדר.

**2. Capabilities מקודמות**: **H** (בעיקר — Economic Risk Proportionality + Autonomous Reinvestment Budget, §4.7א/4.7ב), **I** (פרוסה מינימלית — "כסף/תקציבים/commitments", מופעל-מהיום-הראשון per §4.9).

**3. למה כאן ולא מוקדם/מאוחר יותר**: לפני M1 אין כסף אמיתי לשקול ביחס אליו. זהו ה-unlock הקריטי למניעת Founder Bottleneck — חייב לבוא מוקדם, מיד אחרי שיש דבר אחד אמיתי לשקול ביחס אליו. מאומת חיצונית: reinvest-profits הוא בדיוק פלייבוק-bootstrap הסטנדרטי (Mailchimp/Basecamp/GitHub).

**4. מה כבר קיים**: `RiskPolicy.evaluate()` (ארבעת צירי-הסיכון), `amount_threshold` (סף אבסולוטי קבוע), `Ledger`/`KPIRegistry`, `cashflow.profit()`/`roi()`.

**5. מה באמת חסר**: (א) פונקציית-נתון אמיתית ב-I: זמין/committed/reserved/ceiling. (ב) הרחבת `RiskPolicy` ליחסיות-כלכלית (ציר-סכום בלבד). (ג) "30%" כ-Founder Policy משתנה. (ד) חישוב aggregate exposure אמיתי.

**6. Definition of Done (observable)**: פעולה קטנה-יחסית מתבצעת בלי אישור-פרטני, בתוך ceiling, מתועדת מלאה. פעולה בלתי-הפיכה זהה-בסכום — עדיין עוצרת. חריגת-aggregate — עוצרת.

**7. Dependencies**: M1.

**8. סיכונים עיקריים**: 30% שרירותי — מוקטן בהיותו Founder Policy מוצהרת. חישוב-aggregate שגוי — מוקטן בהגדרה מפורשת מראש.

**9. מה במפורש אינו נבנה כאן**: mandates עשירים, עומק-I מלא (זה M10), שינוי לצירי reversible/privileged/legal.

---

## Milestone 3 — K: Attention / Prioritization / Salience (Minimum Viable, Cross-Domain)

**1. מטרה עסקית**: שנפח-פעילות גדל בלי שהפאונדר מוצף — ואירוע דחוף לא נבלע בתור.

**2. Capabilities מקודמות**: **K** (בעיקר — בנייה ממשית ראשונה של יכולת שהיום מפוצלת).

**3. למה כאן ולא מוקדם/מאוחר יותר**: לפני M1 אין נפח לתעדף; לפני M2 אין תור מסונן-ע"י-H לתעדף (§4.8). מיד-אחרי M2 — שניהם קיימים. מאומת חיצונית: כל משפחת-revenue שנבדקה נהנית מ-parallel-experiments — ה-K נדרשת אף יותר ברגע שיש כמה מנועים אמיתיים, לא רק כמה Opportunities בתוך אחד.

**4. מה כבר קיים**: `Prioritizer`, `Strategist.reallocate()`, `MAX_CONCURRENT_COMMITMENTS` — שלושה מנגנונים נפרדים, top-down בלבד.

**5. מה באמת חסר**: איחוד cross-domain; bottom-up salience/interrupt (לא קיים כלל); תיקון urgency-מבוסס-גיל.

**6. Definition of Done (observable)**: סדר-תעדוף שונה מסדר-יצירה, מוסבר. Finding סינתטי דחוף מוכח כקוטע את הסדר.

**7. Dependencies**: M1, M2.

**8. סיכונים עיקריים**: תיעדוף-שגוי פוגע באמון, לא בבטיחות (H ממשיכה לגייט ללא-תלות ב-K).

**9. מה במפורש אינו נבנה כאן**: A's proactive-outreach (זה M9). שינוי בסמכות ה-Decision/Gate עצמן.

---

## Milestone 4 — E: Experimentation / Pilot / Learning (Minimum Real Pilot)

**1. מטרה עסקית**: לבדוק hypothesis שאינה מוכחת עדיין בפיילוט קטן-זול-נשלט, ולסגור בפעם הראשונה את לולאת ה-ASIF (`evidence → factors → hypothesis → experiment → outcome → learning`) מקצה לקצה.

**2. Capabilities מקודמות**: **E** (בעיקר — כמעט לא-קיימת היום).

**3. למה כאן ולא מוקדם/מאוחר יותר**: E תלויה טכנית רק ב-D/G (קיימים). אך פיילוט הוא פעולה-בעולם-האמיתי עם עלות — לפני M2, כל פיילוט היה נתקע מאחורי אישור-פרטני. אחרי M2, E הופכת מ-"רעיון" ל-"כלי שימושי בפועל". הערך המיידי ביותר: בדיקת הזדמנויות existing-market לא-ודאיות (כבר יש ערוץ-מימוש דרך M1) — לא צריך לחכות ל-C-extension.

**4. מה כבר קיים**: `G`/orchestrator, `D`/`decide()` (מייצר `insufficient_evidence`), `SuccessLaw`'s track-record.

**5. מה באמת חסר**: מנגנון שלם `insufficient_evidence`→עיצוב-בדיקה→ביצוע-דרך-G→תוצאה-אמיתית→עדכון-`SuccessLaw`. אין Task category ל-E כלל היום.

**6. Definition of Done (observable)**: hypothesis מסומן `insufficient_evidence` עובר פיילוט אמיתי, תוצאה מדודה משנה confidence עתידי בפועל.

**7. Dependencies**: D, G (קיימים). נהנית מ-M2, לא חוסמת בלעדיו.

**8. סיכונים עיקריים**: פיתוי להתייחס לתוצאה-חלקית כ-proof — מנוגד ל-§4.4. מוקטן בהגדרה מפורשת מראש.

**9. מה במפורש אינו נבנה כאן**: פיילוטים על הזדמנויות C-extension (עוד לא קיימות).

---

## Milestone 5 — Minimal Real Commerce Unlock (Digital Products / Storefront)

**נוסף בעקבות מחקר (`ROADMAP_RECONCILIATION_M4_M7.md` §4), נשלף מ-"Future Improvements".**

**1. מטרה עסקית**: לפתוח, דרך אינטגרציית-credential אחת (storefront+payment), שלוש משפחות revenue בבת-אחת: Digital Products, Subscriptions, E-commerce-קל — כל אחת ללא-מלאי-משמעותי.

**2. Capabilities מקודמות**: **F** (מכשיר מונטיזציה נוסף מעבר ל-affiliate), נהנית מ-**I**'s פרוסת-כסף/תקציבים (M2).

**3. למה כאן ולא מוקדם/מאוחר יותר**: מחקר חיצוני מצא ש-Digital Products הוא המשפחה השנייה-הכי-מוכנה-ל-bootstrap אחרי Affiliate (הון כמעט-אפס, margin 90-95%, לא תלוי-publishing). דורש M2 כדי לממן את עלות-האינטגרציה ולתת ל-ניסויי-מוצר לרוץ בלי אישור-פרטני-לכל-ניסוי.

**4. מה כבר קיים**: `content_factory`'s generation דטרמיניסטי-חינמי (יכול לייצר תוכן-מוצר), `Ledger`/`KPIRegistry` כללי.

**5. מה באמת חסר**: אינטגרציית storefront/payment-processor אמיתית אחת (פלטפורמה אחת), מנגנון-רישום/מכירה אמיתי (הרחבת `atlas.integrations` — `CommerceProvider`-style, לא Protocol חדש).

**6. Definition of Done (observable)**: מוצר דיגיטלי אחד אמיתי, נמכר תמורת תשלום אמיתי, בלי מלאי, רשום ב-Ledger.

**7. Dependencies**: M2.

**8. סיכונים עיקריים**: מדיניות-פלטפורמה/payment-processor — מוקטן ע"י בחירת פלטפורמה קלה-ל-multi-home, לא התחייבות-בלעדית.

**9. מה במפורש אינו נבנה כאן**: fulfillment פיזי/POD אמיתי (נשאר Future). מחזורי-חיוב-מנוי (follow-on לאחר שמכירה-חד-פעמית עובדת).

---

## Milestone 6 — Minimal Real Publishing Unlock (Content Distribution)

**נוסף בעקבות מחקר, נשלף מ-"Future Improvements", מוגבר-עדיפות — נמצא כה-unlock עם המינוף הגבוה ביותר בכל התהליך.**

**1. מטרה עסקית**: להוכיח פרסום-אמיתי-אוטונומי אחד לפלטפורמה חיצונית — פותח בו-זמנית Content/Media, מקדים את Digital Influencer (M7), ומעניק ל-C ערוץ-evidence שני עתידי (audience-sensing).

**2. Capabilities מקודמות**: **G** (מבצעת את פעולת-הפרסום), תורם עתידי ל-**C**.

**3. למה כאן ולא מוקדם/מאוחר יותר**: מחקר + reconciliation מצאו זו נקודת-המינוף הגבוהה ביותר — פותחת יותר מיעד-אחד בבת-אחת. דורש M2 לאותה סיבה כמו M5. מגיע **אחרי** M3 כדי שערוץ-ציבורי-חדש לא ייצור רעש-פאונדר לפני ש-K/H בשלים לנתב אותו.

**4. מה כבר קיים**: `content_factory` generation, `editorial_review` QA, `ContentPublisher` Protocol (שמור, **אפס מימושים**), `publishing_gateway` (עוצר ב-QUEUED).

**5. מה באמת חסר**: מימוש `ContentPublisher` אחד אמיתי (פלטפורמה אחת), credential אמיתי.

**6. Definition of Done (observable)**: תוכן אמיתי אחד מתפרסם אוטונומית לפלטפורמה חיצונית אמיתית, עם views/engagement **אמיתיים נמדדים חזרה** (לא מדומים).

**7. Dependencies**: M2.

**8. סיכונים עיקריים**: מדיניות-פלטפורמה/moderation — מוקטן ע"י בחירת פלטפורמה/סוג-תוכן בעל-הכי-פחות סיכון להתחיל.

**9. מה במפורש אינו נבנה כאן**: persona/התנהגות-Digital-Expert (זה M7). generation אמיתי של וידאו/מדיה-עשירה (עדיין credential-blocked, Future).

---

## Milestone 7 — Digital Expert: First Trust-Preserving Pilot

**נוסף בעקבות מחקר+reconciliation, מפורש ונפרד מ-M6, כולל חידוד-אמון מלא (הוכרע 2026-08-13).**

**1. מטרה עסקית**: להוכיח ש-Digital Influencer/Digital Expert של ATLAS פועל כמנוע-ערך-מבוסס-אמון לקהל — **לא Sales Agent**. עיקרון-על: **"The Digital Expert exists to create verified value for its audience — not to sell to it."** הזרימה: `listen → understand → research → create useful value → respond → learn` — **לא** `problem → find product → recommend/sell`. Monetization = possible outcome, לעולם לא required stage.

**2. Capabilities מקודמות**: **Digital Influencer** (I-asset layer — Factory/Brand/ranking/lifetime-value, כבר בנוי בעומק), **Editorial Review** (הרחבה — לא מנגנון-QA מקביל).

**3. למה כאן ולא מוקדם/מאוחר יותר**: תלוי ב-M6 (זקוק לפרסום-אמיתי כדי לפעול בעולם). שכבת-הזהות (persona/מותג/דירוג) כבר מוכנה — ה-Milestone הזה עוסק ב**התנהגות ואמון**, לא בבניית-זהות מאפס.

**4. מה כבר קיים**: Digital Influencer Factory, Brand Factory, `ranking.py`, `asset_value.py`, `performance.py` (מוכן, ריק-מנתונים), חיווט `campaign_advance.py` למודל affiliate בלבד.

**5. מה באמת חסר**: פרסום-אמיתי דרך M6; **Audience Listening Loop** (`comments/questions/behavior → pattern detection → research/evidence → useful response/content → feedback/learning`) — לא קיים בשום מקום; אכיפת-אמון/גילוי-AI/הפרדת-evidence-hypothesis-opinion, כהרחבת Editorial Review; **סדר-חישוב מפורש** — קביעת-מה-מועיל **לפני** בדיקת-מונטיזציה, לא רק תוצאה-נכונה.

**6. Definition of Done (observable) — שלושה רכיבים, כולם נדרשים**:
   **א. Digital Expert אמיתי ושקוף כ-AI** — persona אמיתי, גילוי-AI גלוי (לא התחזות), נותן value מבוסס-evidence אמיתי (לא מומצא), מבחין בגלוי בין evidence/hypothesis/opinion.
   **ב. שני Integrity Tests חיים, לא simulated**: **"$10 Truth Test"** — תרחיש אמיתי שבו ההמלצה-הטובה-ביותר מייצרת פחות הכנסה מאלטרנטיבה-פחות-מתאימה, וההמלצה בפועל הולכת אחרי הערך. **"$0 Value Test"** — תרחיש אמיתי שבו אין מוצר מתאים כלל, והתגובה עדיין מועילה (לא "אין לי מה למכור"). **"Commercial incentive must never alter the recommendation that would have been given without that incentive"** — סדר-החישוב עצמו (לא רק התוצאה) מוכח: קביעת-הערך קודמת לבדיקת-מונטיזציה.
   **ג. Audience Listening Loop דו-כיווני אמיתי**: מחזור אחד שלם ומודגם בפועל — תגובות-קהל אמיתיות → זיהוי-דפוס → מחקר/evidence → תוכן/תגובה מועילים → משוב-קהל → למידה. לא simulated.

**7. Dependencies**: M6, שכבת-הזהות הקיימת (Factory/Brand).

**8. סיכונים עיקריים**: סיכון-מוניטיני אם אכיפת-האמון מתועדת אך לא נאכפת בפועל — מוקטן ע"י מימוש כהרחבה אמיתית של Editorial Review's בדיקות דטרמיניסטיות קיימות, ובדיקה מול תרחישים-אדברסריאליים (שני ה-Integrity Tests **הם** הבדיקה האדברסריאלית). "Trust is a compounding asset created by repeated truthful usefulness" — לא conversion mechanism; אסור להשתמש באמון כדי להצדיק פגיעה בערך-לקהל. בתחומים מקצועיים/רגישים — גבולות-סמכות מתאימים, לא תחליף-לבעל-מקצוע.

**9. מה במפורש אינו נבנה כאן**: שכבות-מונטיזציה נוספות מעל האודיינס (subscription/licensing — מאוחר יותר, ניזון ל-M10). ריבוי-personas/ריבוי-פלטפורמות.

---

## Milestone 8 — C-Extension: Value Discovery Engine (Beyond Existing Market)

**זהה במהות למקור (היה M5 בהצעה הראשונית) — ממוספר מחדש בעקבות הכנסת M5-M7 חדשים. Position/dependencies ללא שינוי.**

**1. מטרה עסקית**: לתת ל-ATLAS את חצי-החזון השני של Discovery — למצוא הזדמנות מ**צורך אמיתי** (לא רק משוק-affiliate-קיים), כולל פתרונות-שעדיין-לא-קיימים ושיפורי-מוצר — ולבדוק אותה בפועל דרך E, לא רק לתעד אותה.

**2. Capabilities מקודמות**: **C** (Value Discovery Engine #24, פתרונות-לא-קיימים #25, שיפור-מוצר-קיים #26, width-before-narrowing #23).

**3. למה כאן ולא מוקדם/מאוחר יותר**: הכי-פחות-מוכחת ברשימה — הימור-bootstrap מסוכן לפני שיש loop עובד (M1) ומנגנון-בדיקה (M4). **נבדק מפורש מול Audience-Sensing (reconciliation §1)**: C-extension **אינו תלוי** ב-Digital Influencer/M7 — יש לו ערוץ-evidence חלופי (`MarketSignalProvider`), לכן מיקומו **אינו זז**. ברגע ש-M7 קיים, C **יכול** (לא חייב) לקבל ערוץ-evidence שני עשיר יותר — שיפור-עתידי, לא תנאי-DoD.

**4. מה כבר קיים**: מנגנון Subject Discovery לצד-השוק-הקיים (מוכח), `opportunity_ranking.py`/`confidence.py`.

**5. מה באמת חסר**: מקור-evidence אמיתי לצורך/כאב (`MarketSignalProvider`, שמור-וריק), לוגיקת-הפקת-מועמד-הזדמנות מ-need, חיבור ל-E.

**6. Definition of Done (observable)**: צורך/כאב אמיתי (evidence מצוטט, לא ממוצר-affiliate) מתגלה, מדורג, עובר ל-E לבדיקה אמיתית אחת עם תוצאה מדודה.

**7. Dependencies**: M4 (E), D (קיים).

**8. סיכונים עיקריים**: אנקרינג — מוקטן ע"י 13-השלבים הקיימים (כבר עם counterfactual test).

**9. מה במפורש אינו נבנה כאן**: שום generation אמיתי של מוצר/שירות חדש (credential-blocked, מחוץ ל-Roadmap כליל).

---

## Milestone 9 — A/B Maturity: Proactive Presence + Unified Senses

**זהה במהות למקור (היה M6) — ממוספר מחדש. עדכון-תלות אמיתי (reconciliation §4/§5): עצמאי מ-M4-M8, לא רק ממוספר-מחדש.**

**1. מטרה עסקית**: להפוך את ATLAS לישות שיוזמת פנייה טבעית לפאונדר כשצריך, שומרת מצב-חשיבה-עסקי תמידי, ומקבלת קלט מולטימודלי מאוחד — מעורבות-הפאונדר **נחווית** קטנה, לא רק נמדדת.

**2. Capabilities מקודמות**: **A** (יוזמה-החוצה #6, מצב-עסקי-תמידי #28, אימות #21), **B** (Senses מאוחדת, וידאו/תמלול #20).

**3. למה כאן ולא מוקדם/מאוחר יותר**: יוזמה-החוצה לפני H/K ממודרגים היא בדיוק ה-"רעש" שהופך פאונדר לצוואר-בקבוק — אחרי M2+M3 יש תור מסונן-ומדורג להעביר. **תוקן ב-reconciliation**: אין צורך לחכות ל-M4-M8 — הלולאה שכבר קמה ב-M1-M3 עצמה (הכנסה אמיתית, escalations אמיתיים, Findings אמיתיים) כבר מספקת תוכן-משמעותי-מספיק ליוזמה, ולכן M9 **עצמאי ומקביל** ל-M4-M8, תלוי רק ב-M2+M3.

**4. מה כבר קיים**: `/api/converse` אמיתי (טקסט, דו-כיווני-פנימה), קלט טקסט/קול/תמונה/מסמך (Gemini-based).

**5. מה באמת חסר**: מנגנון יזום-פנייה אמיתי, State מצב-עסקי-תמידי, אימות המסלול שיחה→Goal/Task (#21), שכבת-Senses מאוחדת, וידאו.

**6. Definition of Done (observable)**: ATLAS יוזם שיחה אמיתית סביב escalation/finding אמיתי בלי שנשאל. שיחה→Goal/Task אמיתי, מאומתת קצה-לקצה בפעם הראשונה.

**7. Dependencies**: M2, M3 **בלבד** (לא M4-M8).

**8. סיכונים עיקריים**: יוזמה פולשנית אם K/H לא מכוילים — מוקטן ע"י DoD של M3.

**9. מה במפורש אינו נבנה כאן**: Command Room מלא/ריבוי-חברות בממשק (תלוי-I-עמוקה, M10+, ומחוץ ל-Roadmap כפי שכבר תועד ב-CLAUDE.md).

---

## Milestone 10 — I: Portfolio Depth, Activated by Real Complexity

**זהה במהות למקור (היה M7) — ממוספר מחדש, תלויות מורחבות.**

**1. מטרה עסקית**: לתת ל-ATLAS יכולת-החלטה אמיתית **בין** נכסים/הזדמנויות/חברות מרובים — ברגע, ורק ברגע, שזה אמיתי ולא תיאורטי.

**2. Capabilities מקודמות**: **I** (עומק — מעבר לפרוסה שהופעלה ב-M2).

**3. למה כאן ולא מוקדם/מאוחר יותר**: DNA-extensible principle (§4.9) בפעולה — I גדלה רק אחרי ש-M1/M4/M8 **ועכשיו גם M5/M6/M7** ייצרו יותר מנכס/ערוץ/persona אמיתי אחד להשוות. בנייתו קודם = "empire-management system now", בניגוד להכרעה 6.

**4. מה כבר קיים**: שימוש-חוזר-בנכסים, מוכנות-מבנית-לריבוי-חברות, `Strategist` ranking, פרוסת כסף/תקציבים מ-M2.

**5. מה באמת חסר**: דירוג-פורטפוליו מעבר ל-lifetime-value, בחירת-מודל-הכנסה שנייה, ניצני-CEO-stage **רק אם** מורכבות מצדיקה. **עדכון**: I's דירוג-עתידי צריך לשקלל ערך-מצטבר-נכס (Digital Influencer/Brand lifetime value) שונה מרווח-חד-פעמי (affiliate/commerce campaign) — כיוונון-פנימי, לא Capability חדשה (מחקר §6).

**6. Definition of Done (observable)**: החלטה אמיתית בין 2+ נכסים/ערוצים אמיתיים-נמדדים מתקבלת ע"י I, לא ידנית, עם נימוק הנשען על נתון-אמיתי.

**7. Dependencies**: M1, M4, M8 (כבמקור) **+ M5, M6, M7** (מקורות-מורכבות נוספים — נכסים/ערוצים/persona אמיתיים חדשים).

**8. סיכונים עיקריים**: בנייה מעבר-למוצדק — מוקטן ע"י DoD הדורש מורכבות-אמיתית-קיימת כתנאי-סף.

**9. מה במפורש אינו נבנה כאן**: שלב-CEO המלא, AI Leadership Protocol.

---

## Critical Path

**M1 → M2 → M3** — שרשרת בלתי-ניתנת-לעקיפה: כל אחד הוא ה-unlock המילולי של הבא. Backbone שממנו כל שאר ה-Milestones נגזרים.

## מבנה-מקביליות אחרי M3

```
                    ┌────────────► M4 (E) ────────────► M8 (C-extension)
                    │
M1 → M2 → M3 ───────┼────────────► M5 (Commerce) ─┐
                    │                              ├──► M7 (Digital Expert) ──┐
                    ├────────────► M6 (Publishing) ┘                          │
                    │                                                          ├──► M10 (I depth)
                    └────────────► M9 (A/B) ─────────────────────────────────┘
```

- **חזית-ניסוי**: M4(E) → M8(C-extension).
- **חזית-נכסים**: M5(Commerce) ‖ M6(Publishing) → M7(Digital Expert).
- **חזית-נוכחות**: M9(A/B) — עצמאית לגמרי, תלויה רק ב-M2+M3.
- כל שלוש החזיתות ניזונות ל-M10, האחרון.

## הנקודה הראשונה שבה ATLAS מרוויח כסף אמיתי כמעט-בלי-הון

**סוף M1.** לא בנייה חדשה — verification על תשתית קיימת בלבד.

## הנקודה הראשונה שבה ATLAS יכול להתחיל reinvestment אוטונומי מכסף שהוא ייצר

**סוף M2.** תלוי ישירות ב-M1.

## הנקודה שבה Founder Bottleneck מתחיל לרדת מהותית

**סוף M3, לא סוף M2 לבדו.** M2 מקטין *נפח*; H לבדה לא מספיקה, כי תור מצומצם-אך-לא-מדורג עדיין עלול להכריע פאונדר. הירידה המהותית קורית רק כש-K קיימת **לצד** H — שתיהן יחד.

## Future Improvements שנשארים מחוץ ל-Roadmap הזה, ולמה

- **שלב-CEO מלא** (Analytics/CFO/Marketing/TikTok ownership, AI Leadership Protocol) — אין עדיין מורכבות-עסקית-אמיתית שמצדיקה (per 4.9); מועמד-Roadmap-הבא רק כש-M10 חושף צורך אמיתי.
- **Supplier Identification + Shopify/sales channel (מלא)** — זוג צמוד-במכוון, credential-blocked מעבר ל-storefront-המינימלי של M5; שניהם דורשים החלטת-ספק-אמיתית שטרם התקבלה.
- **Real Creative-Asset/UGC generation (וידאו/תמונה/קול)** — עדיין credential-blocked, מעבר לתוכן-הטקסטואלי/דטרמיניסטי שכבר קיים.
- **ASIF numeric blending** (שילוב Success Laws לתוך ניקוד-confidence מספרי) — הכרעת-משקל נפרדת עתידית, לא נדרשת ללולאה הראשונה.
- **H mandates עשירים / שפת-מדיניות מלאה** — M2 בונה MVP; שפה עשירה יותר נשארת future.
- **Command Room / ממשק ריבוי-חברות מאוחד** — תלוי-I-עמוקה (M10+), כבר paused ב-CLAUDE.md.
- **Digistore24 `fetch_recent_sales()` field-mapping מלא** — M1 עושה קריאה-ראשונה-לאימות בלבד.
- **Subscription/Licensing כשכבות-מונטיזציה נוספות מעל audience** — מוזכר ב-M7 כ"לא נבנה כאן"; ניזון ל-M10 כשיהיה נכס-audience אמיתי-ומוכח.

---

**סטטוס: 🔒 נעול, מאושר. M1–M10, dependencies ו-parallelism — כפי שמתועד כאן.** שום קוד לא נכתב, שום Implementation לא נפתח.
