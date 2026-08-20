# Design — Bridge 1: Finding → Opportunity (בלבד, לא גשרים 2/3)

**תאריך:** 2026-08-11
**מקור בלעדי:** `BUSINESS_BRAIN_INTEGRATION_QUALIFICATION.md`, `DESIGN_OPPORTUNITY_UNIVERSAL_CORE.md`, קריאה ישירה של `brain/decision_engine.py` (MIN_INDEPENDENT_SOURCES), `brain/discovery/exploration_gate.py` (sourced_finding_count), `brain/opportunity_ranking.py` (subject-scoped scoring הקיים).

---

## Why this is a Bridge and not a Capability

**לא מוסיפים כאן שום אינטליגנציה חדשה.** הגשר לא שופט איכות ראיה (זה כבר קיים — Evidence Validation), לא משווה בין מועמדים (זה Reasoning, גשר 2), לא מחליט כלום (זה Decision). כל מה שהגשר עושה הוא **לזהות עובדה מבנית שכבר ניתנת לחישוב במלואה מקוד קיים** (האם חצינו סף ראיות) **ולבצע פעולה מכנית על ישות קיימת** (find-or-create על Opportunity). אם מחקנו את הגשר, שתי היכולות (הצטברות Findings, ו-Opportunity Universal Core) עדיין קיימות ועובדות בנפרד — הן פשוט לא מדברות זו עם זו. זו בדיוק ההבחנה: **Capability מוסיפה חשיבה חדשה; Connectivity מאפשרת לחשיבה קיימת לפגוש חשיבה קיימת אחרת.**

---

## 1. האירוע העסקי שמפעיל את הגשר

לא "מי קורא למי" — האירוע העסקי: **זוג (category, subject) ספציפי חצה לראשונה את סף הראיות האמיתי** (`MIN_INDEPENDENT_SOURCES`, הקבוע הקיים ב-`decision_engine.py` — לא קבוע חדש, שימוש חוזר שלישי באותו סף, אחרי `decide()` עצמו ואחרי `exploration_gate.sourced_finding_count()`). **לא** "הגיע Finding כלשהו" — זה גרעיני מדי; היה יוצר Opportunities מרעש, מ-Finding בודד לא-מאומת. האירוע הוא ברמת ה-**subject הספציפי** (בדיוק כמו ש-`opportunity_ranking.py` כבר קובע היום עבור Opportunity Discovery V1) — לא ברמת category גולמית, שזו בדיוק רמת-הגרנולריות שכבר זיהינו כמקור לעיגון (anchoring).

## 2. חוזה הגשר

**קלט:** Findings אמיתיים מ-KnowledgeBase, עם evidence אמיתי, לזוג (category, subject) אחד.

**פלט:** Opportunity אמיתי אחד ב-OpportunityStore — נוצר בפעם הראשונה שהסף נחצה, **מתעדכן** (לא משוכפל) בכל פעם שראיה חדשה מצטרפת לאותו subject.

**מתחייב במפורש שלא לעשות:**
- **לא קובע `score`** — עניין של כל ערוץ בנפרד (כבר תועד).
- **לא קובע `competition`** — אין עדיין מנגנון שמעריך תחרות אמיתית מ-Findings לבד.
- **לא מקדם `stage` מעבר ל-`"discovered"`** — קידום ל-researched/ranked/selected דורש שיפוט (השוואה או בחירת מייסד), לא עובדה מבנית. זו שאלה אמיתית ופתוחה במפורש — **מי בדיוק מקדם stage, ומתי, לא הוכרע כאן ובכוונה.**
- **לא קורא ל-Reasoning ולא ל-Decision** — נשאר בדיוק בגבול Finding↔Opportunity.
- **לא יוצר Opportunity כפול** לאותו (category, subject) — find-or-create, אותו אידיום שכבר קיים (`_discovery_goal()`, בדיקות `already_proposed`).

## 3. גבולות מפורשים — מה נשאר מחוץ לאחריות, כדי לא לבלוע גשרים עתידיים

- **לא בוחר בין Opportunities** — זה גשר 2 בלבד.
- **לא משפיע על `decide()`** — זה גשר 3 בלבד.
- **לא נוגע במנגנון יצירת ה-Findings עצמו** (`ResearchDiscoveryAgent`, `advance_executive_discovery`) — קורא את הפלט שלהם, לא משנה איך הם עובדים.
- **לא נוגע ב-RiskPolicy, Delegator, Goal, Task System** — אותם שישה אילוצים שכבר חלים על כל המסע הזה.
- **קידום Stage נשאר שאלה פתוחה, לא מוכרעת בשקט** — מפורש כ-Backlog, לא "כבר טופל כאן."

## 4. מבחן ההפרכה

**השערה:** Findings אמיתיים, שמצטברים דרך המנגנון הקיים, גורמים ל-Opportunity אמיתי להתקיים — עם evidence_finding_ids נכון — בלי שום יצירה ידנית.

**מבחן קונקרטי, בשלושה חלקים, כל אחד יכול להפריך לבד:**
1. שני Findings אמיתיים לאותו (category, subject), חוצים את הסף — מריצים את הגשר — **בדיוק** Opportunity אחד נוצר, לא אפס, לא שניים, עם evidence_finding_ids שתואם בדיוק לשני ה-Findings.
2. Finding שלישי אמיתי לאותו subject מתווסף — מריצים שוב — **אותו** Opportunity (אותו id) מתעדכן, לא נוצר שני. אם נוצר Opportunity כפול — הגשר שגוי, גם אם החלק הראשון עבר.
3. Finding בודד (מתחת לסף) ל-subject **אחר** — מריצים — **אין** Opportunity נוצר. אם נוצר — הגשר יצר רעש מראיה לא-מספקת, שגוי, גם אם שני החלקים הקודמים עברו.

---

**סטטוס:** Design של גשר 1 בלבד. ממתין לנעילה לפני קוד.
