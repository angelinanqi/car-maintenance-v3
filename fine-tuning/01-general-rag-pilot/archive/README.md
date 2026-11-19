# General RAG pilot archive

Use the [pilot file guide](../README.md) for the executed notebook, dataset, training logs and raw results.

The pilot tested whether supervised fine-tuning could help Gemma 3 4B generate an answer from a supplied passage. The recorded run used response-only loss and completed 50 optimiser updates on a Colab Tesla T4. The prepared split contains 320 training, 24 validation and 12 public test examples. Three automotive development probes were appended to the answer comparison. [Executed notebook](../EditedRoadie_Gemma3_QLoRA.ipynb) · [Trainer state](../training-logs/trainer-state.json) · [Split manifest](run-20261106-094913-UTC/dataset-manifest.json)

## Dataset

[Pints AI Finetune-RAG on Hugging Face](https://huggingface.co/datasets/pints-ai/Finetune-RAG)

The notebook uses `finetunerag_dataset.jsonl` at revision `3374821d5e10262bc523828de8a9fefa88055ddf`. It verifies the file's SHA-256, groups matching source filenames or normalised chunks before splitting, and keeps whole source chunks and target answers that fit the token budget. [Pinned dataset revision](https://huggingface.co/datasets/pints-ai/Finetune-RAG/tree/3374821d5e10262bc523828de8a9fefa88055ddf) · [Saved manifest](run-20261106-094913-UTC/dataset-manifest.json)

## Notebooks and scripts

| File | Role |
| --- | --- |
| [EditedRoadie_Gemma3_QLoRA.ipynb](../EditedRoadie_Gemma3_QLoRA.ipynb) | Downloaded from the executed Colab notebook with saved cell output. This is the primary record of the pilot code and GPU session. It saves to `MyDrive/MyRoadie-finetuning`. |
| `~/Documents/to organize/Roadie_Gemma3_QLoRA.ipynb` | Original local authoring version, with no cell output. It uses `MyDrive/Roadie-finetuning` and includes an optional Q8_0 export cell absent from the executed download. |
| [editedroadie_gemma3_qlora.py](scripts/editedroadie_gemma3_qlora.py) | Colab Python export of the executed notebook code for reading and searching. It still depends on the Colab GPU, Drive mount, package installation and notebook runtime. |
| [data_prep.py](scripts/data_prep.py) and [local validation](scripts/local-validation.json) | The preparation helper matches the authoring notebook's embedded cell. The executed notebook changes the helper's docstring and comments. The local validation records preparation checks. |
| [Roadie_Recovery.ipynb](colab/Roadie_Recovery.ipynb) | Separate recovery notebook. It inspects a saved run and backs up a candidate adapter. Optional GPU cells reload it to make a separate comparison or export. It contains no training cell. |

## Recorded outputs

| Evidence | Files |
| --- | --- |
| Prepared data | [Training](../dataset/train.jsonl) · [Validation](../dataset/validation.jsonl) · [Public test](../dataset/test.jsonl) · [Actual evaluation inputs](../results/evaluation-inputs.json) |
| Settings and environment | [Config](../training-logs/config.json) · [Package versions](run-20261106-094913-UTC/pip-freeze.txt) · [Trainable parameters](run-20261106-094913-UTC/trainable-parameters.json) |
| Training | [Run status](run-20261106-094913-UTC/status.json) · [Trainer state](../training-logs/trainer-state.json) · [Per-step loss and learning rate](../training-logs/training-log.json) · [Training metrics](../training-logs/training-metrics.json) |
| Answer evaluation | [Base answers](../results/base-answers.json) · [Tuned answers](../results/tuned-answers.json) · [Paired review template](run-20261106-094913-UTC/paired-review.json) · [Comparison](run-20261106-094913-UTC/comparison.md) · [Metrics](../results/comparison-metrics.json) · [AI-assisted review](../../archive/fine-tuning-documentation/review.md) |

Validation loss fell from 1.4362 to 0.7550 and public-test word F1 rose from 0.4933 to 0.5679. Literal citation presence fell from 9/12 to 6/12 and more answers hit the generation cap. The oil-check answer repeated the procedure, and the brake probe added repair stages the supplied warning did not support. Word overlap and citation counts measure surface properties of the captured answers. [Comparison metrics](../results/comparison-metrics.json) · [Qualitative review](../../archive/fine-tuning-documentation/review.md)

## Drive and reproducibility

The [pilot Drive folder](https://drive.google.com/drive/folders/1YdSE2quUOldMF8wULoc6jnt9iGiEvpgr) supplied the 19 local run records. It also lists the original pilot ZIP, the PEFT adapter, and checkpoints 40 and 50. The weight files were verified by filename in Drive. The archive links to the original Drive run for the adapter and checkpoints. The run status records no Ollama deployment, and no pilot GGUF was found in the inspected run listing.

Use the executed notebook and saved configuration to trace the original method. For read-only Colab inspection using the archived recovery notebook, use a copy and set its `ROOT` to `/content/drive/MyDrive/MyRoadie-finetuning` and `RUN_PATH` to `/content/drive/MyDrive/MyRoadie-finetuning/20261106-094913-UTC`. Use only the mount and inspection cell for a read-only check. The archived notebook retains its original path. The backup cell writes a ZIP under `/content/`, and the optional GPU comparison writes to `RUN/recovery-<UTC timestamp>/`.
