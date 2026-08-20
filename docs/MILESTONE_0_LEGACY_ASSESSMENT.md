# Milestone 0 — מיפוי המערכת הקיימת מול המפרט (Legacy Assessment)

**תאריך:** 2026-08-11
**מטרה:** מיפוי בלבד. מסמך זה אינו מכיל אף החלטת מימוש. המטרה היחידה היא לבנות תמונת מצב מלאה של `src/atlas/` הקיים מול `docs/BUSINESS_BRAIN_AGENTIC_OS_SPECIFICATION.md`, כתנאי מוקדם להחלטה משותפת (שכתוב מלא / ריפקטור / בנייה מקבילית) — בהתאם ל-Article VIII ("Build Once, Reuse Forever") ולהנחיה המפורשת של המייסד.

**מתודולוגיה:** כל קובץ נקרא בפועל (לא הוסק משם הקובץ). המיפוי בוצע על ידי ארבעה סוכני מחקר מקבילים, כל אחד סוקר חלק שונה של הקוד, ואומת/נערך מחדש כאן מול המפרט. ציטוטי פונקציות/מחלקות הם אמיתיים, לא ניחוש.

**היקף:** כ-140 קבצי Python תחת `src/atlas/`, פרוסים על פני `core/`, `brain/` (כ-70 קבצים), `assets/` (9 מחלקות-בת), `hands/`, `integrations/`, `influencer/`, `brand/`, `campaign/`, `orchestrator/`, `headquarters/`, וקבצי הכניסה הראשיים.

---

## חלק א׳ — ממצאים קריטיים חוצי-מערכת

(מפורט גם בהודעת הצ'אט הקודמת — מובא כאן שוב לצורך שלמות המסמך)

1. **`brain/ceo.py` — `CEOBrain.tick()`** מריץ ברצף אחד, ללא הפרדה, את כל 4 שכבות Business Brain יחד עם פעולות Agentic OS אמיתיות (כ-10 גשרי pipeline-advance, דלגציה, ניטור). זו הפונקציה שמופעלת בפועל כל 30 דקות על ידי Windows Scheduled Task אמיתי. הפרה מרכזית של "כל שכבה סומכת רק על תוצר השכבה הקודמת, ואין state פרטי."
2. **שלושה מנגנוני "ראיות→החלטה" מקבילים ולא מתואמים**: `decision_engine.py`, `improvement.py`, `opportunity_discovery_advance.py`. המפרט דורש שכבת Executive Decision יחידה.
3. **`brain/campaign_advance.py`** — המנגנון העשיר ביותר בקוד (כבר יצר בפועל Campaign עם רווח אמיתי) — משלב Reasoning + Decision + פעולה אמיתית בעולם בפונקציה אחת, ללא גבול שכבתי.
4. **הפרת "ללא state פרטי" חוזרת**: `IntelligenceIndex`, `ResourceIndex` (שני stores מלאים שנדרסים בכל סריקה), `Task.priority_score` (Projection שנשמר על ה-Entity עצמו), `KPIRegistry` (סכום מצטבר במקום חישוב מחדש מ-`LedgerEntry`).
5. **שיפוט עסקי בתוך קוד ביצוע טהור**: `affiliate_department/agent.py` (מדרג/בוחר/מחייב בפנים), `orchestrator/compliance_review.py` (שיפוט עסקי בתוך מנוע התיאום עצמו), `recruitment_workforce/matching.py` (פונקציית תמחור עסקית לצד matching מבני טהור, באותו קובץ).
6. **התנגשות שם: שני מושגי "Asset" שונים** — `core.models.AssetRecord` (יכולת קוד רשומה) מול `Asset` החדש (נכס עסקי לשימוש חוזר).
7. **שלושה ממשקי הפעלה נפרדים, לא מתואמים**: `headquarters/server.py`, `app.py`+`repl.py`, `cli.py`. אף אחד לא תואם במלואו ל-Article VI. `conversation_memory.py` — הבסיס הכי קרוב ל-ConversationTurn, אך דליל. `claude_executive.py` — מושג שונה לגמרי (Agent/Action/Outcome).
8. **State תפעולי אמיתי וחי**: `.atlas/brain.json` (12MB, מתעדכן כל 30 דקות), היסטוריית הכנסות/decisions/ledger אמיתית. כל מסלול חייב להתייחס לכך במפורש.
9. **שבעה קבצי "pipeline_advance" כמעט-זהים** תחת `atlas.brain` (`pipeline_advance.py` עד `publishing_gateway_advance.py`) — הם Agentic OS טהור לפי הגדרת המפרט עצמה, אך ממוקמים וכפולים במבנה כמעט זהה.
10. **צביר plugin (audio/document/image/video/youtube/browser) הוא הקוד הנקי והשמיש ביותר בכל הבסיס** — תשתית איסוף Findings אמיתית, ללא שום פרשנות מעורבבת. שווה לציין כממצא חיובי משמעותי.
11. **`resource_allowlist.py`/`browser_allowlist.py`** — מבשרים חזקים וכמעט-מוכנים ל-Authorization החדש, אך קיימים כשני registries נפרדים וכפולים במקום entity אחד.
12. **`Campaign` (models.py)** מערבב שדות בסגנון BusinessUnit (goal_id, budget, timeline) עם שדות שימוש-בנכס (influencer_ids, brand_id) בישות אחת — המפרט שומר Company/BusinessUnit ו-Asset נפרדים.

---

## חלק ב׳ — מפת המודולים המלאה

עמודות: **תפקיד בפועל** | **שכבה במפרט** | **תואם למפרט?** | **ניתן למחזר כפי שהוא?** | **כדאי ריפקטור?** | **להחליף לחלוטין?** | **נימוק**

### `src/atlas/core/` — רישום הנכסים (Asset Registry)

| קובץ | תפקיד בפועל | שכבה במפרט | תואם? | למחזר כפי שהוא? | ריפקטור? | החלפה מלאה? | נימוק |
|---|---|---|---|---|---|---|---|
| `capabilities.py` | `Runnable`/`Triggerable`/`Reportable` — 3 Protocols. | Agentic OS (חוזה יכולת) | כן | כן | לא | לא | טיפוס מבני טהור, ללא שיפוט עסקי. |
| `loader.py` | `discover_manifests()` — סורק `manifest.toml`, בונה `AssetRecord`, אף פעם לא מייבא קוד asset. | Agentic OS | כן | כן | לא | לא | דטרמיניסטי לחלוטין. |
| `models.py` | `AssetRecord` — dataclass קפוא (id/name/kind/entrypoint/config). | לא ישות Domain במובן החדש | חלקי | כן, עם שינוי שם | כן | לא | אותו שם ("Asset") כמו הישות החדשה, אך מושג שונה לגמרי — התנגשות שם קריטית (ממצא #6). |
| `registry.py` | `Registry.dispatch(asset_id, verb)` — טעינה עצלה, בדיקת יכולת, קריאה, שמירת מצב אחרון. | Agentic OS (הפעלת פעולה) | כן | כן | לא | לא | דלגציה דטרמיניסטית, ללא שיפוט. |
| `store.py` | `read_json`/`write_json_atomic`, `Store`/`JSONStore`. | תשתית / persistence | N/A | כן | לא | לא | תשתית טהורה. |

### `src/atlas/brain/` — חלק 1: הליבה (models, ceo, planning, decision, reporting)

| קובץ | תפקיד בפועל | שכבה במפרט | תואם? | למחזר כפי שהוא? | ריפקטור? | החלפה מלאה? | נימוק |
|---|---|---|---|---|---|---|---|
| `models.py` | `Goal`, `StrategicObjective`, `Task`, `Finding`, `SuccessLaw`, `Decision`, `LedgerEntry`, `Proposal` — 7 מתוך 16 הישויות החדשות, כמעט מילה-במילה. `Task.transition()` כולל לוגיקת state-machine מוטבעת בישות עצמה. | ישויות Domain | חלקי | כן, עם שינוי | כן | לא | הישויות עצמן תואמות היטב (כולל חלוקת State/Fact); `Task.transition()` מפר "כללים שייכים לשכבת המפרט, לא לנתוני Domain." |
| `memory.py` | `BrainMemory` — CRUD למסמך JSON יחיד. | אחסון Domain | כן | כן | לא | לא | תואם. |
| `store.py` | `BrainStore` + `JSONFileStore`. | תשתית | N/A | כן | לא | לא | תשתית מתחלפת. |
| `ceo.py` | `CEOBrain.tick()`/`review()`/`approve()`/`reject()` — מפעיל planner, prioritizer, risk gate, delegator, monitor, ~10 גשרי pipeline-advance, strategist, reporter — הכל ברצף אחד. | חוצה את כל 4 השכבות + Agentic OS, ללא הפרדה | **לא** | לא | — | **כן** | ממצא קריטי #1. זו שורש-ההרכבה של המערכת, אך היא מכילה היום לוגיקה ששייכת לכל שכבה בנפרד — לא ניתן "לרפקטר קלות", נדרש פירוק אמיתי. |
| `planner.py` | `SimplePlanner.plan()` — Task אחד פתוח לכל Goal פעיל, קטגוריה ממילון מילות-מפתח. | Rules (תחליף זמני ל-Reasoning, לפי ה-docstring שלו) | חלקי | כן | לא | לא | כן מודה בעצמו שאינו "תחליף לחשיבה אסטרטגית אמיתית." |
| `prioritizer.py` | `SimplePrioritizer.score()` — נוסחה, כותב `Task.priority_score` שנשמר. | Reasoning בצורתו, אך persisted | חלקי | לא כפי שהוא | כן | לא | Projection שנשמר במקום להיחשב מחדש — מפר את הכלל. |
| `risk.py` | `RiskPolicy.evaluate()` — בדיקה fail-closed על 4 צירי סיכון. | Rules / שער ממשל | כן | כן | לא | לא | דטרמיניסטי לגמרי, תואם "בדיקת כלל קבוע." |
| `delegator.py` | `Delegator.delegate()` — ניתוב Task ל-asset תואם, אחרת Proposal. | Agentic OS | כן | כן | לא | לא | תואם. |
| `monitor.py` | `Monitor.sync()` — קריאת `report()` חזרה, עדכון סטטוס, KPI תפעוליים. | Agentic OS | כן | כן | לא | לא | תואם. |
| `strategist.py` | `SimpleStrategist.reallocate()` — מדרג Goals לפי `blended_score`, ממפה דירוג ל-priority, משעה goals תקועים. | Reasoning (דירוג) + Decision (כתיבה) מאוחדים | חלקי | כן, עם שינוי | כן | לא | המפרט מזהה זאת במפורש כמופע Reasoning→Decision, אך כאן זה פונקציה אחת ללא מסירת Standings Map. |
| `decision_engine.py` | `decide()`/`decide_all()` — משלב `confidence_score()` עם הקשר חברה ל-5 verdicts, כותב Decision. | Executive Decision, סופג גם תפקידי Reasoning | חלקי | כן, עם שינוי | כן | לא | הדימיון האמיתי הקרוב ביותר ל-Decision החדש; מבצע גם דירוג ספקים בפנים במקום לצרוך Standings Map מוכן. |
| `decision_engine_integration.py` | `evaluate_task_readiness()` — 3 בדיקות טהורות (משאבים/הזדמנות/זמן) → EXECUTE/WAIT. | Agentic OS (בדיקת כלל קבוע), ממוקם בטעות ב-brain | **לא** (כשכבת Business Brain) | כן | כן (מיקום) | לא | ה-docstring עצמו: "no hidden state, no scoring blend" — זה בדיוק הגדרת Agentic OS. |
| `decision_apply.py` | `apply_decision()` — ב-"invest" יוצר Goal חדש + Task אוטו-דלגציה; ב-"propose_capability" יוצר Goal + Task. | שלב הכתיבה של Executive Decision | חלקי | כן, עם שינוי | כן | לא | המפרט מגביל את כתיבת Decision ל-Decision+Goal.priority-update-או-Proposal בלבד; כאן "invest" יוצר Goal חדש לגמרי — רחב יותר מהיקף המפרט. |
| `decisions.py` | `DecisionLog` — אחסון append-only, `superseded_id`. | Domain Fact store | כן | כן | לא | לא | התאמה מדויקת ל-Fact. |
| `confidence.py` | `confidence_score()` + 6 פונקציות גורם, `weighted_average_of_available()`, `rank_by_confidence()`. | Projection | כן | כן | לא | לא | מחושב מחדש בכל קריאה, לא נשמר — תואם במדויק. |
| `explain.py` | `explain_opportunity()` — תצוגת "למה" לקריאה בלבד. | Projection | כן | כן | לא | לא | תואם. |
| `valuation.py` | `blended()` — משלב אומדן מייסד עם KPI נמדד, לפי `maturity()`. | Projection, בצורת Understanding (פרשנות ישות בודדת) | חלקי-טוב | כן | לא | לא | מועמד לפורמליזציה כפרימיטיב Understanding. |
| `scoring.py` | `score_cash_flow`/`score_strategic_value`/`blended_score` — נירמול min-max בתוך horizon. | Projection, בצורת Reasoning | כן | כן | לא | לא | השוואה מפורשת בין ישויות, לא נשמר. |
| `cashflow.py` | `profit()`/`roi()`/`goal_cash_flow()` — None כשלא נמדד, אף פעם לא מזויף. | Projection | כן | כן | לא | לא | תואם. |
| `reporter.py` | `Reporter.summarize()` — מצרף goals/tasks/proposals/KPI/cash-flow/opportunities/success-laws/portfolio/publishing-readiness. | Perception מיועד, אך כולל תוכן מדורג | חלקי | לא כפי שהוא | כן | לא | קורא ישירות ל-`rank_by_confidence`/`rank_opportunities`/וכו' — מערבב Perception טהור עם פלט Reasoning מדורג. |
| `console.py` | `build_console_view()`/`find_warnings()`/`build_briefing()` — אגרגציה לקריאה בלבד + בדיקות סף קבועות. | Executive Perception | כן — ההתאמה הטובה ביותר בקבוצה | כן | לא | לא | ארגון עובדות גולמיות טהור, ללא דירוג/פרשנות. |
| `kpi.py` | `KPIRegistry` — סדרת זמן גנרית לפי שם מדד. | אחסון Domain, ללא ישות 1:1 ישירה | חלקי | כן | כן | לא | אין ישות "KPI" ייעודית בין 16 הישויות; הקרוב ביותר הוא זרם Outcome/Fact. |
| `kpi_intake.py` | `record_revenue()` + `record_manual_*()` — ייחוס דטרמיניסטי, fail-closed. | Rules / Agentic-OS-adjacent | כן | כן | לא | לא | ללא שיפוט, מיפוי מכני טהור. |
| `ledger.py` | `Ledger` — אחסון append-only, אף פעם לא משתנה. | Domain Fact store | כן | כן | לא | לא | אותו דיסציפלין כמו `DecisionLog`. |
| `improvement.py` | `propose_improvements()` — gated ראייתית, יוצר Tasks מסוג redesign/improve. | מנגנון "זיהוי+החלטה" שני, מקביל ל-decision_engine | חלקי | כן, עם שינוי | כן | לא | ראה ממצא #2 — כפילות מבנית עם decision_engine. |
| `intake.py` | `absorb_opportunities()` — הופך opportunities גולמיים מ-Research ל-Finding + Tasks. | איסוף עובדות גולמי, Perception-adjacent | חלקי | כן | לא | לא | מיפוי עובדה-למצב מכני, ללא שיקלול ראייתי. |
| `pipeline_advance.py` ואחיו (7 קבצים — ראו רשימה בממצא #9) | גשרי "המשך את השלב הבא" זהים במבנה, per-asset. | Agentic OS | כן, אך ממוקמים בטעות | כן | כן (מיקום) | לא | תואמים כמעט מילה-במילה להגדרת Agentic OS של המפרט, אך יושבים תחת `atlas.brain`. |
| `campaign_advance.py` | `advance_decision_driven_campaigns()` — חיפוש שימוש חוזר, יצירת Campaign, הפעלה, שיוך Success Laws, Proposals. | Reasoning + Decision + Action מאוחדים | **לא** | לא | — | **כן** | ממצא קריטי #3 — הלוגיקה בעלת הערך הגבוה ביותר בקוד, אך ללא שום גבול שכבתי. |
| `opportunity_ranking.py`, `provider_ranking.py`, `asset_value.py`, `portfolio.py` | פונקציות Projection/דירוג טהורות, מחושבות מחדש. | Projection helper | כן | כן | לא | לא | תואמים היטב. |
| `opportunity_discovery_advance.py` | `advance_opportunity_discovery()` — מקדם evidence שעוברת סף ל-Opportunity אמיתי. | מנגנון "החלטה מראיות" שלישי, מחוץ ל-DecisionLog | חלקי | כן, עם שינוי | כן | לא | ראה ממצא #2. |
| `feature_flags.py` | `opportunity_discovery_v1_enabled()` — בדיקת `os.environ`. | לא חלק מהמפרט | N/A | לא | — | כן | תפקיד קרוב-מושגית ל-Authorization עתידי, אך אינו כזה בפועל. |

### `src/atlas/brain/` — חלק 2: מודיעין / מחקר / חישה (35 קבצים)

| קובץ | תפקיד בפועל | שכבה במפרט | תואם? | למחזר כפי שהוא? | ריפקטור? | החלפה מלאה? | נימוק |
|---|---|---|---|---|---|---|---|
| `intelligence_engine.py` | `collect_intelligence()` — מריץ providers, **דורס** `IntelligenceIndex` בכל סריקה. | Perception-adjacent | חלקי | כן, עם שינוי | כן | לא | דיסציפלינת בידוד-תקלות תקינה; ה-index הנשמר מפר "ללא state פרטי." |
| `intelligence_index.py` | אחסון full-replacement, נשמר. | לא שייך לאף שכבה | **לא** | לא | — | **כן** | הפרת state פרטי ישירה (ממצא #4). |
| `intelligence_cycle_advance.py` | גשר tick לכל Goal פעיל, מפעיל `run_intelligence_workflow()`. | Agentic OS Orchestration | חלקי | כן, עם שינוי | כן | לא | תקין כגשר; מחובר למונוליט (הקובץ הבא). |
| `intelligence_research_framework.py` | `build_research_framework()` — תבנית דטרמיניסטית, לעולם לא ממציאה תשובות. | לא שכבה מוגדרת — הכנה טרום-Perception | חלקי | כן, עם שינוי | כן | לא | הדיסציפלינה (לא להמציא) שווה שימור. |
| `intelligence_workflow.py` | `run_intelligence_workflow()` — **פונקציה מונוליטית בת 8 שלבים**: Perception+Reasoning+Decision ברצף אחד. | חוצה 3 שכבות | **לא** | לא כפי שהוא | — | **כן** (המעטפת; השלבים עצמם ניתנים למחזור) | הממצא החד ביותר בקבוצה — בדיוק אנטי-הדפוס שהמפרט נועד למנוע. |
| `knowledge.py` | `KnowledgeBase` — אחסון `Finding`/`SuccessLaw`. | אחסון Domain | כן | כן | לא | לא | יישום ייחוס אמיתי של Finding+SuccessLaw. |
| `knowledge_source_registry.py`+`knowledge_source_research.py` | `select_plugin()`/`collect_evidence_from_source()` — חישה אמיתית, שער איכות, שמירת Finding יחיד. | Domain/Finding-sourcing | כן | כן | לא | לא | צינור חישה נקי, לדוגמה. |
| `resource_discovery_engine.py` | `scan_resources()` — אותו דפוס provider-isolation, גדור על ידי Allowlist. | Perception-adjacent | חלקי | כן, עם שינוי | כן | לא | דיסציפלינת ממשל מצוינת; אין ישות Domain ל-Resource. |
| `resource_index.py` | אחסון full-replacement, נשמר, זהה במבנה ל-`intelligence_index.py`. | לא שייך לאף שכבה | **לא** | לא | — | **כן** | אותה הפרה כמו `intelligence_index.py`. |
| `resource_allowlist.py`+`browser_allowlist.py` | 2 allow-lists ניתנות-אישור-מייסד, default-deny. | מבשר ל-Authorization | חלקי | כן, עם שינוי | כן | לא | ממצא #11 — מבנה נכון, כפול. |
| `market_intelligence_provider.py` | מתאם טהור, מתייג Finding מחדש. | נורמליזציה | כן | כן, עם שינוי | כן | לא | תקין אך מזין את ה-index הבעייתי. |
| `digistore24_opportunity_discovery.py` | `score_marketplace_entry()` — ניקוד עסקי משוקלל בתוך מודול "גילוי". | מערבב Perception+Reasoning | חלקי | כן, עם שינוי | כן | לא | הנוסחה שמישה; צריכה חילוץ. |
| `opportunity_discovery_engine.py` | דפוס provider-isolation + מיון פנימי. | בעיקר Finding-sourcing עם דירוג מוטבע | חלקי | כן, עם שינוי | כן | לא | דדופ מבני תקין; מיון צריך לצאת לשכבת Reasoning. |
| `success_patterns.py` | `identify_success_patterns()` — מקבץ Campaigns אמיתיים, מדרג לפי רווח נמדד. | **Executive Reasoning** | כן | כן | לא | לא | התאמה נקייה. |
| `success_principles_engine.py` | `analyze_success_principles()` — מסווג Campaigns לפי Success Law, לעולם לא ממציא סיבתיות. | **Executive Reasoning** | כן | כן | לא | לא | התאמה נקייה, חופפת ל-success_patterns. |
| `evidence_validation.py` | `assess_observation_quality()` — בדיקות דטרמיניסטיות + שיפוט AI אחד. | שער איכות Perception-adjacent | כן | כן | לא | לא | fail-closed, תואם. |
| `business_execution_planning.py` | `build_execution_plan()` — סינתזה של decide()+דירוג+בדיקות. | Reasoning-adjacent, אחרי Decision | חלקי | כן, עם שינוי | כן | לא | מטשטש גבול Reasoning/Decision. |
| `capital_allocation.py` | `recommend_allocation()` — ממליץ בלבד, לעולם לא מיישם. | **Executive Reasoning** | כן | כן | לא | לא | תבנית טובה לפונקציית הקצאת-הון פורמלית. |
| `time_service.py` | `TimeService` — קריאת שעון יחידה, שאר הכל טרנספורמציות טהורות. | תשתית חוצה-שכבות | כן | כן | לא | לא | ראוי כשירות משותף מוזרק לכל השכבות. |
| `recall.py` | `recall()` — חיפוש טקסט חופשי על פני 9 stores. | מבשר גס ל-Reality Map | חלקי | כן, עם שינוי | כן | לא | דפוס חיפוש טוב; דורש ארגון מחדש ל-8 הדומיינים הקבועים. |
| `conversation_memory.py` | `ConversationMemory` — רשומה append-only אמיתית של כל turn. | **Conversation Management (Agentic OS)** | חלקי | כן, עם שינוי | כן | לא | הבסיס הנכון ל-ConversationTurn, אך דליל מדי (ממצא #7). |
| `claude_executive.py` | `ClaudeExecutiveLog`/`send_task()` — רישום דלגציה ל-Claude CLI. | **לא** Conversation Management — קרוב יותר ל-Agent/Action/Outcome | לא כ-Conversation; חלקי כ-Agent/Action | כן, עם שינוי | כן | לא | אין לבלבל עם conversation_memory (ממצא #7). |
| `browser_live_monitor.py` | `observe_and_compare()` — diff טהור בין תצפיות. | Perception-adjacent | כן | כן | לא | לא | קטן וכן. |
| `browser_plugin.py`, `browser_research.py` | מפיקי Finding מבוססי דפדפן; `browser_research.py` מוצהר כמיושן לטובת knowledge_source_research. | Domain/Finding-sourcing | כן/חלקי | כן | כן (לאחד) | לא | כפילות מוצהרת בעצמה. |
| `screen_observation.py`+`screen_reader.py` | לכידת מסך אמיתית + הבנת Gemini, נשמר כ-Finding. | Domain/Finding-sourcing | כן | כן | לא | לא | תואם. |
| `audio_plugin.py`, `document_plugin.py`, `image_plugin.py`, `video_plugin.py`, `youtube_plugin.py` | 5 מימושי plugin זהים מבנית, כל אחד קריאת Gemini אמיתית, גדור Allowlist. | Domain/Finding-sourcing | כן | כן | לא | לא | ממצא #10 — הקוד הנקי והשמיש ביותר בכל הבסיס. |
| `sales_sync.py` | `record_real_sale()` — כתיבת LedgerEntry אידמפוטנטית + עדכון KPI מצטבר. | חלק Fact תואם; חלק Projection-נשמר לא תואם | חלקי | כן, עם שינוי | כן | לא | כתיבת LedgerEntry תואמת במדויק; הסכום המצטבר ב-KPIRegistry מפר "לחשב מחדש, לא לשמור." |

### `src/atlas/assets/` — סוכני "מחלקה" תפעוליים

| קובץ/מודול | תפקיד בפועל | שכבה במפרט | תואם? | למחזר כפי שהוא? | ריפקטור? | החלפה מלאה? | נימוק |
|---|---|---|---|---|---|---|---|
| `affiliate_department/agent.py` | `run()`→discover→evaluate (מנקד, ממיין, **כותב stage="selected"/"lost" בעצמו**)→plan_content. | Business Brain (Reasoning/Decision) בתוך Agentic OS | **לא** | לא | — | חלקית (לפצל) | בחירה+חיוב בתוך asset ביצוע טהור — בדיוק מה שהמפרט אוסר (ממצא #5). |
| `affiliate_department/models.py`+`store.py` | `AffiliateOpportunity` (10 stages), אחסון atomic. | Domain (Opportunity) + Agentic OS | כן | כן, כייחוס | לא | לא | מבנה נתונים תקין; 10 השלבים ממזגים כמה pipelines. |
| `affiliate_department/scoring.py` | `score_opportunity()` — נוסחה משוקללת טהורה. | Business Brain — Reasoning | כן | **כן, ישירות** | לא | לא | הקוד הנקי ביותר בקבוצה — קטן, טהור, ללא side-effect. |
| `affiliate_intelligence/agent.py`+`agents.py` | `Discovery`/`Research`/`RankingAgent` — 3 שכבות Business Brain בתוך מחלקת dispatch. | Perception+Understanding+Reasoning בתוך Agentic-OS-shaped class | חלקי | לא כפי שהוא | — | חלקית (לפצל) | ה-Ranking עצמו תואם Reasoning; ה"מחקר" הוא טבלת placeholder קבועה, לא Perception אמיתי. |
| `campaign_execution/agent.py` | מחזיר תשובה כנה קבועה, ללא ניקוד/בחירה. | Agentic OS — Orchestration Delegation | **כן, לדוגמה** | כן | לא | לא | ההתאמה הטובה ביותר בכל ה-batch. |
| `content_factory/agent.py`+`generator.py` | הרכבת תבניות דטרמיניסטית; זוויות שיווקיות קבועות בקוד. | Agentic OS מכנית, אך אסטרטגיית תוכן מוקשית | חלקי | כן, עם שינוי | כן | לא | ביצוע ללא שיפוט, אך בחירת אסטרטגיה שייכת ל-Business Brain. |
| `creative_agent/agent.py`+`generator.py` | הרכבת shot-list דטרמיניסטית + רישום קובץ אמיתי. | Agentic OS | כן, ברובו | כן | לא | לא | תואם היטב למושג Asset/עובדה. |
| `editorial_review/agent.py`+`checks.py` | 7 בדיקות בוליאניות דטרמיניסטיות, סף קבוע. | Agentic OS — שער כלל קבוע | כן, קרוב | כן, עם שינוי | כן | לא | דומה מאוד ל-Risk-gate; קבועי מדיניות מוקשים בקוד. |
| `hands/agent.py` (asset) | דלגציה ל-Browser/Desktop Hands, "לעולם לא מחליט מה לעשות." | Agentic OS — Delegation | **כן, לדוגמה** | כן | לא | לא | מימוש כמעט-ספר-לימוד. |
| `maya/agent.py` | stub ריק — `run()` רק מהדהד task_id. | Agent Management placeholder | N/A | לא | — | **כן** | אין דבר של ממש למחזר מלבד צורת ה-Protocol. |
| `publishing_gateway/agent.py`+`builder.py`+`models.py`+`store.py` | state-machine עם שערי כלל קבוע בלבד, ללא ניקוד. | Agentic OS | כן, קרוב | כן, ברובו | כן | לא | `PublishPackage` צריך למופות ל-Asset/Action/Outcome החדשים. |
| `recruitment_workforce/agent.py`+`models.py`+`store.py` | state-machine עם שערי אישור-מייסד מפורשים. | Agentic OS Orchestration/Task Mgmt | כן, ברובו | כן | לא | לא | שער האישור ממופה ישירות ל-Authorization. |
| `recruitment_workforce/matching.py` | `select_candidates()` (מבני טהור) + `compute_revenue_model()` (מדיניות תמחור עסקית) — **באותו קובץ**. | פיצול Agentic OS / Business Brain | חלקי | לא כפי שהוא | — | חלקית (לפצל) | ממצא #5 — שתי הפונקציות בצדדים מנוגדים של הגבול. |
| `research/agent.py` | `_discover()` — 2 מחרוזות placeholder קבועות; `_classify()` — מיפוי מילות-מפתח. | Perception (מזויף) + Understanding | חלקי | לא | — | **כן** (הגילוי; הסיווג ניתן למחזור) | הלוגיקה היחידה האמיתית היא מחולל placeholder. |
| `revenue/agent.py`+`channels/*.py` | ניתוב לפי קטגוריה למחלקה, כל ערוץ מחזיר `0.0` ביושר. | Agentic OS — דלגציה מבנית | כן, למעטפת | כן, למעטפת | לא | לא | ניתוב ללא שיפוט; הערוצים דורשים עבודת אינטגרציה נפרדת ממילא. |

### `src/atlas/hands/` — ביצוע פעולות אמיתיות בעולם

| קובץ | תפקיד בפועל | שכבה במפרט | תואם? | למחזר כפי שהוא? | ריפקטור? | החלפה מלאה? | נימוק |
|---|---|---|---|---|---|---|---|
| `models.py`+`registry.py` | `HandsRequest` (4 צירי סיכון), `validate_steps()` (כלל קבוע), CRUD טהור. | Domain (Action-sequence) + Agentic OS | כן, נקי | כן | לא | לא | הישות הכי קרובה קיימת ל-Action החדש. |
| `dispatch.py` | `request_hands_action()` — יוצר Task risk-gated אמיתי, משתמש מחדש במנגנון RiskPolicy/Delegator הקיים. | Agentic OS Orchestration | כן, קרוב מאוד | כן | לא | לא | זהו בפועל תבנית הגשר שהמפרט מתאר. |
| `browser_hands.py`+`desktop_hands.py` | ביצוע אמיתי (browser_use / עכבר-מקלדת), "המוח מחליט מה, המודול הזה רק מבצע." | Agentic OS — מבצע ה-Delegation/Action האמיתי | **כן, לדוגמה** | כן | לא | לא | ככל הנראה הזוג התואם-ביותר-למפרט בכל הבסיס כולו. |

### `src/atlas/integrations/` — קישוריות פלטפורמה אמיתית

כל 14 הקבצים (`base.py`, `registry.py`, `digistore24.py`, `gemini_provider.py`, `claude_provider.py`, `youtube_provider.py`, `local_folder_provider.py`, `browser_use_observer.py`, `browser_observer_registry.py`, `ai_provider_registry.py`, `signal_registry.py`, ושלושת קבצי ה-placeholders) — **תשתית (Infrastructure)**, מחוץ לשתי השכבות, בדיוק כפי שהמפרט מצפה. תואמים, ניתנים למחזור כפי שהם, ללא ריפקטור, ללא החלפה. הבדיקה היחידה הראויה לציון: `validate_link()` ב-`digistore24.py` הוא בדיקה מבנית (regex/parsing), לא שיפוט — תואם.

### `src/atlas/influencer/`, `src/atlas/brand/`, `src/atlas/campaign/`

| קובץ | תפקיד בפועל | שכבה במפרט | תואם? | למחזר כפי שהוא? | ריפקטור? | החלפה מלאה? | נימוק |
|---|---|---|---|---|---|---|---|
| `influencer/models.py` | `DigitalInfluencer` + תתי-פרופילים, `TEMPLATE_KINDS`. | Domain (Asset: Influencer) | כן | כן | לא | לא | `categories` הוא בדיוק הדוגמה שהמפרט עצמו נותן לעובדה מבנית. |
| `influencer/registry.py` | CRUD + `attach_asset()`+`add_category()`. | Domain (כתיבה) | חלקי | כן | כן | לא | הכתיבות עצמן תקינות, אך ללא בדיקת Authorization לפניהן. |
| `influencer/ranking.py` | `rank_influencers()`/`prefer_market_match()` — טהור, קריאה-בלבד, אף פעם לא כותב. | **Business Brain — Reasoning** | כן, מבנית | כן | כן (מיקום) | לא | סטטלס לחלוטין; דורש רק העברה. |
| `influencer/factory.py` | Draft (Understanding) + Suggestion + `create_influencer_from_proposal` (ביצוע לאחר Decision, fail-closed על אישור). | Understanding + Agentic-OS-adjacent | חלקי | לא כפי שהוא | — | חלקית (לפצל) | הטיוטה/הצעה שייכות ל-Understanding; היצירה היא "ביצוע החלטה שכבר התקבלה." |
| `influencer/performance.py` | `record_metric()`/`performance_snapshot()` — סמנטיקת החלפה, לא הצטברות. | Domain (ביצועי Asset) | כן | כן | לא | לא | תואם. |
| `brand/models.py`, `registry.py`, `factory.py` | מקבילים מדויקים ל-influencer/* (Brand במקום Influencer). | זהה למקביליו | זהה | זהה | זהה | זהה | אותו ניתוח. |
| `campaign/models.py` | `Campaign` — מערבב שדות BusinessUnit (goal_id/budget/timeline) עם שימוש-בנכס (influencer_ids/brand_id). | Domain (Asset/BusinessUnit מעורבב) | חלקי | כן | כן | לא | ממצא #12. |
| `campaign/registry.py` | CRUD + `create_campaign()` הקורא ישירות ל-`confidence_score()` מ-Business Brain. | אחסון Domain הפונה ישירות ל-Business Brain | חלקי | כן, עם שינוי | כן | לא | כיוון הקריאה הפוך מהמפרט (Domain קורא ל-Brain, לא להיפך). |

### `src/atlas/orchestrator/`

| קובץ | תפקיד בפועל | שכבה במפרט | תואם? | למחזר כפי שהוא? | ריפקטור? | החלפה מלאה? | נימוק |
|---|---|---|---|---|---|---|---|
| `orchestrator.py` | `start_execution()`/`advance_execution()` — בונה DAG, מחשב מחדש בכל קריאה, "כותב אך לא בעל" (מתאם ב-task_id, לעולם לא כותב KPI/Ledger בעצמו). | **המועמד האמיתי הקרוב ביותר ל-Orchestration החדש** | חלקי | לא כפי שהוא | כן | לא | הרוח נכונה (recompute-fresh, resumable), אך אוצר המילים (4 kinds) לא תואם Planning→Asset-check→Matching→Risk-gate→Delegation; אין מושג Agent/Matching. |
| `compliance_review.py` | `review_content_compliance()` — היוריסטיקות שיפוט עסקי אמיתיות (גילוי AI, תביעות לא-מבוססות). | Business Brain (Understanding/Reasoning) **בתוך** מנוע Agentic OS | **לא** | לא | — | חלקית (להעביר) | ממצא #5 — דליפת שיפוט עסקי לתוך מנוע התיאום עצמו. |
| `models.py`+`registry.py` | `ExecutionStep`/`ExecutionPlan`, CRUD טהור. | Agentic OS | חלקי | כן, עם שינוי | כן | לא | אוצר המילים (4 kinds) דורש התאמה אם מאמצים את המפרט מילולית. |

### `src/atlas/headquarters/`, קבצי כניסה (`app.py`, `cli.py`, `repl.py`, `speech.py`)

| קובץ | תפקיד בפועל | שכבה במפרט | תואם? | למחזר כפי שהוא? | ריפקטור? | החלפה מלאה? | נימוק |
|---|---|---|---|---|---|---|---|
| `headquarters/server.py` | שרת Starlette — `/api/state`, `/api/approve`, `/api/converse` (שיחת AI אמיתית), `/api/events`. | מטשטש Headquarters מול Conversation Interface | חלקי | לא כפי שהוא | כן | לא | לפי Article VI, Headquarters אמור להיות תפעולי-בלבד, לא UX ראשי — כאן שני התפקידים בשרת אחד. |
| `app.py` | מסך-מלא סביב `repl.dispatch()`, שכבת ניסוחים טבעיים, ללא קריאת AI אמיתית. | Interface — Conversation-proto מקומי | חלקי | לא כפי שהוא | כן | לא | צורת Conversation אך ללא היכולת הגנרטיבית האמיתית שיש ל-`api_converse`. |
| `repl.py` | ניתוב פקודות דק, קורא ישירות ל-`atlas.brain.console`. | Interface — Headquarters מסוף | חלקי | כן | כן | לא | הפרדת לוגיקה/הצגה טובה, אך גזירה שלישית ונפרדת של אותה תצוגה תפעולית. |
| `speech.py` | TTS/STT מקומי (Windows), אף פעם לא זורק. | תשתית שה-Conversation Interface צורך | כן | כן | לא | לא | תואם. |
| `cli.py` | עשרות פקודות one-shot ישירות ל-Domain (`influencer create`, `campaign revenue record`...). | Interface-שכבתי, עוקף גם Conversation וגם Headquarters | לא | חלקי | כן | לא | מייסד שמשתמש ב-CLI עוקף את שני הממשקים האמיתיים; ראוי כממשק פיתוח/דיבוג, לא ממשק מייסד. |

---

## חלק ג׳ — הבהרה מתודולוגית

בכל מקום בו סוכן המחקר ציין "עם שינוי" (with modification) — משמעות הדבר בפועל היא **ריפקטור**: הלוגיקה עצמה אמיתית ושמישה, אך צריכה להיות מוזזת/מפוצלת/משוכתבת-נקודתית כדי לעמוד בגבול השכבתי. בכל מקום בו סומן "No"/"לא" תואם ללא אפשרות מחזור — סומן כ**"להחליף לחלוטין"**. אין במסמך זה שום שקלול בין החלופות (שכתוב מלא / ריפקטור בכל הקוד הקיים / בנייה מקבילית) — זו בדיוק ההחלטה שממתינה לדיון המשותף.

**סיכום מספרי גס** (לצורך תמונת מצב בלבד, לא כהחלטה): הרוב המכריע של הקבצים (למעלה מ-100 מתוך כ-140) מסומנים "ניתן למחזר, לרוב עם ריפקטור נקודתי" — לא "להחליף מלגמרי". מספר קטן ומדויק של קבצים (כ-8) מסומנים "להחליף לחלוטין": `ceo.py` (כמעטפת ההרכבה, לא כל הלוגיקה בתוכו), `campaign_advance.py` (כמעטפת), `intelligence_workflow.py`, `intelligence_index.py`, `resource_index.py`, `maya/agent.py`, `research/agent.py`'s discovery, ו-`core.models.AssetRecord` (שינוי שם, לא מחיקה). זהו ממצא משמעותי בפני עצמו: **רוב הערך העסקי הקיים הוא אמיתי ושמיש** — הבעיה המרכזית היא ארגון/הפרדת-שכבות, לא איכות הלוגיקה עצמה.
