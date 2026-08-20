# Qualification (אימות) — Business Plan Generator, Milestone 4

**תאריך:** 2026-08-13
**מטרה:** לא לתקן. לא לשנות. **למדוד ולהבין** — במיוחד שתי נקודות שהמייסד ביקש אימות ממוקד עליהן, בראיות בלבד. אם נמצא ממצא אמיתי — מתועד, לא מתוקן.

**עדכון (2026-08-13) — Qualification חוזר, אחרי החלטת "כביש אחד"**: הממצא בסעיף 2 למטה (race עם `ATLAS_OPPORTUNITY_DISCOVERY_V1`) הוביל להשוואה תפקודית מלאה מול `opportunity_discovery_advance.py` (דווחה בנפרד), ולהחלטה שאושרה: הפסקת קריאת `advance_opportunity_discovery()` מתוך `tick()` — לא תיקון-תיאום, "כביש אחד" (`docs/DESIGN_BUSINESS_PLAN_GENERATOR.md` §7). **סעיף 2 להלן משוחזר כפי שנכתב במקור (לתיעוד-היסטוריה, לא נמחק), וסעיף 2א חדש מתעד את האימות מחדש** אחרי השינוי הממוקד. שינוי הקוד היחיד: הסרת קריאה+import אחד מ-`ceo.py`. `rank_opportunities()`, הדגל ושני שימושיו האחרים, `opportunity_discovery_advance.py` עצמו ובדיקותיו (8) — **ללא שינוי**, כמאושר.

---

## 1. הוכחה ש-6 הכשלים הם baseline קיים, לא רגרסיה של Milestone 4

**לא "אותו דבר כמו קודם" — הוכחה ישירה, שתי דרכים עצמאיות:**

**(א) בידוד קבצי M4 בפועל.** הוצאתי את שני הקבצים החדשים (`business_plan_advance.py`, `test_business_plan_advance.py`) מחוץ לעץ, ו-`git stash` על ארבעת הקבצים ששונו (`ceo.py`, `models.py`, `cli.py`, `test_ceo.py`) — ניסיון לבודד "לפני-M4." **התברר בפועל**: אף commit לא בוצע במהלך כל ה-Session הזה (93 commits ahead of origin, הכול still working-tree) — `git stash` על קובץ משותף כמו `ceo.py` מחזיר אותו **עד לפני Bridge 1/2/3 ו-M2/M3 גם יחד**, לא רק לפני M4 — לא כלי בידוד תקף כאן. **שוחזר מיידית** (`git stash pop` + הקבצים הוחזרו) — לא הושאר שום דבר בחוסר-עקביות.

**(ב) הוכחה מדויקת יותר, ישירה — הטרייסבק עצמו**: הרצתי `test_first_run_discovers_three_bare_opportunities` בבידוד. הכישלון: `AffiliateIntelligenceAgent.run()` מחזיר `by_stage["discovered"] == 0` במקום `3` — כישלון **בתוך הלוגיקה הפנימית של `AffiliateIntelligenceAgent.run()` עצמה** (גילוי-placeholder), בקובץ (`src/atlas/assets/affiliate_intelligence/agent.py`) **שלא נגעתי בו אף פעם**, לא ב-M4 ולא בכלל ב-Session הזה (מאומת: לא מופיע באף Edit/Write שביצעתי). אין שום קשר לוגי אפשרי בין הכישלון הזה לבין `business_plan_advance.py`/`ALWAYS_REQUIRES_APPROVAL`/חיווט ה-`tick()`.

**(ג) התקדמות מספרית עקבית**: 1493 (baseline לפני M2) → 1502 (+9, M2) → 1503 (+1, תיקון-צורה M3) → 1515 (+12, M4: 11+1) — **אותם 6 שמות בדיוק**, בכל שלב, ללא תוספת/גריעה. הסתברות שזו רגרסיה-שנראית-כמו-baseline-קיים, במקום שקבצי M4 החדשים כלל לא מיובאים על ידי אף אחד מ-6 הבדיקות הכושלות: אפסית.

**מסקנה, ללא ריכוך**: **1515 עברו, 6 כשלים ידועים-מראש, 0 רגרסיות חדשות** — לא "ירוק," במדויק כפי שביקשת.

## 2. אימות ה-Idempotency תחת האינטראקציה עם `ATLAS_OPPORTUNITY_DISCOVERY_V1`

**נבדק חי, שני כיוונים, לא בהנחה — ונמצא ממצא אמיתי בכיוון השני. לא תוקן. מדווח כאן.**

**כיוון א' — המנגנון הישן מקדים** (`opportunity_discovery_advance.py` יוצר `AffiliateOpportunity` בר לפני שהגשר החדש רץ): **בטוח, מאומת חי**. הגשר החדש רואה `goal_id` כבר תפוס ב-`AffiliateStore` (שכבה א' של הדה-דופ) ונסוג לגמרי — `AffiliateOpportunity` אחד בלבד, אפס Task כפול, אפס התנגשות.

**כיוון ב' — הגשר החדש מקדים, והדגל נדלק אחר-כך (ממצא אמיתי, לא צפוי)**: הגשר החדש יוצר Task אמיתי, מבוקש-תנאים. **בזמן שה-Task עדיין פתוח**, הדגל נדלק — המנגנון הישן **לא רואה שהגשר החדש כבר "תפס" את ה-Goal**, כי הבדיקה שלו (`existing_subjects`, לפי `(category, product_name)` ב-`AffiliateStore` בלבד) לא מסתכלת בכלל על `Task`-ים ב-`BrainMemory`. **הוא יוצר `AffiliateOpportunity` בר, מתחרה, לאותו Goal בדיוק.**

**מה קורה בפועל, מאומת חי, שלב-שלב**:
1. הפאונדר מאשר את ה-Task של הגשר החדש (`approve()` — עובד נכון, `status="done"`).
2. `create_affiliate_opportunity_from_terms()` עם תנאים אמיתיים ותקינים — **נכשל, `ValueError: "an AffiliateOpportunity already exists for goal ..."`**. **הדה-דופ הפנימי שלה (שכבה ג') עבד נכון — לא נוצרה כפילות, לא נשמר מידע סותר.** אבל: **התנאים המסחריים האמיתיים שהפאונדר סיפק — נזרקים, לא נשמרים בשום מקום.**
3. **במקביל, לגמרי בלתי-תלוי**, קיים Task אמיתי, פתוח, מהמנגנון הישן ("Founder choice requested: pursue affiliate opportunity 'GreenCoffeeMax'..."). אם הפאונדר מאשר **אותו**, זה ממשיך (ללא שום שינוי מ-M4) ל-`selected_for_marketing` **עם תנאים מסחריים ריקים** (`commission_per_conversion=0.0`, `real_affiliate_link=""`) — ול-Campaign אמיתי, `destination_url=""`.

**זו בדיוק הדוגמה שביקשת שאעצור עליה**: לא כפילות-נתונים (הדה-דופ הפנימי מונע את זה) — אלא **שני Tasks אמיתיים, מקבילים, לא-מתואמים, לאותו Goal**, שהאחד מהם (הישן) יכול להוביל ל-Campaign אמיתי אך **ריק מתנאים מסחריים**, בעוד תנאים אמיתיים ותקינים שכבר סופקו על ידי הפאונדר נזרקים בשקט.

**היקף אמיתי, לא מוגזם**: קורה **רק** כש-`ATLAS_OPPORTUNITY_DISCOVERY_V1` דלוק — כבוי כברירת מחדל בייצור אמיתי. עם זאת, בסביבת הפיתוח **הזאת** הוא דלוק קבוע (עובדה אגבית שנמצאה, לא קשורה ל-M4 עצמו) — כך שהחשיפה בפועל בסביבה הזאת אינה תיאורטית.

**לא תוקן — נכון לרגע כתיבת הסעיף הזה.** לא ב-`business_plan_advance.py`, לא במנגנון הישן. מתועד כאן, לא בקוד, לפי ההנחיה המפורשת.

## 2א. אימות מחדש, אחרי החלטת "כביש אחד" (2026-08-13)

**לא תיקון של ה-race — הסרת הצד השני שלו.** אחרי השוואה תפקודית מלאה (מדווחה בנפרד למייסד) ואישורו: הקריאה היחידה ל-`advance_opportunity_discovery()` הוסרה מ-`CEOBrain.tick()`. שום דבר אחר לא השתנה.

**אומת חי, מחדש, בדיוק באותם תנאים שהראו את הבעיה בפעם הראשונה** — `ATLAS_OPPORTUNITY_DISCOVERY_V1` **דלוק**, 4 ticks:

```
AffiliateOpportunity count: 0
Commercial-terms Tasks (הגשר החדש, המסלול האמיתי היחיד כעת): 1
Task-בחירה אמיתי מהמנגנון הישן (source_opportunity_id != None): 0
```

**ממצא אגבי, מרגיע, לא נבדק קודם**: קיים Task אחד נוסף, קטגוריה `"affiliate_intelligence"`, `status="done"`, `source_opportunity_id=None`, תיאור "Bootstrap affiliate pipeline from Intelligence findings" — **זה השימוש השני, הבלתי-קשור, של הדגל** (`decision_apply.py`'s `OPPORTUNITY_DISCOVERY_BOOTSTRAP_OVERRIDES`, שמנתב את הנתיב הקטגוריאלי הישן ל-`affiliate_intelligence` במקום `affiliate_pipeline`) — **פועל בדיוק כמו שצריך, ללא שינוי**, מבחין נכון מ-Task-בחירה אמיתי (שתמיד `source_opportunity_id != None`). `AffiliateIntelligenceAgent.run()` עצמו, כשמופעל, מדווח ביושר "No real opportunity found" (הבדיקה הפנימית-כפולה שלו לדגל, גם היא ללא שינוי) — אין state תקוע, אין תוצר מפוברק.

**מסקנה**: ה-race מ-סעיף 2 **בלתי-אפשרי מבנית כעת** — לא כי תוקן קוד ספציפי, אלא כי הצד השני של המרוץ פשוט לא רץ יותר, בשום מצב דגל. שני השימושים האחרים בדגל ממשיכים לפעול נכון, ללא נגיעה.

## 3. אימות מבחני ההפרכה של ה-Design — כולם, מחדש, לא רק "כבר עברו"

| חלק | איך אומת (חוזר, לא רק Implementation) |
|---|---|
| א' — Task יחיד, לא AffiliateOpportunity/בחירה | `test_committed_opportunity_gets_exactly_one_commercial_terms_task` + `test_uncommitted_opportunity_gets_no_task` |
| ב' — אין Task שני בהרצה חוזרת | `test_repeated_call_never_creates_a_second_task` |
| ג' — תנאים תקינים → Campaign אמיתי | `test_milestone3_committed_opportunity_reaches_real_campaign_via_business_plan_bridge` (מקצה-לקצה אמיתי) + אימות חי עם **CLI כתת-תהליך אמיתי** |
| ד' — קטגוריה אחרת, הגשר לא נוגע | `test_non_bridged_category_gets_no_task` |
| ה' — `status!="done"`/עמלה=0 נכשלים | `test_create_from_terms_rejects_unapproved_task` + `test_create_from_terms_rejects_zero_commission` |
| ו' — Proposal אמיתי לפני `approve()`, `"done"` רק אחרי | מאומת בתוך אותה בדיקת-קצה-לקצה, שלב-שלב |
| ז' (חדש) — המנגנון הישן לא רץ יותר, בשום מצב דגל | אימות חי מחדש, סעיף 2א למעלה — 4 ticks, דגל דלוק, אפס Task-בחירה אמיתי |

**כל 7 החלקים עברו (ו' ו-ז' כוללים תיקון/החלטה שנעשו תוך כדי Qualification עצמו) — Full Suite: 1515 עברו, אותם 6 כשלים ידועים-מראש, ללא רגרסיה מהשינוי הממוקד.**

---

**סטטוס:** Qualification חוזר הושלם. **הממצא מסעיף 2 טופל** — לא בתיקון-תיאום, אלא בהחלטה ארכיטקטונית שאושרה ("כביש אחד"): הפסקת קריאת `advance_opportunity_discovery()` מתוך `tick()`, מתועדת ב-`docs/DESIGN_BUSINESS_PLAN_GENERATOR.md` §7, מאומתת מחדש חי בסעיף 2א. שינוי הקוד: הסרת קריאה+import אחד בלבד מ-`ceo.py`. `rank_opportunities()`, הדגל ושני שימושיו האחרים, וכל 8 בדיקות `opportunity_discovery_advance.py` — ללא שינוי, כמאושר. Full Suite: 1515 עברו, 6 כשלים ידועים-מראש, ללא רגרסיה. **ממתין לאישורך לפני מעבר ל-Vision Milestone Review (שלב 7/7).**
