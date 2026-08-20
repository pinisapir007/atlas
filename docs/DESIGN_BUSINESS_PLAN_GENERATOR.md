# Design — Business Plan Generator (מחולל תוכנית עסקית), Milestone 4

**תאריך:** 2026-08-12
**מקור בלעדי:** `docs/ARCHITECTURE_INTENT_BUSINESS_PLAN_GENERATOR.md` (נעול), `docs/CAPABILITY_DEFINITION_BUSINESS_PLAN_GENERATOR.md` (נעול).
**מטרה יחידה:** זרימת הנתונים המדויקת, מיפוי השדות, קריטריון "תנאים מסחריים מספיקים," ומניעת כפילות — בלי לגעת ב-`_request_founder_choice()`, ב-`campaign_advance.py`, או ב-Universal Core. **אין קוד.**

**עדכון 1 (2026-08-12, אחרי בדיקה נוספת שביקש המייסד)**: נמצא, בבדיקה ישירה מול הקוד, שהמסלול "הפאונדר מספק תנאים בנפרד" **לא היה שלם** בגרסה הקודמת של המסמך הזה — הוא הניח קיום מנגנון-קליטה שלא נבדק. תוקן: נוסף רכיב חמישי, מפורש (סעיף 6 למטה), מאותה משפחה מדויקת כמו `create_influencer_from_proposal()`/`create_brand_from_proposal()` (שתיהן קיימות, נבדקו ישירות). ללא הרכיב הזה, ה-Task שנוצר בסעיף 4 היה Task בלי מסלול-חזרה אמיתי — פער אמיתי שנמצא לפני Implementation, לא אחריו.

**עדכון 2 (2026-08-12, נמצא בפועל בתחילת Implementation, לפני שקוד נכתב)**: נמצא שהקביעה "`reversible=False` מספיק לבדו" (סעיף 4, גרסה קודמת) **שגויה** — מאומת ישירות מול `_risk_gate_and_delegate()`/`Delegator.delegate()`/`is_structural()`/`CEOBrain.approve()`. בלי תוספת ל-`ALWAYS_REQUIRES_APPROVAL`, `approve()` **לעולם לא** מגיע ל-`task.status=="done"` — הוא נופל למסלול-ההתאמה הרגיל של Registry (כולל ה-`unmatched`-fallback המסוכן שכבר תועד ותוקן פעם אחת בעבר). **תוקן**: `"affiliate_commercial_terms_needed"` מתווספת ל-`ALWAYS_REQUIRES_APPROVAL` — **אך ורק** כדי לעבור במסלול Proposal/approve הקיים, לא ליצור Asset/מנגנון חדש. פירוט מלא בסעיף 4.

**עדכון 3 (2026-08-13, אחרי Qualification — השוואה תפקודית מלאה מול `opportunity_discovery_advance.py`, לא תוקן שם, הוכרע כאן)**: ה-Qualification חשף אינטראקציה אמיתית בין הגשר החדש למנגנון הישן, הפעיל רק כש-`ATLAS_OPPORTUNITY_DISCOVERY_V1` דלוק (כבוי בייצור אמיתי). השוואה תפקודית מלאה (7 שאלות, לא רק ה-race) הובילה למסקנה חד-משמעית, שאושרה על ידי המייסד: **אין הצדקה לשני מסלולים מקבילים לאותה אחריות** — התכונה המייחדת של הישן (בחירה אנושית בין כמה מועמדים מדורגים) כבר מוחלפת על ידי M3 (התחייבות אוטונומית, רגישת-משאבים, לכמה מועמדים בו-זמנית), ולישן יש באג מבני משלו (מגיע ל-`selected_for_marketing` עם תנאים מסחריים ריקים לצמיתות, ללא תלות ב-M4 כלל). **ההחלטה: כביש אחד, לא מחלף.** פירוט מלא בסעיף 7 (חדש).

---

## 1. זרימת הנתונים החדשה, מקצה לקצה

```
Opportunity (Universal Core, M3-committed: goal_id is not None, category="affiliate")
        │
        ▼
[הגשר החדש — רץ כל tick, אחרי commit_ready_opportunities()]
        │
        ├─ כבר קיים AffiliateOpportunity עם אותו goal_id? ──► כן: לא עושה כלום (כבר בטיפול)
        │
        ▼ לא
        ├─ כבר קיים Task פתוח לבקשת תנאים לאותו Opportunity? ──► כן: לא עושה כלום (כבר נשאל)
        │
        ▼ לא
   יוצר Task אחד, קטגוריה "affiliate_commercial_terms_needed"
   (ב-ALWAYS_REQUIRES_APPROVAL) → Proposal אמיתי מקושר נוצר אוטומטית
   באותו tick (is_structural()), task.status = "pending_approval"
        │
        ▼ (בזמן נפרד — הפאונדר מריץ `atlas brain approve <task_id>` — קיים, ללא שינוי)
   approve() סוגר את ה-Proposal המקושר → task.status = "done"
        │
        ▼ (הפאונדר מריץ CLI חדש עם התנאים האמיתיים — סעיף 6 למטה, הרכיב החמישי)
   create_affiliate_opportunity_from_terms(task_id, ...) —
   בודקת task.status=="done", מאמתת (מנגנונים קיימים), בודקת דה-דופ,
   יוצרת AffiliateOpportunity ישירות ב-stage="selected_for_marketing", goal_id מתואם
        │
        ▼ (ה-tick הבא, ללא שינוי כלל)
   campaign_advance.py (קיים) מוצא selected_for_marketing → יוצר Campaign אמיתי
```

**נקודת המפתח**: ה-`AffiliateOpportunity` **נוצר ישירות** ב-`"selected_for_marketing"` — **אף פעם לא** ב-`"discovered"`/`"ranked"`. זו הסיבה שהוא לעולם לא עובר דרך `_request_founder_choice()` (בודק רק `stage == "ranked"`) או `_continue_in_progress_goals()` (בודק רק `discovered"/"researched"`) — **לא כי אנחנו עוקפים אותם בקוד, אלא כי מבנית הוא אף פעם לא נמצא בשלב שהם מסתכלים עליו.** אפס שינוי לשני המנגנונים האלה.

## 2. מיפוי שדות: `Opportunity` (Universal Core) → `AffiliateOpportunity`

| Universal Core | → | `AffiliateOpportunity` | הערה |
|---|---|---|---|
| `subject` | → | `product_name` | ישיר |
| `description` | → | `description` | ישיר |
| `category` | → | `category` | ישיר (תמיד `"affiliate"` — הגשר לא רץ בשביל קטגוריה אחרת) |
| `marketing_niche` | → | `marketing_niche` | ישיר |
| `recommended_market` | → | `recommended_market` | ישיר |
| `competition` (`float \| None`) | → | `competition` (`float`) | `0.0` אם `None` — **אותה ברירת-מחדל ש-`AffiliateOpportunity` כבר מצהיר עליה כ"placeholder," לא המצאה חדשה** |
| `score` (`float \| None`) | → | `score` (`float`) | `0.0` אם `None`, אותו היגיון |
| `goal_id` | → | `goal_id` | **מפתח הקורלציה היחיד — נכתב פעם אחת, לעולם לא נדרס, כמו בכל מקום אחר בקודבייס** |
| `evidence_finding_ids` | → | `notes` (טקסט חופשי בלבד) | אין שדה מובנה מקביל ב-`AffiliateOpportunity` — לא ממציאים אחד. ה-Trail האמיתי נשאר ב-Milestone 2/3 עצמם; `notes` מצטט רק שהוחלט דרך Revenue Strategy, לא משכפל את הראיות עצמן |
| `id`, `task_id` | — | *(לא ממופה)* | `AffiliateOpportunity.task_id` מתייחס להקשר-Task שונה (Mission 003) — מיפוי שגוי היה יוצר קורלציה מזויפת |
| — | | `commission_per_conversion`, `real_affiliate_link`, `provider`, `provider_product_id` | **נשארים ריקים/0.0 — בדיוק כמו `opportunity_discovery_advance.py` כבר עושה היום.** אלה בדיוק התנאים המסחריים שהפאונדר מספק בנפרד (סעיף 4) |
| — | | `estimated_conversion`, `content_difficulty` | אין מקבילה ב-Universal Core (במכוון — לא חלק מהליבה) — נשארים `0.0`, ברירת המחדל הקיימת |
| — | | `stage` | `"selected_for_marketing"` **רק** ברגע שתנאים מסחריים אמיתיים כבר בידינו (זרימה נפרדת, לא בזמן התרגום הראשוני) |

## 3. מה נחשב "תנאים מסחריים מספיקים"

**שלושה תנאים, כולם אמיתיים, כולם נבדקים ע"י מנגנון קיים, ללא המצאת קריטריון חדש:**

1. **`real_affiliate_link` אמיתי ותקין** — עובר `validate_provider_link()` (קיים, `affiliate_department/models.py`, fail-closed, זהה למה ש-`intake_real_product()` כבר אוכף).
2. **`provider` אמיתי** — נפתר בהצלחה דרך `atlas.integrations.registry.get_provider()` (קיים).
3. **`commission_per_conversion > 0.0`** — **לא `>= 0.0`**. `0.0` הוא ברירת-המחדל של "לא נקבע עדיין" — לקבל `0.0` כ"מספיק" היה שווה-ערך לקבל עמלה מזויפת של אפס, בדיוק סוג ה-fabrication שהקודבייס הזה נמנע ממנו בכל מקום אחר (`revenue_generated: 0.0` המתועד תמיד כ"placeholder כן, לא הכנסה אמיתית").

**כל השלושה ביחד — לא חלקי.** אם רק אחד חסר, המצב זהה ל"שום דבר לא סופק."

## 4. איזה Task נוצר אם חסר מידע

Task **אחד**, קטגוריה חדשה וממוקדת — `"affiliate_commercial_terms_needed"` (מחרוזת פתוחה, כמו כל קטגוריית Task אחרת בקודבייס; **לא** `"create_asset"` — זו לא יצירת נכס, ולא נכון סמנטית להשתמש בקטגוריה הזו).

**תוקן (2026-08-12), אחרי בדיקת-Implementation שמצאה פער אמיתי — ראו הודעת-העדכון בראש המסמך**: הטענה הקודמת כאן ("`reversible=False` מספיק לבדו") **הייתה שגויה**, מאומתת ישירות מול `_risk_gate_and_delegate()`/`Delegator.delegate()`/`is_structural()`/`CEOBrain.approve()`. **הקטגוריה `"affiliate_commercial_terms_needed"` מתווספת ל-`ALWAYS_REQUIRES_APPROVAL`** (`atlas/brain/models.py`, כרגע `{"create_asset", "recruit_agent"}`) — **לא** כדי ליצור Asset, אלא **אך ורק כדי לעבור במסלול ה-structural-approval הקיים** (`is_structural()` → `Delegator._propose()` → `Proposal` אמיתי מקושר → `pending_approval`), **בדיוק** אותו מנגנון ש-`"create_asset"` כבר עובר. זו הדרך היחידה הקיימת שבה `CEOBrain.approve()` (ללא שינוי קוד) בפועל **סוגר Proposal ומעביר את ה-Task ל-`"done"`** — בלי זה, `approve()` היה מנסה `Delegator.delegate()`'s מסלול-ההתאמה הרגיל (Registry dispatch, כולל ה-`unmatched`-fallback המסוכן שכבר תועד ותוקן פעם אחת בעבר בקודבייס הזה), ולעולם לא מגיע ל-`"done"`.

**חד-משמעית, כדי שלא יהיה בלבול**: התוספת הזו **אינה** יוצרת Asset חדש, **אינה** נוגעת ב-Registry/Delegator/`is_structural()` עצמם (משתמשת בהם בדיוק כפי שהם), ו**אינה** מרחיבה scope — היא שימוש-חוזר מדויק במסלול Proposal/approve שכבר קיים ומוכח, לא מנגנון חדש.

**התוכן**: שם ה-Subject, קטגוריה, `marketing_niche`/`recommended_market`, וההוראה המדויקת (איזה CLI-command להריץ עם התנאים האמיתיים) — **אותו סגנון בדיוק** כמו `_missing_brand_task`/`_missing_market_influencer_task` (מצטט המלצה קונקרטית, לא רק "חסר משהו").

**קריטי, לפי ההכרעה שלכם**: זה **לא** Task של בחירה. אין "אשר/דחה בין כמה". יש בקשה חד-משמעית למידע אחד חסר, על Subject שכבר הוחלט עליו. המסלול הסטרוקטורלי (Proposal/approve) הוא רק **מנגנון-הסגירה הטכני** של ה-Task — הוא לא הופך את זה לבחירה; אין כאן שום מועמד שני להשוות אליו.

## 5. מניעת כפילות/יצירה חוזרת — שתי שכבות, שתיהן מבוססות-תקדים קיים

**שכבה א' — ברמת `AffiliateOpportunity`**: לפני כל פעולה, בדיקה אם כבר קיים `AffiliateOpportunity` כלשהו עם אותו `goal_id` ב-`AffiliateStore` — אם כן, אין עושים כלום (בין אם הוא כבר ב-`selected_for_marketing` ובין אם עדיין ממתין). **אותו דיוק בדיוק כמו `campaign_advance.py`'s `claimed_goal_ids`/`_selected_opportunity_for_goal`.**

**שכבה ב' — ברמת ה-Task**: לפני יצירת Task חדש, בדיקה אם כבר קיים Task פתוח עם `source_opportunity_id == opportunity.id` (ה-id של ה-Opportunity המקורי, Universal Core) וקטגוריה `"affiliate_commercial_terms_needed"` — אם כן, לא נוצר שני. **אותו דיוק בדיוק כמו `_missing_brand_task`/`_missing_market_influencer_task`.**

**תוצאה**: הרצה חוזרת (עוד tick, בלי שהפאונדר עשה כלום) — לא Task שני, לא AffiliateOpportunity שני. ברגע שהפאונדר מספק תנאים אמיתיים — ה-AffiliateOpportunity שנוצר סוגר את הפער, ואין עוד צורך ב-Task (ממילא לא נוצר שני, כי שכבה א' כבר תמצא את ה-AffiliateOpportunity הקיים).

**שכבה ג', הגנת-עומק בתוך הרכיב החמישי עצמו (סעיף 6)**: שכבה א' רצה בגשר (כל tick) — אבל הרכיב החמישי רץ בזמן נפרד, ביוזמת הפאונדר, לא בתוך אותה הרצת-tick. כדי שלא יהיה מרוץ (למשל: הפאונדר מריץ את הפקודה פעמיים, או ה-Task נשאר פתוח בטעות אחרי שכבר טופל) — הרכיב החמישי **בודק בעצמו, שוב, fail-closed**, שאין כבר `AffiliateOpportunity` עם אותו `goal_id` לפני שהוא יוצר אחד — לא מסתמך רק על שכבה א' שרצה במועד אחר.

## 6. הרכיב החמישי — קליטת תנאים מסחריים בפועל (חדש, נמצא חסר בבדיקת המייסד)

**מאותה משפחה בדיוק כמו `create_influencer_from_proposal()`/`create_brand_from_proposal()` (שתיהן קיימות, נבדקו ישירות) — לא מנגנון רביעי, יישום שלישי של אותה תבנית.**

**שם מוצע** (לא נעול-סופית, פרט-מימוש): `create_affiliate_opportunity_from_terms(task_id, memory, opportunities, affiliate_store, commission_per_conversion, real_affiliate_link, provider, provider_product_id="")` — `opportunities: OpportunityStore` נוסף (לא היה בטיוטה הקודמת): הפונקציה משחזרת את שדות ה-Opportunity המקורי (Universal Core) **מחדש**, דרך `task.source_opportunity_id`, ולא סומכת על עותק שמור/מיושן — אותו עיקרון בדיוק ש-`create_influencer_from_proposal()` כבר מיישם ("Recomputes the draft fresh from the real opportunity rather than trusting a stored copy").

**Fail-closed, בשתי דרכים — מראה של `create_influencer_from_proposal()` המדויקת**:
1. **`task_id` חייב להיות Task אמיתי מקטגוריה `"affiliate_commercial_terms_needed"`** — אחרת `ValueError`, בדיוק כמו הבדיקה "not actually a Factory proposal" הקיימת.
2. **`task.status != "done"` → `ValueError`** — יצירה בלתי-אפשרית מבנית לפני ש-`CEOBrain.approve()` (קיים, ללא שינוי) אישר את ה-Task. **מגיע ל-`"done"` דרך מסלול ה-Proposal הסטרוקטורלי (סעיף 4, מתוקן) — לא דרך שום דבר אחר.** זו האכיפה בפועל של "אין בחירה מחדש" — הפאונדר מאשר שהוא מספק מידע למועמד שכבר הוחלט עליו, לא בוחר מועמד.

**אימות** (מנגנונים קיימים, ללא שינוי, ללא כפילות-לוגיקה): `validate_provider_link(provider, real_affiliate_link)` (כולל בתוכו את `get_provider()` — נבדק ישירות בקוד, לא נדרשת קריאה נפרדת). `commission_per_conversion > 0.0` נבדק כאן, fail-closed, לפי הקריטריון בסעיף 3 — לא `>= 0.0`.

**דה-דופ** (שכבה ג', ראו למעלה): בדיקה חוזרת שאין `AffiliateOpportunity` עם אותו `goal_id` (הנלקח מ-`task.goal_id`, שכבר תואם ל-Opportunity המקורי דרך הגשר).

**פעולה**: בונה `AffiliateOpportunity` (מיפוי השדות מסעיף 2, פלוס התנאים המסחריים שסופקו כרגע), `goal_id = task.goal_id`, `.transition("selected_for_marketing", "founder supplied real commercial terms for a Milestone-3-committed opportunity")`, `affiliate_store.save_opportunity(...)`.

**מה זה לא עושה**: לא נוגע ב-`task.status` (כבר `"done"` לפני הקריאה — לא צריך "לסגור" משהו נוסף). לא קורא ל-`campaign_advance.py`, לא יוצר Campaign בעצמו — זה קורה, ללא שינוי, בתחילת ה-tick הבא.

---

## 7. הפסקת קריאת `advance_opportunity_discovery()` מתוך `tick()` — החלטה ממוקדת, לא Cleanup

**רקע**: השוואה תפקודית מלאה (7 שאלות, מדווחת בנפרד למייסד, לא חוזרת כאן במלואה) הראתה שאין הצדקה עסקית או ארכיטקטונית להחזקת שני מסלולים מקבילים לאותה אחריות (Opportunity אמיתי → Campaign, קטגוריית affiliate). ההכרעה שאושרה: **כביש אחד, לא מחלף**.

**מה בדיוק משתנה — רשימה סגורה, לא "ניקיון כללי":**

1. **הקריאה היחידה** ל-`advance_opportunity_discovery(...)` בתוך `CEOBrain.tick()` (`ceo.py`) **מוסרת**, יחד עם ה-import שלה. זו הפעולה היחידה.
2. **`opportunity_discovery_advance.py` עצמו — לא נמחק, לא משתנה.** הפונקציה `advance_opportunity_discovery()` נשארת קיימת, ניתנת-לקריאה-ישירה (למשל מבדיקות, או משימוש עתידי אחר) — רק לא מחוברת יותר ל-tick() האוטומטי.
3. **`rank_opportunities()` (`opportunity_ranking.py`) — ללא שום שינוי.** 6 קוראים אמיתיים ועצמאיים אחרים (CLI `--explain`, `business_execution_planning.py`, `decision_engine_integration.py`, `intelligence_workflow.py`, `reporter.py`, ו-`opportunity_discovery_advance.py` עצמו שנשאר קיים) ממשיכים לפעול בדיוק כפי שהם.
4. **`opportunity_discovery_v1_enabled()` (`feature_flags.py`) — ללא שום שינוי**, כולל שני השימושים העצמאיים האחרים בדגל (`decision_apply.py`'s `OPPORTUNITY_DISCOVERY_BOOTSTRAP_OVERRIDES`, ו-`affiliate_intelligence/agent.py`'s עותק-דגל פנימי משלו) — **לא נוגעים בהם בכלל**.
5. **`tests/brain/test_opportunity_discovery_advance.py` (8 בדיקות) — ללא שום שינוי.** עדיין בודקות את הפונקציה ישירות, לא דרך `tick()` — עדיין תקפות, כי הפונקציה עדיין קיימת ועדיין עובדת.
6. **אין שכבת-תיאום/דה-דופ נוספת נבנית** בין שני ה-bridges — השאלה מתייתרת ברגע שיש כביש אחד בלבד.
7. **`_request_founder_choice()`/`affiliate_intelligence_advance.py` — ללא שינוי.** ממשיכים לשרת את הצינור העצמאי שלהם (intake ידני, `atlas affiliate product add`) — מסלול שלישי, לא נוגעים בו.

**מה זה פותר, בפועל, בלי לתקן את הישן**: מכיוון שהמנגנון הישן לא נקרא יותר מ-`tick()`, ה-race-condition שנמצא ב-Qualification (סעיף 2 של `QUALIFICATION_BUSINESS_PLAN_GENERATOR.md`) הופך **בלתי-אפשרי מבנית** — לא כי תוקן, אלא כי הצד השני של המרוץ כבר לא רץ אוטומטית, בשום מצב דגל.

---

## מבחן הפרכה קונקרטי (Qualification עתידי)

**חלק א'**: Opportunity מחויב (M3), ללא תנאים מסחריים — Task אחד נוצר, **לא** נוצר AffiliateOpportunity, **לא** נוצר Task-בחירה מ-`_request_founder_choice()`.

**חלק ב'**: tick נוסף, בלי פעולת פאונדר — **לא** נוצר Task שני.

**חלק ג'**: הפאונדר מאשר את ה-Task (`approve()`, קיים), ואז מריץ את `create_affiliate_opportunity_from_terms()` עם תנאים אמיתיים ותקינים — AffiliateOpportunity נוצר ישירות ב-`selected_for_marketing`; ה-tick הבא (ללא שינוי ל-`campaign_advance.py`) יוצר Campaign אמיתי — בלי שום Task-בחירה באמצע.

**חלק ד'**: Opportunity מחויב בקטגוריה אחרת (למשל `digital_product`) — הגשר לא נוגע בו כלל, לא נוצר עבורו שום Task/AffiliateOpportunity.

**חלק ה' (חדש)**: קריאה ל-`create_affiliate_opportunity_from_terms()` עם `task_id` שעדיין `status != "done"` — נכשלת, `ValueError`, שום `AffiliateOpportunity` לא נוצר. קריאה עם `commission_per_conversion == 0.0` — נכשלת באותה צורה, גם אם הקישור/ספק תקינים.

**חלק ו' (חדש, נובע מתיקון ALWAYS_REQUIRES_APPROVAL)**: אחרי ש-Task מהקטגוריה `"affiliate_commercial_terms_needed"` עובר tick ראשון — קיים `Proposal` אמיתי, מקושר (`task_id`), עם `status == "pending_approval"`, ו-`task.status == "pending_approval"` (לא `"done"` עדיין). אחרי `approve(task_id)` — ה-Proposal עצמו `status == "applied"`, וה-Task `status == "done"` — **רק אז** `create_affiliate_opportunity_from_terms()` מצליחה.

**חלק ז' (חדש, נובע מסעיף 7 — הפסקת המנגנון הישן)**: גם עם `ATLAS_OPPORTUNITY_DISCOVERY_V1` דלוק, שני ticks (או יותר) לא יוצרים שום `AffiliateOpportunity` בר, בלתי-תלוי, לאותו Goal — כי `advance_opportunity_discovery()` לא נקרא יותר מ-`tick()` בשום מצב דגל. ה-race שנמצא ב-Qualification בלתי-ניתן-לשחזור.

---

**סטטוס:** Design **ננעל מחדש שוב** (2026-08-13), אחרי החלטת "כביש אחד" הממוקדת (עדכון 3 למעלה, סעיף 7). ממתין לביצוע השינוי המינימלי (הסרת קריאה אחת מ-`tick()`) והרצת Qualification חוזרת.
