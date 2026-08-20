# ATLAS — MASTER HANDOFF (Session Checkpoint)

**עודכן:** 2026-08-17, אחרי ONE BRAIN Root Implementation (5 התיקונים המאושרים יושמו בקוד).
**נבדק ישירות מול קוד:** כן — `git status`, `python -m pytest -q` הורצו רגע לפני כתיבת המסמך הזה.
**גרסה קודמת של המסמך הזה** (מוקדם יותר באותו יום) תיארה מצב **DESIGN-ONLY בלבד** — זה **כבר לא נכון**: חמשת התיקונים מיושמים בקוד, נבדקים, ועוברים. המסמך הוחלף כאן במלואו כדי לא להטעות סשן הבא.

> **הוראה לסוכן הבא: זהו MAP TO VERIFY, לא GROUND TRUTH.** אמת כל טענה ישירות מול הקוד לפני שאתה בונה עליה.

---

## 0. תמונת-מצב בשלוש שורות

1. **ONE BRAIN Root Implementation הושלם**: 5 התיקונים המאושרים (Return-Path Subject Verification, Pinned Business Identity + Two-Anchor Conflict, Identity-Conflict Warning, Investigation Workflow + Research Bridge, Task Done Verification Guard) — **כולם ממומשים, נבדקים, עוברים**.
2. **Test suite**: **1873 passed, 6 failed (baseline ידוע-מראש, ללא-קשר) — אפס רגרסיות חדשות.**
3. **Live Validation עדיין לא בוצע** — הכל נבנה/נבדק synthetic-בלבד (tmp_path, fakes). Marketplace navigation, Chrome/CDP, ו-Live Validation אמיתי **לא נגעו בסבב הזה כלל**, כנדרש.

---

## 1. CURRENT SYSTEM STATE — מה קיים בפועל בקוד עכשיו

### קיים, נבדק, עובד
- **שרשרת Businessman V1 (M1-M4)** — ללא שינוי, כפי שהייתה.
- **Bridge 1** (`opportunity_advance.py`) — **עדיין הכותב היחיד** ל-`Opportunity`, עכשיו **גם מכבד pinned business identity + two-anchor-conflict fail-closed** (ראו §4).
- **Return-Path Subject Verification** (`subject_verification.py`, מחובר ל-`knowledge_source_research.collect_evidence_from_source()`) — תצפית שגויה-לגבי-subject לעולם לא נשמרת כ-Finding מהימן.
- **Entity Resolution** (`entity_resolution.py`) — `resolve_canonical_subject()` (pinned-anchor, computed-fresh, fail-closed על קונפליקט-שתי-עוגנים) + `detect_pinned_identity_conflicts()` (מוצג ב-`console.find_warnings()`).
- **Investigation** (`models.py::Investigation` + `investigations.py::InvestigationStore`, `.atlas/investigations.json`) — pre-Opportunity workflow state, אמיתי, נבדק.
- **`investigation_advance.advance_investigations()`** — bridge sense-agnostic, בלי Task/Goal/Delegator, לא ממציא `source_ref`.
- **`marketplace_cognitive_bridge.py`** — **נוקה**: `advance_marketplace_opportunity()`/`mark_candidate()`/`reject_candidate()`/`plan_investigation()` **הוסרו לגמרי**. נשארו רק `ground_marketplace_product()`/`claim_derived_economics()`/`verify_revisit_identity()`.
- **`Task.expected_outcome`/`verification_status`/`verification_evidence_id`** + guard בתוך `Task.transition()` + `Task.try_complete()` — מיושם, מחובר ל-`Monitor._sync_one()` ול-`CEOBrain.approve()`.
- **Structural test** (`test_verification_authority_boundary.py`) — מוודא שאף `agent.py` אמיתי לא כותב `verification_status`/`verification_evidence_id` ישירות.

### DESIGN בלבד, לא קיים בקוד (חשוב — עדיין לא נבנה)
- **Evidence Provenance המלא** (`Finding.claimant`/`Finding.origin_domain`/`evidence_origin()`) — **הוחלט במפורש לא ליישם בסבב הזה** (מחוץ ל-5 התיקונים המאושרים, סיכון-רגרסיה אמיתי אם מיושם על כל 5 הצרכנים של `MIN_INDEPENDENT_SOURCES`). ראו §22 ל-nuance המדויק.
- **מנגנון-התאמה אוטונומי** שיוצר `Claim(predicate="possibly_same_as")` — **לא נבנה בכוונה** (ההוראה המפורשת אסרה זאת). היום: רק tests/קריאה-ידנית יוצרים אותם.
- **`source_ref` selection אוטומטי** — עדיין gap פתוח, מוצהר, לא נפתר.
- **חיבור Marketplace→Investigation אוטומטי** (מי פותח Investigation כש-Marketplace רואה מוצר מעניין) — `advance_investigations()` בנוי ומוכן **לצרוך** Investigations קיימות, אבל שום קוד production עדיין לא **יוצר** Investigation אוטומטית מ-Marketplace. זה נשאר צעד נפרד, עתידי.
- **Live Marketplace navigation/Chrome/CDP** — לא נגעו בכלל.

---

## 2. WORK COMPLETED THIS SESSION (ONE BRAIN Root Implementation)

**קבצים חדשים**:
- `src/atlas/brain/subject_verification.py`
- `src/atlas/brain/entity_resolution.py`
- `src/atlas/brain/investigations.py`
- `src/atlas/brain/investigation_advance.py`
- `tests/brain/test_subject_verification.py` (5 טסטים)
- `tests/brain/test_entity_resolution.py` (10 טסטים)
- `tests/brain/test_investigations.py` (5 טסטים)
- `tests/brain/test_investigation_advance.py` (4 טסטים)
- `tests/brain/test_task_verification_guard.py` (10 טסטים)
- `tests/brain/test_verification_authority_boundary.py` (4 טסטים, structural)
- `tests/brain/test_one_brain_continuity.py` (1 טסט, synthetic end-to-end מלא)

**קבצים ששונו**:
- `src/atlas/brain/models.py` — `Task` +3 שדות + guard ב-`transition()` + `try_complete()` + `TaskVerificationRequired`; `Investigation` dataclass חדש + `INVESTIGATION_STATUSES`.
- `src/atlas/brain/knowledge_source_research.py` — `verify_subject_match()` מחובר, `SubjectAttributionUnverified` חדש.
- `src/atlas/brain/opportunity_advance.py` — grouping עובר דרך `resolve_canonical_subject()`.
- `src/atlas/brain/console.py` — `find_warnings()` +אזהרת-קונפליקט-זהות.
- `src/atlas/brain/marketplace_cognitive_bridge.py` — נוקה (ראו §1).
- `src/atlas/brain/monitor.py` — `_sync_one()` משתמש ב-`task.try_complete()`.
- `src/atlas/brain/ceo.py` — `approve()` משתמש ב-`task.try_complete()`.
- `tests/brain/test_knowledge_source_research.py`, `test_opportunity_advance.py`, `test_console.py`, `test_marketplace_cognitive_bridge.py`, `test_cognitive_continuity.py` — טסטים נוספו/עודכנו.
- `docs/BUSINESSMAN_V1_SOURCE_OF_TRUTH.md`, `docs/ROADMAP_PROPOSAL.md` — פסקת-הצלבה קצרה נוספה לשניהם (§14 הישן).

**סה"כ טסטים חדשים בסבב הזה**: כ-45 (נטו +40 אחרי הסרת 7 טסטים מיושנים מ-`marketplace_cognitive_bridge`/`cognitive_continuity`).

---

## 3. UNCOMMITTED / WORKTREE STATE

**שום commit לא בוצע.** worktree עדיין כולל את כל ה-uncommitted state שנצבר מ-2026-08-11 ואילך (ראו הגרסה הקודמת של מסמך זה לפירוט המלא) + כל השינויים מהסבב הזה (§2 למעלה). **לא בוצע git add/commit/stash/reset בשום שלב.**

---

## 4. חוזה pinned-identity — מדויק, כפי שמומש

```
resolve_canonical_subject(subject_id, category, knowledge, opportunities):
    equivalence_class = walk supported possibly_same_as claims (BFS, שני כיוונים)
    pinned = {o.subject for o in opportunities if o.category==category and o.subject in equivalence_class}
    if len(pinned) == 1: return pinned[0]          # העוגן מנצח תמיד
    if len(pinned) >= 2: return subject_id          # קונפליקט -> fail-closed, ללא שיפור-grouping
    return min(equivalence_class)                   # אין עוגן עדיין -> בטוח לחשב-מחדש
```
מוזרם דרך `opportunity_advance._sourced_findings_by_subject(knowledge, opportunities)` — **הנגיעה היחידה בקוד-הליבה של Bridge 1**, מוגבלת ל-grouping-key בלבד. **מאומת: עם אפס `possibly_same_as` Claims (המצב האמיתי היום) — ההתנהגות זהה-ביט לגרסה המקורית.**

---

## 5. Investigation — מדויק, כפי שמומש

`Investigation(subject_id, category, status, reason_opened, supporting_claim_ids, supporting_finding_ids, contradicting_claim_ids, missing_evidence, closed_reason, id, opened_at, updated_at)` — `.atlas/investigations.json`. Statuses: `open|waiting_for_evidence|ready_for_evaluation|rejected|closed`. **לא נגזר מ-`Claim`** (אפיסטמי) ולא מ-`Task`/`Goal`/`Proposal` (chicken-egg). `advance_investigations(investigations, knowledge, source_refs, ai_provider)` — bridge, קורא ל-`collect_evidence_from_source()` ישירות, בלי Task/Goal/Delegator.

---

## 6. Task Verification Guard — מדויק, כפי שמומש

`Task` +3 שדות: `expected_outcome: str = ""`, `verification_status: str = "unknown"`, `verification_evidence_id: str | None = None`. Guard בתוך `transition()`: אם `expected_outcome` מוצהר ו-`verification_status != "verified_success"` → `transition("done", ...)` **זורק** `TaskVerificationRequired`. `Task.try_complete(reason)` — ה-wrapper הבטוח (מנסה done, נופל ל-blocked אם ה-guard מסרב) — **זה מה ש-`Monitor`/`CEOBrain.approve()` קוראים עכשיו, לא `transition("done",...)` ישירות.** Task ללא `expected_outcome` (ברירת-המחדל, כל Task קיים) — **זהה-לגמרי להתנהגות הישנה**.

---

## 7-13. (ARCHITECTURE / STORES / AUTHORITY MAP / TEST STATE — ראו §4-6 למעלה + הטבלה הבאה)

| Store | חדש/קיים | הערה |
|---|---|---|
| `.atlas/investigations.json` | **חדש** | `InvestigationStore`, לא מחובר לproduction tick() עדיין |
| `.atlas/opportunities.json` | קיים, ללא שינוי-schema | grouping-logic משתנה (§4), הנתונים עצמם לא |
| `.atlas/brain.json` | קיים | Task נושא 3 שדות חדשים, ברירת-מחדל תואמת-לאחור |
| שאר ה-stores | ללא שינוי | |

**Authority Map — שינויים בלבד**: Investigation → יוצר-חדש: מי-שמחליט-לחקור (עדיין אין production caller). Task.verification_status → כותב-בלעדי: קוד-אימות-עצמאי, **לעולם לא** actuator עצמו (אכוף מבנית, `test_verification_authority_boundary.py`).

---

## 14. Test State

**נבדק הרגע**: `python -m pytest -q` → **1873 passed, 6 failed, 72.70s**. אותם 6 כשלים ידועים בדיוק כמו כל הסבבים הקודמים (env-var isolation, לא קשור). **אפס רגרסיה חדשה.**

---

## 15. Roadmap / Governance State

ללא שינוי מהותי — עדיין שני מסלולים נפרדים. **עודכן**: שני המסמכים עכשיו מכילים פסקת-הצלבה קצרה, הדדית, שמצביעה על קיום המסלול השני (לא מיזוג, רק מודעות מפורשת).

---

## 16. DO-NOT-BUILD LIST (עדיין תקף, ללא שינוי)

זהה לגרסה הקודמת — ראו הרשימה בגרסה הקודמת של מסמך זה בהיסטוריה, או ה-Final Report המלא של הסבב הזה (בתמלול השיחה).

---

## 17. NEXT SESSION — משימה מדויקת

**DO NOT ASSUME LIVE-READY.** הסבב הזה סגר את חמשת הפערים הארכיטקטוניים (Design→Code), **אך שום דבר לא אומת מול Marketplace אמיתי**. הצעד הבא, לפי ההוראה המפורשת של הסבב הזה:

1. קרא את המסמך הזה + ה-Final Report המלא (בתמלול השיחה שהובילה לכתיבתו).
2. אמת מחדש שהקוד עדיין תואם למה שכתוב כאן (§1-6) — ישירות מהקבצים, לא מהמסמך.
3. **אל תתחיל Live Validation בלי GO נפרד ומפורש** — הסבב הזה **לא** אישר Live Validation. §17 (STRICT LOCK) של ה-GO המקורי אסר זאת במפורש.
4. שאלת-הפתיחה למי שממשיך: מה עדיין חסר כדי שה-Investigation→Bridge-1 chain יהיה **production-wired** (לא רק synthetic-tested) — במיוחד: מי בפועל יפתח Investigation מ-Marketplace, ומי יספק `source_ref` אמיתי?

---

## 18. UNKNOWNs

- האם ה-Design שסוכם (5 תיקונים) יעמוד במבחן Live אמיתי — לא נבדק, רק synthetic.
- `source_ref` selection האוטונומי — עדיין לא הוכרע כלל.
- מתי/אם evidence provenance (claimant/origin_domain) ייבנה — לא הוכרע.
- מי-בפועל יפעיל `advance_investigations()` מ-`tick()` (אם בכלל) — לא נבנה, לא הוכרע.
