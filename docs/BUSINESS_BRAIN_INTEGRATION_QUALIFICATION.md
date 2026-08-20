# Business Brain Integration Qualification — מסמך תכנון בלבד

**תאריך:** 2026-08-11
**מטרה:** לא קוד. לא Implementation. ארבע שאלות בלבד — מה מנותק, אילו חיבורים חסרים באמת, סדר אינטגרציה מינימלי, ו-Qualification Run #4.

---

## 1. מה בדיוק עדיין מנותק בשרשרת

בדקתי כל חוליה בנפרד מול הקוד האמיתי, לא הנחתי:

- **Decision → Goal → Execution: עובד, מוכח.** `apply_decision()`, `Delegator`, `Registry.dispatch()` — הוכחו חיים ב-Run #2, ללא שינוי מאז.
- **Finding → Opportunity: אין חיבור בכלל.** שום קוד קיים — לא Research Discovery, לא `advance_executive_discovery()`, לא `intake.absorb_opportunities()` — יוצר או מעדכן `Opportunity` אמיתי. `OpportunityStore` נבנה היום ונשאר ריק לחלוטין בכל תרחיש אוטונומי אמיתי.
- **Opportunity → Reasoning: אין חיבור בכלל.** `compare_opportunities()` קיים ועובד, אבל שום דבר לא קורא לו מיוזמתו. הוא מחכה ל-`list[Opportunity]` שמישהו יזין ידנית.
- **Reasoning → Decision: אין חיבור בכלל.** גם אם Reasoning היה רץ אוטומטית, שום דבר לא צורך את הפלט שלו כדי להשפיע על **איזו** קטגוריה מגיעה ל-`decide_with_discovery()` או **מתי**.

**זה לא שלושה כשלים בלתי-תלויים.** בדקתי את התלות ביניהם, לא רק מנה אותם: השלישי תלוי בשני, שתלוי בראשון. בלי Opportunities אמיתיים, אין מה להשוות; בלי השוואה אמיתית, אין מה שישפיע על Decision. **גורם השורש האחד האמיתי: אין גשר אוטומטי כלשהו בין הצטברות Findings (הקיימת ועובדת) לבין שלושת השלבים החדשים (Opportunity/Reasoning/Decision-selection) — הוא מתבטא כשלושה חיבורים חסרים, לא כי יש שלושה גורמי שורש, אלא כי הם רצף אחד.**

## 2. אילו חיבורים חסרים באמת (לא Feature, לא Refactor)

שלושה גשרים, **מאותו דפוס בדיוק** שכבר הוכח שבע פעמים בקוד הזה (`advance_recruitment_pipeline`, `advance_affiliate_pipeline`, `advance_content_factory` וכו', ועד `advance_executive_discovery` שכבר בנינו): קריאה למנגנון קיים, ללא שינוי בו, ללא לוגיקה חדשה מעבר לגישור עצמו.

1. **גשר Finding→Opportunity**: בהינתן Findings אמיתיים שהצטברו סביב subject/category משותפים, ליצור או לעדכן Opportunity אמיתי, מחובר ל-evidence_finding_ids האמיתיים שלו.
2. **גשר Opportunity→Reasoning**: בהינתן 2+ Opportunities אמיתיים באותו stage, לקרוא ל-`compare_opportunities()` הקיים — לא לבנות מנגנון השוואה חדש, רק להפעיל את הקיים.
3. **גשר Reasoning→Decision**: להשתמש בפלט האמיתי של ההשוואה כדי להשפיע על סדר/בחירה של קריאות ל-`decide_with_discovery()` — **בלי לגעת בחתימה שלה**, בדיוק כפי שכבר ננעל ב-Architecture Intent.

אף אחד מהשלושה אינו יכולת חדשה. שלושתם קיימים כבר. חסר רק החוט שמפעיל אותם ברצף, מיוזמתם.

## 3. סדר האינטגרציה המינימלי ביותר

לפי התלות שכבר זוהתה (סעיף 1) — לא לפי בחירה: גשר 1 קודם, נבדק לבדו, **לפני** שגשר 2 נבנה בכלל. גשר 2 קודם, נבדק לבדו, לפני גשר 3.

**לא בונים את כל השלושה יחד.** בונים רק את גשר 1 קודם — הצעד הקטן ביותר שמאפשר לבדוק השערה עצמאית ראשונה: "Findings אמיתיים מצטברים ל-Opportunity אמיתי, בלי יצירה ידנית." רק אחרי שזה מוכח, ממשיכים לגשר 2, ואז 3. זו בדיוק המשמעת שכבר עבדה בכל Milestone עד היום.

## 4. Qualification Run #4 — לא כדי לעבור, כדי להפריך

**ההשערה שנבדקת:** "ATLAS מסוגל לחשוב כמוח עסקי אחד" — כלומר, בהינתן Findings אמיתיים בלבד, ואפס יצירה ידנית של Opportunity, אפס קריאה ידנית ל-Reasoning, ואפס קוד זמני — המערכת יוצרת Opportunities אמיתיים מעצמה, משווה ביניהם מעצמה כשיש כאלה באותו stage, וההשוואה הזו **משפיעה בפועל, בצורה ניתנת-להוכחה**, על איזו קטגוריה מגיעה ל-Decision.

**מבחן ההפרכה הקונקרטי:** להריץ `tick()` חוזר (בדיוק כמו Run #1/#2), ללא שום זריעה ידנית של Opportunity/Reasoning. לבדוק שלוש עובדות, לא רושם כללי:
1. האם Opportunities אמיתיים נוצרים לבד, מ-Findings אמיתיים?
2. האם, ברגע שיש 2+ Opportunities באותו stage, Reasoning נקרא לבד?
3. **המבחן המכריע**: לבנות במכוון מצב שבו Opportunity אחד עדיף בבירור על אחיו (יותר ראיות, פחות תחרות) — ולוודא שההעדפה הזו **באמת** משנה איזו קטגוריה מגיעה ל-Decision ראשונה, לא רק "נראית טוב בדוח."

אם אחד משלושת אלה לא קורה — זה Backlog אמיתי ומדויק, לא כישלון של המוח העסקי. בדיוק כמו כל Run קודם, ההרצה מצליחה במטרתה גם אם ההשערה מופרכת — כי אז נדע בדיוק איפה השרשרת עדיין לא חיה, לא רק מתועדת.

---

## 5. עדכון לאחר Implementation (2026-08-11) — המערכת כפי שהיא באמת, לא כפי שתוכננה

סעיפים 1-4 למעלה הם רשומת התכנון המקורית, לפני שנכתבה שורת קוד אחת — נשארים כפי שהם, לא נמחקים ולא נכתבים מחדש (העיקרון הקבוע של הפרויקט: תיעוד לא מוחק היסטוריה). הסעיף הזה מתאר את מה שבאמת קיים היום ב-`main`, אחרי ש-Design, Implementation, ו-1485/1485 בדיקות ירוקות כבר קרו בפועל. **Qualification Run #4 ירוץ נגד הסעיף הזה, לא נגד סעיף 4.**

### שמות אמיתיים ומיקומים

| חוליה | פונקציה אמיתית | קובץ |
|---|---|---|
| Bridge 1 (Finding→Opportunity) | `advance_opportunities_from_findings(knowledge, opportunities)` | `src/atlas/brain/opportunity_advance.py` |
| Bridge 2 (Opportunity→Reasoning) | `advance_opportunity_comparisons(opportunities)` | `src/atlas/brain/reasoning_advance.py` |
| Bridge 3 (Reasoning→Decision) | `apply_reasoning_priority(decisions_and_tasks, comparisons, opportunities_by_id)` | `src/atlas/brain/decision_priority_advance.py` |
| האחסון האמיתי | `OpportunityStore` (`self.opportunities` על `CEOBrain`) | `src/atlas/brain/opportunities.py` |

### חוזים אמיתיים (לא כפי ששוערו בתכנון)

- **Bridge 1** מקבל `KnowledgeBase` + `OpportunityStore` אמיתיים, מחזיר `list[Opportunity]` — רק אלה שנוצרו/עודכנו בפועל בקריאה הזו (לא כל ה-Opportunities הקיימים). מקבץ Findings לפי `(category, subject)`, מתעלם מ-`subject == ""` לחלוטין (אין Opportunity בלי subject אמיתי).
- **Bridge 2** מקבל `OpportunityStore`, מחזיר `list[dict]` — תוצאת השוואה אחת (`{"preferred_id", "stage", "compared", "scores", "reasoning"}`) לכל stage עם 2+ Opportunities אמיתיים. Stage עם Opportunity יחיד מדולג בשקט.
- **Bridge 3** מקבל `list[tuple[Decision, Task | None]]` (הפלט האמיתי של `_decide_and_apply()`, ראה למטה), את תוצאות Bridge 2, ומילון `{opportunity_id: Opportunity}` — מחזיר רק את ה-`Task`-ים שבאמת קיבלו Boost (`priority_score += REASONING_PRIORITY_BOOST`, קבוע = 1.0).
- **`_decide_and_apply()` (שינוי אמיתי היחיד בקוד קיים)**: כעת מחזירה `list[tuple[Decision, Task | None]]` במקום `None` — `Task` הוא `None` בדיוק עבור verdicts שלא יוצרים אחד (`insufficient_evidence`, `already_invested`, `already_proposed`).

### רצף הקריאות האמיתי בתוך `CEOBrain.tick()`

```
plan → prioritize → risk-gate+delegate → monitor → absorb_opportunities (הישן)
  → advance_executive_discovery
  → Bridge 1: advance_opportunities_from_findings(self.knowledge, self.opportunities)
  → Bridge 2: advance_opportunity_comparisons(self.opportunities)  →  comparisons
  → decisions_and_tasks = self._decide_and_apply()
  → opportunities_by_id = {o.id: o for o in self.opportunities.opportunities()}
  → Bridge 3: apply_reasoning_priority(decisions_and_tasks, comparisons, opportunities_by_id)
  → for boosted_task in <תוצאת Bridge 3>: self.memory.save_task(boosted_task)   # ראה ממצא למטה
  → advance_intelligence_cycle → ... (שאר גשרי ה-*_advance.py הקיימים, ללא שינוי)
```

### ממצא אמיתי שהתגלה רק ב-Implementation, לא היה ידוע בזמן ה-Design

`apply_reasoning_priority()` משנה את אובייקט ה-`Task` **In-place**, אבל `_decide_and_apply()` כבר שמר את אותו Task ל-`BrainMemory` (JSON אמיתי, ללא זהות אובייקט משותפת בין כתיבה לקריאה) *לפני* שה-Boost קרה — כך שבלי תיקון, ה-Boost היה קורה בזיכרון בלבד ולעולם לא נשמר. **תוקן** בלולאה נוספת ב-`tick()` ששומרת מחדש כל Task שבאמת קיבל Boost, דרך `memory.save_task()` הקיימת — עדיין אורקסטרציה טהורה, לא לוגיקה חדשה (`feedback_bridge_design_principles`, עיקרון #6: "Integration never owns behavior"). **המשמעות ל-Run #4**: כל בדיקה של Bridge 3 חייבת לקרוא את ה-Task מחדש דרך `brain.memory.get_task(...)`/`brain.memory.tasks()` — לא לסמוך על רפרנס לאובייקט שנוצר לפני ה-`tick()`.

### מבחני ההפרכה כפי שהם קיימים היום (לא כפי ששוערו בסעיף 4)

מבחן ההפרכה בסעיף 4 היה תיאורי-כללי. הגרסה האמיתית, שכבר רצה וירוקה:

- `tests/brain/test_opportunity_advance.py`, `tests/brain/test_reasoning_advance.py`, `tests/brain/test_decision_priority_advance.py` — כל גשר בבידוד מלא, ללא `tick()`, כפי שהיה מאז שכל אחד נבנה (ללא שינוי).
- `tests/brain/test_ceo.py::test_tick_wires_bridge_1_creates_a_real_opportunity_from_sourced_findings` — עובדה #1 מסעיף 4 (Opportunities נוצרים לבד מ-Findings אמיתיים, דרך `tick()` אמיתי, ללא זריעה ידנית).
- `tests/brain/test_ceo.py::test_tick_wires_bridges_2_and_3_boosts_the_reasoning_preferred_categorys_real_task` — עובדות #2 ו-#3 מסעיף 4 יחד: שתי קטגוריות אמיתיות (`digital_product` עם 3 מקורות, `ugc` עם 2), Reasoning מעדיף את זו עם הראיות החזקות יותר לבד, וה-Boost אכן פוגע ב-`priority_score` האמיתי של ה-Task הנכון בלבד — ה-verdict של שתי ההחלטות נשאר בדיוק כפי ש-`decide()` היה מייצר לבד, ללא השפעה (המבחן המכריע של סעיף 4, § "Bridge may influence, but never decide" — כעת בדיקה אוטומטית, לא רק עיקרון).
- **מה שעדיין לא נבדק על ידי אף אחד מאלה, ו-Run #4 חייב לבדוק**: התרחיש שבסעיף 4 מתאר — ריצות `tick()` **חוזרות** (כמו Run #1/#2, לא tick יחיד אחד), על מערכת חיה שמצטברת אורגנית לאורך זמן, כולל מצבים שהתכנון לא צפה (Findings שמצטברים בין ticks, קטגוריות עם subject ריק שנשארות מחוץ ל-Opportunity לגמרי, stage שמתקדם באמצע — ראה `campaign_advance.py`), לא רק תרחיש מבונה בקפידה של tick() בודד.

---

**סטטוס:** המסמך משקף את המימוש האמיתי (סעיף 5). ממתין לאישורך לפני הרצת Qualification Run #4 בפועל.
