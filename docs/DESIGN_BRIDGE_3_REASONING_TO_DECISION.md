# Design — Bridge 3: Reasoning → Decision (הגשר האחרון, הכי עדין)

**תאריך:** 2026-08-11
**מקור בלעדי:** `BUSINESS_BRAIN_INTEGRATION_QUALIFICATION.md`, `ARCHITECTURE_INTENT_EXECUTIVE_REASONING.md` (המחייב המפורש: לא נוגעים בחתימת `decide()`), קריאה ישירה של `brain/decision_engine.py`, `brain/decision_apply.py`, `brain/discovery/decide.py` (decide_all_with_discovery).

---

## Why this is a Bridge and not a Capability

מחיקת הגשר הזה משאירה את Reasoning (Bridge 2 + `compare_opportunities`) ואת Decision (`decide_with_discovery`/`apply_decision`, ללא שינוי) שלמים ועובדים בנפרד — בדיוק כמו הגשרים הקודמים. הגשר לא משווה (זה כבר קיים), לא מחליט (זה כבר קיים) — רק **מעביר סדר-עדיפות אמיתי, שכבר חושב על ידי Reasoning, למקום שבו Decision קורא קטגוריות.**

## מהו נשאר באחריות הבלעדית של Decision — גם אחרי הגשר הזה

רשימה מפורשת, לא מובנת מאליה:

- **בחירת ה-verdict** לכל קטגוריה (invest/already_invested/propose_capability/already_proposed/insufficient_evidence/exploration_incomplete/insufficient_evidence_after_research) — נשאר בלעדית בתוך `decide()`, ללא שינוי.
- **חישוב Confidence** — `confidence_score()` נשאר בלעדית תפקיד Decision.
- **יצירת Goal** — רק `apply_decision()`.
- **יצירת Task המחייב** (זה שמתאר investment/capability-gap אמיתי) — רק `apply_decision()`.
- **יצירת Proposal** — רק `Delegator._propose()`/RiskPolicy, ללא שינוי.
- **קביעת "האם יש מספיק ראיות"** — `MIN_INDEPENDENT_SOURCES`, שער הרוחב, `research_exhausted()` — כולם נשארים בדיקות בלעדיות של Decision. Reasoning לא שופט ראיות מחדש.
- **מניעת כפילות** (already_invested/already_proposed) — נשאר בלוגיקה הפנימית של `decide()` בלבד.
- **הזכות שכל קטגוריה, בסופו של דבר, תיבחן בעצמה** — הגשר עשוי לדחות **מתי**, לעולם לא למנוע **אם**.

## Bridge may influence, but never decide

הגשר הזה מותר לו להשפיע רק על **סדר/עדיפות** — מי מוערך קודם. **אסור לו** לדלג על קטגוריה, לשנות את מה ש-`decide()` מחזיר לה, או למנוע ממנה הגעה לבדיקה משלה. זו לא מגבלה טכנית — זו הפרדה קוגניטיבית: Reasoning ריבון על ההשוואה, Decision ריבון על ההחלטה, ואסור לערבב.

## 1. האירוע העסקי שמפעיל את הגשר

קיימת תוצאת השוואה אמיתית מ-Bridge 2 (`advance_opportunity_comparisons()`) עבור קבוצת Opportunities באותו stage, **וגם** יש עדיין קטגוריות מתוך אותה קבוצה שטרם קיבלו את קריאת ה-`decide_with_discovery()` שלהן במחזור הנוכחי.

## 2. חוזה הגשר

**קלט:** תוצאות השוואה אמיתיות מ-Bridge 2 (`preferred_id`, `compared`, `reasoning`) + מיפוי אמיתי מ-Opportunity ל-category (שדה `category` הקיים על Opportunity).

**פלט:** **סדר עדיפות בלבד** — רשימת קטגוריות מסודרת, לא verdict, לא Goal, לא Task, לא Proposal. משהו ש-`_decide_and_apply()` (או קורא עתידי) יכול לצרוך כדי להחליט **באיזה סדר** לקרוא ל-`decide_with_discovery()` לכל קטגוריה.

**מתחייב במפורש שלא לעשות (מעבר לרשימה למעלה):**
- **לא קורא בעצמו ל-`apply_decision()`** — זה תמיד יקרה, אם בכלל, דרך הזרימה הקיימת.
- **לא נוגע בחתימה של `decide()`/`decide_with_discovery()`** — אפס שינוי, בדיוק כפי שכבר ננעל ב-Architecture Intent.
- **לא מדלג לצמיתות על אף קטגוריה** — כל קטגוריה מקבלת, בסופו של דבר, קריאת `decide()` עצמאית משלה.

## Influence must be observable

אם הגשר משפיע — חייב להיות אפשר למדוד את ההשפעה. **ובאותה מידה** — חייב להיות אפשר להוכיח שהמערכת מגיעה להחלטות **נכונות** גם כשההשפעה שלו נעדרת. Bridge אינו תנאי לאמיתות ההחלטה — הוא תנאי ליעילות שבה מגיעים אליה. **החלק השני כבר הוכח, לא רק נטען**: Qualification Run #2 כבר הראה ש-`decide_with_discovery()` מגיע ל-verdicts נכונים לגמרי **בלי** שום Bridge 3 קיים בכלל — כלומר נכונות ההחלטה כבר מוכחת כבלתי-תלויה בגשר הזה, מראש.

## שתי השערות מימוש — לא הכרעה, נבדקו בפועל

לא הוכרע מראש. שתי אפשרויות אמיתיות הוצגו כהשערות מקבילות, ונבנה מבחן Qualification קטן, מבודד, שהצליח להפריך אחת מהן בפועל — לא רק בטיעון:

**השערה א' — שינוי סדר האיטרציה** בתוך `decide_all_with_discovery()` עצמה, כך שהקטגוריה המועדפת נבדקת קודם.
**השערה ב' — השפעה על `priority_score`** של ה-Task האמיתי שנוצר על ידי `apply_decision()`, דרך המנגנון הקיים כבר (`SimplePrioritizer`/מיון `open_tasks` לפני דלגציה, קיים ב-`ceo.tick()`).

**הניסוי שבוצע בפועל** (לא רק תוכנן): הרצתי `decide_with_discovery()`+`apply_decision()` על שתי קטגוריות אמיתיות ("affiliate", "digital_product"), פעם אחת בכל סדר אפשרי, בסביבת scratch מבודדת. השוויתי את התוצאה האמיתית לכל קטגוריה — verdict, האם Goal נוצר, מהו priority_score של ה-Task שנוצר — בין שני הסדרים.

**תוצאה אמיתית, לא הנחה**: `IDENTICAL=True` לשתי הקטגוריות. verdict זהה, יצירת Goal זהה, `task_priority_score=0.0` בשני המקרים — **ללא שום קשר לסדר.** הסיבה שהתגלתה: `apply_decision()` יוצר Task עם `priority_score` ברירת-מחדל (0.0); `SimplePrioritizer.score()` הוא שקובע אותו בפועל, ורץ במעבר **נפרד ומאוחר יותר** ב-`tick()`, לא בתוך `_decide_and_apply()` כלל. **השערה א' הופרכה אמפירית — סדר האיטרציה בתוך `decide_all_with_discovery()` אינו משפיע על שום דבר נצפה במערכת הנוכחית.**

**השערה ב' נותרה עומדת, ומגובה בקוד קיים וכבר-נבדק**: `ceo.tick()` כבר עושה `open_tasks.sort(key=lambda t: t.priority_score, reverse=True)` ממש לפני לולאת הדלגציה — מנגנון אמיתי, קיים, שכבר קובע איזה Task מטופל קודם. השפעה על `priority_score` היא הדרך היחידה מבין השתיים שיש לה נתיב סיבתי אמיתי וקיים להשפעה נצפית.

**המסקנה, מבוססת ראיות ולא הכרעה מוקדמת: השערה ב' היא דרך המימוש הנכונה.** לא כי היא "נראית טובה יותר" — כי השערה א' נבדקה ונמצאה חסרת השפעה בפועל.

## 3. גבולות מפורשים

- לא בוחר verdict, לא יוצר Goal/Task/Proposal בעצמו (הרשימה למעלה).
- לא נוגע ב-Bridge 1 או Bridge 2 — קורא את הפלט של Bridge 2 בלבד.
- לא שומר state — גשר סטטלס, אותו כלל בדיוק כמו Bridge 2.
- לא פועל כשאין תוצאת השוואה אמיתית (אין Opportunities מרובים באותו stage) — פשוט אין השפעה, לא שגיאה.

## 4. מבחן ההפרכה

1. **העדפה אמיתית מ-Reasoning בין X ל-Y** → לאחר הפעלת הגשר, X נבדק/מטופל לפני Y באותו מחזור.
2. **שניהם עדיין נבדקים** — X ו-Y שניהם מקבלים verdict אמיתי, עצמאי, מ-`decide()` באותו מחזור — לא נבדק רק אחד.
3. **המבחן המכריע**: בונים במכוון מצב שבו Reasoning מעדיף את X, אבל **הראיות האמיתיות** של Y מספיקות ל-"invest" בעוד שהראיות של X לא ("insufficient_evidence"). **התוצאה חייבת להישאר: X מקבל insufficient_evidence, Y מקבל invest — בדיוק כפי שהראיות שלהם קובעות, ללא קשר להעדפת Reasoning.** אם ההעדפה משנה את ה-verdict עצמו — הגשר שגוי, גם אם הסדר תקין.
4. **שינוי ראיה אמיתי הופך את העדפת Reasoning** (כבר מוכח ב-Bridge 2) → סדר העדיפות של הגשר הזה משתנה בהתאם.

---

**סטטוס:** Design של הגשר האחרון. ממתין לנעילה לפני קוד.
