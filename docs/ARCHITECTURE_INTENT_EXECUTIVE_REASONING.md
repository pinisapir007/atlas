# Architecture Intent — Executive Reasoning (היכולת החדשה, לפי `CAPABILITY_DEFINITION_NEXT_MILESTONE.md`)

**תאריך:** 2026-08-11 (נעול), **עודכן:** 2026-08-11 (אותו יום — ראיות חדשות, לא טעות)
**מטרה:** מיקום ארכיטקטוני בלבד — אחריות, קלט, פלט, תלויות, וגבולות. **לא מחלקות, לא מודולים, לא APIs.**

---

## הערת עדכון — למה המסמך הזה השתנה, לא נכתב מחדש

הגרסה הראשונה של המסמך הזה קבעה ש-Reasoning פועל **אחרי** Decision, על Decisions שכבר קיימים. זו הייתה החלטה נכונה **על בסיס הראיות שהיו קיימות אז** — Opportunity עדיין לא היה קיים כישות אמיתית, ולכן הדרך היחידה שנראתה בטוחה הייתה להשוות תוצרים מוגמרים. **זו לא הייתה טעות — זו הייתה המסקנה הנכונה מהראיות שהיו אז.** בניית Opportunity Universal Core באותו יום, ובדיקה חוזרת של הנחת ה-`StrategicObjective`, סיפקו ראיה חדשה שהמיקום המקורי לא לקח בחשבון. הסעיף הבא מתאר את המיקום המעודכן. הגרסה הקודמת נשמרת כאן, לא נמחקת, מאותה סיבה בדיוק ש-`Decision.superseded_id` אף פעם לא מוחק היסטוריה.

## מסגרת, לא חוליה — הערה על Identity

השרשרת הקוגניטיבית המלאה (Identity → Finding → Opportunity → Reasoning → Decision → Goal → Execution → Learning) **אינה שרשרת אחידה מסוג אחד.** שבע החוליות מ-Finding עד Learning הן זרימת-נתונים אמיתית — כל אחת הופכת/מזינה את הבאה. **Identity אינה כזו.** היא לא "הופכת" ל-Finding — היא המסגרת שבתוכה השרשרת כולה פועלת: מה בכלל מחפשים, מה נחשב ראיה, מה נחשב הזדמנות, מהי הצלחה. מוצגת נכון כך:

```
                    Identity
                        │
                        ▼
Finding → Opportunity → Reasoning → Decision → Goal → Execution → Learning
```

לא כחוליה ראשונה בצינור רציף.

## המיקום המעודכן — פתרון, לא רק פשרה מוצהרת

**המתח המקורי (Reasoning קנוני-לפני-Decision מול הצורך לא-לגעת-ב-`decide()`) התברר כדיכוטומיה כוזבת, לא כפשרה אמיתית.** "Reasoning לפני Decision" ו-"Reasoning משנה את מה ש-`decide()` מקבל כקלט" הם שני דברים שונים לגמרי — התערבבו כי לא היה עוד Opportunity שיכול להראות את ההבדל.

**המיקום המעודכן: Reasoning פועל בין Opportunity ל-Decision — לפני Decision באמת, לא רק כסטייה מוצהרת — בלי לגעת בחתימה של `decide()` בכלל.** `decide()` ממשיך לקבל `category: str` בדיוק כפי שהוא היום, ללא שום שינוי. Reasoning משווה בין Opportunities אמיתיים ומשפיע על **איזו** קטגוריה מגיעה בכלל ל-`decide()`, או **באיזה סדר** — לא על מה ש-`decide()` עצמו עושה ברגע שהוא כן נקרא. זה מקיים גם את הסדר הקנוני של ה-Specification וגם את העיקרון "אל תיגע בליבה מוכחת" בו-זמנית — לא צריך לבחור ביניהם.

## אחריות (מעודכן)

בהינתן 2+ **Opportunities** אמיתיים שכבר נוצרו (לא Decisions), להפיק תוצר אחד, אמיתי, שמצטט אותם במפורש ומצהיר העדפה מנומקת ביניהם, עומד במבחן ההפרכה שכבר הוגדר (`CAPABILITY_DEFINITION_NEXT_MILESTONE.md`, סעיף 6, מותאם ל-Opportunity). **לעולם לא מחייב, ולעולם לא משנה Opportunity קיים** — קריאה-בלבד, אותו דיוק בדיוק כמו `explain_opportunity()` הקיים.

## מה היא מקבלת (מעודכן)

- **Opportunities אמיתיים קיימים** (מ-`OpportunityStore`, נבנה ונבדק היום) — לא Decisions, לא Findings גולמיים ישירות. Opportunity כבר צבר את הראיות הרלוונטיות (`evidence_finding_ids`); Reasoning סומך על כך במלואו (Cognitive Continuity).
- **אות מדיניות/העדפה** — עדיין תלות הכרחית (Policy-Dependence Test), עדיין ללא פתרון מלא: `StrategicObjective` נשאר לא-ישים במלואו, כי אין עדיין הערכת-שישה-קריטריונים בסגנון founder_estimate שיכולה להתחבר ל-Opportunity (בדיוק כפי שנמצא לפני שהוא הפך ל-Goal). זה **נשאר Backlog אמיתי**, לא נפתר על ידי קיומו של Opportunity — רק קיבל בית ברור וממוקד יותר לחיות בו.

## מה היא מחזירה

ללא שינוי מהותי: תוצר Reasoning אמיתי שמשווה 2+ **Opportunities**, מצהיר העדפה, מצטט ראיות אמיתיות מכל צד (score/competition/evidence_finding_ids מתוך ה-Opportunities עצמם), עומד במבחן ההפרכה. **לא Goal, לא Task, לא Proposal, ולא שינוי ל-Opportunity עצמו.**

## על מה היא נשענת (מעודכן)

- `OpportunityStore` — קיים, נבנה ונבדק היום, ללא שינוי נוסף.
- שדות `Opportunity` הקיימים (subject/category/score/competition/evidence_finding_ids) — ללא שינוי.
- שום איסוף ראיות חדש, שום קריאת AI/רשת חדשה — כל הראיות כבר קיימות ברגע ש-Opportunity נוצר.

## על מה היא **אינה** אחראית (גבולות, מעודכן)

- **לא מחייבת שום דבר** — לא יוצרת Goal/Task/Proposal. תפקיד Decision בלבד.
- **לא אוספת ראיות חדשות** — תפקיד Research Trigger.
- **לא משנה Opportunity קיים** — קריאה-בלבד, לא נוגעת ב-stage/score/שום שדה.
- **לא קוראת ל-`decide()` בעצמה ולא קובעת את ה-verdict הסופי** — משפיעה לכל היותר על סדר/בחירה של מה מגיע ל-Decision, לא על מה Decision עושה כשהוא כן נקרא.
- **לא מחליפה ואינה עורכת** את `decide()`, `confidence_score()`, `recommend_allocation()`, `rank_by_confidence()`, `rank_portfolio()`, `OpportunityStore` — שכבה נוספת, אדיטיבית בלבד.
- **לא מחליטה במקום המייסד** — מסבירה ומשווה בלבד.

---

**סטטוס:** מעודכן על בסיס ראיות חדשות (Opportunity Universal Core), לא סתירה למה שנעל קודם. ממתין לנעילה לפני Design מחודש/קוד.
