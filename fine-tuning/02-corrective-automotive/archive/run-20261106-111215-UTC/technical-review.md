# Corrective automotive fine-tuning review

AI-assisted technical review of captured answers against their supplied passages. These are not human researcher labels or a certified automotive assessment. Original run outputs are unchanged.

## Conclusion

The corrective adapter demonstrates improvement on the intended source-preservation and missing-procedure behaviours in this small comparison. It restores omitted conditions and identifies missing repair stages more reliably than the base in several cases. It also removes the earlier fine-tune's brake-stage fabrication and oil-procedure duplication on exposed regression probes. This supports a narrow improvement claim for these captured tasks, not a general accuracy or safety claim.

One extraction-gap case remains unacceptable: the source has a missing destination gear label and the tuned response repeats an incomplete instruction instead of flagging the gap. Missing-specification responses also sometimes quote irrelevant source text unnecessarily.

## Recorded run and checks

- Saved trainer state: 30 optimizer steps.
- Recorded training duration: 133.98 seconds, excluding model setup and comparison.
- 176 prepared automotive training examples; 16 prepared held-out examples, of which 12 were used in the bounded comparison.
- Train/comparison source-document names and exact normalized source hashes are disjoint.
- Both base and tuned: 12/12 main outputs contain the expected citation; 0/12 reach the 320-token generation cap.
- Adapter weights are present locally; see artifact-verification.json for weight/state checks.
- No GGUF or Ollama deployment is present in this run.

## Pairwise technical assessment

| Case | Assessment | Evidence |
|---|---|---|

| fbf2bfe063aff6a1-source | Unresolved | Source loses the destination gear symbol. Base invents N; tuned avoids N but produces incomplete shift instructions instead of identifying the extraction gap. Neither answer is acceptable practical guidance. |

| 9ea753097690e165-source | Improved coverage | Tuned restores the requirement to carry a valid intelligent key before starting; base omits it. Steps remain intact. |

| fa37a6f0e761b6e9-source | Comparable | Both retain the coolant composition, corrosion purpose and no-clear-water precaution. Tuned quotes the source. |

| ae8c9f6a2c86f608-source | Improved coverage | Tuned restores Settings → Alarm Volume and retains ignition/battery conditions; base omits the navigation sequence. |

| e338637244b7a40e-source | Improved coverage | Both preserve the refuelling prohibitions. Tuned additionally retains the source explanation about leaking fuel causing explosion/fire. |

| 02aa3bbd774ba62b-source | Improved conditions | Tuned retains the key, gear, brake and ignition conditions. Base incorrectly compresses the OFF condition into not pressing the brake, omitting that the ignition switch must also be pressed again. |

| aa660b4baf796f84-procedure-gap | Comparable | Both identify absence of a replacement procedure and retain warnings. Neither invents replacement stages. |

| 906f5b75262359e9-procedure-gap | Improved boundary | Tuned explicitly says no repair stages are supplied. Base interprets the excerpt as a towing-process explanation without clearly identifying the requested repair-stage evidence gap. |

| 60d276ab11c4ae0e-procedure-gap | Improved boundary | Tuned refuses to infer removal/replacement instructions and retains both air-cleaner precautions. Base incorrectly frames not oiling the element as removal/replacement guidance. |

| b1215c98ab243e4e-specification-gap | Correct, more verbose | Both identify missing torque. Tuned unnecessarily quotes unrelated multimedia instructions before the gap statement; base is more focused. |

| cbbc0cfc1e061620-specification-gap | Comparable | Both explicitly identify missing torque; tuned is concise. |

| 0f409b81dc85602a-specification-gap | Correct, more verbose | Both identify missing torque. Tuned copies the entire unrelated sensor-limitations excerpt, so base is more concise. |

| dev-oil | Exposed regression check passes | Tuned retains warm-up, stop, waiting period, wipe/reinsert/read and F/L exactly once. Base is also complete; the first broad fine-tune had duplicated the procedure. |

| dev-no-pin | Exposed regression check passes | Both retain no-pin/service-centre advice; tuned preserves the supplied damage precaution. |

| dev-evidence-gap | Exposed regression check improves | Tuned explicitly states replacement stages are absent and gives only the supported warning. The first broad fine-tune fabricated caliper removal, rotor resurfacing, installation and testing. |

## Limits of the comparison

The question forms closely follow the automatic training templates, and the answers are often direct quotations. Document-family separation tests transfer to different passages, but does not establish general conversational improvement. The three earlier development probes have been inspected repeatedly and remain exposed regression checks. No reserved Roadie final evaluation dataset was read or used for this run. The review does not independently certify source text, extraction completeness, or real-world vehicle applicability.

The new 12-case citation/cap counts should not be directly compared to the first run's mixed-domain counts as if they were the same benchmark: the questions, context lengths and generation budgets differ. The repeated three development probes offer a direct qualitative regression check, with generation caps also differing. None of those three hit either cap.

## Integration implication

This adapter is a stronger candidate for Roadie than the first broad fine-tune on the targeted behaviours. Preserve the application's manufacturer procedure display and procedure-evidence guard. Export the corrective adapter into a separate Ollama model, validate its chat template/stop behaviour and actual Roadie-path answers, and retain the existing working model for rollback. Fix or detect missing source symbols rather than expecting fine-tuning to recover them.

## Suggested results wording

"A 30-step corrective fine-tune using automotive manual excerpts improved preservation of source conditions and recognition of missing procedural evidence in a small document-separated comparison. The corrective model restored omitted preparation details and stopped fabricating brake-replacement stages on an exposed regression case. Both base and tuned models included citations in all 12 main comparison outputs, with no outputs reaching the generation cap. An incomplete-source-symbol case remained unresolved, and broader application evaluation is still required."

Files: [captured comparison](comparison.md), [status](status.json), [structured review](technical-review.json), [artifact checks](artifact-verification.json).
