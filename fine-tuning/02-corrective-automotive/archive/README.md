# Corrective automotive archive

Use the [corrective run file guide](../README.md) for the dataset, script, logs, generated answers and adapter weights.

The corrective run targeted the pilot's repetition and unsupported repair steps. It reloaded the original Gemma 3 4B instruction-tuned checkpoint at revision `316726ca0bd24aa323bfaf86e8a379ee1176d1fe` and attached a fresh rank-8 LoRA adapter to the 4-bit base. It trained for 30 optimiser updates with batch size 1, gradient accumulation 4, a learning rate of 0.00008, and a 1,024-token training limit. [Training script](../run_corrective.py) · [Saved configuration](../training-logs/config.json) · [Trainer state](../training-logs/trainer-state.json)

## Colab entry point and data

- [COLAB-CELL.txt](colab/COLAB-CELL.txt) is an upload cell for [run_corrective.py](../run_corrective.py). It expects a GPU runtime with the original notebook's imports, `RUN`, and `CONFIG`. It checks for the pilot adapter and reads the pilot's `evaluation-inputs.json` for the three exposed probes. The weights used for training come from the original base checkpoint. The script writes a fresh sibling run directory and offers a ZIP of the outputs. The [executed pilot notebook](../../01-general-rag-pilot/EditedRoadie_Gemma3_QLoRA.ipynb) shows where `RUN` and `CONFIG` came from.
- [Prepared examples](../dataset/dataset.json), [document split](data-prep/manifest.json), and [local validation](data-prep/local-validation.json) document the inputs. The script embeds those examples. The [run copy](run-20261106-111215-UTC/dataset.json) has different JSON formatting and the same records. The saved [training selection](../dataset/training-selection.json) confirms that all 176 examples passed the length filter.
- The training documents are the 2018 Alza, 2023 Axia, 2016 Bezza, 2020 Bezza and 2021 Myvi owner manuals. The held-out sources are the All-New Saga and 2005 Myvi manuals. Of 16 prepared cases, 12 entered the main comparison alongside three labelled, previously seen regression probes. There was no in-training validation. The [methodology record](run-20261106-111215-UTC/methodology.md) describes how chunks and templates were selected. The exact original raw-to-prepared dataset builder was unavailable.

## Recorded outputs

| Evidence | Files |
| --- | --- |
| Training | [Status](run-20261106-111215-UTC/status.json) · [Trainer state](../training-logs/trainer-state.json) · [Per-step loss and learning rate](../training-logs/training-log.json) · [Final training metrics](../training-logs/training-metrics.json) |
| Answer evaluation | [Inputs](../results/evaluation-inputs.json) · [Base answers](../results/base-answers.json) · [Tuned answers](../results/tuned-answers.json) · [Comparison](run-20261106-111215-UTC/comparison.md) · [Metrics](../results/comparison-metrics.json) · [Technical review](run-20261106-111215-UTC/technical-review.md) |
| PEFT adapter | [Generated model card](run-20261106-111215-UTC/adapter/README.md) · [Project model card](../../archive/corrective-20261106-111215-UTC/adapter/README.md) · [Adapter configuration](../results/adapter/adapter_config.json) · [Local weights](../results/adapter/adapter_model.safetensors) · [Verification record](run-20261106-111215-UTC/artifact-verification.json) |

The run recorded a training loss of 0.6393. Both models cited evidence on 12/12 main cases and neither hit the generation cap. Reading the answers showed that the corrective adapter preserved more source details and identified missing procedures in several cases. It sometimes copied irrelevant text, and a missing gear symbol in the source remained unresolved. The repeated oil and brake probes are examples of targeted improvements on already exposed cases. [Training metrics](../training-logs/training-metrics.json) · [Comparison metrics](../results/comparison-metrics.json) · [Pairwise review](run-20261106-111215-UTC/technical-review.md#pairwise-technical-assessment)

## Historical deployment

The corrective adapter was converted from PEFT safetensors to an F32 GGUF LoRA using the llama.cpp revision recorded in the deployment metadata. The Ollama Modelfile pairs the GGUF adapter with `gemma3:4b` under the temporary tag `roadie-gemma3-ft`. Keep the Modelfile and GGUF together if reproducing the historical import with an already installed base. The prior local RAG smoke checks and authenticated API checks are deployment evidence. The submitted model remains `gemma3:4b`. [Modelfile](deployment/Modelfile) · [Local GGUF](deployment/roadie-corrective-lora-f32.gguf) · [Deployment record](deployment/deployment.json) · [Authenticated checks](deployment/authenticated-check/summary.json) · [Final configuration](../../../app.config.json#L87)

The optional [EXPORT-CELL.txt](colab/EXPORT-CELL.txt) describes a separate merged Q8_0 export from Colab. The locally verified GGUF is the adapter-only export described above. The original Colab path was `/content/drive/MyDrive/MyRoadie-finetuning/corrective-20261106-111215-UTC/`. The Drive listing includes `adapter/` and `checkpoints/`. The preserved download omitted checkpoint directories. Heavy weights and tokenizer payloads are kept locally and ignored by Git. [Corrective Drive folder](https://drive.google.com/drive/folders/1zNXVWhAGidBxndwFukrsT0kFtIq-OOPY)

The authenticated-check script is historical. Running it writes into the same directory as the saved captures, so use a working copy if repeating it.
