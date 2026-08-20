# Future Improvements / North Star Audit

**תאריך:** 2026-08-13
**מטרה:** למנוע מצב שבו רעיונות מהותיים שסומנו "אחר כך" הולכים לאיבוד תוך כדי בניית המערכת. **מיפוי בלבד** — לא Design, לא שינוי Roadmap, לא קוד. בוצע אחרי סגירת Milestone 4, לפני פתיחת Milestone 5 או עדכון Roadmap, כפי שהונחה.

**מתודולוגיה**: שני agents נפרדים סרקו במלואם (א) כל 44 קבצי `docs/*.md` + `ATLAS_CONSTITUTION.md`, (ב) כל 34 קבצי הזיכרון (`C:\Users\User\.claude\projects\...\memory\`). בנוסף, נקרא ישירות `docs/BUSINESSMAN_V1_SOURCE_OF_TRUTH.md` (§1, §8 Backlog) ו-`docs/BUSINESSMAN_V1_INVENTORY.md` במלואם. כל פריט למטה מצוטט/מצוין למקור אמיתי — שום capability לא הומצא.

---

## 0. חמישה מונחים — ממצא מקורי, ואז הבהרה רשמית מהמייסד (2026-08-13)

**ממצא מקורי, נשמר כהיסטוריה, לא נמחק**: `Revenue Intelligence`, `Success & Failure Intelligence`, `Failure Simulation`, `Success Optimizer`, `ASIF`/`ATLAS Success Intelligence Framework` נבדקו בחיפוש מלא בכל 44 מסמכי `docs/`, ב-`ATLAS_CONSTITUTION.md`, ובכל 34 קבצי הזיכרון — נמצאו **אך ורק** בתוך המשפט שבו התבקש החיפוש עצמו. שום הגדרה קודמת לא הייתה קיימת.

**הבהרה רשמית, ניתנה במפורש כ-North Star concepts חדשים/מובהרים — לא כ-capabilities שכבר תוכננו:**

- **Revenue Intelligence** — הבנה שיטתית מהם הגורמים שמייצרים הכנסה ולמה: צורך, קהל, הצעה, מוצר/שירות, economics, ערוץ, מסר, timing וגורמים רלוונטיים נוספים. **לא** reporting על הכנסה שכבר קרתה — הפקת intelligence שמסייעת **לבחור ולשפר** הזדמנויות.
- **Success & Failure Intelligence** — למידה שיטתית מהצלחות **וכישלונות**, פנימיים וחיצוניים, **כשיש evidence אמינה** — זיהוי factors שמעלים/מורידים הסתברות-הצלחה. **ללא הסקת causality ללא בסיס.**
- **Failure Simulation** — לפני commitment/scaling משמעותי: בחינה מובנית של איך Opportunity/Plan עלולים להיכשל, אילו assumptions רגישים, אילו failure modes ראוי לבדוק.
- **Success Optimizer** — אחרי שנבחרה Opportunity/Plan: חיפוש שיטתי של שיפורים שיכולים להעלות ערך/execution-readiness/הסתברות-הצלחה **לפני scaling**, תוך שמירת דיוק evidence/uncertainty.
- **ASIF / ATLAS Success Intelligence Framework** — **לא Subsystem נפרד בהכרח** — כינוי אפשרי למסגרת מאחדת סביב הלולאה: **evidence → success/failure factors → hypothesis → experiment/pilot → measured outcome → learning**. האם `SuccessLaw` הקיים מתאים כבסיס — ייבדק בעתיד, **לא מונח כאן**, לא משנה קוד.

**עיקרון מפורש שנקבע, קריטי לכל המשך העבודה על חמשת אלה**: **אסור ליצור חמישה Subsystems רק כי יש חמישה שמות.** הארכיטקטורה נקבעת לפי אחריות אמיתית, לא לפי שם. ראו "השערת איחוד" בתוך Bucket 4 למטה.

---

## 1. Bucket 1 — קיים בקוד, לא ממוסד ב-Roadmap

| פריט | קיים היכן | סטטוס אמיתי | למה חשוב לחזון | חפיפה/תלות | מכוסה או חסר |
|---|---|---|---|---|---|
| **Presence / Conversation** | `POST /api/converse` (`src/atlas/headquarters/server.py`, commit `af17089`, "ATLAS Presence V1") — LLM אמיתי, פתוח, מבוסס-הקשר-אמיתי (`build_briefing()`, אישורים ממתינים), רושם דרך `ConversationMemory` | **קוד אמיתי, עובד** — אפס הופעה ב-Roadmap הרשמי (`SOURCE_OF_TRUTH`/`INVENTORY`), **אין שום מסמך תכנון בשם "Presence" בכלל** | זה בדיוק הבסיס הטכני ל-LLM-CEO Conversation מה-North Star | Value Discovery (שיחה יכולה להזין מחקר), permanent business-mode (§4) | **קיים חלקית** — הצינור הטכני קיים; "free conversation never bypasses governance" (Constitution Art. IV: "Task... never created directly from a Conversation reply") נעול כעיקרון, אך **לא אומת שהמסלול הלגיטימי ההפוך (בקשת-פאונדר-אמיתית → Goal/Task אמיתי) בכלל עובד** (`ATLAS_V1_FAILURE_ANALYSIS.md`, כשל 4/5) |
| **`SuccessLaw`** | `atlas.brain.models.SuccessLaw`, `KnowledgeBase.save_success_law()`, `asset_value.success_law_lifetime_value()`, `rank_success_laws_by_track_record()` | **מוכח, חי** — "the first complete measurable closed-loop business cycle" | הבסיס האמיתי היחיד הקיים ל-ASIF (אם זו הכוונה) | ר' סעיף 0 | **קיים, אך לא תחת המיתוג/הרחבה המבוקשים** |
| **Cash Engine / Asset Engine** | `docs/ATLAS_BUSINESS_BLUEPRINT.md` §2/§5 — "Cash Engine finances the Asset Engine" | **מוכח חלקית** — Recruitment חי, Affiliate/Stock Images/TikTok "Planned" | האנלוג הקיים הכי קרוב ל-"Cashflow Engine" מה-North Star, בשם שונה | Cashflow Engine (North Star) | **קיים, שם שונה, מסגור שונה** — לא מנוסח כ"חיפוש-מתמיד-של-הזדמנויות-קיימות" |
| **שימוש-חוזר בנכסים חוצה-קטגוריות** | `_find_reusable_influencer()`/`_find_reusable_brand()`, Business Asset Portfolio | **מוכח, חי** | חלק מהתשתית ל"הזדמנויות לקהלים, כולל משפיענים" | Value Discovery Engine | **מכסה רק "שימוש חוזר בנכס קיים," לא "גילוי צורך אצל קהל"** |
| **מוכנות-מבנית לריבוי-חברות** (`CEOBrain`/כל Registry מוזרקי-תלות) | מאומת חי (2026-08-12) | **קיים מבנית, לא מתוזמר** | תשתית ל-"CEO מנהל כמה חברות" | שלב CEO (§1) | חסר רק שכבת-תזמור מעל N מופעי `CEOBrain` |

## 2. Bucket 2 — מתוכנן/מתועד לעתיד (מפורש בשם, לא North Star חדש)

| פריט | מקור | תנאי/גורם חוסם |
|---|---|---|
| **תקשורת-יזומה-החוצה של ATLAS** | `docs/ATLAS_V1_FAILURE_ANALYSIS.md` — "אין שום דרך ש-ATLAS ידע לך על החלטה אמיתית מיוזמתו" | לא תלוי credential — פער מפרט/עיצוב אמיתי, מוצהר כיעד v2 |
| **5 ספקי-Affiliate + 5 ספקי-Resource אמיתיים** | `docs/ATLAS_ARCHITECTURE_REFERENCE.md` §5 | credential-blocked, כל אחד החלטה נפרדת |
| **הרחבות Time Awareness** (תזכורות, לוח-שנה, jobs חוזרים) | `docs/ATLAS_ARCHITECTURE_REFERENCE.md` §2.3 | "הפרימיטיבים הגנריים מוכנים, שום דבר מעליהם עדיין לא נבנה" |
| **מודול-ביצוע אמיתי ל-`BusinessExecutionPlan`** | `docs/ATLAS_ARCHITECTURE_REFERENCE.md` | לא נבנה במכוון ב-V1 |
| **Analytics/CFO/Marketing כמחלקות** | `docs/ATLAS_BUSINESS_BLUEPRINT.md` §4/§11 | כל אחת מותנית בטריגר אמיתי (מספיק פעילות/הכנסה/משהו-לקדם) |
| **בעלות TikTok** | `docs/ATLAS_BUSINESS_BLUEPRINT.md` §7 | "Open Architectural Decision," לא ננעל |
| **שלב CEO** (מחלקות, עובדים, Agents חדשים, כמה מנועי-הכנסה במקביל) | `SOURCE_OF_TRUTH` §1 עצמו | "ייוולד מתוך צורך שנחשף בעבודה, לא מתוכנן מראש" |
| **בחירה אמיתית בין מודלי-הכנסה** | Backlog M3 (`SOURCE_OF_TRUTH` §8) | ממתין לערוץ-ביצוע אמיתי שני (credential-blocked) |
| **הרחבת Reasoning — יחסים בין הזדמנויות (משלימות/מתחרות)** | `docs/ARCHITECTURE_INTENT_BUSINESS_OPPORTUNITY_EVALUATION.md`, Backlog M2 | ממתין ל-Reasoning עשיר יותר |
| **שדה `founder_explanation` מובנה על Task** | `docs/FOUNDER_ASSISTED_BUSINESS.md` | "Design only. No code changes this mission" — מעולם לא מומש |
| **13 השלבים של New Business Methodology כשער-קוד אמיתי** | `docs/NEW_BUSINESS_METHODOLOGY.md`; מאושר עדיין נכון ב-`ATLAS_V1_FAILURE_ANALYSIS.md` | "קיים רק כמסמך נהלים... אף פעם לא קודד" |
| **מסמך ארכיטקטורת Senses/Brain/Actions** | `project_atlas_senses_brain_actions_architecture.md` (זיכרון) | טריגר: "מיד אחרי שאבן-דרך M7 תושלם ותאושר" — **לא אושר בשום זיכרון מאוחר יותר שנכתב בכלל** |
| **AI Leadership Protocol המילולי** (Claude/ChatGPT/Gemini/Hermes כ"מנהלים" נפרדים) | `feedback_ceo_decision_protocol.md` §10 | "אין גישת-כלים ברמת הסביבה הזו לקרוא ל-ChatGPT/Gemini/Hermes כמערכות נפרדות היום" — גייטד על תשתית שלא קיימת |

## 3. Bucket 3 — קיים חלקית

| פריט | מה קיים | מה חסר |
|---|---|---|
| **הפרדת Evidence/Hypothesis/Proof** | קיים **בינארי**, **רק ל-`SuccessLaw`** (Constitution Art. IV: "ההבדל בין Finding ל-SuccessLaw הוא ההבדל בין 'ראיתי X' ל-'X נוטה לעבוד'"; `evidence-backed`/`hypothesis`) | **שלישיית evidence/hypothesis/proof** על פני כל Opportunity, ובפרט על פתרונות-שעדיין-לא-קיימים (North Star) — לא קיים |
| **Multimodal — קול/וידאו** | audio/image/document plugins (Gemini-based) — **כבר מוכחים, לא North Star** | **וידאו/תמלול ספציפית** — מגבלה מוצהרת: `docs/ARCHITECTURE_INTENT_GAP_A_SUBJECT_DISCOVERY.md`: "לא פותר YouTube/וידאו... אין תמלול... מוצהר במפורש כמחוץ לתחום" |
| **שיחה חופשית לא עוקפת Governance** | העיקרון **נעול** (Constitution Art. IV: "Task... never created directly from a Conversation reply"; Spec §3.4: "אינו יוצר Task/Goal ישירות") | **המסלול הלגיטימי** (בקשת-פאונדר-אמיתית בשיחה → Goal/Task אמיתי) **מעולם לא אומת שקיים ועובד** (`ATLAS_V1_FAILURE_ANALYSIS.md`) |
| **Digital Business Understanding כ-Capability פעילה** | `SOURCE_OF_TRUTH` §1 — Meta Capability, "מזינה את כל ה-Milestones" | "שאיפה מוצהרת... תיבנה בהדרגה" — היום רק Success Laws record-only |
| **Width-before-narrowing / מחקר יזום** | מחקר קורה (`ResearchDiscoveryAgent`) | אין מנגנון מבני שכופה סריקת-רוחב לפני צמצום; verdict `insufficient_evidence` לא מפעיל מחקר חדש מיוזמת ATLAS (`ATLAS_V1_FAILURE_ANALYSIS.md`) |

## 4. Bucket 4 — חזון/רעיון שסוכם, עדיין לא בתכנון הרשמי

כל הפריטים כאן מקורם ב-`project_atlas_north_star_llm_ceo_value_discovery.md` (הזיכרון היחיד שמכיל אותם) — **אושרו על ידך בשיחה הזו, נשמרו בזיכרון בלבד, אפס נוכחות ב-Roadmap הרשמי**, כמאושר בשני ה-Agents.

- **Value Discovery Engine** — גילוי צרכים/כאבים/פערים אצל עסקים/לקוחות/קהלים (**כולל קהלי משפיענים**, נוסח מדויק, לא מתיחה). **חדש לגמרי** — `evaluate_opportunities()`/`rank_opportunities()` מדרגים מועמדים **שכבר התגלו**; שום מנגנון לא מגלה **מ**צורך.
- **פתרונות/מוצרים שעדיין לא קיימים** — הרחבה מפורשת של Value Discovery (חידוד 2026-08-13): "לזהות מתוך מחקר צורך אמיתי שעדיין אין לו פתרון." **אושר כנעדר לחלוטין** — כל מנגנוני הגילוי הקיימים מוגבלים למוצרים/תוכניות-Affiliate **קיימים**; `ATLAS_V1_FAILURE_ANALYSIS.md` אף מבקר את הכיוון ההפוך (עיגון-סביב-מוצר-קיים).
- **זיהוי שיפור-משמעותי למוצר קיים** — אותה הרחבה, מקרה ב'. לא קיים בשום מנגנון.
- **שני מנועים (Cashflow+Value Discovery) פועלים במקביל ומזינים זה את זה** — "Value Discovery יוצר הזדמנויות חדשות מתוך צרכים אמיתיים, ומזין אותן חזרה למערכת ההערכה/החלטה/ביצוע הקיימת (M2-M4, ללא שינוי מנגנון — מקור חדש למועמדים, לא צינור-החלטה/ביצוע חדש)."
- **מצב-עסקי-תמידי גם בשיחה חופשית** — "ATLAS צריך להיות במצב-חשיבה עסקי קבוע... **בו-זמנית** עם מה שהשיחה עצמה עוסקת בו."
- **הפרדת evidence/hypothesis/proof, מורחבת** — לא רק ל-SuccessLaw (כבר קיים חלקית, Bucket 3) — לכל Value Discovery: "**אין דבר כזה 'הוכחה' שפתרון-שעדיין-לא-נבנה יצליח**" — הרחבה ישירה של Constitution Article IX, לא עיקרון חדש.
- **Pilot/MVP קטן ומבוקר לבדיקת השערה עסקית** — שונה במפורש מ-"MVP" ההנדסי-הפנימי הקיים (`docs/DESIGN_EXECUTIVE_REASONING_MVP.md` וכו', שמתאר בניית-קוד-מינימלית, לא פיילוט-עסקי-אמיתי). **לא קיים בשום מנגנון עסקי**.
- **ממשק שיחה מולטימודלי עתידי** (קול+וידאו) — "ככל שהארכיטקטורה העתידית תאפשר." חופף חלקית ל-Bucket 3 (video/transcription gap).
- **מיסוד "Presence/Cashflow Engine/Value Discovery Engine" ב-Roadmap הרשמי** — התוכנית המשולשת עצמה (לא רק התוכן) — עדיין לא בוצעה, בכוונה, עד סגירת M4 (כעת סגור).

### 4א. חמשת מונחי ה-Intelligence/Simulation/Optimizer/ASIF — כעת מוגדרים (2026-08-13)

- **Revenue Intelligence** — הבנה שיטתית של גורמי-הכנסה (צורך/קהל/הצעה/economics/ערוץ/מסר/timing), לצורך בחירה ושיפור, לא reporting.
- **Success & Failure Intelligence** — למידה שיטתית מהצלחות/כישלונות אמיתיים (evidence-gated, ללא causality מומצא).
- **Failure Simulation** — בחינה מובנית של מצבי-כשל/רגישות-הנחות **לפני** commitment/scaling.
- **Success Optimizer** — חיפוש שיטתי של שיפורים **אחרי** בחירה, **לפני** scaling.
- **ASIF** — כינוי-אפשרי-בלבד למסגרת המאחדת: evidence → factors → hypothesis → experiment/pilot → outcome → learning.

**השערת-איחוד, לפי אחריות אמיתית — לא הכרעה, לסימון בלבד עבור Architecture Intent עתידי**:

1. **Revenue Intelligence ↔ Success & Failure Intelligence** — חפיפה אמיתית: שתיהן "חילוץ factors מ-evidence." ההבדל: Revenue Intelligence ממוקד בגורמים **כלכליים/הצעתיים** (למה זה מרוויח); Success & Failure Intelligence רחב יותר (כולל גורמי-ביצוע/timing/התאמת-שוק, כולל למידה **מכישלון**, לא רק הצלחה). **ייתכן ש-Revenue Intelligence הוא תת-מקרה ממוקד-הכנסה של Success & Failure Intelligence הרחב יותר — לא שני מנגנונים נפרדים.**
2. **Failure Simulation ↔ Success Optimizer** — חפיפה חזקה עוד יותר: שתיהן פועלות **באותה נקודה בדיוק בציר-הזמן** (לפני commitment/scaling משמעותי), על **אותו קלט** (ה-Opportunity/Plan שכבר נבחר), ומייצרות המלצות מובנות. **קנדידט טבעי לאיחוד**: "בדיקת-לפני-הרחבה" אחת, עם שתי עדשות (סיכון-כשל / הזדמנות-שיפור) — לא שני Engines.
3. **ASIF כמסגרת-על, לא כרכיב שישי** — אם ASIF הוא באמת שם ללולאה evidence→factors→hypothesis→experiment→outcome→learning, אז הוא **כבר מכיל בתוכו** רכיבים שכבר קיימים או כבר ב-Bucket 4: `SuccessLaw` (Bucket 1, "measured outcome → learning"), Pilot/MVP עסקי (למעלה, "experiment/pilot"), הפרדת evidence/hypothesis/proof (למעלה, המשמעת האפיסטמית של הלולאה כולה). **ASIF עשוי להיות השם למסגרת המלאה, לא Subsystem נוסף מעליה.**
4. **מסקנה מוצעת, לא הכרעה**: קרוב לוודאי **לא** חמישה Subsystems. קרוב יותר: (א) מנגנון-אחד לחילוץ-factors מ-evidence (משרת גם Revenue Intelligence וגם Success & Failure Intelligence), (ב) שער-אחד לפני-הרחבה בשתי עדשות (Failure Simulation + Success Optimizer), (ג) הלולאה כולה (כולל Pilot/MVP ו-SuccessLaw הקיים) תחת שם-על אחד, אולי ASIF. **תלוי בהחלטת Architecture Intent אמיתית, לא כאן.**

### 4ב. Delegated Authority / Autonomy by Policy / Founder Bottleneck Prevention (חדש, 2026-08-13, לאחר בקשת ה-Audit)

**הבעיה**: ככל ש-ATLAS יטפל בעשרות/מאות/אלפי Opportunities במקביל, approval-per-action הופך את הפאונדר לצוואר-הבקבוק. Tasks נערמים, הזדמנויות מתיישנות, ה-throughput מוגבל בקצב-אישורים אנושי.

**הכיוון**: הפאונדר מגדיר מראש mandates/policies (תקציב, risk limits, סוגי-פעולות, thresholds, גבולות-סמכות). פעולות שגרתיות-ובטוחות-בתוך-המדיניות מתבצעות אוטונומית. פעולות משמעותיות-אך-בתוך-mandate מתבצעות **ומדווחות/נכללות בסיכום**. חריגות/סיכון-גבוה/מחוץ-לסמכות/אסטרטגי עולים לפאונדר. **Governance לא מוסר — עובר מ"אישור-לכל-פעולה" ל"אוטונומיה-בתוך-גבולות-מנוהלים."** ATLAS מבצע aggregation/prioritization של escalations, כך שהפאונדר מקבל תמונת-על + מספר קטן של החלטות מהותיות. **מדד ארכיטקטוני**: כשמספר-ההזדמנויות גדל בסדרי-גודל, עומס-ההחלטות-השגרתיות על הפאונדר לא אמור לגדול באותו יחס.

**חפיפה עם מנגנונים קיימים — נבדק ישירות, לא הונח:**

| מנגנון קיים | מה כבר נכון היום |
|---|---|
| `RiskPolicy.evaluate()` (fail-closed, 4 צירי-סיכון + `ALWAYS_REQUIRES_APPROVAL` + `redesign_` prefix) | **זהו כבר שער-מדיניות, לא שיפוט-אנושי-לכל-פעולה.** Task שעובר את כל הצירים **כבר מתבצע אוטונומית, ללא אישור** — הצורה הבסיסית של "אוטונומיה-בתוך-גבולות" **כבר קיימת**, לפחות למקרה הפשוט ביותר (הפיך לגמרי, עלות אפס, ללא הרשאות/הסכם). |
| `amount_threshold` (כרגע `0.0`) | קבוע-מדיניות אמיתי, **כבר ניתן-לעריכה** — נקודת-הרחבה טבעית ל"תקציב מוגדר-מראש" |
| `ALWAYS_REQUIRES_APPROVAL` (`set`, פתוח) | מיפוי-מדיניות אמיתי של "סוגי-פעולות שתמיד עולים" — בדיוק הרעיון של "גבולות-סמכות כנתונים," לא לוגיקה קשיחה |
| `MAX_CONCURRENT_COMMITMENTS` (M3) | תקדים אמיתי ל-"risk limit"/"threshold" כקבוע-מדיניות מוצהר |
| `Strategist.reallocate()` | תקדים חי ל-"פעולה עסקית שגרתית, מתמשכת, אוטונומית לגמרי, ללא אישור בכלל" |
| `Delegator._propose()` → `Proposal` → `approve()` | **מסלול ה-Escalation כבר קיים** — פעולה מחוץ-לגבולות יוצרת Proposal אמיתי, ממתין לפאונדר |
| `atlas brain approvals` | רשימה **שטוחה, לא-מתועדפת** היום — **כאן החוסר האמיתי**: אין aggregation/prioritization |
| `Reporter.summarize()`/`build_briefing()` | הבסיס הקיים הכי קרוב ל"תמונת-על" — לא בנוי היום כ-digest-מתועדף-של-escalations ספציפית |

**מה באמת חדש/חסר, לא רק שם חדש למנגנון קיים**:
1. Mandates עשירים, מוגדרי-פאונדר, מעבר לארבעת הצירים הקבועים של `RiskPolicy` היום (תקציב-לפי-קטגוריה, רמות-סמכות-לפי-סוג-הזדמנות).
2. **Aggregation/prioritization אמיתי** של אישורים ממתינים — לא קיים היום בשום מקום.
3. **מדד ארכיטקטוני מפורש** (עומס-החלטות לא גדל פרופורציונלית לנפח-הזדמנויות) — לא נמדד/מטורגט על ידי שום מנגנון קיים.
4. **שכבה שלישית**: "מתבצע אוטונומית **וגם** מדווח בסיכום" — שונה מהבינארי-של-היום (או אוטונומי-ושקוף-לגמרי, או חוסם-לאישור) — לא קיימת עדיין, אך `Task.history`/`event_log`/`DecisionLog` כבר מספקים תשתית-גלם אפשרית לבנות עליה.

**מסקנה**: **להרחיב מנגנונים קיימים (RiskPolicy, Proposal/approve, Reporter), לא לבנות מערכת מקבילה** — תואם ישירות את ההנחיה שלך.

## 5. Bucket 5 — Technical/Architecture Debt (נפרד מחזון-מוצר)

| פריט | מקור | הערה |
|---|---|---|
| **`opportunity_discovery_advance.py` כתשתית רדומה** | Milestone 4 closure, `SOURCE_OF_TRUTH` §8 | גורלה טרם הוכרע — להשאיר או Cleanup עתידי |
| **Architecture Debt Article VIII** (`affiliate_pipeline` אפוי-לקטגוריה; `campaign_advance.py`'s `BRIDGED_CATEGORIES` קשיח) | `SOURCE_OF_TRUTH` §8 | לא נוצר/הורחב ב-M4, קיים מקודם |
| **`Goal.founder_estimate`/`Strategist` לא-פעיל** | ירושה מ-M3, אושר שוב ב-M4 | Campaign אמיתי נוצר, אך Strategist "לא רואה" את ה-Goal |
| **`Delegator` first-match routing** | מסומן מאז `project_atlas_first_operational_agent.md` (2026-07-21!), עדיין לא נבדק תחת חוק-שלוש-השאלות | פתוח הכי הרבה זמן מכל הפריטים ברשימה |
| **`Campaign.platform_strategy`/`content_strategy` כ-`str` חופשי, לא מבני/רבים** | M4 Design, זוהה תוך כדי | שאלת Shape-vs-Implementation אמיתית, לא נפתרה |
| **`SimplePlanner` ללא דה-דופ** — Task חדש לכל Goal פעיל בכל tick | `project_atlas_qualification_framework.md` | אושר שוב ב-Run #2 ("104 Tasks כלליים") |
| **`Monitor.sync()`** מסמן "done" לפי `report()` מצטבר של ה-Asset, לא לפי Task ספציפי | `project_atlas_qualification_framework.md` | Backlog מערכתי |
| **`Registry.dispatch()` ברירת-מחדל-עצלה** תוקן רק ל-`research_discovery` | `project_atlas_qualification_framework.md` | תבנית כללית עדיין פתוחה |
| **Bridge 3 boost mechanism** דורש redesign מול `SimplePrioritizer` | `project_atlas_business_brain_integration.md` | לא הוכרע |
| **"Business Standings Map"** — לא קיים | `project_atlas_qualification_framework.md` | Backlog מ-Run #1 |
| **New Business Methodology — כתוב, אף פעם לא קודד** | גם Bucket 2 וגם כאן — תיעוד שאף פעם לא נאכף בקוד | "תרם בפועל לכשל v1" |

---

## מפת תלויות ראשונית (לא סדר Milestones — לא הוכרע)

```
Value Discovery Engine
 ├─ תלוי ב: הפרדת Evidence/Hypothesis/Proof (הרחבת Article IX)
 ├─ תלוי ב: מנגנון Pilot/MVP עסקי (איך פותרים "הוכחה עדיין לא קיימת")
 ├─ מזין: השרשרת הקיימת M2→M3→M4 (מקור-מועמדים חדש, לא צינור-החלטה חדש)
 ├─ חופף: "שיפור למוצר קיים" ו-"פתרון-שעדיין-לא-קיים" (שני מקרים תחת אותו Capability)
 └─ חופף חלקית: "שימוש-חוזר בנכסים" (Bucket 1) — לא אותו דבר, לא לבלבל

Cashflow Engine
 ├─ = מיסוד/מיתוג של M1-M4 הקיים (בעיקר Bucket 1, לא בנייה חדשה)
 └─ פועל במקביל עם: Value Discovery Engine (שניהם מזינים את אותה שרשרת M2-M4)

Presence / Conversation
 ├─ כבר קיים טכנית (Bucket 1) — /api/converse
 ├─ תלוי ב: תקשורת-יזומה-החוצה (כרגע חסרה — שיחה היום היא pull-only)
 ├─ תלוי ב: אימות שהמסלול הלגיטימי (שיחה→Goal/Task אמיתי) בכלל עובד
 ├─ נשען על (לא משנה): "שיחה חופשית לא עוקפת Governance" — כבר נעול כעיקרון
 └─ מארח מעליו: "מצב-עסקי-תמידי" (Bucket 4 — צריך שכבת-שיחה כדי להתלבש עליה)

מולטימודליות (קול/וידאו)
 ├─ קיים חלקית (Bucket 3) — audio/image/document כבר עובדים
 ├─ חסר במפורש: וידאו/תמלול (Gap A כבר תיעד את זה במפורש)
 └─ מזין גם: Presence/Conversation וגם Value Discovery (מחקר ממקורות לא-טקסטואליים)

אשכול ASIF (עודכן, 2026-08-13 — מוגדר, לא עוד "לא-מוגדר")
 ├─ Revenue Intelligence ↔ Success & Failure Intelligence — חפיפה אמיתית, קנדידט-איחוד (4א.1)
 ├─ Failure Simulation ↔ Success Optimizer — חפיפה חזקה, קנדידט-איחוד ל"שער לפני-הרחבה" אחד (4א.2)
 ├─ תלוי ב: הפרדת Evidence/Hypothesis/Proof (כבר במפה, Value Discovery Engine)
 ├─ תלוי ב/מכיל: Pilot/MVP עסקי ("experiment/pilot" בלולאה)
 ├─ נשען על, כבר קיים: SuccessLaw (Bucket 1 — "measured outcome → learning")
 ├─ מזין ומוזן על ידי: Value Discovery Engine (factors/simulation/optimizer רלוונטיים גם ל"האם/איך לרדוף צורך חדש")
 └─ ASIF = שם-על אפשרי ללולאה כולה, לא Subsystem שישי — לא הוכרע

Delegated Authority / Autonomy by Policy (חדש, 2026-08-13)
 ├─ מרחיב, לא מחליף: RiskPolicy, ALWAYS_REQUIRES_APPROVAL, Proposal/approve, Reporter (כולם קיימים)
 ├─ תלות-דחיפות אמיתית ← Value Discovery Engine: מנוע שמייצר הרבה מועמדי-פיילוט חדשים הופך את צוואר-הבקבוק לדחוף בהרבה
 ├─ תלות-דחיפות אמיתית ← מוכנות-מבנית-לריבוי-חברות (Bucket 1): עוד חברות = עוד Tasks = אותה בעיה בקנה-מידה גדול יותר
 ├─ מאפשר בעתיד: אישור-מדיניות (לא ידני) ל-Pilot/MVP עסקי קטנים, בתוך mandate
 └─ לא תלוי ב: אף פריט אחר ברשימה — יכול להתקדם עצמאית

CEO Stage (מחלקות, Agents חדשים, כמה מנועים במקביל)
 ├─ תלוי ב: הוכחת מחזור עסקי שלם אחד (Businessman V1) — כבר בתהליך, M1-M4 קיימים
 ├─ מכיל בתוכו: "בחירה אמיתית בין מודלי-הכנסה" (Bucket 2, credential-blocked)
 ├─ מכיל בתוכו: AI Leadership Protocol המילולי (גייטד על תשתית חיצונית)
 └─ נהנה מ-: Delegated Authority (ניהול-כמה-מנועים-במקביל דורש בדיוק את אותה הרחבת-מדיניות)
```

---

## רשימה מסכמת — כל Future Improvement / North Star Candidate, לבדיקה שלא נשכח כלום (2026-08-13)

**Bucket 1 (קיים בקוד, לא ב-Roadmap)**: Presence/Conversation · SuccessLaw · Cash Engine/Asset Engine · שימוש-חוזר-בנכסים-חוצה-קטגוריות · מוכנות-מבנית-לריבוי-חברות.

**Bucket 2 (מתוכנן/מתועד)**: תקשורת-יזומה-החוצה · 5 ספקי-Affiliate+5 Resource · הרחבות Time Awareness · מודול-ביצוע ל-BusinessExecutionPlan · Analytics/CFO/Marketing · בעלות TikTok · שלב CEO · בחירה-אמיתית-בין-מודלי-הכנסה · הרחבת Reasoning (יחסים בין הזדמנויות) · `founder_explanation` על Task · 13-שלבי-Methodology כשער-קוד · מסמך Senses/Brain/Actions · AI Leadership Protocol המילולי.

**Bucket 3 (קיים חלקית)**: הפרדת Evidence/Hypothesis/Proof (רק ל-SuccessLaw, בינארי) · Multimodal קול/וידאו (וידאו/תמלול חסר) · שיחה-לא-עוקפת-Governance (העיקרון נעול, המסלול-הלגיטימי לא אומת) · Digital Business Understanding כ-Capability פעילה · Width-before-narrowing/מחקר יזום.

**Bucket 4 (חזון מוסכם, לא בתכנון רשמי)**: Value Discovery Engine · פתרונות-שעדיין-לא-קיימים · שיפור-משמעותי-למוצר-קיים · שני-מנועים-במקביל-ומזינים-זה-את-זה · מצב-עסקי-תמידי-בשיחה-חופשית · הפרדת evidence/hypothesis/proof מורחבת (מעבר ל-SuccessLaw) · Pilot/MVP עסקי · ממשק-שיחה-מולטימודלי-עתידי · מיסוד Presence/Cashflow/Value-Discovery ב-Roadmap הרשמי · **Revenue Intelligence** · **Success & Failure Intelligence** · **Failure Simulation** · **Success Optimizer** · **ASIF** (ר' השערת-איחוד, 4א) · **Delegated Authority / Autonomy by Policy / Founder Bottleneck Prevention** (4ב, חדש).

**Bucket 5 (Technical/Architecture Debt)**: `opportunity_discovery_advance.py` רדום · Architecture Debt Article VIII · `Goal.founder_estimate`/Strategist לא-פעיל · `Delegator` first-match · `Campaign.platform_strategy` כטקסט-חופשי · `SimplePlanner` ללא דה-דופ · `Monitor.sync()` אגרגטיבי · `Registry.dispatch()` ברירת-מחדל-עצלה · Bridge 3 boost mechanism · Business Standings Map חסר · New Business Methodology לא-קודד.

**סה"כ: 5 + 13 + 5 + 15 + 11 = 49 פריטים אמיתיים, מצוטטים למקור.**

---

**סטטוס:** Inventory בלבד, כמבוקש — **עודכן 2026-08-13** עם הבהרת חמשת המונחים (סעיף 0, 4א) ופריט חדש (Delegated Authority, 4ב). **לא בוצע שינוי ל-Roadmap, ל-Source of Truth, ל-Design פעיל, או לקוד.** ממתין לבדיקתך ולהחלטה משותפת מה נכנס רשמית לתוכנית, באיזה סדר.
