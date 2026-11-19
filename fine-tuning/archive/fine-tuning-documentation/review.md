# Roadie fine-tuning pilot review

This is an AI-assisted technical assessment of the supplied captured outputs, not human researcher labels or automotive certification. Original status.json and comparison.md are preserved unchanged.

## Outcome

The run records 50 completed optimizer steps and completion of base/tuned comparisons. It provides evidence of a completed training experiment. Only status.json and comparison.md were supplied locally: adapter weights, training logs, split files, configuration and exported GGUF are not yet available here for independent verification or import.

The fine-tune changes model behaviour, but does not establish an overall reliability improvement. Several outputs are more faithful to source wording, while others become repetitive, lose citations or invent unsupported details. The warning-only brake excerpt produces a materially worse tuned answer.

## Recorded diagnostics

| Diagnostic | Base | Tuned |
|---|---:|---:|

| Validation loss | 1.4362 | 0.7550 |

| Public reference word F1 | 0.4933 | 0.5679 |

| Public outputs containing [S1] | 9/12 | 6/12 |

| Public outputs reaching the 384-token cap | 6/12 | 7/12 |

Validation loss fell 47.4%. Word F1 rose by 7.46 percentage points. These measure likelihood/overlap, not factual correctness. Citation presence measures the literal marker, not whether it supports the claim.

The epoch recorded during tuned validation is 0.625. This is a short pilot, not multiple full epochs. The many capped public outputs limit completeness and citation comparisons: a citation appended at the end can be omitted by the cap. This does not prove citation capability deteriorated independently of response length.

## Case observations

| Case | Assessment | Observation |
|---|---|---|

| c1db098fde8653792149 | Concern | Both outputs hit the cap. Tuned repeats the approximately 70 billion yen investment claim, while the supplied English cash-flow table states approximately 7 billion yen. Human-resource coverage improves but financial section remains unfinished. |

| 64c7aab779f2acab1232 | Incomplete | Both outputs hit the cap. Tuned details license/distribution formats but is cut off before completing the requested terms and lacks a source citation in the captured output. |

| 43cbd6dec9fba60e6f1f | Regression | Tuned repeats multiple paragraphs and hits the cap where base finishes. Chart headings such as Good to have, Most critical and Future of retail are incorrectly presented as individual capabilities. |

| 469eb1a7198d090dc76a | Mixed | Tuned completes with a citation and explains expandable segments. Its final paragraph presents the old fragmented-allocation problem after describing the mitigation without clearly distinguishing the two. Base is truncated. |

| d738cec89f8c63c4cca1 | Useful | Tuned gives a coherent cited account broadly following the supplied historical passage; neither output hits the cap. This review checks against supplied text, not external historical verification. |

| 5ad07976d2ae69477774 | Improved focus, incomplete | Tuned concentrates on employee duties and preserves equipment-use and task-authorization conditions. Both outputs hit the cap; tuned ends at Risk and has no captured citation. |

| 315747141def87274037 | Improvement | Tuned preserves the requested 15% and 38% return-to-compliance figures with citation and avoids base misreading over 74% as over 7.4%. Subjective significant/considerable characterizations should be avoided. |

| 1d993cd330d0ef0a68a3 | Useful | Both correctly explain the supplied origin/meaning; tuned also preserves the badge detail and cites S1. |

| 9be3a483aba86401c28d | Incomplete | Tuned closely follows supplied agreement wording but both outputs hit the cap. Tuned ends mid-condition and omits its trailing citation; no legal conclusion about the actual agreement is made here. |

| 7c6bf7aa70b9c09910f1 | Regression | Base completes a compact cited tools/practices list. Tuned adds circular Tools/Value/Usage/Frequency exposition, covers fewer items before hitting the cap, and omits its captured citation. |

| 3a622c0377a917a52fcc | Incorrect | Tuned assigns pooled equity to Level 2 and fixed income/government securities to Level 3, contradicting the supplied Level 1 and Level 2 classifications. It also places money market investments under Level 1 despite source Level 2. Base also has a money-market classification error; neither is fully reliable. |

| a1cf40c2015a2de2c15a | Incomplete | Tuned covers supplied security partnerships, procurement and research guidance, but both outputs hit the cap. Tuned has no captured citation. No external policy verification is claimed. |

| dev-oil | Complete but repetitive | Both retain warm-up, stop, wait a few minutes, wipe, full reinsertion and F/L. Tuned reproduces the procedure twice; no demonstrated completeness improvement over this base answer. |

| dev-no-pin | Useful | Both say no pin and contact the service centre; tuned explicitly adds the supplied nozzle-damage precaution. |

| dev-evidence-gap | Regression | Tuned invents caliper removal/installation, rotor resurfacing and testing stages from a warning-only excerpt. Base is also imperfect: it frames checking/replacement as stages and adds a mechanic recommendation not stated in the excerpt. Tuned demonstrates a clear evidence-boundary failure. |

## Scope and interpretation

Twelve public examples are identified as held out by the provided report. Three Roadie probes are exposed development cases, and are not an independent held-out automotive score. No historical Roadie evaluation score is rewritten. No additional model/API calls were made for this review.

The generated answers were compared against supplied passages only. This review does not endorse the underlying financial, historical, legal or safety claims as current authoritative advice. Two tables/diagrams are visibly extraction-sensitive, which reinforces the need to preserve source geometry/labels.

## Integration decision and next artifact

The saved adapter is suitable to preserve and export as an experimental fine-tuned model. Do not use lower loss alone to promote it as safer or more accurate. Keep the application's complete manufacturer-procedure display and professional-procedure evidence guard. Those guards directly address the observed brake fabrication and do not depend on this model obeying the prompt.

Next obtain the adapter bundle (adapter weights/configuration/tokenizer plus original run configuration) and export a merged GGUF from Colab. Then prepare a Mac-appropriate quantization, create a separate Ollama tag, run actual Roadie queries, and select the tag in app.config.json only after verifying import/template/stop behaviour and the guarded paths. The local fine-tuning directory currently contains no deployable model.

## Honest submission wording

"Gemma 3 4B underwent a 50-step parameter-efficient supervised fine-tuning pilot for evidence-conditioned question answering. Recorded validation loss decreased from 1.4362 to 0.7550 and public reference word F1 increased from 0.4933 to 0.5679. Qualitative review found mixed results, including repetition, truncation and unsupported procedure generation. Application-level grounding and manufacturer-procedure safeguards remain necessary. Ollama deployment is a separate validation step."

Artifacts: [original comparison](comparison.md), [original run status](status.json), [structured review](review.json).
