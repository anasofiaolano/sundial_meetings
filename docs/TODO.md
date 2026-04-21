- editable template for the notes

- i wanna be able to paste in photos as attachments in notes

- clarify that rerun button.

- the stuff at the top / metadata including the list of attendees, also has to be included when the LLM is queried.

- maybe overview should have the view my dad was showing today.

- don't want content drift. you can still tell AI to include stuff in the overview though.

- will need to explain to them the shift to the overview page.
  - editable
  - pulls in from crm
  - captures the overview of the project / whats happened etc.

- But then does that feel like we would lose the self-updating notes, like those project files that we're
  talking about? Or maybe that's a conversation to have with a team if they don't really use it? Based on your  
  understanding of the CRM, what do you think is the best way to handle this? Do you think that there's a
  risk that this has redundant notes in those that might already be in the CRM?


- will need to train on rep voice

- may wanna give them an editor bar for the ntoes sections

- if call outline not comprehensie in capturing details then i also wanna have like an other notes section. ultimately, maybe they'll personalize the notes they want added.

- more possible suggested actions than just set reminders and update stage? maybe crm stuff. or maybe can suggest more follow up emails to e.g. design team etc if given context.

- CRM should allow to set multiple reminders

- these sourced actions (e.g. setting reminders) will ALSO live in the record page so they could do it from either

- undo / change e.g. setting reminders

- find me where in the meeting we said x -> goes and highlights the section. -> and can it PLAY BACK when you click? like otter

- need fix width of the chatbot box

- dictation for notes will be so good. i want to implement something like a wisprflow for them if they don't wanna pay for it. i can add it in mine.

Monday: https://www.youtube.com/watch?v=Y-ENRhHEwSw

- templates shareable across org
  - rly easy insert templates or generate ton of drafts from a template

- schema backfilling: add a new field, and the system re-analyzes all historical unstructured data to populate it retroactively

- see if can find online information about the people you spoke with and the areas they mentioned (e.g. helpful context we searched)

- sync email and calendar

- currently live call copilot prompt needs refining (e.g. says "only take client questions not sales rep questions - but in reality how will it be able to distinguish?)

- for the live call copilot, going to want a custom words thing so it understands what we're talking about better. e.g. it has a hard time getting "Juan"

- does client_id change to be CTN?

- chat needs things like a resend

- storage
  - run directory?

- strengthen db and conns

- prompt audit

- need date on the comms input or else ai will assume falsely based on upload time

- understand this: see very end

- explain this pop thing?
  98                                                                             
       99 -    # Pop briefing                                                         
          - fields so they don't bloat the main result JSON blob.                     
       99 +    # Pop briefing/email                                                   
          + fields so they don't bloat the main result JSON blob.                     
      100      briefing    = result.pop("briefing",    None)                          
      101      briefing_at = result.pop("briefing_at", None)                          
      102 +    email_html  = result.pop("email_html",  None)                          
      103                                                                             
      104      conn.execute(                                                          
      105 -        "UPDATE jobs SET status='done', completed_at=?, result=?,          
          -briefing=?, briefing_at=? WHERE id=?",                                     
      106 -        (now, json.dumps(result, ensure_ascii=False), briefing,            
          -briefing_at, job_id),                                                      
      105 +        "UPDATE jobs SET status='done', completed_at=?, result=?,          
          +briefing=?, briefing_at=?, email_html=? WHERE id=?",                       
      106 +        (now, json.dumps(result, ensure_ascii=False), briefing,            
          +briefing_at, email_html, job_id),              

- Rethink parent/rerun model — currently run_briefing is a flag passed from worker →
  pipeline based on parent_job_id IS NULL. Clunky because the pipeline shouldn't need
  to be told what kind of job it is from the outside. Better long-term: give jobs a
  job_type column (original / rerun) and let the pipeline (or a dedicated rerun
  pipeline) decide its own behavior based on that. Also consider whether reruns should
   ever regenerate a briefing (e.g. if the focus_hint produced significantly different
   notes).

- fast api refresher - e.g. "serving static files"

- understand dom.js that was created.

- make this general purpose to also accept e.g. memos / stray notes. maybe it should group the input intelligently? maybe separate calls from inputs? but still show the upload date or the date of the meeting? i would like the "show day of meeting" thing.

- reminders should extract / recommend dates
  - So we should also pass them a calendar of stuff?
  - and notes on the usual timings the team prefers, to keep in mind?

- let's train on emails like Espa: an easy way may be to select emails you wanna share, or to copy paste in emails to share, or to forward the emails you wanna share. and there's always an edit your voice tab where you can modify this (but we don't wanna add too many crazy options for them lol)

- a "context" doc that's hidden(?) that has notes about e.g. the user etc. like claude's memory.
  - will be important for, for example, getting names right. tell the side chat that it's spelled Ana, and we'll save it to memory so we don't get it wrong again.

- next up will be accepting/rejecting the changes (just like claude code!)

- and we'll want a token / cost monitor

- the rename thing is buggy sometimes. maybe only when the worker is working on that file actively? or when it's working on a file in general?

- Here's an idea. Instead of passing the full corpus, maybe each thread can also be compacted. It's like, 'Here's the most recent, and here's a compaction of what was in this note before.' It's like every dot could be like many pages, but you're not going to pass everything; you're not going to pass the whole book, just the summary of the book and the most recent bit. Each doc has something that's going to go through everything and decide if anything should be consolidated or is redundant or not, so it's like each doc has its own separate process after that. 



==

GET http://localhost:3003/api/files 404 (Not Found)                                 
fetchFiles @ files.js:5                                                               
loadFiles @ app.js:39                                                                 
init @ app.js:150                                                                     
(anonymous) @ app.js:154Understand this error                                         
calls.js:5  GET http://localhost:3003/api/calls 404 (Not Found)                       
fetchCalls @ calls.js:5                                                               
loadCalls @ app.js:31                                                                 
init @ app.js:150                                                                     
(anonymous) @ app.js:154Understand this error                                         
calls.js:5  GET http://localhost:3003/api/calls 404 (Not Found)                       
fetchCalls @ calls.js:5                                                               
loadCalls @ app.js:31                                                                 
setInterval                                                                           
init @ app.js:151                                                                     
await in init                                                                         
(anonymous) @ app.js:154Understand this error                                         
calls.js:5  GET http://localhost:3003/api/calls 404 (Not Found)                       
fetchCalls @ calls.js:5                                                               
loadCalls @ app.js:31                                                                 
setInterval                                                                           
init @ app.js:151                                                                     
await in init                                                                         
(anonymous) @ app.js:154Understand this error                                         
calls.js:5  GET http://localhost:3003/api/calls 404 (Not Found)                       
fetchCalls @ calls.js:5                                                               
loadCalls @ app.js:31                                                                 
setInterval                                                                           
init @ app.js:151                                                                     
await in init                                                                         
(anonymous) @ app.js:154Understand this error                                         

⏺ The StaticFiles mount at "/" is intercepting /api/calls and /api/files — it looks
  for those as files in the frontend/ folder, finds nothing, returns 404. The API
  routes never get reached.

  Fix: mount at "/static" instead, keep the explicit @app.get("/") for index.html,
  update the two references in index.html.

⏺ Read 1 file (ctrl+o to expand)

⏺ Update(sundial_meetings/backend/server.py)
  ⎿  Added 4 lines, removed 5 lines
      150  with _connect() as conn:
      151      _ensure_table(conn)
      152   
      153 -# Serve the frontend/ directory as static files.                    
      154 -# All /api/* routes are registered first so they take precedence.   
      155 -# This mount handles everything else: /, /css/styles.css,           
          -/js/app.js, etc.                                                    
      156 -# html=True makes it serve index.html for unknown paths (SPA        
          -behaviour).                                                         
      157 -app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), 
          - name="frontend")                                                   
      153 +# Serve the frontend/ directory under /static/.                     
      154 +# Mounting at "/" intercepts /api/* routes even when defined first  
          +— mounting                                                          
      155 +# at "/static" avoids that. index.html is served by the explicit    
          +route below.                                                        
      156 +app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)),      
          +name="frontend")                                                    
      157   
      158   
      159  # -----------------------------------------------------------------
           ----------

⏺ Now restore the explicit @app.get("/") route (which I removed earlier when adding
  the mount):

⏺ Update(sundial_meetings/backend/server.py)
  ⎿  Added 5 lines
      156  app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)),
           name="frontend")
      157   
      158   
      159 +@app.get("/")                                                       
      160 +def index():                                                        
      161 +    return FileResponse(str(FRONTEND_DIR / "index.html"))           
      162 +                                                                    
      163 +                                                                    
      164  # -----------------------------------------------------------------
           ----------
      165  # Core endpoints
      166  # -----------------------------------------------------------------
           ----------

⏺ Now update the two references in index.html:

⏺ Update(sundial_meetings/frontend/index.html)
  ⎿  Added 1 line, removed 1 line
       6    <title>Sundial</title>
       7    <script src="https://cdn.tailwindcss.com"></script>
       8    <script
          src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
       9 -  <link rel="stylesheet" href="/css/styles.css">                     
       9 +  <link rel="stylesheet" href="/static/css/styles.css">              
      10  </head>
      11  <body class="h-screen flex flex-col bg-white text-sm text-gray-800
          overflow-hidden">
      12   

⏺ Update(sundial_meetings/frontend/index.html)
  ⎿  Added 1 line, removed 1 line
      110      <div class="text-lg font-medium text-blue-700">Drop to process
           transcript</div>
      111    </div>
      112   
      113 -  <script type="module" src="/js/app.js"></script>                  
      113 +  <script type="module" src="/static/js/app.js"></script>           
      114  </body>
      115  </html>

⏺ The JS module imports (./state/index.js, ../utils/dom.js etc.) are relative paths so
   they resolve correctly regardless — only the two entry points in index.html needed
  updating. Restart the server and it should work.

