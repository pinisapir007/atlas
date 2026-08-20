# ATLAS Businessman V1 — מקור האמת (Single Source of Truth)

**נוצר:** 2026-08-12 | **החזון ננעל רשמית:** 2026-08-12
**מטרה:** המסמך היחיד שמנהל את התקדמות החזון של ATLAS. לא Design, לא Architecture — סטטוס. **כל Capability/Design/RCA חדש נבדק קודם מול המסמך הזה: "לאיזה Milestone זה שייך?" אם הוא לא שייך לשלב הפעיל — לא מתחילים אותו.**
**חוק תחזוקה**: לא נמחק. עדכון = תוספת/שינוי סטטוס, בדיוק כמו `Decision.superseded_id`. שם שלב באנגלית מלווה תמיד בתרגום עברי.

**⚠️ הצלבה קריטית עם מסלול-תכנון שני (נוספה 2026-08-17, ONE BRAIN Root Implementation Audit)**: קיים Roadmap שני, נפרד, `docs/ROADMAP_PROPOSAL.md` (מספור **M1-M10**, שונה לגמרי מ-**Milestone 1-7** כאן) — עוקב אחרי Digistore24/Marketplace Discovery ("M1 Marketplace Discovery"), ננעל יום אחד מאוחר יותר (2026-08-13) ומעולם לא מתייחס למסמך הזה בשמו. שני המסמכים **לא מאוחדים**. **לפני עבודה על אחד — לבדוק את שניהם.** `opportunity_advance.advance_opportunities_from_findings()` (Bridge 1) הוא הצינור-הכתיבה-היחיד המאושר ל-`Opportunity` בשני המסלולים גם יחד — כל עבודה עתידית שנוגעת ב-Opportunity, מכל מסלול, חייבת לעבור דרכו.

---

## 📊 Project Dashboard (לוח הבקרה של הפרויקט) — מבט של 3 שניות, מתעדכן בזמן אמת

```
══════════════════════════════════════════════════

🚀 חזון ATLAS
   Businessman V1  →  CEO

   Businessman V1:  ■■■■■□□  4/7 Approved · לפני Milestone 5

──────────────────────────────────────────────────

✅ Milestone 4 — Business Plan Generator (Affiliate V1) — Approved

   התקדמות Milestone 4 (כולה הושלמה):

   ☑ Definition of Ready        (הגדרת מוכנות)
   ☑ Capability Definition      (הגדרת יכולת)
   ☑ Architecture Intent        (כוונה ארכיטקטונית)
   ☑ Design                    (תכנון) — נעול
   ☑ Implementation            (מימוש)
   ☑ Qualification             (אימות) — כולל Qualification חוזר
   ☑ Vision Milestone Review   (סקירת אבן דרך)

──────────────────────────────────────────────────

✔ הושלם:     Milestone 1 ✅ · Milestone 2 ✅ · Milestone 3 ✅ · Milestone 4 ✅
🟡 עכשיו:     Future Improvements / North Star Audit (לא Milestone — מיפוי בלבד)
⬜ הבא:       Milestone 5 — Execution Workflow (טרם נפתח)

══════════════════════════════════════════════════
```

**מסמכים פעילים כרגע:** אף Milestone פעיל — Milestone 4 נסגר במלואו. לפני פתיחת Milestone 5 או שינוי Roadmap: **Future Improvements / North Star Audit** (מיפוי בלבד, לא שינוי Roadmap, לא קוד).

**שרשרת מלאה, לתמונה רחבה:** ✅ 1.Subject Discovery · ✅ 2.Business Opportunity Evaluation · ✅ 3.Revenue Strategy · ✅ 4.Business Plan Generator (Affiliate V1) · ⬜ 5.Execution Workflow · ⬜ 6.KPI Tracking · ⬜ 7.Learning Loop · ← לאחר מכן: שלב CEO.

**עדכון אחרון:** 2026-08-13 — *Milestone 4 — ✅ Approved.* כל 7 השלבים הושלמו. שלושה סיכונים/חובות לא-חוסמים נשמרו במפורש ב-Backlog (§8), ללא תיקון: `opportunity_discovery_advance.py` כתשתית רדומה (גורלה טרם הוכרע), Architecture Debt הקיים (לא נוצר ב-M4), `Goal.founder_estimate`/Strategist לא-פעיל (ירושה מ-M3). **כעת: Future Improvements / North Star Audit** — מיפוי מלא של כל יכולת/רעיון שסומן "אחר כך"/North Star/Backlog/out-of-scope בתיעוד ובזיכרון הפרויקט, לפני החלטה על Milestone 5 או עדכון Roadmap. אין שינוי Roadmap עדיין.

---

## 1. החזון (Vision) — נעול, רשמי, לא משתנה אלא בראיה חזקה

ATLAS נועד להיות **מנכ"ל דיגיטלי** (Digital CEO). לא Assistant. לא Agent. לא כלי AI. אלא ישות עסקית אחת המסוגלת להבין, להחליט, לבצע, למדוד, ללמוד — ולנהל חברה דיגיטלית שלמה לאורך שנים.

**סדר הבנייה, לא החזון עצמו:**

```
Businessman (איש עסקים דיגיטלי)
        ↓
CEO (מנכ"ל דיגיטלי)
```

**מבחן-העל לכל החלטה בפרויקט**: "האם זה מקרב את ATLAS להיות מנכ"ל דיגיטלי טוב יותר?" **וגם**: "איזו החלטה עסקית אמיתית משתפרת בזכות זה?" שתי השאלות ביחד, לא אחת בלבד.

### שלב ראשון: Businessman (איש עסקים דיגיטלי)

מטרתו: להוכיח מחזור עסקי אמיתי שמייצר הכנסה. לא להקים חברה, לא לנהל עובדים — לדעת להקים ולהפעיל עסק דיגיטלי בעצמו.

**Digital Business Understanding (הבנת עולם העסקים הדיגיטליים) — Meta Capability, לא Milestone.** יכולת-על שמלווה את ATLAS לאורך כל חייו — אילו מודלים עסקיים קיימים, אילו מנועי הכנסה קיימים, איך זורם הכסף, אילו הזדמנויות קיימות, איך השוק משתנה. **מזינה את כל ה-Milestones, אינה מחליפה אף אחד מהם** (ובפרט, אינה Milestone 1 — Milestone 1 הוא Subject Discovery, יכולת צרה ומוכחת בתוך ה-Meta Capability הרחבה הזו, לא שם אחר לה). כשמגיעים אליה ישירות כ-Capability, היא תתורגם לקריטריוני הצלחה מדידים — לא כתובה ככזו כאן בכוונה.

### Businessman צורך יכולות, CEO בונה ארגון

**Businessman**: משתמש ביכולות קיימות, ב-Agents קיימים, ב-AI קיים, בפרילנסרים, בספקים חיצוניים כשצריך. **צורך שירותים, טרנזקציונית.**

**CEO**: מחליט אילו יכולות חסרות, אילו Agents חדשים לבנות, אילו מחלקות דרושות, אילו עובדים קבועים דרושים, בונה ומנהל את הארגון. **בונה מבנה ארגוני, מתמשך.**

הקו: Businessman יכול להשתמש ב-Agent קיים או לשכור פרילנסר לפרויקט בודד. הוא **לא** מקים מחלקות, **לא** בונה Agents חדשים, **לא** בונה מבנה ארגוני קבוע — זה שייך אך ורק ל-CEO.

> **הבהרה נעולה ב-Constitution (2026-08-12, Article VIII)**: יכולות ארגוניות (TikTok, YouTube, Content, Landing Pages, Email, Analytics, Sales, Finance, CRM וכו') הן תשתית פלטפורמה משותפת, **לא שייכות לקטגוריה עסקית** (Affiliate/eCommerce/Digital Products/...). "Business categories use organizational capabilities; they do not own them." **Businessman מפעיל** יכולות שכבר בנויות מראש (זה "Agent קיים" בדיוק) — הוא לא בונה אותן; זה נשאר שייך ל-CEO בלבד, בדיוק כפי שכבר נקבע כאן. הצורה הטכנית (Agent עצמאי / Registry Asset / מבנה אחר) **לא הוכרעה** — החלטת Architecture/Implementation עתידית. ראו `ATLAS_CONSTITUTION.md` Article VIII למקור הבלעדי — לא משוכפל כאן.

### שרשרת יצירת ההכנסה (Revenue Creation Chain) — 7 ה-Milestones, לפי סדר

1. **Subject Discovery** (גילוי Subject עסקי)
2. **Business Opportunity Evaluation** (הערכת הזדמנות עסקית)
3. **Revenue Strategy** (אסטרטגיית הכנסה)
4. **Business Plan Generator** (מחולל תוכנית עסקית) — **כולל במפורש** Marketing & Campaign Strategy (אסטרטגיית שיווק וקמפיינים: מותג, קהל, תוכן, פלטפורמות, נכסים דיגיטליים, משפכי שיווק) כחלק בלתי-נפרד מהתוכנית העסקית עצמה, לא כ-Milestone נפרד
5. **Execution Workflow** (זרימת ביצוע)
6. **KPI Tracking** (מעקב אחר מדדי ביצוע)
7. **Learning Loop** (לולאת למידה)

**Definition of Ready ל-Businessman V1 כולו** (לא לחוליה בודדת): מחזור עסקי אחד, שלם, מקצה לקצה — מחקר → בחירת הזדמנות → אסטרטגיה → Campaign (כולל אסטרטגיית שיווק) → ביצוע דרך Founder Loop → מדידה → למידה — שמייצר הכנסה אמיתית. לא עשרה מחזורים. אחד.

### שלב שני: CEO (מנכ"ל דיגיטלי) — אחרי Businessman

רק לאחר ש-Businessman הוכיח מחזור עסקי שלם, מתחיל שלב ה-CEO: מחלקות, עובדים קבועים, Agents חדשים, ספקים, חלוקת אחריות, האצלת סמכויות, ניהול כמה מנועי הכנסה במקביל. **ייוולד מתוך צורך שנחשף בעבודה, לא מתוכנן מראש.**

### עיקרון האוטונומיה

ברירת המחדל: ATLAS פועל לבד. הוא עוצר ומבקש אישור כשהוא מזהה פעולה מסוכנת, בלתי הפיכה, לא-תואמת-מדיניות, **או פעולה שאין לו עדיין יכולת שיפוט בשלה לגביה, או ודאות מספקת לגביה** (לא רק "אין לו עדיין יכולת ביצוע"). לאחר מכן הוא לומד את המדיניות החדשה — גבולות האוטונומיה עצמם מתפתחים עם הזמן, מבוססי-ראיה.

---

## 2. תהליך רשמי לכל Milestone — 7 שלבים, לא מדלגים

> ### 📜 חוק קבוע: **התהליך שבו נבנה ATLAS הוא חלק בלתי נפרד מהחזון של ATLAS.**
> לא רק המוצר הסופי חשוב — גם המשמעת שבה הוא נבנה. Milestone 2 (Business Opportunity Evaluation) הוכיח את זה בפועל, לא רק בהצהרה: **זו הפעם הראשונה שאבן דרך שלמה עברה את כל 7 השלבים במלואם**, מקצה לקצה, ללא קיצור דרך אחד. זו הראיה שהתהליך עצמו עובד — לא רק הקוד שהוא מייצר.

> ### 📜 חוק קבוע נוסף (נעול 2026-08-12, מ-Milestone 3): **הפיילוט מוכיח את היסודות — הוא לא מגדיר את גבולותיהם. החזון מגדיר את הגבולות.**
> כל יסוד ארכיטקטוני שנבנה ב-Businessman V1 הוא היסוד ש-ATLAS השלם ייבנה עליו — לא גרסה זמנית שתיזרק. המימוש נשאר קטן ומוכח-ראיות; הארכיטקטורה לא.
>
> **מבחן שלוש-השאלות, חובה בכל Architecture Intent/Design מרגע זה:**
> 1. **עובד עבור הפיילוט?**
> 2. **יעבוד גם כש-ATLAS יגדל פי 100/1,000** — מוצרים, משפיענים, מודלי הכנסה, חברות?
> 3. **ישרוד עד שלב ה-CEO בלי לפרק ולבנות מחדש?**
>
> אם התשובה לשאלה 2 או 3 שלילית — עוצרים וחושבים מחדש, לא ממשיכים "כי הפיילוט עובד."
>
> **מנגנון-בדיקה מבצעי, כדי שהמבחן יהיה ניתן-להפרכה ולא תיאורטי:**
> - **שאלה 2 נבדקת דרך צורת-הנתונים**: כל שדה/מבנה שמייצג מושג עסקי שמהותו רבים (מוצרים, משפיענים, מודלי הכנסה, חברות) חייב להיות רב-ערכי (`list`/`dict`/`set`) מהיום הראשון — גם אם רק פריט אחד ממלא אותו בפועל כרגע. **הלוגיקה/האלגוריתם שמנהלים/בוחרים/מדרגים בין כמה פריטים אמיתיים נבנים רק כשיש ראיה אמיתית לכך — לא לפני.** צורת-נתונים סקלרית (`dict[str, str]`, אובייקט בודד, first-match) במקום שהמושג העסקי רב-מטבעו נחשבת כשל.
> - **שאלה 3 נבדקת דרך הזרקת-תלות + יחידת-פעולה בודדת**: כל state/registry/store חייב להיות ניתן-להזרקה (constructor param, `path`/`store`, לעולם לא global/singleton קשיח), ומאורגן ליחידה בודדת (קטגוריה/Goal/קמפיין/חברה אחת) ששכבת-תזמור חיצונית (כמו `ceo.tick()` היום, שכבת-CEO עתידית מחר) מריצה שוב ושוב — לא לוגיקה שמניחה "יש רק הרצה אחת בעולם."
>
> **דוגמה שכבר נבדקה ועברה** (2026-08-12): `CEOBrain`/`atlas.core.Registry`/כל Registry (`BrainMemory`, `OpportunityStore`, `CampaignRegistry`...) כבר מוזרקי-תלות במלואם — ריצה עתידית של כמה חברות במקביל, כל אחת עם קבוצת-Registries משלה, לא דורשת פירוק, רק שכבת-תזמור חדשה. **דוגמה שנכשלה ותוקנה**: `confidence.BOOTSTRAP_TASK_CATEGORY: dict[str, str]` — קטגוריה→ערוץ יחיד, תקרה ארכיטקטונית אמיתית; תוקנה ל-`BOOTSTRAP_TASK_CATEGORIES: dict[str, list[str]]` (ראו Milestone 3 §5) מבלי לגעת בקוד הנעול של `decision_apply.py` — באמצעות מפה חדשה ונפרדת, לא עריכת הקיימת, בדיוק כפי ש-`OPPORTUNITY_DISCOVERY_BOOTSTRAP_OVERRIDES` כבר עשה קודם.

```
Definition of Ready (הגדרת מוכנות)
        ↓
Capability Definition (הגדרת יכולת)
        ↓
Architecture Intent (כוונה ארכיטקטונית)
        ↓
Design (תכנון)
        ↓
Implementation (מימוש)
        ↓
Qualification (אימות)
        ↓
Vision Milestone Review (סקירת אבן דרך בחזון)
        ↓
✅ Approved (מאושר)
```

**רק אחרי שכל 7 השלבים הושלמו במלואם, וה-Vision Milestone Review אישר — מסמנים ✅ Approved במסמך הזה, ורק אז מתחיל ה-Milestone הבא.** לא קופצים קדימה. לא מוסיפים יכולות מרעיון רגעי. לא חוזרים אחורה בלי ראיה חדשה.

---

## 3. Milestone 1 — Subject Discovery (גילוי Subject עסקי) — ✅ Approved

**Definition of Ready:** מנגנון אוטונומי, ללא זריעה אנושית, שממלא `Finding.subject` בערך אמיתי, ספציפי, לא מפוברק, לא הד של הקטגוריה — מוכלל על פני יותר מתחום טקסטואלי אחד.

**Vision Milestone Review:**
- **מטרה:** ATLAS מוצא הזדמנויות עסקיות אמיתיות, ספציפיות — לא רק "קטגוריה שווה מעקב."
- **קריטריוני הצלחה:** ראו Definition of Ready למעלה.
- **ראיות:** `docs/ROOT_CAUSE_ANALYSIS_RUN4.md` (H1 נכשלה לבדה; H2+ניווט אמיתי אוששה, 6/6 קטגוריות טקסטואליות, אפס כשל מלא). `docs/ARCHITECTURE_INTENT_GAP_A_SUBJECT_DISCOVERY.md` + `docs/DESIGN_GAP_A_SUBJECT_DISCOVERY.md` נעולים. מומש ב-`src/atlas/assets/research_discovery/agent.py`. 11 בדיקות חדשות, 1490/1490 חבילה מלאה. **אימות חי במקצה-לקצה, בקוד ייצור אמיתי**: `ResearchDiscoveryAgent.run()` ייצר `Finding(subject="Notion templates")`/`Finding(subject="Canva templates")` אוטונומית, ללא זריעה אנושית — לראשונה.
- **מחוץ לתחום, בכוונה:** `Finding.market` (לא נבדק). YouTube/וידאו (מנגנון תמלול נפרד, לא קיים). סינון byline — **Known Limitation מוצהר**, נמדד ב-Qualification עתידי, לא נבנה. Business Opportunity Evaluation (Milestone הבא). Digital Business Understanding הרחב (Meta Capability, לא הושלם ולא אמור להיות מושלם כאן).
- **סטטוס:** **✅ Approved.**

---

## 4. Milestone 2 — Business Opportunity Evaluation (הערכת הזדמנות עסקית) — ✅ Approved

**Definition of Ready (נעולה, 2026-08-12):**

> בהינתן 2+ מועמדים עסקיים אמיתיים (Subjects) שהתגלו אוטונומית באותה קטגוריה, ATLAS מסוגל לייצר, ללא סיוע אנושי, עבור כל אחד: **הערכה** עסקית אמיתית מבוססת-ראיות (יתרונות, חסרונות, מה ידוע/לא ידוע — לעולם לא מפוברק), ו**סיווג** אמיתי — "מוכן להתקדם" או "אין עדיין מספיק ראיות, להמתין." בין המועמדים ה"מוכנים" — דירוג מנומק. ההערכה/הדירוג משתנים נכון כאשר ראיות אמיתיות חדשות מתווספות.

**גבול מפורש, שהוסכם אחרי דיון אמיתי (לא מובן מאליו — נשמר כהיסטוריה, לא נמחק)**: Milestone 2 **אינו** מחליט כמה מנועי הכנסה להפעיל בפועל במקביל, ואינו כופה בחירת-מנצח-יחיד. שאלת "כמה להתחיל, בהינתן משאבים/סיכון" נבדקה במפורש והוחלט שהיא שייכת ל-**Milestone 3 (Revenue Strategy) ול-`Strategist` הקיים והמוכח** (הקצאת-משאבים מתמשכת, לא החלטה חד-פעמית) — לא ל-Milestone הזה. הוחלט כדי למנוע כפילות/קריסת-גבולות בין השלבים.

**מבחן ההפרכה ל-Qualification עתידי**: שני מועמדים אמיתיים, אחד עם ראיות אובייקטיבית חזקות יותר — ATLAS מעדיף אותו נכון. כשראיה אמיתית חדשה הופכת את התמונה — הדירוג/הסיווג מתהפכים נכון, לא נשארים תקועים.

**רקע/ראיות שכבר נאספו** (מ-`docs/BUSINESSMAN_V1_INVENTORY.md`): `opportunity_ranking.explain_opportunity_subject()`/`opportunity_confidence()` כבר קיימים ברמת Subject בודד — אבל רק 2 גורמים (מקורות, עדכניות), מתוך 9 קריטריונים עסקיים אמיתיים שהוגדרו (ביקוש, תחרות, דרך-אמיתית-להכניס-כסף, תוכנית-Affiliate, הגעה-לקהל, זמן-להכנסה, סיכון, פוטנציאל-הכנסה, התאמה-ליכולות) — חלקם מחוץ לתחום כאן במפורש (ראו למטה).

**מחוץ לתחום, בכוונה**: ביקוש-שוק אמיתי (אין מקור נתונים קיים), בדיקת-תוכנית-Affiliate אוטומטית (קיים רק ל-affiliate ספציפית), הגעה-לקהל ברמת Subject (שייך ל-Milestone מאוחר יותר/CEO). כמה מנועים להפעיל במקביל (ראו הגבול המפורש למעלה — שייך ל-Milestone 3/Strategist).

**שאלה שהוכרעה** (`docs/CAPABILITY_DEFINITION_BUSINESS_OPPORTUNITY_EVALUATION.md`): זו **יכולת חדשה**, לא הרחבה של `explain_opportunity_subject()` או של Reasoning — נבדק ישירות בקוד (טבלת קלט/פלט), ואושר דרך מבחן Policy-Dependence (סף ה"מוכן/לא-מוכן" ומשקלות הדירוג הם החלטות-מדיניות אמיתיות, לא עובדה מכנית).

**Qualification** (`docs/QUALIFICATION_BUSINESS_OPPORTUNITY_EVALUATION.md`) — ענה במפורש על שלוש השאלות: (1) Ready/Wait **לעולם לא** מופעל בצינור החי — לא "לעיתים רחוקות," **ודאות מבנית**: Bridge 1 הוא הכותב היחיד ל-Opportunity האמיתי, ומעולם לא יוצר אחד עם פחות מ-`MIN_INDEPENDENT_SOURCES`. הוכח סטטית (חיפוש קוד מלא) **וגם** חי (6 ticks אמיתיים, `wait` לא הופיע אף פעם). (2) לא כפילות מזיקה — שני השערים תמיד מסכימים, אין ניגוד — אבל רדומה, לא מבצעת עבודה אמיתית כרגע. (3) נמצאו שני Consumer-ים עתידיים סבירים: נתיב-יצירה עתידי שני שעוקף את Bridge 1, או הפרדה עתידית בין סף-קיום לסף-מוכנות-עסקית (זהים היום במקרה, לא מהכרח). **אין תיקון, אין שינוי קוד.**

**Vision Milestone Review (2026-08-12):**
- **מטרה:** ATLAS מסוגל להעריך כל הזדמנות עסקית אמיתית בפני עצמה — יתרונות/חסרונות/מה ידוע/לא ידוע — ולסווג אותה "מוכנה להתקדם" מול "עדיין לא," ולדרג באופן מנומק את המוכנות, בלי לכפות בחירת-מנצח-יחיד ובלי לגעת בהקצאת משאבים.
- **קריטריוני הצלחה:** ראו Definition of Ready למעלה.
- **ראיות:** `docs/CAPABILITY_DEFINITION_BUSINESS_OPPORTUNITY_EVALUATION.md` (יכולת חדשה, לא הרחבה — נבדק ישירות בקוד ובמבחן Policy-Dependence). `docs/ARCHITECTURE_INTENT_BUSINESS_OPPORTUNITY_EVALUATION.md` (קריא-בלבד, החלטה נעולה עם נימוק ישיר מ-RCA גורם B; לא תלוי ב-Reasoning, הוכרע במפורש). `docs/DESIGN_BUSINESS_OPPORTUNITY_EVALUATION.md` (גורמים אמיתיים בלבד, שימוש חוזר במנגנונים קיימים, מבחן הפרכה מפורש). מומש ב-`src/atlas/brain/opportunity_evaluation.py`. 9 בדיקות חדשות עוברות, חבילה מלאה 1502 עוברות (6 כשלים קיימים-מראש אומתו כלא-קשורים דרך `git stash`). **אימות חי, מקצה-לקצה, דרך קוד ייצור אמיתי**: Findings אמיתיים → Bridge 1 → Opportunities אמיתיים → הערכה אמיתית — Notion templates (4 מקורות) דורג נכון מעל Canva templates (2 מקורות). `docs/QUALIFICATION_BUSINESS_OPPORTUNITY_EVALUATION.md` — שלוש השאלות שהוגדרו נענו במלואן, בראיות (קוד + ריצה חיה), ללא תיקון.
- **מחוץ לתחום, בכוונה:** הקצאת-משאבים/כמה-מנועים-במקביל (Milestone 3/`Strategist`). אפיון יחסים בין הזדמנויות (משלימות/מתחרות — Backlog, הרחבה עתידית של Reasoning). ביקוש-שוק/Affiliate-אוטומטי/הגעה-לקהל/פוטנציאל-$ (אין מקור נתונים אמיתי). שינוי Opportunity קיים (קריא-בלבד, נעול). תלות ב-Reasoning (הוכרע שלא).
- **סטטוס:** **✅ Approved.**

---

## 5. Milestone 3 — Revenue Strategy (אסטרטגיית הכנסה) — ✅ Approved

**נפתח רשמית 2026-08-12.** לפי המשמעת שנקבעה: מתחילים מחדש משלב 1/7 — **Definition of Ready** — לא Design, לא קוד.

**רקע/ראיות קיימות** (מ-`docs/BUSINESSMAN_V1_INVENTORY.md`): "Revenue Strategy" קיים היום **בחלקים נפרדים**, לא כמנגנון אחד: `Strategist.reallocate()` (מוכח, חי — אבל פועל **אחרי** מחויבות, על Goals פעילים בלבד, לא על Opportunities טרום-מחויבות), `_find_reusable_influencer()`/`_find_reusable_brand()` (מוכח, חי — בחירת נכס קיים לשימוש חוזר), `provider_ranking.rank_providers()` (מוכח — בחירת ספק בתוך קטגוריה). **הפער האמיתי**: שום מנגנון לא גוזר מהראיות איזה **מודל הכנסה** (Affiliate/SaaS/Subscription/Digital Product/Services/Advertising) מתאים למועמד ספציפי — `Campaign.platform_strategy` וכו' נשארים טקסט חופשי.

**גבול שכבר נעול מ-Milestone 2 (לא נפתח מחדש, רק מוזכר)**: זהו המקום הרשמי שבו מוכרעת השאלה "כמה מועמדים לרדוף בפועל במקביל, בהינתן משאבים/סיכון" — לא ב-Milestone 2. שימוש חוזר ב-`Strategist` הקיים, לא מנגנון הקצאה מקביל חדש.

**Definition of Ready (נעולה, 2026-08-12):**

> בהינתן מועמדים "מוכנים" (ready), כבר מוערכים ומדורגים (תוצר Milestone 2, `evaluate_opportunities()`), ATLAS מסוגל להחליט, ללא סיוע אנושי: (א) האם להתחייב בפועל למועמד — לא רק להעריך אותו; (ב) איזה מודל הכנסה אמיתי, מבוסס-ראיות, מתאים לו — לא ניחוש; (ג) כמה מועמדים נכון להפעיל בפועל במקביל כרגע, בהתחשב במשאבים/סיכון/יכולת ביצוע אמיתיים — תוך שימוש חוזר ב-`Strategist` הקיים והמוכח, לא מנגנון הקצאה מקביל חדש. **ורק לאחר ההחלטות האלה** — ליצור את ה-`Goal` האמיתי, כביצוע מכני של ההחלטה שכבר התקבלה (לא כמעבר-ישויות מכני מוקדם יותר). ההחלטה משתנה נכון כאשר משאבים/ראיות אמיתיים משתנים.

**שאלה אדריכלית — הוכרעה (2026-08-12), לא כ-Bridge**: `Goal` בקוד הזה הוא לא עובדה מבנית ניטרלית — הוא **המחויבות העסקית המכרעת** עצמה (מרגע יצירתו, `Strategist` מנהל אותו, משאבים עשויים לזרום, Tasks עשויים להיווצר). Bridge, לפי העיקרון הנעול "משפיע, לעולם לא מחליט," לא יכול ליצור מחויבות עצמה. **התקדים**: `decide()` (שיפוט) ו-`apply_decision()` (ביצוע מכני של verdict שכבר הוחלט) הם שני שלבים תחת אותה אחריות אחת (Decision Engine), לא Bridge נפרד. **לכן**: Milestone 3 אחראי גם על ההחלטה (האם/איזה מודל/כמה) וגם על יצירת ה-Goal בפועל כביצוע מכני של ההחלטה שלו-עצמו — לא גשר נפרד. `Bridges משפיעים. Milestones מחליטים` — נשמר במלואו.

**Capability Definition** (`docs/CAPABILITY_DEFINITION_REVENUE_STRATEGY.md`) — נבדק ישירות: **יכולת חדשה**, לא הרחבה. `apply_decision()` יוצר Goal ברמת-קטגוריה בלבד, **בלי להכיר שום Subject ספציפי** שהוערך ב-Milestone 2 (ממצא אמיתי, לא הונח). אף מנגנון קיים לא מגשר בין Subject-ready לבין Goal-עם-מודל-הכנסה-ומתוקצב. עבר מבחן Policy-Dependence (בחירת מודל-הכנסה וכמות-ההתחייבות תלויות-מדיניות אמיתיות).

**Architecture Intent** (`docs/ARCHITECTURE_INTENT_REVENUE_STRATEGY.md`) — חלוקת אחריות עסקית נעולה לפי ארבעת העקרונות: Revenue Strategy מחליט הכל (התחייבות/מודל/כמות) ויוצר Goal כביצוע מכני; `Strategist` ללא שינוי — מנהל Goals קיימים, לעולם לא יוצר. **ממצא ביושר**: מודל-הכנסה עשוי להיות דטרמיניסטי כרגע (`BOOTSTRAP_TASK_CATEGORY` הוא מיפוי 1:1) — Backlog אמיתי, לא מפוברק. **שאלת תיאום פתוחה, לא הוכרעה**: שני נתיבי יצירת-Goal (הישן הקטגוריאלי + החדש ברמת-Subject) עשויים להתנגש — מקביל בדיוק לתקדים `claimed_goal_ids` שכבר נפתר פעם בין `content_factory_advance` ל-`campaign_advance`. מסומן ל-Design.

**Design** (`docs/DESIGN_REVENUE_STRATEGY.md`) — הכריע חד-משמעית את שאלת התיאום: Milestone 3 בלבד יוצר Goal מיוחס-Subject; `decide()`/`apply_decision()` הישן ללא שינוי. אכיפת "Opportunity אחד → Goal אחד לכל היותר" (`opportunity.goal_id is not None` → דילוג). לפני יצירה חדשה, בדיקה חוזרת ב-`goals_touching_category()` (קיים, אותה בדיקה כמו `decide()`'s "already_invested") — אם קיים Goal קטגוריאלי מהנתיב הישן, **מצטרפים** אליו (Reuse Before Build) במקום ליצור כפול; אם כבר "תפוס" ע"י Opportunity אחר — נוצר Goal נפרד. מודל-הכנסה נשאר דטרמיניסטי (ביושר, לפי Architecture Intent); מכסת-משאבים היא סף מוצהר פשוט, לא מודל מומצא. 4 חלקי מבחן הפרכה מוגדרים.

**Implementation** (`src/atlas/brain/revenue_strategy.py`, `tests/brain/test_revenue_strategy.py`) — `commit_ready_opportunities(category, opportunities, knowledge, memory)` בנוי **בדיוק** לפי ה-Design הנעול, ללא סטייה: (א) בדיקת אידמפוטנטיות ראשונה (`opportunity.goal_id is not None` → `already_committed`, דילוג); (ב) קביעת מודל-הכנסה מ-`BOOTSTRAP_TASK_CATEGORY` — אם אין ערוץ אמיתי → `no_real_channel`, לא ממציא אחד; (ג) בדיקת מכסת-משאבים — קבוע מוצהר `MAX_CONCURRENT_COMMITMENTS = 3`, נספר מ-`BrainMemory.goals()` פעילים אמיתיים, מחושב מחדש בכל קריאה (ללא מצב שמור); אם מוצה → `deferred_resources`, לא נדחה/נמחק; (ד) הצטרפות-לפני-יצירה: `goals_touching_category()` (קיים, ללא שינוי) מאתר Goal קטגוריאלי פעיל שאף Opportunity אחר לא כבר תפס (`opportunity.goal_id`) — אם נמצא, מצטרפים (`joined_existing_goal`); אחרת, נוצר `Goal`+`Task` חדשים, מתואמים דרך `Opportunity.goal_id`/`task_id` (נכתבים פעם אחת בלבד). `decide()`/`apply_decision()` — לא נגעו בקוד שלהם כלל, רק נקראים (`goals_touching_category`) לפני החלטה.

**בדיקות**: 16 בדיקות (`test_revenue_strategy.py`) — כולל **4 חלקי מבחן ההפרכה המדויקים של ה-Design (§7)**: (א) הצטרפות ל-Goal קטגוריאלי קיים, לא כפילות; (ב) שני Subjects "ready" באותה קטגוריה מקבלים שני Goals נפרדים; (ג) הרצה חוזרת לא יוצרת Goal שני (אכיפת 1:1); (ד) מיצוי-משאבים דוחה, ולא פוסל, וההתחייבות מתחדשת אוטומטית כשמשאב מתפנה. Full Suite: 1501 עברו + 6 כשלים ידועים-מראש (`affiliate_intelligence`, מתועדים כלא-קשורים לעבודה הזאת, שאומתו בעבר עם `git stash`) — **ללא רגרסיה חדשה**.

**Live Verification** — הורץ בתיקיית scratch מבודדת (`tempfile.mkdtemp`, לעולם לא `.atlas/` האמיתי) דרך הצינור האמיתי: Finding אמיתי → Bridge 1 (`advance_opportunities_from_findings`) → Milestone 2 (`evaluate_opportunities`) → Milestone 3 (`commit_ready_opportunities`). 5 תרחישים, כולם אושרו, **ללא ממצא בלתי-צפוי אחד** (לא נדרש תיעוד-ממצא לפי המשמעת שנקבעה לשלב הזה): Goal חדש נוצר עם ראיה אמיתית; הרצה חוזרת לא יצרה כפול; הצטרפות אמיתית ל-Goal מנתיב `apply_decision()` הישן; Goal נפרד ל-Subject שני שהגיע אחרי שה-Goal הקטגוריאלי כבר "תפוס"; דחייה-ואז-חידוש-אוטומטי כשמשאב התפנה.

**Qualification** (`docs/QUALIFICATION_REVENUE_STRATEGY.md`) — המייסד ביקש לבדוק **התנהגות עסקית**, לא רק תקינות קוד, ושאל 4 שאלות מפורשות. תשובות מבוססות-ראיות בלבד (כולל הרצה חיה, ישירה, של `Strategist.reallocate()` על Goal אמיתי מ-M3 מול Goal קטגוריאלי ישן): (1) "בחירת מודל הכנסה" מכנית לחלוטין — `BOOTSTRAP_TASK_CATEGORY` הוא תמיד מיפוי 1:1, ו**ממצא חדש**: `revenue_strategy.py` אפילו לא בודק את `OPPORTUNITY_DISCOVERY_BOOTSTRAP_OVERRIDES`/`opportunity_discovery_v1_enabled()` — המקום היחיד בקודבייס שבו לקטגוריה יש בפועל יותר מערוץ אמיתי אחד; "כמה/מתי להתחייב" **כן** החלטה אמיתית — מאומת חי ששינוי מצב-משאבים אמיתי (לא קוד) הופך את אותה תוצאה מ-`deferred_resources` ל-`committed_new_goal`. (2) ה-Goal החדש נושא Subject אמיתי וקישור 1:1 אכוף — שיפור אמיתי מול ה-Goal הקטגוריאלי — אך `founder_estimate` ריק, זהה בדיוק לנתיב הישן: התחייבות-לרדוף אמיתית, לא עדיין התחייבות פיננסית מלאה. (3) הרצה חיה הראתה **0 החלטות** מ-`Strategist.reallocate()` עבור Goal של M3 (`_has_any_input() == False`, `score_cash_flow() == 0.5` נייטרלי) — זהה בדיוק להתנהגותו מול Goal קטגוריאלי ישן ללא נתונים; Strategist לא מקבל "חומר עבודה חדש" בפועל עד שיהיה איתות אמיתי ראשון. (4) התקדמות אמיתית קיימת ומאומתת (ייחוס-Subject שלא היה קיים כלל, שער-התחייבות רגיש-משאבים שלא היה קיים כלל) — אך לא סגירה מלאה של הפער שהוגדר ב-Capability Definition; שני מתוך שלושה יעדים הושגו, השלישי (בחירת מודל אמיתית) נשאר פתוח ביושר. אין תיקון בוצע.

**דיון אדריכלי, אחרי Qualification (2026-08-12)** — המייסד ביקש לבדוק האם ה-Definition of Ready המקורית עדיין הוגנת, לאור הממצא ש"בחירת מודל הכנסה" מכנית לחלוטין. **התברר, בבדיקה נוספת, שזה עמוק מ"אין עוד ערוץ אמיתי עדיין"**: `category` ו-`revenue model` הם היום, בפועל, **אותו ציר** (`BOOTSTRAP_TASK_CATEGORY` הוא מיפוי 1:1) — בחירה אמיתית דורשת גם ערוץ-ביצוע אמיתי שני לקטגוריה **וגם** הפרדה ארכיטקטונית שלא קיימת. מכאן נולד עיקרון-על חדש, שאומץ כחוק קבוע ל-§2 (ראו שם): **"הפיילוט מוכיח את היסודות — הוא לא מגדיר את גבולותיהם. החזון מגדיר את הגבולות,"** עם מבחן שלוש-השאלות (עובד לפיילוט? / פי 100-1,000? / שורד עד CEO בלי לפרק?), ומנגנון-בדיקה מבצעי (Shape-vs-Implementation: צורת-נתונים רבים מהיום הראשון, לוגיקה רק עם ראיה אמיתית).

**תיקון שנובע ישירות מהחוק החדש** (`docs/QUALIFICATION_REVENUE_STRATEGY_SHAPE_FIX.md`) — `confidence.BOOTSTRAP_TASK_CATEGORY: dict[str,str]` זוהה כתקרה ארכיטקטונית אמיתית (נכשל במבחן שלוש-השאלות). תוקן באמצעות `BOOTSTRAP_TASK_CATEGORIES: dict[str,list[str]]` **חדש, נפרד** — מבלי לגעת בשורה אחת ב-`decision_apply.py` הנעול (אותו מנגנון-הפרדה בדיוק כמו `OPPORTUNITY_DISCOVERY_BOOTSTRAP_OVERRIDES`). `revenue_strategy.py` עבר לקרוא מהחדש, בוחר `channels[0]` ביושר (אין עדיין לוגיקת-בחירה, כי אין עדיין ראיה אמיתית לבחור על פיה). מאומת: Full Suite 1503 עברו (+2 בדיקות-צורה) + 6 כשלים ידועים-מראש; הרצה חיה של `decision_apply.py` עם ובלי דגל ה-V1 — זהה-בית להתנהגות הישנה; 5 התרחישים החיים של Milestone 3 חזרו על עצמם זהים. `Delegator` first-match תויג ל-Backlog (§8) כפריט-ביקורת עתידי, לא נבדק כעת.

**Vision Milestone Review (2026-08-12):**
- **מטרה:** ATLAS מסוגל להחליט, לכל Subject "מוכן" (תוצר Milestone 2): האם להתחייב אליו בפועל, לתעד את ערוץ-הביצוע האמיתי שלו, וכמה מועמדים נכון להתחייב אליהם בפועל במקביל כרגע — בהתחשב במשאבים אמיתיים — וליצור עבור כל אחד מהם Goal אמיתי, מיוחס-Subject, מתואם נכון מול הנתיב הקטגוריאלי הישן (הצטרפות-לפני-יצירה, ללא כפילות, ללא שינוי לקוד הנעול שלו).
- **קריטריוני הצלחה:** Definition of Ready המקורית (למעלה) + החוק החדש ב-§2, שנוסף כתוצאה ישירה מה-Qualification של ה-Milestone הזה.
- **ראיות:** כל 4 מסמכי המתודולוגיה נעולים (`CAPABILITY_DEFINITION`/`ARCHITECTURE_INTENT`/`DESIGN`/הקוד עצמו). 18 בדיקות ב-`test_revenue_strategy.py` + 2 ב-`test_confidence.py` (הצורה), כולל 4 חלקי מבחן ההפרכה של ה-Design. Full Suite: 1503 עוברות, 6 כשלים ידועים-מראש לא-קשורים. **אימות חי כפול**: מקצה-לקצה דרך הצינור האמיתי (5 תרחישים, לפני ואחרי התיקון, זהים), ובדיקה ישירה של `decision_apply.py` עם/בלי הדגל — אפס שינוי התנהגות. `docs/QUALIFICATION_REVENUE_STRATEGY.md` — 4 שאלות עסקיות (לא טכניות) נענו במלואן, בראיות בלבד, כולל ממצא חדש (הדגל שלא נבדק) ובדיקה חיה ישירה של Strategist. `docs/QUALIFICATION_REVENUE_STRATEGY_SHAPE_FIX.md` — התיקון האדריכלי אומת בנפרד, בהתאם למשמעת שהמייסד ביקש לשמר גם על שינוי קטן.
- **מה עדיין פתוח, ביושר, מתועד ל-Backlog** (§8): בחירה אמיתית בין מודלי-הכנסה (הלוגיקה, לא הצורה) — ממתינה לערוץ-ביצוע אמיתי שני; `founder_estimate` ריק על Goal חדש — Strategist לא פועל עליו בפועל עד איתות אמיתי ראשון; `Delegator` first-match — לא נבדק תחת החוק החדש.
- **מחוץ לתחום, בכוונה:** שינוי ל-`Strategist`/`decide()`/`apply_decision()` (כולם ללא שינוי קוד). בניית ערוץ-ביצוע אמיתי שני (credential-blocked, שייך ל-CEO). לוגיקת-בחירה בין כמה מודלים (אין עדיין ראיה אמיתית).
- **סטטוס:** **✅ Approved.**

---

## 6. Milestone 4 — Business Plan Generator (מחולל תוכנית עסקית) — ✅ Approved

**נפתח רשמית 2026-08-12**, ישירות מתוך ה-Vision Milestone Review של Milestone 3 — הצגת-ניתוח מלאה (ללא קוד) מול ה-Roadmap הקיים זיהתה במדויק את הפער האמיתי, לא הונח.

**מיקוד השרשרת שאושר**: Subject Discovery → Opportunity → Evaluation (M2) → Decision/Commitment (M3) → Goal → **[הגשר החסר]** → Campaign → Execution. `Campaign`/`create_campaign()`/`campaign_advance.py` כבר קיימים ומוכחים — הפער הוא **אך ורק** החיבור בין Goal מחויב (M3) לבין Campaign קיים, ולא כל הרחבה נוספת.

**גבולות נעולים, לאורך כל השלבים**:
- **Affiliate בלבד** — קטגוריה יחידה, לפי הערוץ האמיתי היחיד הקיים היום. שום הכרעה על קטגוריה שנייה.
- **Universal Core (`atlas.brain.models.Opportunity`) ללא שום שדה/לוגיקה Affiliate-specific** — נשאר אגנוסטי-קטגוריה לחלוטין. `AffiliateOpportunity` נשאר Adapter/extension downstream, מוגבל ל-affiliate.
- **`campaign_advance.py`, `Campaign`, `create_campaign()`, `_request_founder_choice()` — ללא שום שינוי קוד** לאורך כל ה-Milestone.
- **M3 decides WHAT to pursue. M4 continues into HOW to execute it.** Opportunity שכבר `committed` ב-M3 אינה חוזרת לבחירת-Founder עסקית נוספת — התערבות-Founder מותרת **רק** עבור מידע/אישור אמיתי שחסר (תנאים מסחריים, הרשאה חיצונית), לעולם לא "בחירה מחדש."

**Definition of Ready (מאושר, 2026-08-12)**: קריטריון ההצלחה התפעולי — Opportunity שהתגלתה אוטונומית, עברה M2 ו-M3 והוגדרה committed, מסוגלת להגיע ל-Campaign פעיל **ללא בחירה ידנית של הפאונדר באמצע השרשרת**. ה-DoD העליון של Businessman V1 (§1) נשאר כפי שהוא — לא הומצא DoD חדש ל-Milestone הזה בפני עצמו.

**Capability Definition** (`docs/CAPABILITY_DEFINITION_BUSINESS_PLAN_GENERATOR.md`, נעול) — **בדיקה כנה, לא מיופה**: זו בעיקר יכולת **Integration/Wiring**, לא יכולת עסקית חדשה. כל שיפוט עסקי אמיתי (האם/כמה/איזה מודל להתחייב) כבר קיים ונעול ב-Milestone 3. מבחן Policy-Dependence: רוב המנגנון מכני; שאלה אחת אמיתית ופתוחה סומנה ל-Architecture Intent — האם Opportunity מחויב עדיין עובר דרך `_request_founder_choice()` הקיים.

**Architecture Intent** (`docs/ARCHITECTURE_INTENT_BUSINESS_PLAN_GENERATOR.md`, נעול) — הוכרע: **גשר קטן, יחיד, האחריות היחידה ש-M4 מוסיף.** מתרגם Opportunity מחויב ל-`AffiliateOpportunity`, בודק מכנית אם תנאים מסחריים קיימים, ואם לא — Task ממוקד (לא `_request_founder_choice()`). `campaign_advance.py`/Universal Core/`_request_founder_choice()` — ללא שינוי. עבר מבחן שלוש-השאלות; Article VIII לא רלוונטי ישירות (לוגיקת-מוח פנימית, לא יכולת-ביצוע).

**Design** (`docs/DESIGN_BUSINESS_PLAN_GENERATOR.md`, **נעול מחדש** 2026-08-12, אחרי שני תיקונים) — זרימת נתונים מקצה-לקצה, מיפוי שדות מלא, קריטריון "תנאים מסחריים מספיקים" (קישור תקין + ספק אמיתי + `commission_per_conversion > 0.0` דווקא, לא `>= 0.0`), Task ממוקד (`"affiliate_commercial_terms_needed"`, לא `"create_asset"`), דה-דופ בשלוש שכבות. **תיקון 1, תוך כדי הביקורת של המייסד**: נמצא שהמסלול "הפאונדר מספק תנאים בנפרד" לא היה שלם — נוסף רכיב חמישי, מפורש, `create_affiliate_opportunity_from_terms()`, מאותה משפחה בדיוק כמו `create_influencer_from_proposal()`/`create_brand_from_proposal()`. **תיקון 2, נמצא ע"י Claude בתחילת Implementation, לפני קוד**: הטענה "`reversible=False` מספיק לבדו" הייתה שגויה — מאומת ישירות ש-`approve()` בלי `Proposal` מקושר היה נופל למסלול-ההתאמה המסוכן של Registry (`unmatched` fallback, אותה תבנית-כשל שכבר תוקנה פעם בעבר) ולעולם לא מגיע ל-`"done"`. תוקן: `"affiliate_commercial_terms_needed"` נוספת ל-`ALWAYS_REQUIRES_APPROVAL` — **אך ורק** לשימוש-חוזר במסלול Proposal/approve הקיים, לא Asset/מנגנון חדש. 6 חלקי מבחן הפרכה מוגדרים (נוסף חלק ו').

**Implementation** (`src/atlas/brain/business_plan_advance.py`, `tests/brain/test_business_plan_advance.py`, שינויים ב-`models.py`/`ceo.py`/`cli.py`/`test_ceo.py`) — `advance_business_plan_generation()` (הגשר, Task ממוקד בלבד) ו-`create_affiliate_opportunity_from_terms()` (הרכיב החמישי) נבנו בדיוק לפי ה-Design. 12 בדיקות חדשות (11 יחידה + 1 קצה-לקצה אמיתית דרך `tick()`/`approve()`/CLI). Full Suite: 1515 עברו, 6 כשלים ידועים-מראש. אימות חי כלל קריאה אמיתית ל-CLI כתת-תהליך.

**Qualification** (`docs/QUALIFICATION_BUSINESS_PLAN_GENERATOR.md`) — שתי בדיקות ממוקדות: (1) 6 הכשלים מוכחים כ-baseline קיים בשלוש דרכים עצמאיות (טרייסבק ישיר, לא רק השוואת-מספרים). (2) **ממצא אמיתי, לא מתוקן בקוד**: אינטראקציה בין `ATLAS_OPPORTUNITY_DISCOVERY_V1` (כשדלוק) לגשר החדש — הדה-דופ הפנימי מונע כפילות-נתונים, אך תנאים מסחריים אמיתיים שסופקו עלולים להיזרק בשקט כשמנגנון ישן, בלתי-תלוי, כבר תפס את אותו Goal.

**החלטת "כביש אחד" (2026-08-13)** — לפני תיקון-תיאום, בוצעה השוואה תפקודית מלאה בין `opportunity_discovery_advance.py` הישן לבין מסלול M4 (7 שאלות: אחריות/inputs/תוצרים/יכולת-ייחודית/תרחיש-דו-קיום/deprecate-או-מחלף/סיכוני-הסרה) — **אין הצדקה עסקית לשני מסלולים מקבילים**. אושר: הפסקת קריאת `advance_opportunity_discovery()` מתוך `tick()` בלבד — לא Cleanup רחב. `docs/DESIGN_BUSINESS_PLAN_GENERATOR.md` §7 (נעול מחדש) מתעד את ההחלטה המדויקת: `rank_opportunities()` (6 קוראים אחרים), הדגל (2 שימושים אחרים), הקובץ/הפונקציה/8 הבדיקות של `opportunity_discovery_advance.py` — **הכול ללא שינוי**. שינוי הקוד בפועל: הסרת import+קריאה אחת מ-`ceo.py`. **Qualification חוזר**: ה-race בלתי-אפשרי מבנית כעת (מאומת חי, אותם תנאים בדיוק שהראו את הבעיה), שני השימושים האחרים בדגל ממשיכים לפעול נכון (כולל ממצא-אגבי-מרגיע: `AffiliateIntelligenceAgent.run()` מדווח ביושר "No real opportunity found" ולא תוקע state). 7/7 חלקי מבחן ההפרכה עברו (ז' חדש). Full Suite: 1515 עברו, 6 כשלים ידועים-מראש, ללא רגרסיה.

**Vision Milestone Review (2026-08-13):**

- **מטרה:** Opportunity שהתגלתה אוטונומית (M1), הוערכה (M2) והוחלטה-והתקצבה (M3, קטגוריית affiliate) מגיעה ל-Campaign אמיתי, פעיל, **ללא בחירה עסקית ידנית של הפאונדר באמצע השרשרת** — התערבותו מוגבלת למידע אמיתי-חיצוני שATLAS מבנה לא יכול לדעת בעצמו.
- **קריטריוני הצלחה:** Definition of Ready למעלה + עקרון "M3 decides WHAT, M4 continues HOW."

**תשובות מפורשות לחמש השאלות שנשאלו:**

**1. האם M4 משיג את היכולת מקצה-לקצה?** **כן, מאומת חי פעמיים, לא נטען בלבד.** בפעם הראשונה (Implementation) ובפעם השנייה (Qualification חוזר, אחרי הסרת המסלול הישן) — שרשרת אמיתית מלאה: Finding אמיתי → Bridge 1 → M2/M3 מתחייבים → Task אמיתי → `Proposal` אמיתי → `approve()` → **CLI כתת-תהליך אמיתי** (`atlas affiliate commercial-terms supply`) → `AffiliateOpportunity` אמיתי ב-`selected_for_marketing` → `campaign_advance.py` (ללא שינוי) → Campaign אמיתי, עם `destination_url`/`product_offer` אמיתיים. אפס בחירת-מוצר ידנית באמצע. תקף **בתוך הגבול המאושר** — קטגוריית affiliate בלבד.

**2. Gaps ידועים שנותרו בתוך ה-Scope?** **לא נמצא gap מהותי שלא טופל.** שני הפערים האמיתיים שהתגלו תוך כדי הדרך (המסלול-חוזר-לתנאים-מסחריים החסר; `reversible=False` לא מספיק) **נמצאו ותוקנו לפני שנעל הקוד**, לא הושארו. הגבול היחיד שנשאר הוא זה שאושר במפורש מההתחלה — Affiliate בלבד — לא תקלה, החלטת-scope מודעת.

**3. סיכונים/חובות טכניות לתיעוד, שלא חוסמים סגירה?**
- **`opportunity_discovery_advance.py`** נשאר בקוד, פונקציונלי, עם 8 בדיקות תקפות — אך מנותק מייצור. שאלה פתוחה, אמיתית, לא-חוסמת: להשאיר כתשתית-רדומה או לתייג ל-Cleanup עתידי אמיתי — לא הוכרעה כאן, לא צריכה להיות.
- **Architecture Debt קיים** (§8): שרשרת `affiliate_pipeline` הישנה אפויה-לקטגוריה; `campaign_advance.py`'s `BRIDGED_CATEGORIES` מוגבל ל-affiliate. לא נוצר/הורחב על ידי M4 — קיים מלפני, מתועד, לא נוגע.
- **`Goal.founder_estimate` ריק, `Strategist` לא פועל על Goal של M3/M4 בפועל** (מ-Qualification של M3, עדיין נכון) — Campaign אמיתי נוצר, אך ה-Goal מאחוריו עדיין לא "נראה" ל-Strategist עד איתות-KPI ראשון.
- אף אחד מאלה לא חוסם סגירה — כולם מתועדים, לא מוסתרים. **נשמרים במפורש, ללא תיקון, כחלק מסגירת M4** (ראו גם §8, Backlog) — לפי הנחיית המייסד לא לתקן אותם במסגרת הסגירה הזו.

**4. עקביות בין Design, Implementation, Qualification, ו-Source of Truth?** **נבדק ישירות שוב עכשיו, לא רק נטען**: חתימת `create_affiliate_opportunity_from_terms()` בקוד בפועל (`business_plan_advance.py:119-128`) תואמת מילה-במילה למה שה-Design מפרט. `ALWAYS_REQUIRES_APPROVAL` בקוד תואם להחלטה המתועדת. הקריאה היחידה שהוסרה מ-`ceo.py` תואמת בדיוק למה שסעיף 7 של ה-Design אומר. Full Suite הורץ שוב הרגע: **1515 עברו, אותם 6 כשלים ידועים-מראש, ללא רגרסיה.** ה-Source of Truth (הסעיף הזה) עודכן בכל שלב, לא בדיעבד. **כן, עקבי.**

**5. האם M4 ראוי להיסגר כ-complete?** **בהמלצתי — כן.** היכולת מוכחת מקצה-לקצה, כל ממצא אמיתי שהתגלה (חמישה, לאורך הדרך) טופל במפורש — לא תוקן בשקט ולא הוסתר — התיעוד עקבי, והפערים שנותרו הם גבולות-scope מודעים או חוב-טכני מתועד ולא-חוסם. **המייסד אישר את ההמלצה — 2026-08-13.**

- **מחוץ לתחום, בכוונה:** קטגוריה שנייה (credential-blocked/CEO-stage). שינוי ל-`Campaign`/`campaign_advance.py`/`_request_founder_choice()`/Universal Core (כולם ללא שינוי קוד). Cleanup של `opportunity_discovery_advance.py`.
- **סטטוס:** **✅ Approved (2026-08-13).** כל 7 השלבים הושלמו במלואם, ללא קיצור דרך. שלושת הסיכונים/החובות הלא-חוסמים (סעיף 3 למעלה) נשמרים מפורשות ב-Backlog (§8), ללא תיקון, כפי שהונחה.

---

## 7. Milestones 5-7 — ראו Inventory, עדיין לא התחילו רשמית

פירוט מלא של מה שכבר קיים בכל שלב: `docs/BUSINESSMAN_V1_INVENTORY.md`. תמצית:
- **Execution Workflow** — מנגנון בסיסי מוכח (`atlas.orchestrator`).
- **KPI Tracking** — מנגנון בסיסי מוכח (`KPIRegistry`/`Ledger`).
- **Learning Loop** — שלושה מנגנונים בסיסיים מוכחים (`Strategist`, `success_patterns`, `Success Laws`).

---

## 8. Backlog — רעיונות אמיתיים, מחוץ לשלב הפעיל, לא נשכחים

- **גורם שורש B** (Bridge 3 / `Task.priority_score` אינרטי) — הוחלט במפורש שלא חוסם Businessman V1; Founder Loop משמש כצרכן במקום. פתוח מחדש רק אם/כש-ATLAS ינוע לכיוון בחירה אלגוריתמית מלאה (שלב CEO?).
- **H2/H3 (root cause B)** — לא נבדקו, לא נדרשים כרגע.
- **Digital Business Understanding כ-Capability פעילה** (Meta Capability, סעיף 1) — למידת מתחרים/best-practices עמוקה, מעבר ל-Success Laws record-only. שאיפה מוצהרת של Businessman, אך תיבנה בהדרגה, לא כ-Milestone חוסם.
- **Business Mastery** / **Business Operations** (ניהול-מקביל אמיתי בין כמה מנועים) — שלבים עתידיים מוצהרים, לא Businessman V1.
- **CEO** (מחלקות, עובדים, Agents חדשים) — נדחה במכוון עד שמחזור עסקי אחד יוכיח את עצמו.
- **סינון-byline** ב-Subject Discovery — Known Limitation, נמדד לא נבנה, אלא אם ראיות עתידיות יראו דליפה משמעותית.
- **Autonomous execution מלא** (מעבר ל-Founder Loop) — שאיפה מוצהרת, לא V1.
- **הרחבה עתידית של Executive Reasoning — אפיון יחסים בין הזדמנויות, לא רק העדפה בין שתיים** (2026-08-12): האם שתי הזדמנויות שכבר עברו הערכה (Milestone 2) **משלימות** זו את זו (למשל: תזרים-מהיר מול נכס-ארוך-טווח) או **מתחרות** (על אותו קהל/משאבים/זמן) — ופלט איכותי כמו "להפעיל יחד" / "להתחיל באחד, להכין את השני" / "לבחור אחד בלבד" / "להמתין." **לא שייך היום** — Reasoning הקיים (`compare_opportunities()`) משתמש רק ב-2 גורמים צרים (competition+evidence), פיזית חסר לו הקלט העשיר הדרוש (סיכון, זמן-להכנסה, אופי-הכנסה) שרק Milestone 2 מחשב. **עדיין לא הקצאת-משאבים** (Strategist נשאר האחראי הבלעדי לזה) — רק המלצת-איכות על היחס בין מועמדים. נשמר לעתיד, לא ל-V1 הנוכחי, כדי לא לפתוח מחדש Milestone 2 שכבר ננעל.
- **בחירה אמיתית בין מודלי-הכנסה** (Milestone 3, 2026-08-12) — הצורה כבר מוכנה (`BOOTSTRAP_TASK_CATEGORIES: dict[str,list[str]]`), אך הלוגיקה לא נבנית עד שיתקיימו שני תנאים אמיתיים: (1) ערוץ-ביצוע אמיתי שני לאותה קטגוריה (credential-blocked היום, digital_product/content הם placeholder — שייך לשלב ה-CEO, בניית יכולת חדשה, לא Businessman צורך-קיים). (2) הפרדה ארכיטקטונית אמיתית בין `category` ל-`revenue model` כשני צירים עצמאיים — לא קיימת היום.
- **Goal חדש (Milestone 3) חסר מסגרת פיננסית, Strategist לא פועל עליו בפועל** (2026-08-12, **אושר מחדש כפתוח ב-Vision Milestone Review של Milestone 4, 2026-08-13**) — `founder_estimate` ריק בכל Goal שנוצר (כולל Goals שהגיעו ל-Campaign אמיתי דרך M4); מאומת חי ש-`Strategist.reallocate()` מחזיר 0 החלטות עד שיש איתות אמיתי ראשון (founder_estimate או קריאת KPI). לא רגרסיה — זהה להתנהגות מול Goal קטגוריאלי ישן — אך פער אמיתי, פתוח. **לא תוקן במסגרת סגירת M4, במכוון.**
- **`Delegator` first-match routing** (2026-08-12, תחת החוק החדש) — לא נבדק עדיין תחת מבחן שלוש-השאלות; ייתכן שזו תקרה ארכיטקטונית נוספת אם בעתיד יהיו כמה assets אמיתיים המתחרים על אותה קטגוריה. סומן, לא נבדק.
- **`opportunity_discovery_advance.py` כתשתית רדומה** (2026-08-13, Milestone 4) — הפונקציה `advance_opportunity_discovery()`, `rank_opportunities()` (הישות שהיא צורכת), 8 בדיקותיה, והדגל שמגן עליה — כולם נשארו קיימים ותקינים בקוד, אך מנותקים מ-`tick()` (החלטת "כביש אחד," `docs/DESIGN_BUSINESS_PLAN_GENERATOR.md` §7). **שאלה פתוחה, לא הוכרעה, לא-חוסמת**: להשאיר כתשתית-רדומה-לשימוש-עתידי-אפשרי, או לתייג ל-Cleanup אמיתי (הסרת הקובץ/הבדיקות) מתישהו בעתיד. לא תוקן/הוכרע במסגרת סגירת M4, במכוון.

### 🏗️ Architecture Debt — מול Article VIII החדש (2026-08-12), מתועד בכוונה, **לא Refactor עכשיו**

נמצא תוך כדי הדיון שהוביל לתיקון ה-Constitution — לא תוקן, רק מתועד, בהתאם להנחיית המייסד המפורשת:

- **שרשרת `affiliate_pipeline` הישנה** (`AffiliateDepartmentAgent` → `content_factory` → `editorial_review` → `creative_agent` → `publishing_gateway`) **אפויה ישירות לתוך קטגוריית Affiliate** — פועלת על `AffiliateOpportunity` באופן ישיר, לא כיכולת-ביצוע משותפת שקטגוריות אחרות יכולות להשתמש בה. תחת Article VIII החדש, זו לא הצורה הנכונה ("קטגוריה עסקית לא מחזיקה מחלקה משלה") — אבל היא ממשיכה לעבוד בדיוק כפי שהיא, ללא שינוי.
- **`campaign_advance.py`'s `BRIDGED_CATEGORIES = {"affiliate"}`** — הצינור החדש והכללי-יותר (Campaign→Influencer→Production→Orchestrator) קרוב יותר לצורה הנכונה (`Campaign.category` הוא מחרוזת פתוחה), אך בפועל מחובר רק לקטגוריית Affiliate כרגע. לא הרחבה נדרשת עכשיו — אין עדיין ראיה/צורך אמיתי לקטגוריה שנייה.
- **טיפול עתידי**: יטופלו רק כשצורך אמיתי יחייב שימוש חוזר ביכולות האלה מקטגוריה שאינה Affiliate — לא מראש, לא כ"ניקיון."
- **אושר מחדש כפתוח, לא-חוסם, ב-Vision Milestone Review של Milestone 4 (2026-08-13)** — M4 לא יצר ולא הרחיב את החוב הזה; קרא אותו כפי שהוא, ללא נגיעה.

---

## 9. חוק ממשל (Governance Rule)

לפני כל RCA/Capability Definition/Design חדש: **"לאיזה Milestone בשרשרת הזו זה שייך?"** אם התשובה היא "אף אחד מהשלב הפעיל" — לא מתחילים, מוסיפים ל-Backlog (סעיף 8) במקום. **כל Milestone עובר את שבעת השלבים בסעיף 2 במלואם, בסדר, לפני שמסמנים ✅ Approved ועוברים הלאה.**

---

**סטטוס מסמך:** **החזון (סעיף 1) נעול רשמית, 2026-08-12.** מעכשיו משתנה רק דרך המימוש, לא היעד, אלא בראיה חזקה שמצדיקה שינוי. הבא בתור: לנסח Definition of Ready ל-Milestone 2 (Business Opportunity Evaluation), לפני תחילת Capability Definition שלו.
