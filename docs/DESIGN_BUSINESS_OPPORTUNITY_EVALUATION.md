# Design — Business Opportunity Evaluation (הערכת הזדמנות עסקית), Milestone 2

**תאריך:** 2026-08-12
**מקור בלעדי:** `docs/ARCHITECTURE_INTENT_BUSINESS_OPPORTUNITY_EVALUATION.md` (נעול), `docs/CAPABILITY_DEFINITION_BUSINESS_OPPORTUNITY_EVALUATION.md` (נעול), `docs/BUSINESSMAN_V1_SOURCE_OF_TRUTH.md` §4.
**מטרה יחידה:** להוכיח ש-ATLAS מסוגל להעריך ולסווג כל Opportunity בפני עצמו — לא רק לדרג — ולהפיק המלצה אחת, מנומקת, לכל אחד, שעומדת במבחן הפרכה.

---

## 1. הקלט המדויק

- **1+ אובייקטי `Opportunity` אמיתיים**, נשלפים דרך `OpportunityStore.by_category()` (קיים, ללא שינוי) — כל ה-Opportunities באותה קטגוריה, לא מוגבל ל-stage בודד (בניגוד ל-Reasoning — כאן אין השוואה חוצת-Opportunities שדורשת "תפוחים לתפוחים").
- הראיות האמיתיות מאחורי כל Opportunity, דרך `Opportunity.evidence_finding_ids` → `KnowledgeBase.findings()` (לציטוט בלבד, לא איסוף חדש).

## 2. הפלט המדויק

לכל Opportunity, תוצר אחד: **פירוט גורמים אמיתיים** (כל גורם: ערך אמיתי או `None` מפורש — לעולם לא מפוברק), **סיווג** (`"ready"`/`"wait"`), ו**נימוק טקסטואלי** שמצטט את הגורמים בפועל. עבור קבוצת ה-`"ready"` בלבד — **דירוג** לפי ניקוד משוקלל מהגורמים הזמינים.

## 3. פעולת החשיבה החדשה — הגורמים האמיתיים, לא מפוברקים

נבדק ישירות מה יש בקוד היום, לא הונח:

| גורם | מקור אמיתי | תמיד זמין? |
|---|---|---|
| חוזק ראיות | `len(evidence_finding_ids)`, רוויה (אותו דפוס כמו `source_corroboration_score()`) | כן |
| עדכניות | `recency_score(category, knowledge, subject=...)` (קיים, כבר תומך ב-subject) | כן, אם יש Findings |
| תחרות | `Opportunity.competition` | **לרוב לא** — Bridge 1 לא ממלא אותו, נשאר `None` היום כמעט תמיד. מוצג ביושר כ-"לא ידוע," לא מדולג בשקט |
| מוכנות-ביצוע (proxy אמיתי, לא מפוברק, ל"זמן-להכנסה"+"התאמה-ליכולות") | `CATEGORY_TASK_CATEGORIES.get(category)` — האם קיים ערוץ ביצוע אמיתי לקטגוריה (עובדה מבנית קיימת, לא ניחוש) | כן |
| סיכונים איכותיים | הרחבת `_assess_opportunity_risks()`-style (רשימת אמירות אמיתיות, לא ציון בדוי) | כן |

**במפורש "לא ידוע," לעולם לא מפוברק**: ביקוש-שוק אמיתי, בדיקת-תוכנית-Affiliate, הגעה-לקהל, פוטנציאל-הכנסה במונחי $. אלה מופיעים בפלט כ-`None`/כרשימת "מה עדיין לא ידוע," לא מנוחשים.

**כלל הסיווג (ready/wait)** — סף מדיניות מוצהר, לא המצאה חדשה: חוצה `MIN_INDEPENDENT_SOURCES` (אותו סף בדיוק שכבר משמש 3 פעמים בקוד הזה — `decide()`, `exploration_gate`, Bridge 1) → `"ready"`. אחרת → `"wait"`. **שימוש חוזר, לא סף רביעי-שרירותי.**

**כלל הדירוג בין ה-`"ready"`** — `weighted_average_of_available()` (primitive משותף קיים) על הגורמים הזמינים, עם קבוע-משקלות חדש, מוצהר, ניתן-לעריכה (אותה מחלקה בדיוק כמו `REASONING_WEIGHTS`/`confidence.WEIGHTS`) — **לא** קורא ל-`reasoning.compare_opportunities()` (הוכרע ב-Architecture Intent).

## 4. רכיבים קיימים בשימוש, ללא שינוי

`OpportunityStore.by_category()`, `recency_score()` (עם `subject=`), `CATEGORY_TASK_CATEGORIES`, `weighted_average_of_available()`, `decision_engine.MIN_INDEPENDENT_SOURCES`, `KnowledgeBase.findings()`.

## 5. אחריות שהוא מקבל

לחשב, לכל Opportunity אמיתי בקטגוריה, פירוט-גורמים אמיתי, סיווג ready/wait דטרמיניסטי, ונימוק שמצטט אותם — ולדרג את קבוצת ה-ready בלבד, בניקוד ניתן-לשחזור.

## 6. אחריות שהוא **לא** מקבל, במפורש

- לא יוצר Goal/Task/Proposal.
- לא קורא ל-`decide()`.
- **לא משנה Opportunity קיים** — קריא-בלבד, אף פעם לא נוגע ב-stage/competition/שום שדה (נעול ב-Architecture Intent, נימוק: מניעת מחלקת-הבאג שנמצאה היום ב-`Task.priority_score`).
- **לא קורא ל-`reasoning.compare_opportunities()`** — הוכרע במפורש, לא תלות.
- לא מחליט כמה Opportunities לרדוף במקביל, לא מקצה משאבים — Milestone 3/`Strategist`.
- לא מאפיין יחסים בין Opportunities (משלימים/מתחרים) — נשמר ב-Backlog להרחבה עתידית של Reasoning, לא כאן.
- לא נקרא אוטומטית מ-`tick()` — on-demand, קריא-בלבד, בדיוק כמו `explain_opportunity_subject()`/`compare_opportunities()`.
- לא ממציא ערך לגורם שאין לו מקור אמיתי (ביקוש/Affiliate/קהל/$) — `None`/"לא ידוע" מפורש.

## 7. ה-MVP הקטן ביותר שניתן לבנות

פונקציה אחת, טהורה, קריאה-בלבד. מקבלת קטגוריה + `OpportunityStore` + `KnowledgeBase`, מחזירה רשימת תוצרים (סעיף 2) — אחד לכל Opportunity בקטגוריה, עם הקבוצה ה-ready ממוינת. ללא state חדש, ללא persistence, ללא אינטגרציה ל-`tick()`.

## 8. מבחן הפרכה קונקרטי (Qualification עתידי)

שני Opportunities אמיתיים, אותה קטגוריה: אחד עם 3 Findings אמיתיים וערוץ-ביצוע קיים לקטגוריה, שני עם רק Finding אחד. **הראשון חייב להיות מסווג `"ready"`, השני `"wait"`** (לא חוצה MIN_INDEPENDENT_SOURCES). כשמוסיפים Finding אמיתי שני לשני — הוא חייב להתהפך ל-`"ready"`. בין שני Opportunities ready, זה עם יותר ראיות/ערוץ-קיים חייב לדרג גבוה יותר — **אם נחליף בין הערכים בפועל, הדירוג חייב להתהפך.** אם לא — היכולת לא הוכחה, גם אם "נראית" עובדת.

---

**סטטוס:** Design, ממתין לנעילה לפני Implementation (שלב 5 מתוך 7).