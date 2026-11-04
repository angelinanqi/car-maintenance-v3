# Roadie recovery — 4 November 2026

The core single-question flows improved materially. The system is running with
the recovered code and a freshly built admin app. This is not a claim that every
answer is correct: spatial descriptions and some multi-turn numerical answers
remain unreliable. Use the demonstration sequence below and inspect originals.

## What actually failed

1. **Evidence was retrieved, then crowded out.** Oil-check instructions, the oil
   gauge illustration and the engine layout existed in the indexed Alza manual.
   The original reference selector promoted every table above images regardless
   of relevance. Unrelated schedules and warranty tables filled the eight-reference
   shortlist. Reference/page metadata and table packages were packed before prose,
   sometimes leaving no oil-check instructions in the final model context.
2. **Visual ranking lost useful section names.** Generated image descriptions
   reduced an engine-oil illustration to “Oil Level Gauge”. The cross encoder
   preferred transmission-fluid images. Restoring section names as search hints
   improved this ranking without treating those headings as image evidence.
   Reviewed image identities still retain their own search representation.
3. **A second visual limit hid useful originals.** Eight shortlisted attachments
   shared only three illustration page inputs. Lower-ranked useful originals could
   be described to the writer without their actual pixels. All shortlisted
   illustrations now fit the same bounded shortlist; tables retain separate limits.
4. **Table packing favoured later candidates accidentally.** An equal allocation
   across all tables could be smaller than the first, most relevant table's
   minimum source/header wrapper. It was omitted; later tables inherited unused
   space. Tables now pack in relevance order after protected prose.
5. **Validation confused presentation errors with missing evidence.** A duplicate
   inline citation, an incorrect block-basis field, or an omitted duplicate page
   citation could discard useful independent content. These cases now retain only
   independently valid content. Exact bound original pages can complete table
   provenance when actually supplied and the model marks table context sufficient.
   Unknown citations, absent/unrelated pages, insufficient table context and
   unsupported values are still rejected. General blocks never acquire source
   authority from accidental citation arrays.
6. **Retrieval queries included output-format noise.** Words such as “video”
   could promote a generic resource guide over the requested maintenance task.
   The interpretation call now separates the technical search from presentation.
   Ambiguous fluid requests can clarify before a broad reservoir search.
7. **The writer did not know video availability.** Eligible video candidates are now
   supplied explicitly, and the writer selects up to two external links. The
   subsequent video recovery below removes the transcript requirement.
   Missing-video notices also follow the actual user request,
   rather than a model-generated flag that incorrectly marked picture requests.
8. **The running system was stale.** Services started at 01:33, while generation
   files were edited after 02:10–02:22. The served admin build also predated the
   existing catalogue-test UI. Both source and build are now loaded through the
   normal single-instance launcher.

The embedding model, collection, database schema, provider/model, original
documents and application integrations were retained. There was no bulk rebuild,
new paid dependency, new model, or manually submitted processing job. Existing
queued processing resumes through the application's normal workers.

## Evidence and verification

Local artifacts are under `output/recovery/` (ignored by Git):

| Artifact | Purpose |
| --- | --- |
| `baseline-20261104/evaluation/` | 30-question baseline using the original on-disk pipeline |
| `baseline-20261104/oil-live.json` | Failure reproduced against the original running service |
| `baseline-20261104/retrieval-audit.json` | Retrieved prose/media and reranking comparisons |
| `baseline-20261104/visual-rerank-ablation.json` | Search-hint ranking comparison |
| `baseline-20261104/video-inventory.json` | Prepared video inventory |
| `verified-release/` | Same 30 questions on the frozen recovery source |
| `comparison.json` | Objective before/after counts; not an accuracy score |
| `heldout-evaluation/` | Eight unseen questions; includes failures, not just successes |
| `clarification-verification/` | Targeted ambiguity checks |
| `safety-verification/` | Starting symptoms and Malay overheating checks |
| `myvi-evaluation/` | Three questions against the separate Myvi 2021 manuals |
| `verified-conversations/` | Actual sequential conversation turns, including unresolved failures |
| `focused-tests.log` | 39 focused tests passed |
| `archived-regressions.log` | 89 compatible archived checks passed |
| `js-regressions.log` | Seven archived JavaScript checks passed |
| `web-build.log` | Production admin build passed |
| `backend-integration.json` | Real table-source resolution, page bytes and saved-chat restore |

Each live evaluation case retains the input, model-call text, actual source/image
labels, response and trace. Release manifests record source hashes and model
settings. Traces contain source excerpts; keep them local.

Both 30-case runs completed without service errors. Median pipeline time was
5.993 s before and 5.598 s after. These are in-process pipeline measurements,
not complete browser/mobile latency. Model warm-up and database/source resolution
add time; this was not a controlled performance benchmark or an accuracy score.

For the oil-picture case specifically, supplied prose sources increased from
**zero to five**, while image inputs decreased from **16 to eight**. The wrong
transmission-fluid attachment was replaced with the actual oil-gauge and engine-
layout originals. All six explicit/implicit video-request cases in the frozen
set received a missing-video notice. All rendered citation IDs in that set were
present in the returned source metadata; that check does not prove entailment.

Concrete before/after examples:

| Question/capability | Baseline | Frozen release |
| --- | --- | --- |
| Informal oil-check picture request | General answer, no cited evidence, unrelated fluid image; original live service refused | Manual steps with oil-gauge and engine-layout images and citations |
| Oil-check question in Malay | Generic advice, no image, asked again whether a picture was wanted | Initially Malay manual steps and actual oil-gauge illustration; subsequent English-only correction verified English answers with originals |
| Alza cold tyre pressure and original table | Exact answer withheld because original-page citation was missing | Standard 185/55R15: 230 kPa / 33 psi; compact spare distinguished; original tables returned |
| Video requests | No videos; some requests ignored, one answer claimed videos could not be provided | Honest no-matching-video notice plus supported text/illustrations |
| Vehicle conflict | Asked for model, year, engine and variant generically | Names the selected Alza 2018 and asks whether another vehicle was intended |
| Active Malay overheating | Generic emergency answer after model calls | Immediate overheating fallback including the hot-cap warning |
| Vague fluid/fear question | Broad fluid advice, sometimes treated a feared action as completed | Focused clarification before instructions |

Manual inspection also covered the original engine-layout image and tyre table.
The second-vehicle check retrieved Myvi-specific instructions (including its
different oil-check waiting condition), rather than substituting the Alza steps.

The authenticated Safari admin flow was exercised through its real backend.
The oil-check answer displayed the actual oil-gauge original from page 185 and
its source citations. A second browser question displayed tyre-check guidance,
learning-guide/manual citations and the real tyre-label illustration. The exact
pressure/table question was additionally run through the actual backend service,
using the already signed-in administrator's catalogue context, followed by real
source ownership/revision checks: two table attachments, the shared original
page 230 returned HTTP 200 image bytes, and saved-chat restore returned both
messages. This service-level check is distinct from browser authentication;
original table rendering was not directly exercised on the phone.
Android rendering was inspected in code but not exercised on a device: Flutter
and ADB were not available in this shell. No mobile source changes were needed
for these recovery changes.

Archived-suite qualifications: a road-safety import class lacks its original HTML
fixture. Two old automatic-attachment expectations also fail against the saved
baseline. A third old assertion requires a redundant explicit page citation;
the recovery intentionally replaces that behaviour with exact supplied-page
provenance completion, covered by new tests. These were excluded explicitly from
the 89 compatible checks; the original failures were not hidden or rewritten.

## Remaining limitations

- Video content, compatibility and spoken language are not verified by a title or
  transcript match. Relevant external-link recommendations now work with both
  configured channels (see subsequent verification below). Missing exact-model
  tutorials still receive an honest fallback; restricted repairs remain excluded.
- Initial engine-bay left/right/driver/passenger wording varied across repeated
  answers. The subsequent answer-quality change withholds generated side claims
  and uses labelled originals. This does not establish every other location claim.
- Initial multi-turn pressure checks over-refused or mixed a supported value with
  an unnecessary withheld-value notice. The subsequent answer-quality recovery
  returned useful overinflation guidance in two final runs, with unit-conditional
  pressure answers. This remains model-mediated, rather than universally solved.
- Educational airbag explanations now work in final checks; procedural and mixed
  repair requests remain restricted. See the narrow safety change below.
- Long schedules, variant-specific specifications and unsupported configurations
  need careful original-page review. Source citations are provenance, not a full
  logical proof of every sentence. No claim of perfect entailment is made.
- The chatbot cannot inspect the present condition of the user's car. Some
  answers explain checks without explicitly restating that limitation.
- Existing background document work and network/database calls can affect
  latency. Keep one launcher running and let models warm up before presenting.

## Practical demonstration

Allow roughly 6–8 minutes, with time for source loading. Use a published catalogue
vehicle in admin, or the matching active vehicle on the already-installed phone.
Do not claim the phone has been verified by this recovery run.

1. Start with **Perodua Alza 2018** and a new conversation. Ask:
   “engine oil check where ah? i dunno which one. can show pic?”
   Explain the manual steps, then enlarge the actual oil-gauge/engine-layout
   original and inspect its source. This demonstrates retrieval and visual evidence.
2. Ask a complete specification question in a fresh conversation:
   “What cold tyre pressure should I use for my Alza 2018? Show the original table.”
   Show the standard-tyre row, its units and the separate compact-spare row.
3. Ask “How do I replace windscreen wiper blades? Got a general video I can watch?”
   Show the Alza manual explanation and the labelled ChrisFix external tutorials.
   Explain that a general tutorial does not establish model-specific compatibility.
4. In a general conversation with no conflicting selected vehicle, ask:
   “Can you show me a video of an engine oil change on a Proton Persona 1.6 auto?”
   Show the matching Karworx Auto link. Its missing transcript does not prevent
   a recommendation. Answers and labels are English; original video titles remain
   as published. A Persona request in an Alza-selected chat correctly clarifies.
5. Demonstrate a safety boundary: an explicit current overheating report produces
   immediate stop/safe-assistance/hot-cap guidance. Label it as a hypothetical
   demonstration; the system should not be presented as an emergency-service substitute.
6. If time permits, demonstrate a clarification: “my dad say check water in car,
   which water?” or a named vehicle that conflicts with the selected one.

Keep original documents ready as a fallback. If an exact value is withheld, show
the original and acknowledge the limitation. Do not repeatedly retry until a
favourable response appears or present earlier cached results as fresh success.
Avoid using open-ended multi-turn numerical reasoning, unindexed videos or
generated left/right geometry as evidence of a capability that is fully solved.

## Rollback and operation

`output/recovery/baseline-20261104/` preserves the original Git HEAD, working-tree
patch, relevant untracked source files, scope, and previous `.next` production
build. This preserves the user's pre-existing uncommitted work.

`output/recovery/recovery-only.patch` contains only this recovery's source changes.
Its reverse application is checked before delivery. To roll back, stop the normal
launcher, apply that patch in reverse, restore/rebuild the matching admin build,
then use `./start-app.command`. Do not reset the whole repository to HEAD, delete
`output/`, clear Chroma, or run a second overlapping launcher.

The current launcher PID is recorded in `output/recovery/launcher.json`; its
console is `output/logs/recovery-launcher-console.log`. Wait for full graceful
shutdown and release of the launcher lock before starting again. Listening ports
can close briefly before that lock is released.

## Subsequent video recovery and English-only correction

The user confirmed that videos should be clearly labelled external recommendations
and that chatbot output is English-only. This supersedes the initial video and
multilingual-output limitations above.

The investigation found five specific blockers:

- Ingestion deliberately indexed titles/descriptions when captions failed, while
  selection discarded every one of those records. Transcripts are now optional.
- Literal matching compared an internal code such as `perodua-alza-2018` with a
  human-written video title. Compatibility is now assessed by the existing answer
  writer against the actual request and selected vehicle, without that slug test.
- The five-chunk retrieval limit could be occupied by repeated chunks from one
  video. Retrieval now overfetches 40 chunks for the usual five-result setting,
  deduplicates and supplies at most eight eligible video candidates; the writer
  can select at most two. The similarity threshold was retained.
- A manual search rewrite added the selected car to explicitly general tutorial
  requests. In the measured wiper example this reduced the relevant ChrisFix
  video's similarity from 0.847 to 0.661, below the existing 0.75 threshold.
  Video discovery now uses the resolved request; manual retrieval keeps its
  technical query. This adds an embedding when the two queries differ, not an
  additional generation call.
- The writer lacked creator metadata and confused unverified content with
  unavailable links. Cached channel discovery metadata now supplies creator
  names without an API request or reindex. Instructions explicitly distinguish
  selected external links from factual evidence and unavailable media.

Video candidates never enter the factual source list. Their IDs can select links
but cannot validate claims or specifications. The existing generation call selects
links using titles, descriptions, creator names and the actual vehicle/task.
Unknown IDs, excessive recommendations and injection-marked records are rejected.
Metadata-only links receive no timestamp. Both web and mobile display an external
video label and state that content and vehicle compatibility have not been verified.
The app also restores saved recommendations while their channel or scoped guide
remains eligible, rather than clearing every video when a conversation is reopened.

Both generation and clarification instructions now require English, including when
the input is another language. Informal English remains supported. This does not
assert that every recommended video's narration is English.

The new ChrisFix channel was already ready: 418 discovered videos, of which 391
were metadata-only. The prepared collection contained 571 distinct videos / 938
chunks across Karworx Auto, ChrisFix and one embedded guide video. No bulk indexing,
transcript fetching or new paid dependency was needed for this fix.

Verification artifacts under `output/recovery/video-fix/`:

- `iteration-1/`: first live run, preserving contradictory availability notices and
  missed generic/creator matches. These failed behaviours were corrected before release.
- `evaluation/`: subsequent 14 actual pipeline cases, with prompts, real model replies,
  retrieval results and diagnostics. Six positive cases returned relevant links:
  Persona oil change; Kelisa park-light replacement; ChrisFix wipers; ChrisFix air
  filter; Alza manual plus general wiper tutorials; and a wiper follow-up.
- `checks.json`: all 14 cases completed without service errors; expected link
  availability, real indexed video IDs, two-link cap and no contradictory
  missing-video notices in positive cases. Wrong selected vehicle, text-only,
  restricted brake-fluid work and an unavailable e.MAS-specific tutorial returned
  no videos. Oil illustrations and the Alza pressure table still appeared.
  English answers and clarification were inspected for the non-English inputs.
- `unit-tests.log`: 54 focused backend/RAG checks passed, including new metadata-only,
  citation-boundary, failure, timestamp and saved-link eligibility regressions.
- `archived-tests.log`: 42 guide-indexing, saved-cost and content-media checks passed.
- `js-tests.log`: seven existing JavaScript checks passed.
- `web-build.log`: production web build passed. Flutter/Dart are unavailable here;
  mobile labels were updated in source but not executed on Android.
- `backend-roundtrip.json`: a new admin catalogue chat called the running private
  RAG HTTP service and live Gemini, returned the ChrisFix wiper link, saved the
  answer to the database and reopened it with the same video metadata and labels.
  Backend, RAG and web checks all returned HTTP 200. This checks the real backend
  service and persistence path; it is not an Android or new browser interaction test.
- `runtime-manifest.json`: final source hashes. The 14-case batch preceded the
  additive `channel_id` response field and saved-link restoration patch; those
  final changes were checked by the backend round trip and focused tests.

Selection remains model-mediated; these cases do not establish universal accuracy.
Titles/descriptions may be misleading, and the system has not watched or verified
these tutorials. Exact compatibility and factual instructions must still come from
appropriate manuals or reviewed guidance. The previous spatial and multi-turn
numeric limitations remain.

For rollback of only this follow-up, `output/recovery/video-fix/video-fix-only.patch`
reverses the video/English changes while preserving the earlier recovery and the
user's preexisting edits. `before/` also preserves those source files and the prior
web build. Stop the launcher before changing source/build, then restart normally.
The overall `output/recovery/recovery-only.patch` is updated to include this follow-up.

## Answer clarity, section placement and follow-up recovery

This follow-up implements the approved plan for a friendlier English assistant,
validated picture placement, fewer unnecessary refusals and more useful follow-ups.
It supersedes the earlier statement that educational airbag questions always refuse.

### Implemented changes

- Writing instructions now favour a direct answer, simple explanations of technical
  terms, brief headings for substantial sections, bullets for parallel points and
  numbered procedure steps. Short answers need no fixed template. The existing
  Markdown renderers handle these formats; there is no generated HTML or arbitrary
  model-written image URL.
- The writer's existing blocks now have optional display placements. Validated
  blocks become `answer_sections`, each containing its final rendered text and
  selected V attachment labels. The complete `answer` string is retained for old
  clients, old conversations and fallback rendering. This is additive JSON in the
  existing response/persistence path, not a database migration.
- Placement is checked after generation, after backend attachment authorisation and
  on saved-chat restore. The sections must reproduce the complete answer exactly.
  Unknown, unselected, unavailable and duplicate references cannot load extra media.
  Unplaced originals remain available below the answer; withdrawn pictures do not
  remove historical text. Both web and mobile render originals beside sections.
- General explanations and exact specifications are encouraged in separate blocks.
  Independently valid blocks survive rejected claims. Fallback wording identifies
  the affected values/table conditions instead of claiming the whole answer is
  unverifiable. Unspecified pump units are answered conditionally rather than
  assuming that a displayed number is in kPa.
- Live testing showed that instructions alone did not reliably prevent mixed
  general/specification blocks or citation-field mistakes. There is now at most
  one corrective generation for recoverable validation failures. It uses the same
  supplied evidence and specific machine feedback, then passes the same validators.
  It does not receive the failed answer as factual evidence. For a non-specification
  numerical/table correction, the schema also requests general prose without digits
  or measured targets; the normal numeric checks remain in force. The application
  never deletes a number from a rejected sentence and assumes the rest is valid.
  A failed/unavailable correction retains the valid partial answer or honest fallback.
  This can add one existing-provider call and noticeable latency on difficult turns.
- Negated repair warnings were being counted as repair requests at two stages.
  A narrow check now permits a definition combined with explicit reasons NOT to
  repair, such as the airbag example. The writer schema omits a repair-refusal
  outcome only for that narrow educational case after deterministic risk checks.
  Procedural requests and definitions combined with removal/repair requests remain
  restricted. This does not broadly trust model risk labels.
- Generated engine-bay left/right or driver/passenger directions are withheld.
  The writer should identify the printed component label in the supplied original.
  Independent checking instructions remain available; a guessed direction is not
  replaced by another guess.

### Verification and qualifications

All artifacts are local under `output/recovery/answer-quality/`:

- `before/`: source snapshot and previous production web build; existing user edits
  are preserved. The saved baseline modules were loaded in a separate Python
  process without overwriting working files or the running application.
- `baseline/`: eight real pre-change cases on the same saved public scope. The
  airbag education question was restricted; the overinflation follow-up gave only
  an explanation plus a withheld-value notice. There were no section placements.
- `live/` and `verified/`: two initial 20-case runs retained for audit, including
  failed layout, citation and follow-up attempts. These are not presented as passes.
- `release/`: a subsequent 20-case run completed without service errors. It returned
  section layouts, headings/lists, relevant originals, the educational airbag answer,
  the existing video integration and emergency/restricted boundaries. Broad
  dashboard questions still retrieved a partial selection rather than a full
  dashboard-symbol catalogue. One overinflation answer remained partial after its
  correction; the final follow-up change below addressed that failure.
- `final-followups/`: nine cases on the final writing/correction source, including
  sequential pressure and fluid clarification conversations, oil picture placement,
  airbag education and both procedural/mixed repair controls. They completed without
  service errors. The pressure-unit question was conditional on kPa; overinflation
  returned a practical gauge/release/recheck procedure without an unverified target.
- `repeat-pressure/`: another real three-turn conversation on the final source
  again returned a unit-conditional pressure answer and useful overinflation steps.
  One turn took 31.476 seconds. `comparison.json` records layout/status checks and
  timings; these are not accuracy scores or complete browser latency measurements.
- `tests.log`: 73 focused checks passed, including schema compatibility, validated
  sections, source withdrawal, save/restore, guessed-direction withholding and
  correction success/failure/limit checks.
- `archived-tests.log`: 42 existing guide-indexing, saved-cost and content-media
  checks passed. `js-tests.log`: ten checks passed (three placement regressions and
  seven existing checks). `web-build.log`: production web build passed.
- `backend-roundtrip.json`: a real new admin catalogue chat used the running private
  RAG HTTP service/live model, placed an oil diagram before later instructions,
  fetched authorised image bytes (HTTP 200, image/jpeg), saved and reopened the
  identical section layout. Backend, RAG and web health checks all returned 200.
- Browser smoke test: Safari's real authenticated catalogue UI restored old chat
  history, then generated a fresh oil-check answer with formatted steps and the
  original oil-gauge image on page 185. A screenshot and accessibility inspection
  confirmed the rendered reply/card. Arbitrary typing/scrolling remained unreliable
  in the UI automation (`noWindowsAvailable`), so exact mid-answer placement is
  verified by the backend round trip and renderer tests rather than claimed as a
  complete browser interaction test. Flutter/Dart remain unavailable; mobile source
  was updated but an Android build/device run was not performed.

Picture selection and prose remain model-mediated. A diagram may still appear at
its section's end rather than the best possible point, and broad dashboard coverage,
claim entailment, source completeness and numerical follow-ups are not universally
solved. Final checks validate the observed behaviours, not a general accuracy score.
Keep original manuals ready and avoid claiming the app has inspected a car's live
condition. The conditional correction improves resilience but can increase latency.

For a demonstration, use a fresh Alza conversation and ask: “Where is the engine
oil dipstick? Show the relevant diagram beside the explanation, then explain how
to check the oil level in simple English.” Then use a focused red/blue temperature
symbol question and the verified ChrisFix wiper-video request. The broad request
for every dashboard light should not be presented as exhaustive coverage.

`answer-quality-only.patch` reverses only this follow-up. The complete
`output/recovery/recovery-only.patch` also includes these changes. Stop the normal
launcher before changing source/build; restore the matching saved build or rebuild,
then restart normally. No reset of the user's working tree or index is needed.

## Fresh evaluation after answer-quality recovery

A new frozen-code round using current published scopes is recorded in
`output/recovery/evaluation-round-2/report.md`. Thirty primary cases received manual
rubric grades of **25 pass, four partial, one fail**. Three separate calls through
the running backend-to-RAG HTTP adapter received **two pass and one partial**.
There were no service errors. These are observed sample grades, not an accuracy
percentage; current scopes differ from earlier frozen runs.

Two concrete regressions need priority fixes:

1. The direction filter treats “not enough electrical power left” as a left/right
   location claim, removing a useful starting-click explanation.
2. Correction recursively repacks already stripped references, losing original
   image/table evidence bindings. A pressure follow-up retained a contradictory
   missing-value note; one actual HTTP table answer omitted its requested values.

Other partial results were weak unsolicited tyre-age video selection, incomplete
broad-dashboard action guidance, and a washer identification block discarded for
missing citations. Oil guides, explicit matching videos, Myvi-specific sources,
focused temperature-light education, clarification, and restricted/emergency
boundaries worked in this sample. The complete failed drafts/traces are preserved.
No application code or index was changed during this evaluation.

## Final recovery pass and release freeze

The final pass repairs the direction-filter false positive and preserves original
raw reference/image inputs across correction. Citation-basis errors can use the
existing single correction; empty blocks do not add calls. Video discovery is
request-driven, transcripts remain optional, and selected link-only delivery uses
one consistent application notice. An original-message clarification backstop
prevents unspecified prospective water fills from becoming guessed washer advice.
Emergency rendering removes internal diagram metadata while retaining instructions.

The same 30 questions and saved published scopes now receive manual grades of
**27 pass, three partial, zero fail**, compared with **25 pass, four partial, one
fail** before this round. Two additional runs of six critical cases receive
**10 pass and two partial**; eight held-out cases receive **six pass, one partial,
one fail**. The failed held-out case misses an indexed Saga alternator video.
Three final running backend-to-RAG HTTP cases all pass. These are sample grades,
not a statistical accuracy score. Primary median/p90 are 5.479/7.939 seconds;
initial warmup reaches 29.264 seconds. No final service errors occurred.

Remaining limitations matter: exact Alza table narration was only complete in one
of three critical runs, although originals remained available; a primary oil
answer lost identification and a warm-up condition; broad dashboard coverage and
some image citations remain incomplete. A Myvi original-only request acquired an
unwanted no-video notice. Failed/partial attempts are retained. No safety/numeric
checks were loosened to improve the grades.

74 focused Python checks, 42 existing content/guide/cost checks and three JavaScript
layout checks passed. The normal launcher restarted and all services returned 200.
A live backend chat saved/restored sections and attachments unchanged and served
two authorised JPEG originals. A real Safari oil question showed a layout image
before numbered steps, then the gauge card. Android execution remains unverified;
Safari native scrolling is unavailable, so full-page visual QA is limited.

The existing reranker was probed on saved excerpts but was not deployed more
broadly because some rankings worsened. No model, index, infrastructure, paid
dependency or retrieval-threshold changes were made in this round.

The full comparison, traced remaining failures and verified demonstration sequence
are in `output/recovery/final-pass/report.md`; per-case manual grades/checks are in
`review.json`, final traces in `release/` and `consistency/`, and earlier attempts
in `evaluation/` and `targeted/`. `before/` preserves this round's rollback source
and matching web build. `final-pass-only.patch` reverses this round;
`output/recovery/recovery-only.patch` preserves the overall recovery rollback.
Stop the normal launcher before rollback. Preserve this version for the demonstration.
