# Other Notes

## JumpFly (Vendor)
- External agency managing paid search and SEO for Golden Eagle.
- Paid search division: managing ~5,500 keywords on Google.
- SEO division: ~3 people working on organic search for ~1.5 years; provide content recommendations and SEO reports.
- Provide Google Analytics reporting to Sean and Jay.
- Also use phone number tracking for ad attribution.
- Golden Eagle website was fully rebuilt ~2 years ago; lost organic search performance and has not recovered to previous levels.

## Juan (Wang/Wong)
- Anna's father; introduced the consulting team to Golden Eagle.
- Has had prior calls with Jay and Tammy about AI in marketing and sales.
- At his own company, mandated Claude usage for all employees ~3 months ago (purchased licenses for everyone).
- Also instituted a rule that all meetings he or his team attend are recorded (transcript cut off mid-sentence before full detail was given).
- Suggested to Tammy that Golden Eagle consider similar mandatory AI adoption; unclear if Tammy had shared this with the broader team before the call.
- Invoicing Golden Eagle through his company **The Automatic Office**.

### Video-to-Transcript Screenshot Extraction Tool (Jupyter Notebook)
- Juan built a Jupyter notebook tool that automates extraction of full meeting context from a recorded video + transcript:
  1. Takes a video file and its transcript (with speaker-change timestamps).
  2. Walks the video frame by frame; detects screen changes within each speaker segment and takes a screenshot at each change.
  3. For each screenshot: saves the image, generates a JSON description of the screenshot content (via Claude vision), and pairs it with the corresponding transcript segment.
  4. Output per timestamp: screenshot file + JSON description + transcript excerpt — all linked.
  5. The combined output is then passed to Claude with a targeted instruction (e.g., "extract all process and system design information") to synthesize findings.
- Used on a 2-hour requirements meeting with Tammy; extracted structured design/process information in a fraction of the manual time.
- Anna plans to **dog food this tool** for her upcoming Golden Eagle sales leader interviews (6 calls this week with sales leaders, Jay, Tammy, and Sean). She will capture video on her computer, extract audio, run transcription, then pass through the notebook pipeline. Output will feed into her meeting intelligence dashboard.
- Juan will share the notebook with Anna via WhatsApp.
- Anna is considering handling the extraction step herself to control what Daniel sees from the dog-fooded output.

## Easy Track — Lead Generation Pipeline (Internal Project)
- A lead generation pipeline has been built and deployed (on Fly.io, with password protection).
- Flow: enter a query (e.g., company type + location + desired result count) → pulls company list and domains → scrapes phone numbers from websites → uses **Hunter** (currently, swapped from Apollo) to find people, titles, and emails → human review via Higou/LinkedIn profiles → load into an email sequencer.
- **Apollo** was the original data provider but its free tier does not allow programmatic search; Apollo paid tier is ~$60/month.
- **Hunter** is currently being used for development/demo purposes; acknowledged as a tier below Apollo in data quality.
- Plan: switch to Apollo before going into production.
- Email verification layer (API-based) to be added before production to reduce bounce rates.
- **Decision: Easy Track work is tabled for the next few weeks** while the team focuses on the Golden Eagle engagement.

## Sprint / Internal Operations Notes
- Sprint 1 follow-ups: ~2 hours of work remaining; responding to prior outreach contacts, some of whom may convert to clients. Framing: "we are embedding in two companies doing a three-feature AI implementation."
- Accelerate: reporter visiting for a week; team is scheduling interviews and connections for them. Demo night that week is considered high priority.
- Retrospective and sprint planning (Sprint 2) was deferred from last weekend; to be completed as soon as bandwidth allows.
- **Communication norms flagged**: Both partners acknowledged a pattern of unclear scheduling and unmet commitments over the prior weekend and week. Agreed action: be highly explicit about availability windows and desired meeting times rather than leaving plans ambiguous. If a commitment needs to move, state the specific alternative time slot explicitly.
- Both Ana and Daniel have upgraded to paid Whisper (ran out of free words/tier).
- Daniel upgraded to Whisper Premium specifically because he exhausted his word allotment on the free tier.

## Internal Tooling — Meeting Intelligence Dashboard (Ana's Build)
- Ana has built a working GUI-based meeting intelligence dashboard. It processes call transcripts, identifies which project files need updating, and applies changes using a find-and-replace (old value / new value) mechanism — the same approach Claude uses internally when editing codebases (based on Claude's leaked implementation).
- The dashboard holds all calls to date, all project files, and per-person and per-organization content. Every time a new transcript is dropped in, it figures out which files to update and applies changes.
- An AI chat interface is being added so the user can query across all sales calls (e.g., "what's the key thing across all calls?").
- The file-update pipeline uses an index file with pointers to all other files; for large corpora, RAG / vector indices would be the next architectural step.
- Front-end decision: Ana chose **vanilla HTML, JavaScript, and CSS** over React. Rationale: no layers of abstraction, battle-proven, works reliably — important for an enterprise-ready system.
- An **auto-generated email template** feature is built: whenever a call finishes in the system, a follow-up email is auto-generated and queued. Sending is handled by a backend worker cycling through jobs. The email content is fully editable.
- Ana's prompt engineering time on the email template was minimal — the output quality came largely from the underlying model.
- Ana also set up game-audio sound cues (e.g., Warcraft-style "ready" sounds) triggered by Claude when it completes a task or needs user input — different completion types trigger different intensity sounds, implemented via a trigger script.

## Internal Tooling — Demo Annotation Tool (Daniel's Build)
- Daniel built a `/annotate` Claude skill for HTML demo files. When invoked, it opens the HTML file with a clickable overlay so the user can click on UI elements and leave feedback. The tool generates a Markdown file recording which element was clicked and what feedback was given — making it easier to give precise, location-aware feedback to Claude without typing out descriptions.
- This mirrors functionality recently released by Replit (or a similar platform) with additional drawing capabilities.
- **Next step**: Ana will add a proper backend to the annotation tool so it can be used when sending demos to clients for feedback.

## Next Build Priorities (Discussed This Session)
- **Channel integration**: The four communication input channels are: (1) phone calls — via Elevate; (2) video calls — via Teams; (3) SMS/text — via Elevate; (4) email — possibly on custom IMAP/own email servers. Daniel will investigate Golden Eagle's phone system and send an email to Sean to clarify what they have.
- Current baseline workarounds if integrations are not immediately feasible: copy-paste transcripts/emails into the system, or forward emails/texts to a system inbox.
- **Elevate softphone route confirmed (April 8)**: Elevate has a PC app that allows reps to make and receive calls via headset without a physical desk phone. If sales/service reps use this, system audio capture of phone calls becomes viable. Not all staff will adopt headsets; old-school reps prefer physical phones. Sales and service teams are the primary target.
- **Customer follow-up email feature added to scope (April 8)**: The post-call output should include a draft personalized email to the *customer* (not just the rep) recapping key conversation highlights — written in the rep's voice. This addresses a real, documented problem at Golden Eagle where generic copy-paste emails have cost the company sales. Framed internally as sending the customer "key takeaways" from the call.
- **CRM endpoints / auto-suggestions**: In parallel with channel integration, Daniel will begin building endpoints to connect with the CRM — e.g., auto-suggested reminders ("this is your first call with a client, do you want to set a reminder for one week?") that the rep can approve with one click.
- **Claude Office integration**: Ana and Daniel discussed whether the first deliverable should actually be training Golden Eagle staff on Claude's native Office/workflow integrations (pulling data from email, files, etc.) rather than building a full custom UI. Decision deferred — Ana will talk to Sean to get his input before presenting options to the executive team. The executive team should not be involved in this technical decision.
- **Memory/fine-tuning layer**: The system will need a background logic layer (similar to Claude's memory file) that learns company-specific context over time to improve output accuracy.
- **On-prem data risk**: Flagged as a potential implementation risk — anything stored on Golden Eagle's on-prem servers will be harder to access than cloud-hosted data. Cloud assets (O365 email, Teams recordings) are straightforward to extract via connectors. On-prem systems may require Sean to extract data or build a network connection.
- **Historical CRM data**: Identified as useful (not critical) to ingest at some point — would be a one-time migration. Juan (Ana's father) has done large-scale migrations and may handle this. Daniel noted that his dad (a Golden Eagle stakeholder) will not do business unless the CRM data is in the cloud in his S3 buckets, so cloud migration may happen regardless.
