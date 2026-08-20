# Design — Integration: חיבור שלושת הגשרים ללולאת החיים של ATLAS

**תאריך:** 2026-08-11
**מטרה:** לא Design של יכולת חדשה — תכנון החיבור עצמו, כשלב הנדסי בפני עצמו, לפני Qualification Run #4.
**מקור בלעדי:** קריאה ישירה של `brain/ceo.py` (`tick()`, `_decide_and_apply()`) כפי שהם קיימים היום, ושלושת מסמכי ה-Design של הגשרים.

---

## Until Integration, every Bridge remains independently provable — ואיך זה נשמר גם אחרי

שלושת הגשרים הם פונקציות טהורות, קריאות-בעצמן, שכל אחת כבר הוכחה בבידוד מלא. **חיבור אותם ל-`tick()` הוא רק רצף קריאות — לא מיזוג.** אחרי האינטגרציה, כל גשר עדיין ניתן לקריאה ישירה, בבידוד, עם הבדיקות שכבר קיימות לו (`test_opportunity_advance.py`, `test_reasoning_advance.py`, `test_decision_priority_advance.py` — אף אחת מהן לא משתנה). **זו לא הבטחה מופשטת — זו תכונה מובנית מעצם זה ששלושתם נשארים פונקציות עצמאיות, לא הופכים למחלקה אחת מאוחדת.**

## סדר האינטגרציה, לפי התלות הסיבתית שכבר נעולה

לא בחירה — נכפה על ידי מה שכבר קיים ב-`tick()` בפועל:

1. **(קיים, ללא שינוי)** תכנון → תעדוף → **דלגציה בפועל** (כאן, אם ריצה קודמת יצרה משימות מחקר, נוצרים Findings אמיתיים חדשים) → Monitor → absorb_opportunities (המנגנון הישן, לא קשור) → `advance_executive_discovery` (Research Trigger, מייצר משימות מחקר לסבב הבא).
2. **חדש: Bridge 1** — `advance_opportunities_from_findings(self.knowledge, self.opportunities)`. רץ כאן כי כל Findings אמיתיים מהדלגציה של הסבב הזה כבר קיימים ב-KnowledgeBase.
3. **חדש: Bridge 2** — `advance_opportunity_comparisons(self.opportunities)`. רץ מיד אחרי Bridge 1, על ה-OpportunityStore המעודכן.
4. **`_decide_and_apply()` (קיים, שינוי מינימלי אחד — ראה למטה)**.
5. **חדש: Bridge 3** — `apply_reasoning_priority(...)`, צורך את הפלט של `_decide_and_apply()` ואת התוצאות מ-Bridge 2.
6. **(קיים, ללא שינוי)** שאר גשרי ה-`*_advance.py`.

## השינוי היחיד, האמיתי, הנדרש בקוד קיים — לא מוסתר

`_decide_and_apply()` היום **לא חושפת** את זוגות ה-(Decision, Task) שהיא יוצרת בלולאה הפנימית שלה — היא רק שומרת אותם ומחזירה `None`. Bridge 3 חייב לקבל את הזוגות האלה. **הפתרון המינימלי**: `_decide_and_apply()` תאסוף את הזוגות לרשימה במקום לזרוק אותם, ותחזיר אותה. **זהו שינוי לאורכיסטרציה של `ceo.py` בלבד — לא ל-`decide()`, לא ל-`apply_decision()`, לא ללוגיקה הפנימית שלהם.** אותה הבחנה בדיוק שכבר נעשתה כשתוקן #7: מותר לגעת באיך `ceo.py` מארגן קריאות, אסור לגעת בליבה המוגנת עצמה. תקדים ישיר וכבר מאושר.

**תוספת קונסטרקטור אחת ל-`CEOBrain`**: `self.opportunities` (`OpportunityStore`, ברירת מחדל אמיתית), באותו דפוס בדיוק כמו `self.knowledge`/`self.decisions`/`self.ledger` הקיימים.

## גבולות מפורשים

- **אין שינוי ללוגיקה הפנימית של אף גשר** — האינטגרציה היא רק סדר קריאות.
- **אין שינוי ל-`decide()`/`apply_decision()`/`confidence_score()`** — אותו איסור מוחלט שכבר חל מההתחלה.
- **אין הבטחה של תוצאה מסוימת** — האינטגרציה חושפת האם השרשרת מתפקדת, לא קובעת מה היא אמורה להראות.

---

## תוספת אחרי המימוש (2026-08-11) — פרט אמיתי אחד שהתגלה רק בקוד, לא הוחמץ מה-Design אלא לא היה ניתן לצפות אותו בלי לכתוב את הקוד בפועל

בזמן כתיבת הבדיקה האמיתית הראשונה שהריצה את כל שלושת ה-Bridges יחד (`test_tick_wires_bridges_2_and_3_...`), התגלה שה-Boost של Bridge 3 לא היה נצפה בפועל: `apply_reasoning_priority()` משנה את אובייקט ה-`Task` **In-place**, אבל `_decide_and_apply()` כבר שמר את אותו Task ל-`self.memory` (JSON אמיתי) *לפני* שה-Boost קרה, ו-`BrainMemory` קורא/כותב דרך round-trip אמיתי דרך JSON — כלומר אין זהות אובייקט משותפת בין מה שנשמר לבין מה שנקרא בחזרה. התוצאה: ה-Boost היה קורה בזיכרון בלבד, ולעולם לא היה נשמר.

**התיקון, עדיין רק אורקסטרציה טהורה, לא לוגיקה עסקית חדשה**: `tick()` שומר מחדש כל Task שבאמת קיבל Boost, על ידי איטרציה על הרשימה ש-`apply_reasoning_priority()` כבר מחזירה (`self.memory.save_task(boosted_task)`) — לא נוסף שום מנגנון חדש, רק קריאה נוספת לפונקציה קיימת (`memory.save_task`), באותו מקום בדיוק שכל שאר ה-`tick()` כבר עושה את זה לכל Task אחר. עדיין תואם `Integration never owns behavior` — האינטגרציה עדיין לא מחליטה, לא חושבת, רק מוודאת שמה ש-Bridge 3 כבר קבע נשמר במקום הנכון.

זו בדיוק הסיבה שביקשת Implementation כשלב נפרד מה-Design: פרט אמיתי כזה לא היה נראה לפני שהקוד רץ נגד המערכת האמיתית. נשמר כאן, לא הוסתר.

---

**סטטוס:** Integration Implementation הושלם. Bridges 1-3 מחוברים ל-`tick()` בפועל, בדיוק לפי הסדר הנעול. שתי בדיקות אינטגרציה אמיתיות חדשות (`test_tick_wires_bridge_1_creates_a_real_opportunity_from_sourced_findings`, `test_tick_wires_bridges_2_and_3_boosts_the_reasoning_preferred_categorys_real_task`) + כל 1483 הבדיקות הקיימות ירוקות (1485/1485 סה"כ). לא נכתב אף production `.atlas/opportunities.json` — כל בדיקה שקוראת ל-`tick()` מבודדת עם `OpportunityStore` משלה, אותו דפוס בדיוק כמו `ledger`/`campaigns`/וכו'. ממתין ל-Qualification Run #4 לפני כל הכרזה על "השרשרת הקוגניטיבית חיה."
