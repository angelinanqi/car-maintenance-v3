---
base_model: unsloth/gemma-3-4b-it-unsloth-bnb-4bit
library_name: peft
pipeline_tag: text-generation
tags:
  - base_model:adapter:unsloth/gemma-3-4b-it-unsloth-bnb-4bit
  - lora
  - qlora
  - sft
  - transformers
  - trl
  - unsloth
  - automotive
  - retrieval-augmented-generation
  - evidence-grounding
---

# MyRoadie Corrective Automotive QLoRA Adapter

## Model Details

### Model Description

This repository contains an experimental **LoRA adapter for Gemma 3 4B Instruction-Tuned**, developed as part of the MyRoadie Final Year Project.

The adapter was trained using **Quantised Low-Rank Adaptation (QLoRA)** to investigate whether targeted supervised fine-tuning could improve the language model's handling of retrieved automotive-manual evidence.

The experiment focused on three behaviours:

1. **Source preservation:** Retaining important instructions, conditions, warnings and specifications from supplied manufacturer documentation.
2. **Missing-procedure recognition:** Explicitly identifying when retrieved evidence does not contain the repair or replacement procedure requested by a user.
3. **Missing-specification recognition:** Avoiding unsupported numerical specifications when exact values are absent from the supplied evidence.

The corrective experiment was motivated by an earlier general RAG fine-tuning pilot that improved validation loss but exhibited undesirable automotive-answer behaviours, including repetition and unsupported repair stages.

The corrective adapter was trained separately from the original pilot adapter, using a freshly loaded base checkpoint.

**This is an experimental research artifact, not the final selected model for the submitted MyRoadie application.** The final system retained the original Gemma 3 4B instruction-tuned model without the corrective adapter.

### Model Information

| Attribute | Description |
|---|---|
| Project | MyRoadie Final Year Project |
| Model type | Causal language model with LoRA adapter |
| Base model | `unsloth/gemma-3-4b-it-unsloth-bnb-4bit` |
| Base checkpoint revision | `316726ca0bd24aa323bfaf86e8a379ee1176d1fe` |
| Model family | Gemma 3 4B Instruction-Tuned |
| Training method | Supervised Fine-Tuning (SFT) with QLoRA |
| Fine-tuning framework | Unsloth, Hugging Face Transformers, PEFT and TRL |
| Training domain | Automotive manufacturer documentation |
| Training language | English-language automotive excerpts |
| Adapter type | LoRA |
| Adapter rank | 8 |
| Trainable adapter parameters | 14,901,248 |
| Intended use | Experimental evidence-grounded automotive question answering |
| Developed by | MyRoadie FYP researcher |
| Funding | Not documented |
| License | Subject to the applicable Gemma model terms; no separate adapter licence verified |

The base model was already instruction-tuned before the corrective experiment. This training did not create a language model from scratch.

## Uses

### Direct Use

This adapter is intended for research and evaluation of evidence-grounded text generation.

It should be loaded with a compatible Gemma 3 4B instruction-tuned base model and supplied with an instruction, relevant source evidence and a user question.

The adapter is not a standalone language model and cannot generate answers independently of its base model.

### Downstream Use

Potential research applications include:

- Automotive-manual question answering with retrieved evidence.
- Studying preservation of safety warnings, prerequisites and procedural conditions.
- Evaluating responses when requested repair procedures are absent.
- Investigating whether fine-tuning reduces unsupported technical specifications.
- Comparing original and adapter-enabled responses under identical prompts.

The original MyRoadie system uses a retrieval-augmented generation architecture, where document retrieval supplies evidence and the language model generates a response.

This corrective experiment evaluated the answer-writing component using fixed evidence passages. It did not independently validate the complete retrieval pipeline.

### Out-of-Scope Use

This adapter is not intended for:

- Autonomous vehicle diagnosis.
- Unsupervised mechanical repair decisions.
- Generating safety-critical procedures without verified manufacturer instructions.
- Inferring tightening torques, fluid specifications or repair stages absent from evidence.
- Replacing qualified automotive technicians.
- Use as a validated production replacement for the original MyRoadie language model.

## Bias, Risks and Limitations

The adapter was trained on a small, automatically constructed dataset derived from selected automotive manufacturer manuals.

Its principal limitations include:

**Limited training coverage.** The dataset contains 176 training examples from five selected manual documents. This is insufficient to establish broad generalisation across manufacturers, vehicles, repair tasks or question styles.

**Automatically constructed targets.** Training answers were generated using templates and extracted manufacturer text rather than independently authored and verified by human automotive experts.

**Excessive source copying.** The corrective adapter sometimes reproduced long passages that were only partially relevant to the question.

**Document extraction defects.** Missing symbols or malformed extracted text can affect the generated answer. Fine-tuning does not guarantee recovery of information lost during OCR or extraction.

**Limited evaluation.** The principal comparison used 12 held-out examples, with three previously exposed development probes evaluated separately.

**No comprehensive application-level validation.** The adapter comparison isolated text generation using fixed evidence. It did not establish improved end-to-end RAG retrieval, vehicle selection or overall application performance.

### Recommendations

Use this adapter only with compatible model weights, appropriate prompt formatting and independently verified evidence.

For automotive applications, generated instructions should be checked against authoritative manufacturer documentation, particularly when they involve safety-related maintenance or repairs.

The experimental findings should not be interpreted as proof that the adapter consistently outperforms the original model.

## Training Details

### Training Data

The corrective dataset consisted of **192 prepared examples**, separated by source document.

Of these:

- **176 examples** were assigned to training.
- **16 examples** were prepared for held-out comparison.
- **12 held-out examples** were used in the captured primary evaluation.

Three previously exposed automotive development probes were also evaluated separately.

#### Training Categories

| Behavioural objective | Training examples |
|---|---:|
| Preserve source information | 112 |
| Recognise missing repair procedures | 32 |
| Recognise missing exact specifications | 32 |
| **Total** | **176** |

#### Training Source Documents

| Source manual | Examples |
|---|---:|
| Perodua Alza 2018 | 21 |
| Perodua Axia 2023–current | 29 |
| Perodua Bezza 2016 | 20 |
| Perodua Bezza 2020–current | 46 |
| Perodua Myvi 2021–current | 60 |
| **Total** | **176** |

#### Held-Out Source Documents

| Source manual | Prepared examples |
|---|---:|
| Proton All-New Saga | 10 |
| Perodua Myvi 2005 | 6 |
| **Total** | **16** |

The split was organised by source document rather than randomly assigning individual passages.

Exact normalised passage hashes were used to support de-duplication and split checks. However, related automotive topics and similar instructions may still appear across documents.

The separation does not establish complete vehicle-family independence.

### Data Preprocessing

Training examples were constructed from previously extracted manufacturer-manual passages.

The preparation process included:

1. Selecting bounded automotive passages from available extracted documents.
2. Applying passage-length and content checks.
3. Excluding known exposed development probes from the corrective training set.
4. Constructing instruction, evidence, question and target-answer pairs.
5. Formatting examples using the Gemma chat template.
6. Checking sequence lengths before training.
7. Masking user and instruction tokens so that training loss was calculated on assistant response tokens.

All 176 prepared training examples passed the recorded training-length filter.

The original extraction environment and every upstream preprocessing detail were not independently verified in the archived record.

### Training Procedure

The corrective experiment reloaded the original Gemma 3 4B instruction-tuned checkpoint and attached a fresh LoRA adapter.

The frozen base model was loaded using four-bit NF4 quantisation, with double quantisation recorded in the checkpoint configuration.

The adapter was applied to language-model attention and feed-forward projection layers:

- `q_proj`
- `k_proj`
- `v_proj`
- `o_proj`
- `gate_proj`
- `up_proj`
- `down_proj`

Vision-layer adaptation was disabled because the experiment focused on text-based automotive evidence.

Training used supervised response-only loss. The model learned to increase the probability of the expected assistant response tokens while conditioning on the supplied instructions and evidence.

The original base-model parameters remained frozen.

### Training Hyperparameters

| Hyperparameter | Recorded value |
|---|---|
| Base-model loading | 4-bit NF4 |
| Quantisation library | bitsandbytes |
| Double quantisation | Enabled |
| LoRA rank (`r`) | 8 |
| LoRA alpha | 8 |
| LoRA scaling (`alpha/r`) | 1 |
| LoRA dropout | 0 |
| LoRA bias | None |
| Optimiser | `adamw_8bit` |
| Peak learning rate | `8e-5` |
| Learning-rate scheduler | Linear decay |
| Warm-up steps | 3 |
| Weight decay | 0.001 |
| Per-device training batch size | 1 |
| Gradient accumulation steps | 4 |
| Nominal effective batch size | 4 |
| Maximum sequence length | 1,024 tokens |
| Maximum optimiser steps | 30 |
| Recorded epoch progress | 0.681818 |
| Random seed | 3407 |
| Data seed | 3407 |
| Logging frequency | Every optimiser update |
| Checkpoint save interval | 10 steps |
| In-training evaluation | Disabled |
| Dataset packing | Disabled |
| Maximum training wall time | 900 seconds |

The pinned checkpoint configuration declares bfloat16 quantised computation. The exact effective trainer mixed-precision mode was not independently verified.

### Training Runtime and Metrics

| Metric | Recorded result |
|---|---:|
| Completed optimiser updates | 30 |
| Nominal sample exposures | 120 |
| Completed epochs | 0.681818 |
| Training runtime | 133.9776 seconds |
| Training samples per second | 0.896 |
| Training steps per second | 0.224 |
| Aggregate training loss | 0.639348 |
| Final logged step loss | 0.3777 |
| Trainable adapter parameters | 14,901,248 |

The mean logged training loss decreased across successive ten-step intervals:

| Training steps | Mean logged loss |
|---|---:|
| 1–10 | 1.03328 |
| 11–20 | 0.51293 |
| 21–30 | 0.37182 |

The training loss fluctuated between updates because different examples contributed to each logged interval.

The reduction in training loss indicates improved fitting of the supervised targets. It does not independently establish factual accuracy or generalisation.

No corrective validation-loss metric was recorded during training.

### Saved Artifacts

The completed experiment produced a PEFT LoRA adapter saved in Safetensors format.

The recorded artifact verification identified:

- 14,901,248 learned adapter parameters.
- 476 adapter tensors.
- An adapter weight file of approximately 59.7 MB.

A later export converted the adapter into an F32 GGUF adapter for experimental Ollama loading.

Historical integration testing used the model tag `roadie-gemma3-ft` with an Ollama Gemma base.

The GGUF export and temporary loading demonstrate adapter compatibility and an inference integration path. They do not independently establish improved answer quality.

The final submitted application selected `gemma3:4b` without the corrective adapter.

## Evaluation

### Evaluation Methodology

The corrective adapter was evaluated against the original base model using fixed prompts and evidence passages.

The comparison controlled:

- Base-model checkpoint.
- Input prompt.
- Supplied evidence.
- Chat formatting.
- Generation settings.

The adapter was enabled or disabled to compare generated answers.

Generation used deterministic greedy decoding:

| Parameter | Value |
|---|---|
| Sampling | Disabled |
| Maximum new tokens | 320 |
| Generation cache | Enabled |

The primary evaluation consisted of 12 selected held-out examples:

| Evaluation category | Examples |
|---|---:|
| Source preservation | 6 |
| Missing procedure | 3 |
| Missing specification | 3 |
| **Total** | **12** |

Three additional, previously exposed development probes examined engine-oil instruction repetition, washer-nozzle warnings and unsupported brake-replacement procedures.

These development probes were not treated as unseen generalisation tests.

### Evaluation Metrics

The comparison considered:

**Citation-marker presence:** Whether the generated answer included the expected source citation marker.

**Output truncation:** Whether generation reached the configured 320-token limit.

**Source preservation:** Whether relevant instructions, conditions, warnings and details were retained.

**Evidence-boundary recognition:** Whether the model acknowledged missing procedures or specifications instead of inventing them.

**Answer relevance:** Whether the response remained focused on the user's question rather than copying unnecessary source material.

The qualitative assessment was AI-assisted and should not be interpreted as an independently verified automotive accuracy benchmark.

### Results

#### Structural Results

| Metric | Original model | Corrective adapter |
|---|---:|---:|
| Expected citations present | 12/12 | 12/12 |
| Outputs reaching 320-token cap | 0/12 | 0/12 |

Both models satisfied these structural checks in the primary comparison.

#### Qualitative Results

The archived qualitative review classified the 12 primary cases as follows:

| Outcome | Cases |
|---|---:|
| Better source coverage or evidence-boundary handling with corrective adapter | 6 |
| Broadly comparable answers | 3 |
| Correct missing-information response but excessive quotation | 2 |
| Unresolved missing source symbol | 1 |
| **Total** | **12** |

These categories represent observations from a small controlled comparison, not a general-purpose accuracy percentage.

#### Notable Observations

**Improved preservation of prerequisites.** The corrective model retained the requirement to carry a valid intelligent key before starting a vehicle, which the original response omitted.

**Improved recognition of missing repair instructions.** In an air-cleaner example, the corrective model explicitly stated that the supplied evidence contained warnings but not the requested replacement procedure.

**Reduced unsupported procedural expansion.** On the previously exposed brake-pad probe, the corrective model identified the absence of detailed replacement stages rather than presenting unsupported stages as manufacturer instructions.

**Reduced repetition on an exposed example.** The corrective model did not repeat the engine-oil checking procedure, unlike the behaviour observed in the earlier general RAG pilot.

**Excessive quotation.** Some corrective responses copied lengthy source passages even when a short missing-specification statement would have been sufficient.

**Unresolved extraction defect.** An example with a missing transmission-gear symbol remained incomplete. The corrective model avoided inventing a value but did not fully explain the source defect.

### Evaluation Summary

The corrective experiment demonstrated targeted improvements in source preservation and missing-evidence recognition under fixed-input conditions.

However, the evaluation also identified limitations involving