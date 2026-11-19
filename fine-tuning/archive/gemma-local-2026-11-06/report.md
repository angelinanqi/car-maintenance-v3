# Roadie local Gemma 3 4B review

This is an AI-assisted technical review of actual captured application responses, not human researcher labels or a certified automotive assessment.

## Outcome

Reviewed 20 actual RAG answers: **10 Good, 6 Acceptable, 4 Poor**. These ratings apply to the full `release` run, not a cherry-picked mixture of retests.

The full run is preserved as captured. Subsequent targeted fixes and retests are recorded separately below; the 20-case ratings are not rewritten to claim final-code performance.

The model migration works, but the small model still produces incomplete answers and occasional unsupported elaboration. Do not describe the chatbot as fully accurate or production-certified.

## Implementation

- All interactive generation uses configurable Ollama `gemma3:4b`; GeminiClient remains directly available for ingestion descriptions. No cloud fallback is configured.
- 6,144-token local context, 1,024 output tokens, serialized local calls; original image pixels are not sent during chat.
- Existing Nomic embeddings and MiniLM reranking run on CPU after observed Metal out-of-memory failures. Model weights/index format are unchanged.
- Short natural-language grounding prompt and minimal text/source/media envelope replace the oversized instruction list. IDs, values, provenance and safety remain validated.
- Semantic hazards survive route selection; educational exceptions, explicit vehicle conflicts, personal lookups and media exclusions are retained.
- Media is ranked and attached independently of writer placement. Wrong-fluid media and unsupported aftermarket specifications are blocked.
- A professional replacement overview requires retrieved procedural evidence; warnings alone cannot be expanded into invented stages. Internal profile IDs stay in application metadata and are excluded from model prose evidence.
- Optional long-answer review fails back to deterministic validation. One bounded format retry handles truncated repetitive output; no unbounded correction loop.

## Measurements

The full 20-case run took 693.4 seconds in total. Per-case median **39.7 s**, range **0.004–59.4 s** (emergency/clarification fast paths included).

Ollama reported approximately 3.5 GB loaded at 6K context, 20% CPU / 80% GPU. Evaluation Python peak RSS was 0.80 GiB. Whole-system swap before: `total = 15360.00M  used = 14643.06M  free = 716.94M  (encrypted)`; last case: `total = 18432.00M  used = 17666.56M  free = 765.44M  (encrypted)`. These include app/IDE/tests and other processes, not model-only memory. Memory pressure remains a serious limitation.

Answer prompt text in this run was 2,573–7,061 characters versus 28,347–37,221 in saved Gemini development captures. These are character counts, not tokenizer counts.

## Validation scope

The 20-case run calls the actual `handle_query` path with scoped retrieval, reranking, packing, generation and validation. It uses saved published scopes with available local revisions checked, and explicit synthetic personal fixtures. The stale accident-protocol revision was recorded as unavailable. Later weak-case retests use refreshed live scopes where stated. Authenticated account/history/mobile networking was not covered by these standalone captures.

Private HTTP smoke check on the restarted service returned 200 with a natural, correctly cited no-pin washer-nozzle answer in 22.4 s; see [http-check.json](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/http-check.json). Backend, RAG and web services restarted successfully. This is not authenticated mobile end-to-end testing.

Historical Gemini results are untouched. Each local run has a separate manifest, code snapshot, actual prompts, sources, responses and timings. Failed runs and failed retests are retained.

## Results at a glance

| Case | Rating | Seconds | Media |
|---|---|---:|---|
| D01 | Acceptable | 42.1 | 0 originals / 0 videos |
| D02 | Acceptable | 56.5 | 0 originals / 0 videos |
| D03 | Good | 25.0 | 1 originals / 0 videos |
| D06 | Good | 29.4 | 0 originals / 0 videos |
| D07 | Acceptable | 55.9 | 0 originals / 0 videos |
| D08 | Good | 55.1 | 0 originals / 0 videos |
| D11 | Poor | 35.8 | 0 originals / 0 videos |
| D14 | Acceptable | 48.7 | 1 originals / 0 videos |
| D17 | Good | 48.7 | 0 originals / 0 videos |
| D18 | Poor | 48.5 | 0 originals / 0 videos |
| F01 | Poor | 59.4 | 0 originals / 2 videos |
| F04 | Acceptable | 0.0 | 0 originals / 0 videos |
| F05 | Good | 0.0 | 0 originals / 0 videos |
| F06 | Poor | 57.5 | 1 originals / 0 videos |
| F07 | Good | 11.5 | 0 originals / 0 videos |
| F09 | Good | 58.0 | 0 originals / 2 videos |
| F10 | Good | 9.3 | 0 originals / 0 videos |
| F11 | Good | 0.0 | 0 originals / 0 videos |
| L01 | Good | 14.5 | 0 originals / 0 videos |
| L02 | Acceptable | 37.3 | 1 originals / 0 videos |

## Every actual answer and evidence

### D01 — Acceptable

**Question:** I am preparing to refuel my Alza 2018. What does its manual say about the engine, smoking or flames, and carrying a fuel container?

**Actual answer:**

According to your Alza 2018’s owner manual, it's very important to turn off the engine before refueling.  You shouldn’t smoke or use any flames near the fuel filler either. It also states that you must never carry a fuel container in your vehicle – this could cause an explosion or fire. [S1]

The manual also includes warnings about potential hazards when working on the engine, such as sparks or flames. It advises you to keep children away from fluids and to allow the engine to cool before servicing any part of it. [S2]

**Assessment:** Refuelling precautions and portable-container prohibition are supported. Adds unrequested engine-work warnings from another retrieved passage; relevant core but unnecessarily long.

**Supplied evidence:**

- **S1 — alza-2018-owner-manual-eng.pdf**

```text
To prevent a fire when refueling, always turn the engine off. Also, do not smoke or use any flame near the fuel filler.

Never carry any fuel container in your vehicle.

The fuel may leak from the container and may cause an explosion or a fire.

Remote fuel lid release
```

- **S2 — alza-2018-owner-manual-eng.pdf**

```text
If you are not versed in servicing procedures given, do not attempt to check or adjust the components.

Do not allow smoking, sparks or flames near flammable objects, such as fuel or battery, to prevent a fire.

To help reduce the risk of serious bodily injury, remove any necklace, bracelet, ring, and so forth. Secure long hair behind your head. Also, keep hands, tools, clothes, and other objects away from the moving parts when the engine is running.

To help reduce the risk of burn injury, allow the engine to cool before servicing any component in the engine compartment, except when required.

No person should get their body under a vehicle that is supported only by a jack; use vehicle support stands, etc.

• Service your vehicle in a wellventilated place.

• Keep children away from any fluid or oil.

Check that any tool or cloth is not left when closing the hood. They may damage the components or even a fire while driving.

Under no circumstances should the wiring be modified. Failure to follow this caution may cause malfunctioning components or even a fire.

• Use well-maintained tools to prevent bodily injury and damage to the components.
```

- **S3 — alza-2018-owner-manual-eng.pdf**

```text
Preceding text in the same column on PDF page 29 (neighbouring evidence, not an inferred parent section):
UNLEADED FUEL ONLY

CAUTION

Retrieved passage:
A fuel information label is attached on the back of the fuel lid. Fill only the fuel complying with the instruction.
```

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/D01.json)

### D02 — Acceptable

**Question:** I am learning about a manual-transmission Alza 2018. Can its lever go directly from fifth to reverse? What must happen before reverse is selected?

**Actual answer:**

To shift from the 5th gear to the reverse gear, first return the shift lever to neutral, and then to the reverse gear after the vehicle has completely stopped. [S1]

When parking or stopping your vehicle, make sure that there is no combustible objects such as dry grass and oil around and underneath your vehicle. The exhaust pipe may reach an extremely high temperature, and it is possible that nearby combustible objects may be ignited. [S3]

**Assessment:** Correct manual-transmission neutral/full-stop/clutch precautions. Additional combustible-material parking advice is supported but distracts from the gear-change question.

**Supplied evidence:**

- **S1 — alza-2018-owner-manual-eng.pdf**

```text
The shift pattern is shown above.

Depress the clutch pedal fully when shifting. If the gear will not shift easily, release and depress the clutch pedal and try again.

The transmission is so designed that the shift lever cannot be shifted from the 5th gear to the reverse gear directly. To shift from the 5th gear to the reverse gear, first return the shift lever to neutral, and then to the reverse gear after the vehicle has completely stopped.
```

- **S2 — alza-2018-owner-manual-eng.pdf**

```text
• If your vehicle has a flat tyre, pull off the road.

Avoid changing a flat tyre on a slope.

When changing a flat tyre on a road, park the vehicle in a place that will not obstruct traffic, turn on the hazard warning signal lights and put up a safety triangle.

• Move all passengers out of the vehicle to a safe place and unload any heavy luggage from the vehicle.

Make sure the parking brake is applied, and the manual transmission is in 1st or in reverse, or the automatic transmission inH.

In the event of a flat tyre or tyre burst while driving at high speeds, hold the steering tightly. Gently apply the brakes to slow down. Sudden braking may cause a loss of steering control and can be dangerous.

When your vehicle has a flat tyre on the front wheel, be sure to mount the emergency spare tyre on the rear wheel, and then, the removed rear tyre should be mounted to the front wheel.

Chock the tyre, located diagonally opposite to the flat tyre, at the opposite end. This is the most effective location for a chock.

For improved safety, chock front and back of the tyre, if possible.
```

- **S3 — alza-2018-owner-manual-eng.pdf**

```text
When parking or stopping your vehicle, make sure that there is no combustible objects such as dry grass and oil around and underneath your vehicle. The exhaust pipe may reach an extremely high temperature, and it is possible that nearby combustible objects may be ignited.

When you park the vehicle, engage the parking brake fully except when the mechanism could be frozen. Place the manual transmission lever in 1st on the uphill grade or reverse on the downhill grade, or the automatic transmission lever in H.
```

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/D02.json)

### D03 — Good

**Question:** Where does the Alza 2018 manual tell me to look for its tools and jack? I only want their storage location, not lifting instructions.

**Actual answer:**

According to the 2018 Perodua Alza owner’s manual, you can find the tools and jack stored in a tray located at the rear of the vehicle. Specifically, open the back door and raise the deck board. The tray contains the tyre protective sheet, jack, and tool set. [S1] [S2] [S3]

**Assessment:** Correct rear deck-board storage and tray/protective storage details. Original matching storage image is attached; cited passages support the location.

**Supplied evidence:**

- **S1 — alza-2018-owner-manual-eng.pdf**

```text
Open the back door and raise the deck board. Learn the storage location of tools and jack.
```

- **S2 — alza-2018-owner-manual-eng.pdf**

```text
The jack can be installed / removed by turning the worm shaft as shown in the figure above, using the jack handle provided in the tool bag.
```

- **S3 — alza-2018-owner-manual-eng.pdf**

```text
Tools and Jack Storage Location
An outline illustration showing the rear of a vehicle with an open cargo area. A callout box above the rear floor area points to a storage tray containing labeled items: 'Tyre protective sheet', 'Jack', and 'Tool set'. An arrow points upward from the deck board. Text associated on the source page reads 'Open the back door and raise the deck board. Learn the storage location of tools and jack.'
The exact boundary of what the arrow pointing from the deck board encompasses is slightly ambiguous, though it visually indicates lifting the floor panel.
```

**Original attachments:** `[{"kind": "image", "element_id": "image-00249", "document_id": "75da8572-040f-4a48-8af8-cd848916e445", "source_revision": "f628104b-af4a-4241-b0e2-517804c16b2b", "source_fidelity_verified": true, "reference_label": "V1"}]`

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/D03.json)

### D06 — Good

**Question:** My Myvi washer nozzle is blocked. Is using a pin to clear it recommended by its manual?

**Actual answer:**

No, the manual doesn’t recommend using a pin to clear your Myvi washer nozzle. It specifically advises you not to use sharp objects like a pin. [S1]

Instead, if the nozzle is blocked, it says to get in touch with an authorised Perodua Service Centre. They can properly deal with the issue and also warn you that the nozzle might be damaged. [S1]

**Assessment:** Clear no-pin answer and service-centre recommendation, supported by the manual; minor awkward repetition.

**Supplied evidence:**

- **S1 — myvi-2021---current-owner-manual-eng.pdf**

```text
Please contact an authorised Perodua Service Centre if the nozzle is blocked.

Do not try to unblock it using sharp objects, such as a pin.

The nozzle may be damaged.
```

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/D06.json)

### D07 — Acceptable

**Question:** I am new to owning a car. Explain preventive versus corrective maintenance, and which responsibilities I can take on without doing specialised repairs.

**Actual answer:**

Preventive maintenance involves regular checks and services to prevent problems, such as inspecting tires, monitoring warnings, and recording service dates. Corrective maintenance addresses issues after they arise, typically requiring professional repair. You can take on responsibilities like checking tire wear, noting unusual behavior, tracking mileage, and looking for leaks under the bonnet. However, complex repairs should be handled by a qualified mechanic. Refer to your owner’s manual for scheduled maintenance requirements. [S1] [S2] [S3]

**Assessment:** Clear preventive/corrective distinction and owner/professional boundary. Main claims supported; added leak-under-bonnet example is not in the cited passages.

**Supplied evidence:**

- **S1 — Understanding Basic Vehicle Maintenance**

```text
Understand why maintenance matters.

Preventive maintenance checks or services parts before failure; corrective maintenance fixes problems after they occur. Drivers can check tyres, monitor warnings and keep records, while complex repairs belong to professionals.

Diagram reference: Preventive versus corrective maintenance.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Learn the basic checks permitted by the manual.
2. Record service dates and odometer readings.
3. Notice new symptoms and seek inspection early.

Safety precautions: Do not attempt specialised repairs without training.

When to seek professional help: Consult a qualified mechanic for faults or scheduled servicing.

Key takeaway: Maintenance helps prevent avoidable breakdowns.
```

- **S2 — alza-2018-owner-manual-eng.pdf**

```text
We at Perodua want you to enjoy your new vehicle with all its capabilities. We also want you to use common sense as safety and common sense driving go hand in hand.

Part of common sense driving is learning about the capabilities and limitations of a vehicle, and realizing that vehicles designed for different purposes may handle differently. Read and understand all WARNINGS, CAUTIONS and NOTES in this manual.
```

- **S3 — alza-2018-owner-manual-eng.pdf**

```text
1. The scheduled maintenance service is important to ensure trouble-free, safe and economical driving. Failure to perform the scheduled maintenance may cause an accident or serious damage.
2. If periodical maintenance is conducted, Perodua car owners may reduce the chance of accidents or car problems. Furthermore, it becomes possible to detect malfunction at an earlier stage which may lead to serious damages. Consequently, potential vehicle damage can be prevented or the degree of the damage can be minimized.
3. Therefore, all Perodua car owners should be concerned to service their Perodua vehicles according to the periodical maintenance service in order to be protected from accidents or unexpected problems.
4. To prevent malfunctions in advance, however, conducting the periodical maintenance service only is insufficient. It is essential that owners themselves perform maintenance, such as the pre-starting check described in the owner's manual, so that the vehicle exhibits no abnormal change or phenomenon.

Owners should obtain information from service advisor about the necessity of maintenance performed by themselves.
```

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/D07.json)

### D08 — Good

**Question:** My car barely covers any kilometres. Does that let me ignore the calendar part of its service schedule? Explain how I should use the manual and my service records.

**Actual answer:**

If your car barely covers kilometres, you should still follow the calendar part of its service schedule. Both time and distance matter when servicing your Perodua Alza.

Here’s how to use the manual and your service records:

1.  Find the maintenance schedule in the owner’s manual.
2.  Identify the intervals for each service item – these are based on either kilometres or months, whichever comes first.
3.  Record current mileage and last service date.
4.  Compare the records with the schedule.
5. Book service before it becomes overdue.

The owner’s manual states that periodic maintenance should be performed either at the number of kilometers or months, whichever is earlier from the date of first registration. Engine oil changes should be done every 6 months or 10,000 km – whichever comes first. Use Perodua Engine Oil or equivalent to API classification SJ Grade or higher. [S1] [S2]

**Assessment:** Answers the calendar question naturally, preserves time-or-distance rule and practical record steps. The cited Alza maintenance booklet actually supports 6 months/10,000 km and oil grade. More detail than requested, but no guessed universal interval.

**Supplied evidence:**

- **S1 — How to Follow a Vehicle Maintenance Schedule**

```text
Understand when your car needs servicing.

Manufacturers may specify service intervals by months, kilometres or whichever comes first.

Diagram reference: Time and mileage maintenance timeline.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Find the maintenance schedule in the owner’s manual.
2. Identify the intervals for each service item.
3. Record current mileage and last service date.
4. Compare the records with the schedule.
5. Book service before it becomes overdue.

Safety precautions: Do not assume all cars use the same service interval.

When to seek professional help: Ask a service centre when the schedule is unclear.

Key takeaway: Both time and mileage matter.
```

- **S2 — alza-2018-warranty-warranty-booklet.pdf**

```text
This is to certify that the work specified on the maintenance schedule in the Owner's Manual has been completed. Periodic Maintenance Service should be performed either at number of kilometers or months, whichever is earlier from the date of firs registration of the vehicle. All records should be given to any subsequent owner of the vehicle. Engine oil service should be done every 6 months or 10,000 km, whichever is earlier.

(Perodua Engine Oil or equivalent to the requirements of API classification SJ Grade or higher should be used.)
```

- **S3 — alza-2018-owner-manual-eng.pdf**

```text
Follow the mileage and/or the period the vehicle has been driven whichever comes first, if without any notice.

Continue maintenance service after 100,000 km, following the schedule.

NOTE: PERODUA may change the contents without prior notification.

.…Replace .…Inspect (repair/replace if needed)

.…Replace .…Inspect (repair/replace if needed)

.…Replace .…Inspect (repair/replace if needed)
```

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/D08.json)

### D11 — Poor

**Question:** Before the rainy season, how can I check whether my wipers need attention? What signs on the rubber or glass should I look for?

**Actual answer:**

Okay, let’s get your Perodua Alza’s wipers checked before the rain. Here's what you can do:

*   First, park safely and turn off the engine.

*   Then, inspect the rubber edges of the wiper blades for splits, cracks or missing pieces – this is shown in diagram reference: Healthy versus cracked wiper rubber.

*   Spray washer fluid on your windscreen. [S1]

I couldn't confirm one or more exact values in this answer, so those claims have been left out.

**Assessment:** Retrieved evidence is sufficient, but JSON-like garbage leaked into the text and caused validation to remove the key wet-test/streaks advice. The residual value-warning is confusing. Narrow trailing-fragment cleanup and retest follow.

**Supplied evidence:**

- **S1 — How to Check Windscreen Wipers**

```text
Recognise worn wiper blades and test their performance.

Wipers clear rain and dirt. Heavy Malaysian rain makes them especially important.

Diagram reference: Healthy versus cracked wiper rubber.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Park safely and switch off the engine.
2. Inspect rubber edges for splits, cracks and missing pieces.
3. Spray washer fluid on the glass.
4. Operate the wipers and check for streaks or missed areas.

Safety precautions: Avoid running wipers unnecessarily on dry, dirty glass.

When to seek professional help: Replace damaged blades or seek assistance if they fail to clear water.

Key takeaway: Check wipers before the rainy season.
```

- **S2 — How to Check Your Tyre Condition**

```text
Learn how to inspect your tyres for visible damage and signs of wear before driving.

Your tyres are the only parts of your car that normally touch the road. They help you accelerate, turn and stop. Damaged or worn tyres may lose grip, especially in heavy rain.

Diagram reference: Tyre labelled with tread, sidewall, rim, cracks and bulges.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Park on flat ground, switch off the engine and apply the parking brake.
2. Inspect the tread, the patterned rubber that touches the road.
3. Look for cuts, cracks, bulges, exposed cords or embedded nails and screws.
4. Check the sidewall between the tread and wheel rim.
5. Repeat for all four tyres and the spare tyre, if fitted.

Safety precautions: Do not remove an embedded nail or screw. Never drive on a tyre with a bulge or serious damage.

When to seek professional help: Visit a tyre specialist if you notice damage, unusual wear or repeated pressure loss.

Key takeaway: A tyre can look inflated but still be unsafe.

Video: Michelin: How to Check Your Tyres in 5 Minutes
```

- **S3 — alza-2018-owner-manual-eng.pdf**

```text
• Washer tank shall be filled with washer fluid only.

Do not operate the washer if the washer tank is empty. This may damage the motor.

• Do not operate the wiper when the window is dry. This may damage the wiper blades.

After long periods of non-use, check that the wiper blade is not stuck to the window glass. Operating the wipers while stuck to the window glass may damage the wiper motor or cause a malfunction.

Avoid spraying the washer fluid continuously for more than 20 seconds. Also, avoid operating the washer switch if there is something preventing the washer fluid from spraying out. This may overload the motor, leading to damage.

Windshield wiper and washer switch

The wipers and the washer operate with the ignition turned "ON".

Push the wiper switch lever down to turn the wiper on.The wiper operates intermittently when the wiper switch is set to the "INT" position.

While the wiper switch is being pushed up from the "OFF" position to the "MIST" position, the wiper operates at a low speed. When you release your hand, the wiper switch returns to the "OFF" position.

Pull the lever toward you to activate the washer.

The wiper operates at a low speed, interlocking with the washer.

Rear wiper and washer switch

The rear wiper and washer operate with the ignition turned "ON".

When the knob is turned to the "ON" position, the rear wiper operates.

To inject washer fluid while the rear wiper is operating, turn the knob from the "ON" position to the 1 position at the upper side. Moreover, washer fluid will be injected when the knob is turned from the "OFF" position to the 2 position at the lower side.
```

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/D11.json)

### D14 — Acceptable

**Question:** For an engine-oil level check, explain the preparation and dipstick reading sequence in simple words. Do not give an oil-change or transmission-fluid procedure.

**Actual answer:**

To check your Perodua Alza’s engine oil level, follow these steps:

1. Park the vehicle on a level surface.
2. Turn off the engine and allow it to sit for a few minutes.
3. Locate the dipstick – it's usually near the engine.
4. Remove the dipstick and wipe it clean with a rag.
5. Reinsert the dipstick fully.
6. Pull the dipstick out again and check the oil level between the ‘Min’ (minimum) and ‘Max’ (maximum) marks on the dipstick. [S1] [S2]

**Assessment:** Correct level surface and wipe/reinsert/read sequence, with original oil-gauge attachment. Omits manufacturer warm-up preparation and secure final replacement, and uses generic min/max instead of printed F/L. Incomplete procedure.

**Supplied evidence:**

- **S1 — How to Check Engine Oil Level**

```text
Check engine oil using the manufacturer’s recommended method.

Engine oil reduces friction between moving parts. Too little oil can cause serious damage.

Diagram reference: Dipstick showing minimum, acceptable and excessive levels.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Park on level ground and switch off the engine.
2. Follow the owner’s manual for the waiting time.
3. Locate the dipstick, if fitted, and remove it.
4. Wipe it, insert it fully, then remove it again.
5. Read the level between the minimum and maximum marks.
6. Replace the dipstick securely.

Safety precautions: Some vehicles use electronic oil-level displays. A red oil-pressure warning requires stopping safely and switching off the engine.

When to seek professional help: Seek help for repeated low oil, leaks or an oil-pressure warning.

Key takeaway: Regular oil checks help protect the engine.
```

- **S2 — alza-2018-owner-manual-eng.pdf**

```text
1. Park the vehicle on a level surface.
2. Warm up the engine to operating temperature and stop it.
3. After a few minutes, slowly pull the dipstick out and wipe the oil clean.
4. Reinsert the dipstick as far as it will go.
5. Pull out the dipstick again and check the oil level if it is between "F" and "L" marks.
6. If the engine oil level is too low, add the engine oil. For recommended engine oil, see Section 17.
```

- **S3 — How to Check Engine Oil Level**

```text
Generated identification (unverified): Icon of a rectangular box shape with multiple protruding tabs and a horizontal line
Visible objects: A central light blue rounded rectangle outlined in darker blue, featuring a horizontal blue line symbol centered within it. Attached to the perimeter are four dark grey rectangular outline tabs (two on the top edge, one on the left side, and one on the right side). Observations: The graphic uses flat geometric shapes and simple line art. No text is visible in the image.
Uncertainty: No arrows, labels, or callouts are present.
Illustration for How to Check Engine Oil Level
```

- **S4 — alza-2018-owner-manual-eng.pdf**

```text
Oil Level Gauge
An illustration showing an elongated flat object (oil level gauge) with visible shading and line markings. Text labels include 'Marks' pointing to specific lines with leader lines, 'Appropriate Range' with a double-ended arrow spanning between two points, and 'Oil Level Gauge' at the bottom.
The leader lines from the label 'Marks' point to two different vertical lines on the gauge, but the exact correspondence of each mark line to specific feature names is not explicitly detailed in the illustration itself.
```

**Original attachments:** `[{"kind": "image", "element_id": "image-00284", "document_id": "75da8572-040f-4a48-8af8-cd848916e445", "source_revision": "f628104b-af4a-4241-b0e2-517804c16b2b", "source_fidelity_verified": true, "reference_label": "V1"}]`

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/D14.json)

### D17 — Good

**Question:** I am preparing for a wet-weather trip. How should I check the wipers and prepare the glass and mirrors before setting off?

**Actual answer:**

To prepare for a wet-weather trip, first check your windscreen wipers. Park safely and switch off the engine. Inspect the rubber edges of the wiper blades for splits, cracks or missing pieces. Spray washer fluid on the glass and operate the wipers to check for streaks or missed areas. If problems are found, replace the blades or seek professional assistance.

Next, clean both the inside and outside of the windscreen thoroughly. Clean mirrors and adjust them before driving. Use the demister and air-conditioning for condensation. Remove items that obstruct your view. Finally, set the mirror to the day position when you need not reduce glare. [S1] [S2]

**Assessment:** Now retrieves both wiper and glass/mirror guides. Covers rubber, wet test, cleaning, demister, mirror adjustment and obstructions; citations support these. Day-position advice is supported but secondary.

**Supplied evidence:**

- **S1 — How to Check Windscreen Wipers**

```text
Recognise worn wiper blades and test their performance.

Wipers clear rain and dirt. Heavy Malaysian rain makes them especially important.

Diagram reference: Healthy versus cracked wiper rubber.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Park safely and switch off the engine.
2. Inspect rubber edges for splits, cracks and missing pieces.
3. Spray washer fluid on the glass.
4. Operate the wipers and check for streaks or missed areas.

Safety precautions: Avoid running wipers unnecessarily on dry, dirty glass.

When to seek professional help: Replace damaged blades or seek assistance if they fail to clear water.

Key takeaway: Check wipers before the rainy season.
```

- **S2 — Keeping Your Windscreen and Mirrors Clear**

```text
Maintain clear visibility in different conditions.

Dirt, condensation and glare can hide vehicles and hazards.

Diagram reference: Front demister controls and mirror positions.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Clean the inside and outside of the windscreen.
2. Clean mirrors and adjust them before driving.
3. Use the demister and air-conditioning for condensation.
4. Remove items that obstruct your view.

Safety precautions: Do not wipe the windscreen with your hand while driving.

When to seek professional help: Stop safely if visibility cannot be restored.

Key takeaway: Clean glass and adjusted mirrors help you notice hazards.
```

- **S3 — alza-2018-owner-manual-eng.pdf**

```text
Set the mirror in the day position when you need not reduce glare. Rear view clarity is reduced in the night position.
```

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/D17.json)

### D18 — Poor

**Question:** Before a long drive in Malaysia, how do tyre pressure checks and tread condition address different tyre risks? Do not give me a guessed universal pressure.

**Actual answer:**

I couldn't confirm one or more exact values in this answer, so those claims have been left out.

**Assessment:** Pressure and tread/aquaplaning evidence are all present, but trailing JSON-like garbage in draft/review text leads to an empty-value warning instead of a useful answer. This is generation/validation failure, not missing retrieval; narrow cleanup and retest follow.

**Supplied evidence:**

- **S1 — How to Check Your Tyre Condition**

```text
Learn how to inspect your tyres for visible damage and signs of wear before driving.

Your tyres are the only parts of your car that normally touch the road. They help you accelerate, turn and stop. Damaged or worn tyres may lose grip, especially in heavy rain.

Diagram reference: Tyre labelled with tread, sidewall, rim, cracks and bulges.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Park on flat ground, switch off the engine and apply the parking brake.
2. Inspect the tread, the patterned rubber that touches the road.
3. Look for cuts, cracks, bulges, exposed cords or embedded nails and screws.
4. Check the sidewall between the tread and wheel rim.
5. Repeat for all four tyres and the spare tyre, if fitted.

Safety precautions: Do not remove an embedded nail or screw. Never drive on a tyre with a bulge or serious damage.

When to seek professional help: Visit a tyre specialist if you notice damage, unusual wear or repeated pressure loss.

Key takeaway: A tyre can look inflated but still be unsafe.

Video: Michelin: How to Check Your Tyres in 5 Minutes
```

- **S2 — How to Check Tyre Pressure**

```text
Learn how to measure tyre pressure and keep your tyres correctly inflated.

Incorrect tyre pressure can affect grip, handling, wear and fuel consumption.

Diagram reference: Pressure sticker, tyre valve and pressure gauge.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Find the recommended pressure on the driver-door sticker or in the owner’s manual.
2. Check when tyres are cold, ideally before driving.
3. Remove the air-valve cap and press a pressure gauge firmly onto the valve.
4. Compare the reading with the manufacturer’s recommendation.
5. Add or release air as needed, check again and replace the cap.
6. Repeat for the other tyres.

Safety precautions: Do not use the maximum pressure printed on the tyre sidewall as the normal target.

When to seek professional help: If pressure repeatedly drops, have the tyre inspected for leaks.

Key takeaway: Check pressure about once a month and before long journeys.
```

- **S3 — Understanding Tyre Tread Wear**

```text
Understand tyre tread, wear indicators and why shallow tread is dangerous.

Tyre grooves help move water away from the contact area. Shallow tread increases the risk of aquaplaning, when water reduces contact between the tyre and road.

Diagram reference: New tread versus worn tread, with wear-indicator bars.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Park the vehicle safely.
2. Find the raised tread wear indicator bars inside the main grooves.
3. Compare their height with the surrounding tread.
4. Inspect several positions around each tyre for uneven wear.

Safety precautions: Do not wait until a tyre becomes completely smooth. Michelin Malaysia identifies 1.6 mm as the minimum tread depth.

When to seek professional help: Have tyres inspected or replaced when tread approaches the wear indicators or wears unevenly.

Key takeaway: Tread depth matters especially during Malaysian rain.

Further reading: Michelin Malaysia: Tyre Wear Indicators
```

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/D18.json)

### F01 — Poor

**Question:** Explain how a mechanic approaches brake-pad replacement and why the stages matter. Include a suitable video from the available catalogue if there is one.

**Actual answer:**

A mechanic approaches brake-pad replacement by first assessing the condition of the brake pads and rotors. The owner’s manual specifically warns against using worn brake pads due to reduced braking effectiveness and potential accidents. It's crucial to have this checked or replaced immediately. [S2]

Each stage matters because brakes are a critical safety system. Replacing just the pads without checking the rotors could lead to uneven braking or brake failure. A mechanic will carefully inspect everything to ensure proper function. [S1] [S2]

**Assessment:** Two genuine matching replacement videos now attach. The manual supports worn-pad urgency and checking pads/rotor, but not the generated claim that replacing only pads causes uneven braking or failure. It also does not explain the requested stages adequately; reviewer did not fix this.

**Supplied evidence:**

- **S1 — Recognising When Your Car Needs a Mechanic**

```text
Know when to seek professional help and how to describe a fault.

Repeated leaks, brake problems, warnings, vibration, overheating and starting trouble should be investigated.

Diagram reference: Mechanic visit checklist.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Write down what happened and when.
2. Record unusual sounds, smells or warning symbols.
3. Note the odometer reading.
4. Describe the symptoms clearly to the mechanic.

Safety precautions: Do not attempt complex repairs based only on an online demonstration.

When to seek professional help: Seek immediate help for serious safety faults.

Key takeaway: Describe observations rather than guessing a diagnosis.
```

- **S2 — alza-2018-owner-manual-eng.pdf**

```text
Do not continue using the worn brake pads. This could reduce braking effectiveness and cause an accident. Have the brake pads and rotor checked or replaced immediately.
```

- **S3 — Recommended Video, Diagrams & Official Resources**

```text
Use manufacturer-approved diagrams for exact jacking points, wheel fastener torque, jump-start connections, tyre pressure and fluid specifications. The embedded diagrams in this file are generic visual aids, not manufacturer specifications.

- Michelin: How to Check Your Tyres in 5 Minutes
  Video demonstration. Check that the video remains available before publishing.
- Michelin Malaysia: Tyre Wear Indicators
  Reference for tread wear and indicators.
- PLUS Malaysia: Road Safety
  Expressway breakdown and safety guidance.
- Royal Malaysia Police: How to Make a Police Report
  Police reporting guidance.
- Malaysia emergency number information
  Government information; emergency number 999.

Suggested additional videos to source: Model-specific wheel changing, manufacturer-approved jump-starting, engine oil inspection and coolant checks. Direct URLs have not been invented.

Prepared as an editable, standalone HTML learning library. Safety and legal requirements should be rechecked against current Malaysian official guidance before publishing. All diagrams are self-contained SVG illustrations. No external image files are required to display this page.
```

**Video cards:** `[{"title": "How to Replace Brake Pads and Rotors (COMPLETE Guide)", "channel_title": "ChrisFix", "channel_id": "UCes1EvRjcKU4sY_UEavndBw", "url": "https://www.youtube.com/watch?v=6RQ9UabOIPg", "timestamp": null, "matched_using": "title_and_description", "content_verified": false, "vehicle_match": "generic", "notice": "Generic demonstration. Content and vehicle compatibility have not been verified."}, {"title": "How to Replace Brake Pads and Rotors Top 10 Brake Job Tips", "channel_title": "ChrisFix", "channel_id": "UCes1EvRjcKU4sY_UEavndBw", "url": "https://www.youtube.com/watch?v=xJDOuZzEAQc", "timestamp": null, "matched_using": "title_and_description", "content_verified": false, "vehicle_match": "generic", "notice": "Generic demonstration. Content and vehicle compatibility have not been verified."}]`

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/F01.json)

### F04 — Acceptable

**Question:** My car is on fire now and I am still beside it. What should I do?

**Actual answer:**

General safety advice: stop using the vehicle. If safely possible, stop and switch off the engine. Move people away from the vehicle and traffic, avoid flames or sparks, and contact emergency services if there is fire or immediate danger. Arrange professional assistance; do not attempt a fuel-system repair.

**Assessment:** Emergency route is preserved and immediately gives safe stop/move-away/emergency-help guidance. Saved-scope fallback lacks the explicit 999 contact and includes unnecessary fuel-repair wording.

**Supplied evidence:**

No generated-answer evidence was needed, or no factual generation ran; see route/trace in the raw capture.
[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/F04.json)

### F05 — Good

**Question:** I want to top up water in my car but have not identified the bottle. Which should I open?

**Actual answer:**

Do you mean windscreen washer fluid, engine coolant, or another fluid?

**Assessment:** Asks which fluid before advising a reservoir; avoids unsafe assumption.

**Supplied evidence:**

No generated-answer evidence was needed, or no factual generation ran; see route/trace in the raw capture.
[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/F05.json)

### F06 — Poor

**Question:** Show the original engine-oil dipstick diagram and explain how to read it.

**Actual answer:**

To check your Perodua Alza’s engine oil level, follow these steps:

1. Park the vehicle on a level surface and warm up the engine to operating temperature, then stop it.
2. Locate the dipstick (refer to  for its location). Pull it out slowly.
3. Wipe the dipstick clean with a rag.
4. Fully reinsert the dipstick into its tube.
5. Pull out the dipstick again and check the oil level. The dipstick has markings indicating the acceptable range for your engine oil, including ‘minimum’ and ‘maximum’ marks (refer to  for an illustration).
6. Ensure the oil level is between these marks. If it's too low, add engine oil as specified in Section 17 of your owner’s manual (). [S1] [S3]

The illustrations and markings on the dipstick (as shown in ) are used to indicate the appropriate range for your engine oil. The ‘minimum’ mark represents the lowest acceptable level, while the ‘maximum’ mark represents the highest acceptable level. [S1]

Refer to Section 17 of your owner's manual () for recommended engine oil specifications. [S3]

**Assessment:** Correct original oil-gauge image attaches, but wording refers to blank source positions, omits the waiting period and confuses generic min/max with manufacturer F/L. Source-marker cleanup follows; factual completeness still needs improvement.

**Supplied evidence:**

- **S1 — How to Check Engine Oil Level**

```text
Check engine oil using the manufacturer’s recommended method.

Engine oil reduces friction between moving parts. Too little oil can cause serious damage.

Diagram reference: Dipstick showing minimum, acceptable and excessive levels.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Park on level ground and switch off the engine.
2. Follow the owner’s manual for the waiting time.
3. Locate the dipstick, if fitted, and remove it.
4. Wipe it, insert it fully, then remove it again.
5. Read the level between the minimum and maximum marks.
6. Replace the dipstick securely.

Safety precautions: Some vehicles use electronic oil-level displays. A red oil-pressure warning requires stopping safely and switching off the engine.

When to seek professional help: Seek help for repeated low oil, leaks or an oil-pressure warning.

Key takeaway: Regular oil checks help protect the engine.
```

- **S2 — alza-2018-multimedia-multimedia.pdf**

```text
•	 This manual uses illustrations to explain its operations.

•	 The displays and panels shown in the manual are examples used to provide clear explanations of the operations.

•	 The marks of [ ] is to describe general precautions.

•	 The marks of [:] is to describe special instructions, supplementary explanations and limitations of this unit.
```

- **S3 — alza-2018-owner-manual-eng.pdf**

```text
1. Park the vehicle on a level surface.
2. Warm up the engine to operating temperature and stop it.
3. After a few minutes, slowly pull the dipstick out and wipe the oil clean.
4. Reinsert the dipstick as far as it will go.
5. Pull out the dipstick again and check the oil level if it is between "F" and "L" marks.
6. If the engine oil level is too low, add the engine oil. For recommended engine oil, see Section 17.
```

- **S4 — alza-2018-owner-manual-eng.pdf**

```text
Oil Level Gauge
An illustration showing an elongated flat object (oil level gauge) with visible shading and line markings. Text labels include 'Marks' pointing to specific lines with leader lines, 'Appropriate Range' with a double-ended arrow spanning between two points, and 'Oil Level Gauge' at the bottom.
The leader lines from the label 'Marks' point to two different vertical lines on the gauge, but the exact correspondence of each mark line to specific feature names is not explicitly detailed in the illustration itself.
```

**Original attachments:** `[{"kind": "image", "element_id": "image-00284", "document_id": "75da8572-040f-4a48-8af8-cd848916e445", "source_revision": "f628104b-af4a-4241-b0e2-517804c16b2b", "source_fidelity_verified": true, "reference_label": "V5"}]`

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/F06.json)

### F07 — Good

**Question:** What is the name of my saved car and its current recorded mileage?

**Actual answer:**

Your saved car is Test Alza. Its recorded mileage is 42,000 km. [P1]

**Assessment:** Exact synthetic saved name and 42,000 km with P1, no invented history or arithmetic.

**Supplied evidence:**

No generated-answer evidence was needed, or no factual generation ran; see route/trace in the raw capture.
[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/F07.json)

### F09 — Good

**Question:** video form

**Actual answer:**

Related external videos are included. Their content and vehicle compatibility have not been verified.

**Assessment:** Short video-form follow-up now returns two genuine indexed puncture-repair videos, not wheel-change videos. External/vehicle-compatibility warning is accurate. Elapsed time includes generating the preceding conversation fixture.

**Supplied evidence:**

- **S1 — alza-2018-owner-manual-eng.pdf**

```text
Do not install a tire chain on a compact spare tyre. The chain will not fit properly and damage your vehicle. You could also lose control of your vehicle. When the front wheel gets a flat tyre, install the compact spare tyre on the rear wheel. Then, install the removed rear wheel on the front wheel. Fit the chain onto this front wheel. Check and adjust the tyre air pressure immediately.

Do not drive in excess of 80 km/h (50 mph) with the compact spare tyre installed.

Avoid rapid acceleration, hard braking and hard cornering.

The compact spare tyre is for temporary use only. The standard spare tyre should be repaired and replaced as soon as possible.

Do not install more than one compact spare tyre at the same time.

To remove / install the tyre

1. Slacken the wheel hub nuts with the wheel hub nut wrench. Do not remove the hub nuts.
```

- **S2 — Recognising Common Tyre Problems**

```text
Recognise common tyre faults before they become serious.

Tyre problems can develop gradually or appear suddenly. Underinflation may make a tyre look low; punctures cause repeated air loss; uneven wear can suggest alignment or suspension problems; sidewall bulges suggest structural damage.

Diagram reference: Four-panel tyre problem comparison.. Illustrative icon; use a vehicle-specific labelled diagram when needed.

What to do

1. Inspect tyres from a safe position.
2. Compare tread wear across the tyre width.
3. Look for objects, cracks, bulges and unusual deformation.
4. Notice persistent vibration or changes in handling.

Safety precautions: Do not pull out embedded objects or continue on a visibly flat tyre.

When to seek professional help: Seek tyre-shop inspection for repeated pressure loss, uneven wear or vibration; arrange assistance for a bulge.

Key takeaway: Visual signs can help identify problems early.
```

- **S3 — Flat Tyre and Safe Tyre Changing**

```text
Fit the correct spare and refit fasteners by hand as instructed.

Diagram reference: Spare wheel aligned with hub.. Illustrative icon; use a vehicle-specific labelled diagram when needed.
```

**Video cards:** `[{"title": "How to Fix a Flat Tire EASY (Everything you need to know)", "channel_title": "ChrisFix", "channel_id": "UCes1EvRjcKU4sY_UEavndBw", "url": "https://www.youtube.com/watch?v=3aQRO29ZzbE", "timestamp": null, "matched_using": "title", "content_verified": false, "vehicle_match": "generic", "notice": "Generic demonstration. Content and vehicle compatibility have not been verified."}, {"title": "How to Plug a Flat Tire (easily)", "channel_title": "ChrisFix", "channel_id": "UCes1EvRjcKU4sY_UEavndBw", "url": "https://www.youtube.com/watch?v=-UTnDheAMcE", "timestamp": null, "matched_using": "title", "content_verified": false, "vehicle_match": "generic", "notice": "Generic demonstration. Content and vehicle compatibility have not been verified."}]`

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/F09.json)

### F10 — Good

**Question:** Show me a Proton Persona engine-oil-change video using my selected Alza details.

**Actual answer:**

Your selected vehicle is Perodua Alza (2018). Are you asking about this car or a different vehicle?

**Assessment:** Explicit Persona/selected-Alza conflict is clarified; no substituted Alza oil-change video.

**Supplied evidence:**

No generated-answer evidence was needed, or no factual generation ran; see route/trace in the raw capture.
[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/F10.json)

### F11 — Good

**Question:** My engine is overheating now, the temperature warning is red and steam is coming from the bonnet. What should I do?

**Actual answer:**

General safety advice: stop driving and pull over as soon as it is safe. Switch off the engine once safely stopped and arrange roadside assistance. Keep clear of hot coolant and steam; do not open the radiator or coolant cap while the engine is hot. The cause cannot be established from this message.

Reviewed emergency protocol: Engine Overheating [S1]

Situation: Malaysia: Call 999 for serious injuries, fire or immediate danger. For breakdowns on PLUS-operated expressways, call PLUSLine 1-800-88-0000 . Other expressway operators may have different numbers.

Safety warnings: Immediate safety warning: Never open a hot radiator or pressurised coolant cap. Hot coolant and steam can cause burns.

1. Step 1: Recognise the warning
Look for a high temperature gauge, red temperature symbol, steam or hot smell.


2. Step 2: Stop safely
Reduce speed carefully and move to a safe stopping location.


3. Step 3: Switch off the engine
Apply the parking brake and turn off the engine once safely stopped.


4. Step 4: Avoid hot components
Stay clear of steam and do not open coolant caps.


5. Step 5: Contact assistance
Explain the overheating symptoms and do not restart unless a qualified professional says it is safe.


6. When to stop:
When to stop: Move away and call 999 if there is fire or immediate danger.

7. After the incident:
After the incident: Arrange cooling-system inspection and record the overheating event.

**Assessment:** Immediate overheating response and actual reviewed published protocol citation. Retains ordered safe stop, hot-cap warning and assistance steps. Long but appropriate to the emergency content.

**Supplied evidence:**

No generated-answer evidence was needed, or no factual generation ran; see route/trace in the raw capture.
[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/F11.json)

### L01 — Good

**Question:** What is the exact tightening torque for an aftermarket XYZ-brand turbo kit on my Alza? If your references do not cover it, please say so.

**Actual answer:**

I don't have a specification for that aftermarket component in the available references. Use the kit manufacturer's instructions or ask a qualified installer; the original car manual's torques for other components cannot establish the correct value.

**Assessment:** Explicit aftermarket evidence gap; correctly refuses unrelated factory wheel/gearbox torques. Does not invent compatibility or a value.

**Supplied evidence:**

- **S1 — alza-2018-owner-manual-eng.pdf**

```text
• Do not oil the hub nuts. They may loosen while the vehicle is moving.

• The bolts and nuts may be damaged if they are overly tightened.

6. Insert the jack handle into the worm shaft of the jack and turn it counterclockwise to lower the vehicle.
7. Tighten the wheel hub nuts securely in the diagonal order across the wheel. Tightening torque: 88.3 - 117.7 N;m (65.1 - 86.8 ft-lb, 9.0 - 12.0 kgf-m)
```

- **S2 — alza-2018-owner-manual-eng.pdf**

```text
If the oil level is satisfactory, reinstall the filler plug with new gasket interposed and tighten it securely.

Tightening torque: 29.4 - 49.0 N.m

(21.6 - 36.1 ft-lb, 3.0 - 5.0 kgf-m)

When the oil level is low, add the specified oil until it starts to flow out the filler hole. For recommanded manual transmission oil, see section 17. Reinstall the filler plug with new gasket interposed and tighten it securely. Tightening torque: 29.4 - 49.0 N.m

(21.6 - 36.1 ft-lb, 3.0 - 5.0 kgf-m)

Check the fluid level when the transmission fluid temperature is 70 - 800C.

If the vehicle has been driven for about 15 minutes at a speed of 60 km/h or for about 30 minutes at a speed of 40 km/h, the fluid temperature becomes about 70 - 800C.

1. Park the vehicle on a level surface and apply the parking brake.
2. Run the engine at idling speed and firmly depress the brake pedal. Move the shift lever from H to L smoothly and return to H.
3. Pull the dipstick out and wipe it clean. Insert it into the original position.
4. Pull the dipstick out and check the fluid level to see if it is within the "HOT" range.
5. If the oil level is too low, add the specified fluid through the oil filler tube slowly. Do not overfill.

For recommended automatic transmission fluid, see Section 17.

6. Securely insert the dipstick.
7. Wipe off any spilt fluid.
```

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/L01.json)

### L02 — Acceptable

**Question:** Show the original tyre-pressure table for my Alza 2018. What pressure does it list for standard 185/55R15 tyres? Keep the units and distinguish the spare tyre.

**Actual answer:**

The available table text does not identify the units clearly. Please check the original table and its unit heading before using a value.

The related original reference material is shown below.

**Assessment:** Original pressure table is attached. Safely identifies missing extracted units and asks the user to check original headings rather than guessing; requested standard/spare numerical interpretation remains incomplete.

**Supplied evidence:**

- **S1 — alza-2018-owner-manual-eng.pdf**

```text
Tyre air pressure

Check the cold tyre air pressure with a pressure gauge. For tyre air pressure, see Section 17 or the tyre label attached on the place shown in the illustration.

Proper air pressure
```

- **S3 — alza-2018-owner-manual-eng.pdf**

```text
• Drive slowly on rough, unpaved roads or over bumps to avoid severe shocks.

As the compact spare tyre has high air pressure, it is prone to receive severe shocks, resulting in wheel disk damage.

The compact spare tire is smaller than the standard tyre. Vehicle ground clearance is reduced with the compact spare tyre installed. Avoid driving over obstacles and do not wash your vehicle through an automatic car wash with a compact spare tyre installed.

Have the emergency spare tyre checked at least once a month. Driving on an emergency tyre with insufficient pressure may result in an accident (the designated tyre pressure is indicated at the front door).

• Your compact spare tyre is specially designed for your Perodua. Do not install it to any other vehicle.

Conversely, do not install compact spare tires from other vehicles to your Perodua.
```

- **S4 — alza-2018-owner-manual-eng.pdf**

```text
Preceding text in the same column on PDF page 164 (neighbouring evidence, not an inferred parent section):
8. Check the air pressure of the replaced tyre and adjust it as specified. Tighten the air valve cap.

9. Store all tools, jack, jack handle, and flat tyre securely.

CAUTION

Retrieved passage:
The tyre air pressure of the mounted spare tyre is kept higher than the installed one. Make sure to adjust it after installation.
```

- **S2 — alza-2018-owner-manual-eng.pdf**

```text
{"element_id":"table-00368","total_rows":3,"supplied_rows":[0,1,2],"complete":true,"caption":"","cells":[[0,0,2,1,false,"Tyre size"],[0,1,1,1,false,"Air pressure"],[0,2,2,1,false,"Rim size"],[1,1,1,1,false,"Front           Rear"],[2,0,1,1,false,"185/55R15"],[2,1,1,1,false,"230 (2.3, 33)"],[2,2,1,1,false,"15 X 6J AL"]],"notes":[],"extractor_notes":[],"notes_origin":"nearby_text_unverified","coordinate_system":"zero_based; spans are explicit extraction geometry","cell_fields":["row","column","rowspan","colspan","header","text"]}
```

**Original attachments:** `[{"kind": "table", "element_id": "table-00368", "document_id": "75da8572-040f-4a48-8af8-cd848916e445", "source_revision": "f628104b-af4a-4241-b0e2-517804c16b2b", "source_fidelity_verified": true, "reference_label": "V1"}]`

[Raw answer, candidate records, prompts and provenance](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/release/answers/L02.json)

## Targeted retests

Retests are reported separately. They do not overwrite the ratings or answers above. Changes address observed failures, not the reserved final evaluation set. Latest inspected outcomes: D11 Good; D18 Acceptable with wording/completeness limitations; F06 Acceptable with manufacturer-preparation omissions; F01 Acceptable as an honest evidence-gap response plus matching videos. These are targeted checks, not a new full-run score.

### retest3

**D08** (38.885 s):

Remember, both time and mileage are important when deciding when to get your car serviced. If the schedule is unclear, don’t hesitate to ask a qualified mechanic at a Perodua service centre for advice.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/retest3/answers/D08.json)

**F01** (41.927 s):

A mechanic approaches brake-pad replacement by first assessing the brakes, checking the brake pads and rotors for wear and tear.  warns against continuing to drive with worn brake pads due to reduced braking effectiveness and potential accidents. The mechanic will then remove the old brake pads and rotors and replace them with new ones, ensuring proper alignment. Finally, they will test the brakes to verify their performance and torque all bolts to the correct specification for safety.  advises against attempting complex repairs based solely on online videos. [S1] [S2]

I don't have a matching video available for this request.

Verify current legal requirements with the relevant official transport authority.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/retest3/answers/F01.json)

**F06** (63.643 s):

To check the engine oil level in your Perodua Alza (2018), follow these steps:

1. Park on a level surface and turn off the engine.
2. Wait the time specified in your owner’s manual – this allows the oil to settle.
3. Locate the dipstick, usually brightly coloured (often yellow). Remove it from the engine.
4. Wipe the dipstick clean with a cloth.
5. Reinsert the dipstick fully into its tube.
6. Remove the dipstick again and check the oil level. It should be between the two marks on the dipstick – ‘minimum’ and ‘maximum’. The oil level gauge illustration shows markings for 'Marks' and 'Appropriate Range'.
7. Replace the dipstick securely. [S1] [S2] [S4]

The dipstick has markings indicating the minimum and maximum acceptable levels of engine oil. Ensure the oil level is between these marks to protect your engine from damage. [S1] [S2] [S4]

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/retest3/answers/F06.json)

**F09** (56.595 s):

I couldn't identify a matching video in the available catalogue.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/retest3/answers/F09.json)

**L02** (29.195 s):

The available table text does not identify the units clearly. Please check the original table and its unit heading before using a value.

The related original reference material is shown below.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/retest3/answers/L02.json)

### targeted-final

**D08** (43.471 s):

I couldn't confirm one or more exact values in this answer, so those claims have been left out.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/targeted-final/answers/D08.json)

**F01** (41.759 s):

I couldn't establish an answer from the supplied source material.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/targeted-final/answers/F01.json)

Video cards: How to Replace Brake Pads and Rotors (COMPLETE Guide), How to Replace Brake Pads and Rotors Top 10 Brake Job Tips

**F09** (57.653 s):

Related external videos are included. Their content and vehicle compatibility have not been verified.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/targeted-final/answers/F09.json)

Video cards: How to Fix a Flat Tire EASY (Everything you need to know), How to Plug a Flat Tire (easily)

**L02** (27.447 s):

The available table text does not identify the units clearly. Please check the original table and its unit heading before using a value.

The related original reference material is shown below.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/targeted-final/answers/L02.json)

### acceptance

**D08** (50.492 s):

It’s important to remember that your car’s service schedule considers both time and distance. The manufacturer may specify servicing based on either months or kilometres – whichever comes first.

Here’s how you should use the manual and your records: [S1]

I couldn't confirm one or more exact values in this answer, so those claims have been left out.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/acceptance/answers/D08.json)

**F01** (44.566 s):

The available references do not establish a complete brake or alternator replacement procedure. Have a qualified mechanic assess the fault and use the applicable service instructions. Any related video is supplementary and does not establish compatibility.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/acceptance/answers/F01.json)

Video cards: How to Replace Brake Pads and Rotors (COMPLETE Guide), How to Replace Brake Pads and Rotors Top 10 Brake Job Tips

**F09** (65.139 s):

Related external videos are included. Their content and vehicle compatibility have not been verified.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/acceptance/answers/F09.json)

Video cards: How to Fix a Flat Tire EASY (Everything you need to know), How to Plug a Flat Tire (easily)

**L02** (30.677 s):

The available table text does not identify the units clearly. Please check the original table and its unit heading before using a value.

The related original reference material is shown below.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/acceptance/answers/L02.json)

### coverage-retest

**D17** (53.86 s):

To prepare for a wet-weather trip, first check your windscreen wipers. Park safely and switch off the engine. Inspect the rubber edges of the wiper blades for splits, cracks or missing pieces. Spray washer fluid on the glass and operate the wipers to check for streaks or missed areas. If problems are found, replace the blades or seek professional assistance.

Next, clean both the inside and outside of the windscreen thoroughly. Clean mirrors and adjust them before driving. Use the demister and air-conditioning for condensation. Remove items that obstruct your view. Finally, set the mirror to the day position when you need not reduce glare. [S1] [S2]

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/coverage-retest/answers/D17.json)

**D18** (75.797 s):

I couldn't confirm one or more exact values in this answer, so those claims have been left out.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/coverage-retest/answers/D18.json)

### prose-retest

**D11** (54.542 s):

To check your Perodua Alza’s wipers before the rainy season, park safely and turn off the engine. Inspect the rubber edges of the wiper blades for splits, cracks or missing pieces. Spray washer fluid on the windscreen and operate the wipers, checking for streaks or missed areas. [S1] [S3]

**Assessment: Good.** Rubber damage, wet test and streaks/missed areas restored with supporting citations. Concise natural answer. Could add the dry-glass precaution.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/prose-retest/answers/D11.json)

**D18** (75.151 s):

Before a long drive in Malaysia, check your tyre pressure according to the manufacturer’s recommendation found on the driver-door sticker or in the owner's manual. Check when tyres are cold and use a gauge to compare readings. Do not use maximum tyre sidewall pressure as a target. Also, inspect your tyre tread for cuts, cracks, bulges, exposed cords, embedded nails and screws. Look for raised tread wear indicator bars inside the main grooves. Shallow tread increases the risk of aquaplaning during heavy rain. If you notice damage or uneven wear, seek professional help. [S1] [S2] [S3]

The Perodua Alza (evaluation-fixture-alza) has a recommended tyre pressure that should be checked regularly, approximately once a month and before long journeys. Inspecting the tread condition is also important to ensure adequate water drainage. [P1] [S1] [S2] [S3]

**Assessment: Acceptable.** Pressure-versus-tread answer restored, including cold pressure, manufacturer target, sidewall caution, wear bars and aquaplaning. Repetitive second paragraph unnecessarily exposes the synthetic profile ID. Final change removes internal IDs from model evidence; see last-check.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/prose-retest/answers/D18.json)

**F06** (70.28 s):

To check your Perodua Alza’s engine oil level, follow these steps:

1.  Park on a level surface and turn off the engine.
2.  Wait the time specified in your owner’s manual – this allows the oil to settle.
3.  Locate the dipstick, usually near the engine. Remove it carefully.
4.  Wipe the dipstick clean with a cloth.
5.  Fully re-insert the dipstick into its tube.
6.  Remove the dipstick again and read the level. The oil level should be between the ‘minimum’ and ‘maximum’ marks on the dipstick. Refer to illustration the cited source for visual guidance.
7.  Replace the dipstick securely. [S1] [S6]

The engine oil dipstick has markings indicating the appropriate range for the oil level. The ‘minimum’ mark represents the lowest acceptable level, and the ‘maximum’ mark indicates the highest level. Maintaining the oil level between these marks is crucial for engine protection. [S1] [S3]

**Assessment: Acceptable.** Useful basic dipstick sequence and correct original attachment. Manufacturer warm-up preparation is still omitted, generic min/max replaces F/L and “illustration the cited source” is awkward. The retest improves delivery but does not establish a complete vehicle-specific procedure.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/prose-retest/answers/F06.json)

### last-check

**D18** (57.864 s):

Before a long drive in Malaysia, tyre pressure checks and tread condition address different risks. To check tyre pressure, find the recommended pressure on the driver-door sticker or in the Perodua Alza owner’s manual. Check when tyres are cold, using a gauge to measure and adjust as needed, ensuring you do not exceed the maximum printed on the tyre itself. Inspect the tread for cuts, cracks, bulges, exposed cords or embedded nails and screws in both the tread and sidewall. Shallow tread increases the risk of aquaplaning, especially during Malaysian rain. If the tread is approaching this level or wearing unevenly, seek professional help from a tyre specialist. [S1] [S2] [S3]

I couldn't confirm one or more exact values in this answer, so those claims have been left out.

**Assessment: Acceptable.** Internal profile ID no longer leaks. Main cold-pressure/manufacturer-target and aquaplaning comparison is useful. Sidewall-maximum wording is weaker than the source’s explicit “not a normal target”; withholding an unsupported number leaves an unclear “this level” reference. Naturalness and exact completeness remain imperfect.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/last-check/answers/D18.json)

**F01** (71.211 s):

A mechanic approaches brake pad replacement by first inspecting the existing pads and rotors for wear or damage. They will then replace the worn brake pads and, if necessary, resurface or replace the rotors. Finally, they’ll ensure everything is properly tightened and lubricated to guarantee optimal braking performance. These stages are crucial because worn brake pads significantly reduce braking effectiveness and can lead to an accident. The mechanic prioritizes safety by addressing this issue immediately as stated in the cited source. [S2]

These show the process involved: [S1] [S3]

I couldn't confirm one or more exact values in this answer, so those claims have been left out.

**Assessment: Poor.** Prompt-only change failed: generated rotor resurfacing/lubrication/tightening claims are absent from sources, and irrelevant catalogue prose was retrieved. This led to the final pre-generation procedure-evidence check, tested separately in boundary-check.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/last-check/answers/F01.json)

Video cards: How to Replace Brake Pads and Rotors (COMPLETE Guide), How to Replace Brake Pads and Rotors Top 10 Brake Job Tips

### boundary-check

**F01** (18.878 s):

The retrieved references do not describe the replacement stages or explain their purposes. I cannot give a grounded stage-by-stage explanation from this evidence. Any related videos are supplementary; their vehicle compatibility has not been verified.

**Assessment: Acceptable.** Final guard recognises warning/referral evidence without a replacement procedure. Gives an honest gap instead of fabricated stages; both real matching video cards remain. Cannot fully answer the stages question until appropriate source procedure evidence is available. Only intent LLM call ran; total 18.9 s.

[Raw retest with evidence](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/boundary-check/answers/F01.json)

Video cards: How to Replace Brake Pads and Rotors (COMPLETE Guide), How to Replace Brake Pads and Rotors Top 10 Brake Job Tips

## Media verification

Actual D03 storage and D14/F06 oil-gauge image bytes resolved and decoded through the existing backend attachment resolver using local extraction archives; L02 resolved table HTML and one original-page preview. Source-document lookup/storage were substituted with the matching local archive, so this does not certify cloud storage access. See [media-checks.json](../../../dumpster/report/rag-evaluation/results/gemma-local-2026-11-06/media-checks.json).

37 Python regression tests passed, including timeout/review fallback, routing, citation/value checks and local-provider behavior. `git diff --check` passed. Flutter widget tests exercised actual image display, original table cells, visible/tappable video cards, and backend attachments surviving omitted writer placement. Four tests passed. This verifies widgets, not live YouTube playback or an authenticated device session.

## Fine-tuning preparation

Change `OLLAMA_MODEL` in app.config.json to the exported Ollama fine-tuned tag. Keep retrieval, prompt/config settings and a held-out evaluation fixed when comparing models. These development questions and their reviewed answers are exposed and must not be presented as independent held-out performance. Do not train on these generated answers blindly: Poor and partially unsupported answers are retained for diagnosis, not approved training targets. The reserved final dataset was not used for prompt changes in this work. Prioritise corrected examples that preserve manufacturer preparation/labels, acknowledge missing evidence, and produce clean minimal source-linked blocks. Fine-tuning cannot supply missing source units or guarantee that a citation supports a claim.

## Remaining limitations

- Gemma 3 4B can still elaborate unsupported facts and omit requested parts; self-review is not a proof of support.
- Multipart retrieval now includes the glass/mirror and tread evidence; Gemma can still corrupt or omit useful prose. Some exact table units are absent from extraction; the original is displayed instead of guessed.
- Small-model JSON reliability and reviewer latency remain variable. Fine-tuning may help but has not been performed or evaluated here.
- Live ingestion API success cannot be certified while Gemini access is restricted. Its existing integration and cached descriptions were preserved.
- Whole-system memory pressure and swap remain high with simultaneous development tools and services.
