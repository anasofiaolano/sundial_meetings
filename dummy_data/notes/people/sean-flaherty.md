# sean-flaherty

**Role:** IT Manager

## Notes
- **Pending outreach (as of this engagement)**: Ana messaged Sean after the Session 1 training meeting and had not received a response. Daniel had a separate email domain issue (his email domain was flagged/blocked), which is not expected to affect Ana's personal email. Ana plans to follow up via Tammy (ask her to text Sean directly) if she doesn't hear back. Primary topic Ana wants to discuss: Elevate API options for live call capture.

- Wears multiple hats: IT manager, writes website content, writes code, and more. Also handles online marketing, network administration, server management, and builds computers himself. Self-described: "if it takes power or a battery I am in charge of it."
- Works with JumpFly on paid search and SEO; relies on their Google Analytics reports.
- Self-described as not a big believer in analytics; prefers practical results.
- Dream: build an AI agent/bot to automate competitor keyword and SEO analysis, delivering a daily report — reducing manual work and reliance on JumpFly.
- Noted that a lot of historical bot traffic may have inflated past analytics numbers.
- Has been managing Facebook post boosting with Jay for ~1.5 years.
- Has been at Golden Eagle for 21 years; built the custom CRM from scratch starting when he joined. The CRM was built because the off-the-shelf alternative at the time, Act!, only had ~3 custom fields — insufficient to hold the data Golden Eagle needed. The CRM started as a "glorified Rolodex" and grew over time as departments requested new functionality.
- Also built an internal utility site called **EagleVision** (first thing he wrote for the company — a simple punch in/punch out system via web browser that grew into a full internal utilities platform) — contains punch in/punch out, department utilities, and other custom tools.
- The CRM includes a **phonetic/audio comparison name lookup** — if a rep doesn't know how to spell a contact's name, the system will find them phonetically.
- All three systems (CRM, EagleVision, main website) share a single MySQL database and are fully integrated with each other.
- All servers, including the website, are hosted on-premises at Golden Eagle. Infrastructure: redundant fiber connections to the web, fiber-optic networking between buildings, 20-gigabit inter-building connections, 1-gigabit+ per user.
- Owns a **Bee** wearable device for meeting recording/synopsis and action items; showed it to Jay and expressed desire for similar capability for sales calls.
- Expressed interest in phone call integration (capturing caller-ID, date, time via URL string into database) using the Elevate unified communications system's API.
- Previously built a CRM-generated pop-up window that auto-looked up an incoming caller's phone number and displayed who was calling and which rep's customer they were — allowing reps to decide whether to pick up or let it ring to the assigned rep. This feature is no longer active because Golden Eagle switched to the new Elevate phone system and Sean has not yet tied into that API.
- The pop-up system worked by matching the inbound extension and phone number against the contact database and sending a callback acknowledgment to the phone system API (required to prevent re-send loops).
- Has put CRM development on the backburner; the caller ID pop-up feature is a candidate for the consulting team to replicate.
- The call log in the CRM has been used to resolve customer disputes — e.g., a customer claiming a rep never called back when the log shows they did call. Sean noted this protects reps from being unfairly blamed by Jay.
- Confirmed Golden Eagle has decided to stay in the **Microsoft ecosystem** (not Google Docs/Google Workspace).
- Noted that Elevate has a **PC softphone app**: reps can install the app, wear a headset, and make/receive calls without a physical desk phone. Flagged this as a potential route to capture audio directly from the PC (system audio capture).
- Elevate has AI transcription built into its voicemail system (sends transcribed voicemail messages) — but this applies only to voicemail, not live calls. Sean noted the transcription quality is poor/entry-level.
- Confirmed that Elevate SMS (text messaging) is being used and growing — customers text pictures of things they like, reps pull them out of Elevate and store in client files. Noted SMS capability is tied to direct-to-desk extensions.
- Expressed uncertainty about whether Elevate's API allows direct audio capture from live calls — believes the system is relatively closed in that regard.
- Suggested a possible hardware workaround: an in-line device on the phone cord to capture audio (analogous to old-school tape recorder splitters) — acknowledged as low-tech but potentially viable.
- Noted that Golden Eagle recently signed a contract and spent a significant amount on the Elevate phone system (he estimated Jay may have laid out ~$50,000). Switching phone providers for sales calls would require a strong ROI justification — but flagged it as within the realm of possibility if framed correctly (e.g., one additional home sale per year pays for the whole system).
- Estimated that cell phone calls represent less than 20% of total sales call volume — possibly far less — since reps are primarily in-office.
- Describes himself as a "crack-the-whip" type when it comes to process compliance; strong believer that certain system behaviors must be non-optional or staff will ignore them.
- Company has decided to stay in the **Microsoft ecosystem** — not Google Docs/Google Workspace. Teams is the primary meeting platform, though noted that some customers may not be able to connect via Teams (Zoom, etc. may be needed as backup).
- Recounted a real incident where Golden Eagle sales reps sent generic copy-paste follow-up emails to customers; at least one customer explicitly called it out — direct quote: "I'm never buying from somebody who's just going to copy and paste the same crap to me." Jay has since instructed reps to personalize outreach. Sean flagged this as a structural problem the system should solve, not just a training issue.
- Raised a concern about AI accuracy when drawing from historical data: codes change, product lines are added/dropped (e.g., fireplaces), and if the system surfaces outdated information to a salesperson, it could lead to customer misinformation. Customers are highly detail-oriented and will hold Golden Eagle to anything stated. Sean favors human-in-the-loop authorization on outbound content precisely for this reason.
- Described the desired UX principle as "accept, accept, accept" — reps should be able to move through suggested actions with minimal friction, without the system generating more busy work than it saves ("feed the monster" anti-pattern).
- Flagged reading load as a usability concern: pre-meeting briefs or summaries that are too long ("encyclopedia") will be ignored. Brevity is essential for adoption.
- Disclosed personal context behind this preference: he is "horribly color-blind" (works with graphics despite this) and has a self-described reading deficiency — reads English slowly, though reads structured code fast. Used himself as an example of a user who would tune out dense text-heavy outputs, and flagged that other staff will have similar tendencies.
- The CRM's **note immutability** (notes cannot be edited or deleted by reps once saved) was a deliberate design decision by a previous owner — intended as an evidentiary log so that salespeople could not retroactively change or deny what they told a customer. Sean can delete a note at admin level (e.g., to remove an accidental duplicate), but reps cannot.
- The reminder system has existed in the CRM for ~20 years and is still largely unused by reps — Sean cited one recently retired salesperson who had customers who had already moved into their homes still listed as "new lead" in the system.
