"""
Seed the pipeline database with realistic Golden Eagle Log Homes data.

Populates contacts, interactions, and followups drawn from real sales
discovery interviews plus fictional prospects across all pipeline stages.
Idempotent: checks for existing data before inserting.

Usage:
    cd pipeline/backend && python seed.py
"""

from datetime import date, timedelta
from models import init_db, create_contact, create_interaction, create_followup

TODAY = date(2026, 4, 6)

def _past(days):
    return (TODAY - timedelta(days=days)).isoformat()

def _future(days):
    return (TODAY + timedelta(days=days)).isoformat()

def _today():
    return TODAY.isoformat()


PROSPECTS = [
    # ── new_lead (4) ──────────────────────────────────────────────────────
    {"name": "Mark & Sarah Hendricks", "location": "Bozeman, MT", "stage": "new_lead", "temperature": "warm",
     "budget_range": "$1.2M-$1.6M", "sqft": "2800", "style": "full log", "lot_status": "owns land",
     "rapport_notes": "Sarah paints watercolors. Both love fly fishing on the Gallatin. Retiring from Denver in 2027.",
     "estimated_value": 850000},
    {"name": "Tom Nguyen", "location": "Jackson, WY", "stage": "new_lead", "temperature": "cold",
     "budget_range": "$2M-$2.5M", "sqft": "4000", "style": "timber frame", "lot_status": "looking",
     "rapport_notes": "Tech exec from Seattle. Wants a vacation home near ski area. Has two golden retrievers.",
     "estimated_value": 1200000},
    {"name": "Linda Perkins", "location": "Whitefish, MT", "stage": "new_lead", "temperature": "cold",
     "budget_range": "$800K-$1M", "sqft": "2000", "style": "hybrid", "lot_status": "looking",
     "rapport_notes": "Retired teacher. Wants a small cabin near Glacier NP. Quilting enthusiast.",
     "estimated_value": 550000},
    {"name": "Dave & Maria Santos", "location": "Steamboat Springs, CO", "stage": "new_lead", "temperature": "warm",
     "budget_range": "$1.5M-$2M", "sqft": "3500", "style": "full log", "lot_status": "under contract",
     "rapport_notes": "Own a restaurant chain in Dallas. Want a family gathering home. Three kids all under 12.",
     "estimated_value": 950000},

    # ── discovery (4) ─────────────────────────────────────────────────────
    {"name": "Jim & Karen Patterson", "location": "Big Sky, MT", "stage": "discovery", "temperature": "warm",
     "budget_range": "$2M-$2.5M", "sqft": "4200", "style": "timber frame", "lot_status": "owns land",
     "rapport_notes": "Jim is a retired airline pilot. Karen runs a pottery studio. They have 40 acres with creek access.",
     "estimated_value": 1100000},
    {"name": "Robert Chen", "location": "Driggs, ID", "stage": "discovery", "temperature": "warm",
     "budget_range": "$1M-$1.5M", "sqft": "2600", "style": "hybrid", "lot_status": "owns land",
     "rapport_notes": "Software engineer, works remote. Wants home office with mountain views. Avid mountain biker.",
     "estimated_value": 750000},
    {"name": "Angela & Paul Moretti", "location": "Durango, CO", "stage": "discovery", "temperature": "hot",
     "budget_range": "$1.8M-$2.2M", "sqft": "3800", "style": "full log", "lot_status": "owns land",
     "rapport_notes": "Paul is a cardiologist. Angela is an interior designer — very specific vision. Want a great room with 30ft ceilings.",
     "estimated_value": 1050000},
    {"name": "Steve Kowalski", "location": "Red Lodge, MT", "stage": "discovery", "temperature": "cold",
     "budget_range": "$900K-$1.2M", "sqft": "2400", "style": "full log", "lot_status": "looking",
     "rapport_notes": "Rancher, wants to build near existing property. Concerned about snow load on flat roof design.",
     "estimated_value": 650000},

    # ── ballpark (4) ──────────────────────────────────────────────────────
    {"name": "Michael & Diana Ross", "location": "Kalispell, MT", "stage": "ballpark", "temperature": "warm",
     "budget_range": "$1.5M-$1.8M", "sqft": "3200", "style": "timber frame", "lot_status": "owns land",
     "rapport_notes": "Michael coaches high school football. Diana is a nurse. Want covered wrap-around porch for watching sunsets.",
     "estimated_value": 900000},
    {"name": "Jennifer Walsh", "location": "Telluride, CO", "stage": "ballpark", "temperature": "warm",
     "budget_range": "$2.5M-$3M", "sqft": "5200", "style": "timber frame", "lot_status": "owns land",
     "rapport_notes": "Attorney from Chicago. Wants a ski-in/ski-out lodge. Has a wine collection that needs climate-controlled storage.",
     "estimated_value": 1500000},
    {"name": "Craig & Beth Anderson", "location": "Livingston, MT", "stage": "ballpark", "temperature": "warm",
     "budget_range": "$1M-$1.3M", "sqft": "2800", "style": "hybrid", "lot_status": "owns land",
     "rapport_notes": "Both artists. Want studio space with north-facing skylights. Have two horses.",
     "estimated_value": 750000},
    {"name": "Doug Franklin", "location": "Ennis, MT", "stage": "ballpark", "temperature": "hot",
     "budget_range": "$1.2M-$1.5M", "sqft": "3000", "style": "full log", "lot_status": "owns land",
     "rapport_notes": "Retired firefighter from California. Wants to be near Madison River for fly fishing. Very budget-conscious.",
     "estimated_value": 800000},

    # ── dsa (3) ───────────────────────────────────────────────────────────
    {"name": "Richard & Amy Blackwell", "location": "Cody, WY", "stage": "dsa", "temperature": "hot",
     "budget_range": "$1.8M-$2.2M", "sqft": "4000", "style": "full log", "lot_status": "owns land",
     "rapport_notes": "Richard runs a ranch outfitter business. Amy homeschools their 4 kids. Want a huge mudroom and boot room.",
     "estimated_value": 1100000},
    {"name": "Patricia Nguyen-Howell", "location": "Bozeman, MT", "stage": "dsa", "temperature": "hot",
     "budget_range": "$2M-$2.5M", "sqft": "3600", "style": "timber frame", "lot_status": "owns land",
     "rapport_notes": "Architect herself — very detail-oriented on joinery. Wants exposed king post trusses. Husband is a pilot.",
     "estimated_value": 1200000},
    {"name": "George & Ellen Hatch", "location": "West Yellowstone, MT", "stage": "dsa", "temperature": "warm",
     "budget_range": "$1.5M-$1.8M", "sqft": "3400", "style": "hybrid", "lot_status": "owns land",
     "rapport_notes": "Retired from Park Service. Want to be near Yellowstone. Ellen wants a commercial kitchen for catering side business.",
     "estimated_value": 950000},

    # ── design (3) ────────────────────────────────────────────────────────
    {"name": "Kevin & Laura Mitchell", "location": "Flathead Lake, MT", "stage": "design", "temperature": "hot",
     "budget_range": "$2.2M-$2.8M", "sqft": "4500", "style": "full log", "lot_status": "owns land",
     "rapport_notes": "Kevin is a surgeon. Laura wants a yoga studio in the lower level. On floor plan revision 3. Love the Elk Ridge plan.",
     "estimated_value": 1350000},
    {"name": "Scott & Heather Price", "location": "Sheridan, WY", "stage": "design", "temperature": "hot",
     "budget_range": "$1.6M-$2M", "sqft": "3800", "style": "timber frame", "lot_status": "owns land",
     "rapport_notes": "Own a cattle ranch. Want covered outdoor living space for entertaining. Floor plan revision 4 — close to final.",
     "estimated_value": 1000000},
    {"name": "Tony Reeves", "location": "Missoula, MT", "stage": "design", "temperature": "hot",
     "budget_range": "$1.3M-$1.6M", "sqft": "3000", "style": "hybrid", "lot_status": "owns land",
     "rapport_notes": "Brewmaster, opening a taproom. Wants the home to feel like a mountain lodge. Floor plan revision 2.",
     "estimated_value": 850000},

    # ── materials (1) ─────────────────────────────────────────────────────
    {"name": "Bill & Nancy Crawford", "location": "Helena, MT", "stage": "materials", "temperature": "hot",
     "budget_range": "$2M-$2.4M", "sqft": "4200", "style": "full log", "lot_status": "owns land",
     "rapport_notes": "Bill is a judge. Nancy gardens competitively. Detailed materials pricing complete — waiting on final sign-off.",
     "estimated_value": 1250000},

    # ── contract (1) ──────────────────────────────────────────────────────
    {"name": "James & Olivia Park", "location": "Whitefish, MT", "stage": "contract", "temperature": "hot",
     "budget_range": "$2.5M-$3M", "sqft": "5000", "style": "timber frame", "lot_status": "owns land",
     "rapport_notes": "Tech founders from Bay Area. First load of materials shipping next month. Very hands-on — Zoom every week.",
     "estimated_value": 1600000},
]

# Interactions per prospect (keyed by name)
INTERACTIONS = {
    "Mark & Sarah Hendricks": [
        {"type": "call", "date": _past(5), "summary": "Initial discovery call. Mark called after seeing the Lakehouse YouTube tour. Interested in 2800 sqft full log near Bozeman. Owns 10 acres south of town. Sarah wants an art studio."},
    ],
    "Jim & Karen Patterson": [
        {"type": "call", "date": _past(18), "summary": "Discovery call. Jim wants a timber frame with large hangar-style doors. 40 acres near Big Sky with creek. Budget around $2M. Karen wants a pottery studio in the lower level."},
        {"type": "email", "date": _past(12), "summary": "Sent Timber Ridge and Mountain View floor plans. Jim replied — loves the Timber Ridge layout but wants to modify the garage."},
    ],
    "Angela & Paul Moretti": [
        {"type": "call", "date": _past(8), "summary": "Second discovery call. Paul confirmed budget of $1.8-2.2M. Angela (interior designer) has very specific vision — wants great room with 30ft ceilings and stone fireplace. Discussed foundation options for their sloped lot in Durango.",
         "questions_detected": '["What are the foundation options for a sloped lot?", "Can we modify the Ponderosa floor plan ceiling height?"]'},
        {"type": "email", "date": _past(3), "summary": "Sent ballpark estimate. Angela replied with questions about timber sourcing and finish options."},
    ],
    "Michael & Diana Ross": [
        {"type": "call", "date": _past(25), "summary": "Ballpark discussion. Reviewed $1.65M estimate for 3200 sqft timber frame. Michael had questions about the wrap-around porch cost. Diana asked about interior design services."},
        {"type": "email", "date": _past(14), "summary": "Follow-up with porch cost breakdown. Michael asked about timeline — wants to break ground by fall 2027."},
    ],
    "Jennifer Walsh": [
        {"type": "call", "date": _past(40), "summary": "Initial call — wants a 5200 sqft ski lodge in Telluride. Very high budget. Needs climate-controlled wine storage. Asked about HOA compatibility with log construction.",
         "questions_detected": '["Are log homes compatible with Telluride HOA requirements?", "Can you build climate-controlled wine storage?"]'},
        {"type": "email", "date": _past(30), "summary": "Sent preliminary ballpark of $2.7M. Jennifer reviewing with her financial advisor."},
    ],
    "Doug Franklin": [
        {"type": "call", "date": _past(10), "summary": "Ballpark review. Doug is very budget-conscious — concerned about $1.35M estimate. Discussed value engineering options. Wants to keep the Elk Ridge layout but reduce sqft slightly.",
         "questions_detected": '["What can we cut to bring the price under $1.2M?", "Is the design fee refundable if we don\'t proceed?"]'},
    ],
    "Richard & Amy Blackwell": [
        {"type": "call", "date": _past(15), "summary": "DSA signing call. Reviewed design service agreement — $4/sqft x 6200 design sqft = $24,800 deposit. Richard signed via DocuSign. Design team briefed on mudroom/boot room requirements.",
         "action_items": '["Schedule design kickoff meeting", "Send interior design survey to Amy"]'},
        {"type": "meeting", "date": _past(7), "summary": "Design kickoff via Zoom. Amy walked through her Pinterest board. Discussed log profile options — they prefer D-log with saddle notch corners."},
    ],
    "Patricia Nguyen-Howell": [
        {"type": "call", "date": _past(20), "summary": "DSA signed. Patricia (architect herself) very specific about exposed king post trusses. $4/sqft x 5800 design sqft = $23,200 deposit paid."},
        {"type": "email", "date": _past(10), "summary": "Patricia sent her own preliminary sketches for the truss design. Engineering team reviewing for structural feasibility."},
        {"type": "call", "date": _past(4), "summary": "Check-in call. Engineering approved the truss concept with minor modifications. Patricia happy. Moving to first floor plan draft.",
         "action_items": '["Send first floor plan draft by April 12"]'},
    ],
    "Kevin & Laura Mitchell": [
        {"type": "call", "date": _past(30), "summary": "Design review — revision 2 of floor plan. Kevin wants to expand the master suite. Laura still wants yoga studio in lower level. Discussed natural light options."},
        {"type": "meeting", "date": _past(14), "summary": "Zoom floor plan review — revision 3. Getting close. Main remaining issue is the staircase placement. Laura wants it open, Kevin prefers enclosed for sound isolation."},
        {"type": "email", "date": _past(5), "summary": "Sent revision 3 redlines to design team. Staircase compromise: open with acoustic panels. Waiting on updated drawings.",
         "action_items": '["Design team to return revision 4 by April 10", "Schedule in-person visit for material selections"]'},
    ],
    "Scott & Heather Price": [
        {"type": "call", "date": _past(21), "summary": "Design review — revision 3. Outdoor living space expanded to 800 sqft with stone fireplace. Heather wants a dedicated gift-wrapping room (not kidding)."},
        {"type": "meeting", "date": _past(8), "summary": "Revision 4 review. Almost final — just need to resolve the gift-wrapping room placement. Scott suggested converting the back entry closet."},
    ],
    "Bill & Nancy Crawford": [
        {"type": "call", "date": _past(12), "summary": "Materials pricing review. Detailed quote at $1.95M for 4200 sqft full log. Bill reviewing line items. Nancy asked about garden-access doors from the kitchen.",
         "questions_detected": '["Can we add French doors from the kitchen to the garden?", "What is the lead time on custom door orders?"]'},
        {"type": "email", "date": _past(3), "summary": "Bill had his contractor review the pricing. Minor questions about foundation allowance. Expects to sign within 2 weeks."},
    ],
    "James & Olivia Park": [
        {"type": "meeting", "date": _past(7), "summary": "Weekly Zoom check-in. First load of materials (foundation package + floor system) shipping April 20. Builder has site prep complete. Discussed delivery logistics and crane schedule."},
    ],
}

# Followups — mix of overdue, today, this week, future
FOLLOWUPS = {
    "Mark & Sarah Hendricks": [
        {"due_date": _past(1), "reason": "Initial follow-up — qualify on budget and timeline", "action_type": "call", "status": "pending"},
    ],
    "Tom Nguyen": [
        {"due_date": _past(15), "reason": "Follow-up from website inquiry — no response to first email", "action_type": "email", "status": "pending"},
    ],
    "Linda Perkins": [
        {"due_date": _future(45), "reason": "90-day check-in — still looking for land", "action_type": "call", "status": "pending"},
    ],
    "Dave & Maria Santos": [
        {"due_date": _today(), "reason": "Property closing this week — check if land secured", "action_type": "call", "status": "pending"},
    ],
    "Jim & Karen Patterson": [
        {"due_date": _today(), "reason": "Follow-up on Timber Ridge floor plan reaction", "action_type": "call", "status": "pending"},
    ],
    "Robert Chen": [
        {"due_date": _future(3), "reason": "Send mountain view lot floor plan options", "action_type": "email", "status": "pending"},
    ],
    "Angela & Paul Moretti": [
        {"due_date": _past(2), "reason": "Check reaction to ballpark estimate", "action_type": "call", "status": "pending"},
    ],
    "Steve Kowalski": [
        {"due_date": _future(60), "reason": "Quarterly check-in — still looking for land", "action_type": "call", "status": "pending"},
    ],
    "Michael & Diana Ross": [
        {"due_date": _future(5), "reason": "Timeline follow-up — wants to break ground fall 2027", "action_type": "call", "status": "pending"},
    ],
    "Jennifer Walsh": [
        {"due_date": _future(2), "reason": "Check if financial advisor approved the budget", "action_type": "email", "status": "pending"},
    ],
    "Craig & Beth Anderson": [
        {"due_date": _future(7), "reason": "Send studio skylight options from design team", "action_type": "email", "status": "pending"},
    ],
    "Doug Franklin": [
        {"due_date": _past(3), "reason": "Value engineering follow-up — discuss cost reduction options", "action_type": "call", "status": "pending"},
    ],
    "Richard & Amy Blackwell": [
        {"due_date": _future(4), "reason": "Check on interior design survey from Amy", "action_type": "email", "status": "pending"},
    ],
    "Patricia Nguyen-Howell": [
        {"due_date": _future(6), "reason": "First floor plan draft delivery — April 12", "action_type": "call", "status": "pending"},
    ],
    "George & Ellen Hatch": [
        {"due_date": _future(10), "reason": "DSA follow-up — check if deposit is ready", "action_type": "call", "status": "pending"},
    ],
    "Kevin & Laura Mitchell": [
        {"due_date": _future(4), "reason": "Revision 4 delivery — schedule review call", "action_type": "call", "status": "pending"},
    ],
    "Scott & Heather Price": [
        {"due_date": _future(1), "reason": "Gift-wrapping room placement — confirm final layout", "action_type": "call", "status": "pending"},
    ],
    "Tony Reeves": [
        {"due_date": _future(3), "reason": "Revision 2 feedback — mountain lodge aesthetic", "action_type": "call", "status": "pending"},
    ],
    "Bill & Nancy Crawford": [
        {"due_date": _future(7), "reason": "Materials sign-off — Bill reviewing with contractor", "action_type": "call", "status": "pending"},
    ],
    "James & Olivia Park": [
        {"due_date": _future(14), "reason": "First materials shipment April 20 — confirm logistics", "action_type": "call", "status": "pending"},
    ],
}


def seed():
    conn = init_db()

    # Idempotency check
    existing = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    if existing > 0:
        print(f"Database already has {existing} contacts — skipping seed.")
        conn.close()
        return

    print(f"Seeding {len(PROSPECTS)} prospects...")
    contact_ids = {}

    for p in PROSPECTS:
        contact = create_contact(conn, **p)
        contact_ids[p["name"]] = contact["id"]
        print(f"  + {p['name']} ({p['stage']}, {p['temperature']})")

    print(f"\nSeeding interactions...")
    for name, interactions in INTERACTIONS.items():
        cid = contact_ids.get(name)
        if not cid:
            continue
        for ix in interactions:
            create_interaction(conn, contact_id=cid, **ix)
        print(f"  + {name}: {len(interactions)} interactions")

    print(f"\nSeeding followups...")
    for name, followups in FOLLOWUPS.items():
        cid = contact_ids.get(name)
        if not cid:
            continue
        for fu in followups:
            create_followup(conn, contact_id=cid, **fu)
        print(f"  + {name}: {len(followups)} followups")

    total = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    interactions_count = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    followups_count = conn.execute("SELECT COUNT(*) FROM followups").fetchone()[0]
    print(f"\nDone: {total} contacts, {interactions_count} interactions, {followups_count} followups")
    conn.close()


if __name__ == "__main__":
    seed()
