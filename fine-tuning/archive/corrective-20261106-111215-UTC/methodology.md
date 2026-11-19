# Roadie fine-tuning methodology and configuration justification

This account is based on the saved scripts, configuration, trainer state, captured answers and adapter tensors. Training was executed in the user's Google Colab GPU session. Dataset preparation, artifact verification and answer review were assisted by Codex. Quality assessments are AI-assisted technical observations, not independent human researcher labels.

## Method and objective

The method was supervised instruction fine-tuning (SFT) using quantized low-rank adaptation: QLoRA-style parameter-efficient fine-tuning (PEFT). The model learned from examples containing an instruction, a source-labelled evidence passage, a question and an expected answer. The frozen instruction-tuned base was `unsloth/gemma-3-4b-it-unsloth-bnb-4bit`, at revision `316726ca0bd24aa323bfaf86e8a379ee1176d1fe`.

The objective was evidence-conditioned answer behaviour: preserve manufacturer conditions and source labels, avoid inventing missing procedures/specifications, and provide focused answers with citations. This targeted the answer generator. The embedding model, retrieval index, reranker, backend, Flutter application, original-media resolver and deterministic safety/procedure guards were not trained in this process.

SFT minimizes next-token cross-entropy on the assistant answer. Prompt tokens are masked out of the loss with `train_on_responses_only`; the instruction/evidence/question remain conditioning inputs. The Gemma-3 chat template supplies user/model turn boundaries and completion tokens. This is ordinary labelled-target SFT, including targets that acknowledge missing evidence. It is not preference-pair training, reinforcement learning, DPO or full-model pretraining.

For a targeted linear layer, the effective transformation can be written `W_effective = W_frozen + (alpha/r) * B*A`. Only A and B receive training updates. Here r=8 and alpha=8, giving the conventional alpha/r scale of 1. The frozen base uses bitsandbytes NF4 quantization with double quantization according to its pinned model configuration. The Unsloth dynamic checkpoint explicitly excludes selected modules from 4-bit conversion, so it should not be described as every tensor being exactly 4 bits.

The implementation uses an 8-bit AdamW optimizer. It does not reproduce every detail of the original QLoRA paper's optimizer recipe. The saved LoRA tensors are F32; 4-bit base storage must not be confused with adapter storage or runtime arithmetic precision. Exact effective mixed-precision execution on Colab was not fully archived, so a specific FP16/BF16 execution claim is not established from the adapter dtype alone.

## Two separate experiments

| Setting | First general-RAG run | Corrective automotive run |
|---|---|---|
| Starting point | Original Gemma-3 base | Original Gemma-3 base reloaded |
| Data | Automatically prepared subset of pints-ai/Finetune-RAG | Local owner-manual excerpts with conservative template targets |
| Prepared training examples | Up to 320 in original recipe; 0.625 recorded epoch is consistent with 200 exposures over 320 examples | 176, all retained by the length filter |
| Comparison data | 24 validation examples, 12 public test examples, 3 exposed Roadie probes in the recipe | 16 prepared held-out examples; 12 actually used, plus 3 exposed probes |
| Sequence budget | 3,072 tokens in original recipe | 1,024 tokens |
| Optimizer steps | 50 recorded | 30 verified in trainer state |
| Peak learning rate | 1e-4 in original recipe | 8e-5 |
| Warm-up | 5 steps in original recipe | 3 steps |
| Maximum training time | 2,700 seconds in original recipe | 900 seconds |
| Generation cap | 384 tokens | 320 tokens |
| Epoch recorded | 0.625 | 0.681818 |

The two runs are independent adapters. The final corrective adapter is not an 80-step continuation of the first 50-step adapter. The first adapter was kept as evidence, old model/trainer references were released, and the original pinned base was reloaded before attaching a fresh corrective adapter.

The first dataset contains synthetic GPT-4o answers across mixed subjects. Whole preceding/current/following source chunks were included where available; fictitious distractor fields were not used in this simplified recipe. It therefore was not a reproduction of the dataset authors' full training experiment. First-run numeric results were better likelihood/overlap but mixed factual behaviour: validation loss 1.4362→0.7550, reference word F1 0.4933→0.5679, literal citation presence 9/12→6/12, and generation-cap hits 6/12→7/12. The brake probe fabricated repair stages, while the oil probe repeated its procedure. These observations motivated a data/task correction rather than accepting lower loss as sufficient.

For the first run, the local evidence supplied for review was status.json and comparison.md; some configuration details above are from the original prepared recipe rather than a complete recovered first-run environment. The corrective run includes weights, data, actual selected examples, state and logs.

## Corrective dataset

| Target category | Training examples | Prepared held-out examples | Cases actually evaluated |
|---|---:|---:|---:|
| Preserve the supplied source excerpt | 112 | 8 | 6 |
| Acknowledge missing replacement/repair procedure | 32 | 4 | 3 |
| Acknowledge missing exact torque specification | 32 | 4 | 3 |
| Total | 176 | 16 | 12 |

Approximately 64% of training targets preserve source wording and 36% teach missing-evidence boundaries. The two gap categories directly address unsupported repair stages and invented exact values. Their answers are ordinary SFT targets, not negative rewards or contrastive pairs.

Training documents were Alza 2018, Axia 2023-current, Bezza 2016, Bezza 2020-current and Myvi 2021-current owner manuals. The prepared comparison documents were the All-New Saga manual and Myvi 2005 manual. These are distinct source documents; they do not establish separation of all vehicle families, because Myvi appears in both eras.

Preparation selected paragraph/list excerpts from the existing extraction output, required a single reported section chunk, bounded character length, automotive vocabulary, acceptable text quality and a sentence-ending character, and excluded known exposed oil/nozzle/brake probe passages from training. Normalized exact duplicate passages were removed before selection. Selected source text, document names and extraction positions are retained in dataset.json and training-selection.json.

For source-preservation targets, the answer contains the source excerpt verbatim with an early citation. Warning-gap targets combine a clear missing-procedure statement with the warning verbatim. Specification-gap targets state that the value is absent. Source labels vary across S1–S4. Early citations reduce dependence on a trailing citation surviving the output cap. No token-level cutting was used to make an example fit.

These are automatically constructed templates using manufacturer text, not independently human-verified automotive QA labels. Preserving a whole extracted paragraph does not prove that the extraction itself is complete. The held-out missing-gear-symbol case demonstrates this limitation. The method also naturally encourages quotation, which explains more literal answers and occasional unnecessary copying.

## Final model/adaptation configuration

| Configuration | Value | Rationale and limits |
|---|---|---|
| Base family | Gemma 3 4B instruction-tuned | Matches Roadie's existing generation model family and reduces integration changes. |
| Base identifier/revision | Recorded above and in config.json | Identifies the exact base used for the adapter. |
| Full fine-tuning | False | Avoids optimizer/gradient storage for the full base; focuses updates on adapters. |
| Base weight loading | 4-bit, 8-bit loading disabled | Reduces base memory demand for a single Colab GPU. |
| Base quantization | NF4, double quantization; dynamic exclusions | NF4 is the checkpoint's low-bit representation; nested quantization further reduces quantization-metadata storage. This came from the checkpoint, not a quantizer sweep. |
| LoRA rank | 8 | Small adapter capacity and low memory/time cost. A practical bounded choice, not an empirically optimized rank. |
| LoRA alpha | 8 | With standard scaling, alpha/r = 1. |
| LoRA dropout | 0 | Follows the efficient Unsloth configuration and avoids stochastic dropout in a very short run. It does not establish that overfitting is prevented or that zero is optimal. |
| Bias adaptation | none | Keeps additional trainable parameters concentrated in LoRA matrices. |
| Vision adaptation | Disabled | The task uses source text; no image-caption or visual-understanding training was performed. |
| Language adaptation | Enabled | Targets the answer-generation behaviour. |
| Attention targets | q_proj, k_proj, v_proj, o_proj | Adapts attention transformations used while conditioning on instructions and evidence. |
| MLP targets | gate_proj, up_proj, down_proj | Adds adaptation capacity in language-layer feed-forward transformations. |
| Observed target coverage | 7 modules × 34 language layers = 238 modules | Verified from adapter tensor names, rather than inferred only from a regex. |
| Saved LoRA tensors | 476 F32 tensors | Each targeted module has A and B. |
| Actual learned adapter parameters | 14,901,248 | Counted from saved tensor shapes; these are the adapter parameters, not the whole model. |
| Other variants | DoRA and rank-stabilized LoRA disabled | Standard LoRA configuration; no preference or reward-model stage. |

Every one of the 238 saved B tensors contains nonzero values. Combined with trainer state global_step=30 and the saved logs, this verifies real parameter updates. It does not measure answer correctness. The safetensors file is 59,675,008 bytes, approximately 56.9 MiB, including its header. It requires the compatible original base model to run.

## Final optimization and execution settings

| Configuration | Value | Rationale and limits |
|---|---|---|
| Per-device batch size | 1 | Reduces peak memory for the Colab GPU. |
| Gradient accumulation | 4 | Accumulates four microbatches before each optimizer update. |
| Effective batch | 4 examples/update on one GPU | Gives larger-update batches without holding all four examples' activations simultaneously; variable lengths mean token counts per update vary. |
| Optimizer updates | 30 | A deadline/resource bound; no claim of convergence. |
| Approximate example exposures | 120 | 30 updates × 4 examples. This is fewer than a full pass over all 176 prepared examples. |
| Recorded epoch | 0.681818 | Consistent with 120/176. A one-epoch ceiling shown by the trainer must not be reported as one completed epoch. |
| Learning rate | 8e-5 | Reduced from the first run's 1e-4 to make a more conservative short adjustment. No controlled learning-rate ablation was performed. |
| Warm-up | 3 updates | Ramps up to the peak over about 10% of the 30-step budget. |
| Scheduler | Linear | Decays the learning rate after warm-up. |
| Optimizer | adamw_8bit | Reduces optimizer-state memory compared with full-precision states. |
| Weight decay | 0.001 | Mild regularization; not selected through a search. |
| Maximum sequence length | 1,024 tokens | Covers each selected instruction + evidence + question + target, while bounding compute and memory. It is this run's training window, not Gemma's maximum supported context. |
| Locally checked maximum complete training length | 618 tokens | Checked using the Gemma tokenizer and standard turn boundaries; the actual processor length filter also retained all 176 examples in Colab. |
| Sequence packing | False | Keeps separate examples separate instead of concatenating them into a shared training sequence. |
| Response-only loss | Enabled | Learns desired answer tokens rather than training the model to reproduce user instructions/evidence. |
| Seed and data seed | 3407 | Fixes configured initialization/shuffle randomness; does not guarantee bit-identical GPU results across environments. |
| Dataset preprocessing processes | 1 | Avoids extra preprocessing workers for a small dataset. |
| Logging | Every optimizer step | Captures short-run progress and gradient/learning-rate diagnostics. |
| Checkpoint saving | Every 10 steps | Allows partial progress recovery after a disconnect. |
| Checkpoint retention | 2 | Bounds retained checkpoint storage. |
| Automatic in-training evaluation | Disabled | Saves time; final model outputs were compared afterward. |
| Best-checkpoint selection | None | Final adapter saved at the completed step count; no validation-based best-model selection. |
| Time budget | 900 seconds checked after each optimizer step | Training-only cap. A current step can overrun it, and loading/comparison/export are additional time. |
| Actual recorded training time | 133.9776 seconds | About 2 minutes 14 seconds for trainer execution, not total workflow duration. |
| External experiment tracking | None | Logs and artifacts saved to Drive; no W&B/paid model API dependency. |

The actual run used 30 steps rather than reaching its time cap. Average recorded training loss was 0.639348. Logged first-step and last-step batch losses were 1.1257 and 0.3777, respectively; these are different batches. They show the optimization trace, not a held-out accuracy improvement. The corrective run did not compute a held-out validation loss, so 0.639348 must not be compared to the first run's validation loss as if they were the same metric.

Training used Unsloth FastModel, Hugging Face PEFT, TRL SFTTrainer, Transformers and bitsandbytes. The prepared installation pinned Transformers 4.57.6, TRL 0.22.2 and datasets 4.3.0. The saved final adapter records PEFT 0.21.2. Not all runtime packages/GPU hardware details were recovered locally, so these values are not a complete environment lockfile.

## Comparison configuration and interpretation

Base outputs were generated with the adapter disabled on the same loaded base. The corrective model was generated with the new adapter enabled. Both used identical prompts, source text, Gemma chat template and greedy decoding (`do_sample=False`), with `max_new_tokens=320`. Temperature/top-p/top-k were not sampled hyperparameters for this comparison. Greedy decoding reduces sampling variation; it does not make an answer factually correct.

Twelve primary cases were used: six source-preservation, three procedure-gap and three specification-gap cases. Three previously exposed Roadie development probes were repeated separately for oil, washer-nozzle advice and the brake evidence gap. Training and comparison document names and exact normalized excerpt hashes were disjoint. The question templates are shared across train and comparison, so this tests transfer to different source passages within closely related tasks, not broad generalization to arbitrary conversations.

Both base and tuned primary outputs contained the expected citation in 12/12 cases, and neither condition hit the 320-token cap. There was therefore no measured improvement in these two counts. AI-assisted pairwise review found six cases with better coverage/conditions/evidence-boundary handling, three broadly comparable cases, two correct but more verbose tuned answers, and one unresolved incomplete-source case. These are descriptive technical review categories, not an independently labelled accuracy score or a statistical significance result.

The exposed brake probe improved from the first run's fabricated repair stages to an explicit evidence gap; oil-procedure duplication also disappeared. The base oil response was already complete, so no claim should be made that the corrective model newly supplied preparation absent from that particular base answer.

The first run's public citation/cap counts and the corrective run's counts come from different datasets/context lengths/output caps and must not be presented as a controlled cross-run benchmark. The repeated three probes permit narrower qualitative comparison. No reserved final Roadie evaluation questions were used in the corrective construction, training or scoring.

## Role in the application and deployment state

The intended application remains RAG: retrieve evidence at question time, then let the adapted model generate its answer. Fine-tuning encourages how evidence is used; it does not replace the manuals, supply missing source symbols, validate vehicle applicability or guarantee citation support. Roadie's deterministic manufacturer-procedure display and professional-procedure evidence guard address observed failure modes independently of the model's willingness to obey its prompt.

The verified local artifact is an adapter plus tokenizer/processor metadata. GGUF export, any Q4_K_M inference conversion, Ollama model import, and full Roadie-path validation are separate steps. The saved status still records ollama_deployed=false. The bitsandbytes NF4 training checkpoint, an optional Q8 GGUF export intermediate and a planned Q4_K_M deployment file are distinct representations and should be described separately.

## Report-ready paragraph

Gemma 3 4B was adapted for evidence-conditioned automotive question answering using supervised instruction fine-tuning with quantized low-rank adaptation. The instruction-tuned base was loaded using the Unsloth bitsandbytes NF4 checkpoint, while rank-8 LoRA adapters were trained in attention and feed-forward projections across 34 language layers; vision parameters and base weights remained frozen. The corrective dataset contained 176 automatically constructed examples from five owner-manual documents, combining verbatim source-preservation targets with missing-procedure and missing-specification responses. Training used response-only loss, an effective batch size of four, a peak learning rate of 8e-5, three warm-up steps, linear learning-rate decay and an 8-bit AdamW optimizer. Thirty optimizer updates were completed in 133.98 seconds, corresponding to approximately 0.682 epochs. Comparison on 12 examples from separate source documents and three exposed regression probes showed improved preservation of source conditions and recognition of absent procedural evidence in several cases. Citation presence and output-cap counts were unchanged between base and tuned conditions. Incomplete source extraction and unnecessary quotation remained limitations; the results support targeted behavioural improvement rather than a general claim of automotive accuracy.

## Technical references

- QLoRA paper: https://arxiv.org/abs/2305.14314
- PEFT LoRA configuration: https://huggingface.co/docs/peft/en/package_reference/lora
- TRL SFTTrainer version 0.22.2: https://huggingface.co/docs/trl/v0.22.2/en/sft_trainer
- Official Unsloth Gemma 3 notebook: https://github.com/unslothai/notebooks/blob/main/nb/Gemma3_(4B).ipynb
- First-run dataset: https://huggingface.co/datasets/pints-ai/Finetune-RAG

## Local evidence

- config.json; training-metrics.json; trainer-state.json; training-log.json
- dataset.json; training-selection.json; evaluation-inputs.json
- adapter/adapter_config.json; adapter/adapter_model.safetensors
- base-model-config-at-training-revision.json; artifact-verification.json
- base-answers.json; tuned-answers.json; comparison.md; technical-review.md
