# Architecture Intent — Business Opportunity Evaluation (הערכת הזדמנות עסקית), Milestone 2

**תאריך:** 2026-08-12
**מקור בלעדי:** `docs/CAPABILITY_DEFINITION_BUSINESS_OPPORTUNITY_EVALUATION.md` (נעול), `docs/BUSINESSMAN_V1_SOURCE_OF_TRUTH.md` §4.
**מטרה:** מיקום ארכיטקטוני בלבד — אחריות, קלט, פלט, תלויות, גבולות. **לא מחלקות, לא מודולים, לא APIs.**

---

## אחריות

בהינתן 2+ **Opportunities** אמיתיים קיימים (מ-`OpportunityStore`, אותה ישות שכבר בונים Bridge 1/2/Reasoning) באותה קטגוריה, לייצר עבור כל אחד הערכה עסקית אמיתית, מבוססת-ראיות בלבד — יתרונות, חסרונות, מה ידוע/לא ידוע — וסיווג "מוכן להתקדם"/"אין עדיין מספיק ראיות." בין ה"מוכנים" — דירוג מנומק.

## מה זה מקבל

**Opportunities אמיתיים קיימים** (מ-`OpportunityStore`, לא Findings גולמיים ישירות — אותו עיקרון Cognitive Continuity ש-Reasoning כבר מיישם: Opportunity כבר צבר את `evidence_finding_ids` הרלוונטיים, היכולת הזו סומכת על כך במלואו, לא אוספת ראיות בעצמה). ראיות אמיתיות דרך `KnowledgeBase` (לציטוט, לא לאיסוף חדש). Success Laws רלוונטיים (`relevant_success_laws()`, קיים).

## מה זה מחזיר

תוצר אחד, אמיתי, לכל Opportunity: הערכה מנומקת (יתרונות/חסרונות/פערי-ראיה מפורשים — "אין ראיה לביקוש," לא מספר מומצא), סיווג ready/wait, וכאשר ready — ציון/דירוג יחסי בין שכניו ה-ready. **לא Goal, לא Task, לא Proposal.**

## החלטה נעולה — קריא-בלבד, אינו נוגע ב-Opportunity הקיים

**היכולת הזו לעולם לא מְשַׁנה Opportunity קיים** — לא stage, לא competition, לא שום שדה. מחושבת מחדש בכל קריאה, בדיוק כמו `explain_opportunity_subject()`/`compare_opportunities()` הקיימים. **הסיבה, לא רק עקביות-סגנון**: היום בדיוק, ה-RCA של גורם B מצא באג אמיתי שנובע בדיוק ממצב הפוך — שני מנגנונים כותבים לאותו שדה משותף (`Task.priority_score`, `SimplePrioritizer` מול Bridge 3) ללא תיאום, ודורסים זה את זה. שמירה על "קריא-בלבד" כאן, מלכתחילה, היא לא סגנון — היא מניעה ישירה של אותה מחלקת-באג, לפני שהיא נולדת.

**משמעות**: מי-בדיוק מקדם את `Opportunity.stage` (מ-"discovered" ל-"researched"/"ranked"), ומתי, **נשאר שאלה פתוחה, לא-מוכרעת** — בדיוק כפי ש-Bridge 1 כבר הצהיר במפורש ("who does that, and when, is a real, still-open question — not answered here"). היכולת הזו לא עונה עליה. מי שכן יענה עליה — Design/Milestone עתידי, לא כאן.

## שאלה שהוכרעה (2026-08-12) — הדירוג-בין-המוכנים אינו תלוי ב-Reasoning

**הוכרע: לא.** נבדק במפורש אם Reasoning צריך להתרחב כדי לשאת "האם מועמדים משלימים או מתחרים" (רעיון עסקי אמיתי שעלה בדיון) — אך זה נדחה במכוון מ-Milestone 2 עצמו: Reasoning הקיים (`compare_opportunities()`) משתמש רק ב-2 גורמים צרים (competition+evidence), חסר לו פיזית הקלט העשיר (סיכון, זמן-להכנסה, אופי-הכנסה) שרק היכולת הזו מחשבת. שימוש בו לדירוג הסופי היה **מצמצם** את העושר שכבר חושב, לא מנצל אותו. **הדירוג-בין-המוכנים משתמש באותם גורמים עשירים שכבר חושבו עבור הסיווג ready/wait — לא קורא ל-Reasoning.**

**נרשם ביושר, לא הוסתר**: המשמעות היא ש-Reasoning **נשאר בלי צרכן חי** — "Consumer Mismatch" מ-`docs/ROOT_CAUSE_ANALYSIS_RUN4.md` לא נסגר על ידי ההחלטה הזו. הרעיון העסקי שהוביל לשאלה (אפיון יחסים בין הזדמנויות — משלימות/מתחרות) נשמר במפורש ב-Backlog כהרחבה עתידית של Reasoning, לכשיהיה לו הקלט העשיר הדרוש — לא ל-Milestone הזה.

## תלויות

`OpportunityStore` (קיים), שדות `Opportunity` הקיימים, `KnowledgeBase` (לציטוט בלבד), `relevant_success_laws()` (קיים), `weighted_average_of_available()` (primitive משותף קיים). **אין תלות ב-`reasoning.compare_opportunities()`** — הוכרע במפורש למעלה.

## על מה זה **אינו** אחראי (גבולות מפורשים)

- **לא אוסף ראיות חדשות** — תפקיד Research Trigger/Milestone 1. פועל אך ורק על מה שכבר נצבר.
- **לא ממציא נתונים לקריטריונים שאין להם מקור אמיתי** (ביקוש-שוק, בדיקת-Affiliate אוטומטית, הגעה-לקהל) — מציין "לא ידוע" במפורש, לעולם לא מפוברק.
- **לא מחליט כמה מועמדים לרדוף בפועל במקביל, ולא מקצה משאבים** — Milestone 3/`Strategist`, נעול כגבול ב-Definition of Ready.
- **לא יוצר Goal/Task/Proposal, לא קורא ל-`decide()`.**
- **לא משנה Opportunity קיים** — ראו החלטה נעולה למעלה.
- **לא בוחר אסטרטגיית הכנסה** (Affiliate/SaaS/Subscription/וכו') — Milestone 3.

## שכבה

Business Brain — שיפוט אמיתי, לא חישוב מכני (עבר את מבחן Policy-Dependence ב-Capability Definition). לא Agentic OS.

---

**סטטוס:** Architecture Intent **נעול**, 2026-08-12. הבא: Design (שלב 4 מתוך 7).