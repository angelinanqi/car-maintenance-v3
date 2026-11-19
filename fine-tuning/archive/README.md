# Fine-tuning archive

These copies and old instructions show what was recorded at the time. For the submitted model decision and the main evidence, start with the [fine-tuning guide](../README.md).

| Record | Purpose |
| --- | --- |
| [Pilot comparison](fine-tuning-documentation/comparison.md) and [pilot status](fine-tuning-documentation/status.json) | Local copies available before Drive recovery. Both match the respective files in the [archived pilot run records](../01-general-rag-pilot/archive/run-20261106-094913-UTC/) byte for byte. |
| [Pilot technical review](fine-tuning-documentation/review.md) and [review JSON](fine-tuning-documentation/review.json) | AI-assisted review of the captured answers. Statements about missing local artifacts describe the position at the time of that review. |
| [Pilot setup notes](fine-tuning-documentation/pilot-start-here.md) and [export notes](fine-tuning-documentation/EXPORT-NEXT.md) | Instructions for the original authoring notebook and its optional export. Their folder references predate the actual Drive setup and the repository move. |
| [Corrective Colab instructions](fine-tuning-documentation/corrective/START-HERE.md) and [deployment notes](fine-tuning-documentation/deployment/README.md) | Earlier operating instructions, including the temporary period when the corrective model was under test. |
| [Corrective methodology](corrective-20261106-111215-UTC/methodology.md), [comparison](corrective-20261106-111215-UTC/comparison.md), and [technical review](corrective-20261106-111215-UTC/technical-review.md) | Retained copies. The [corrective run guide](../02-corrective-automotive/README.md) links to the raw outputs and supporting records. |
| [Project model card](corrective-20261106-111215-UTC/adapter/README.md) | Expanded write-up. The [Colab-generated card](../02-corrective-automotive/archive/run-20261106-111215-UTC/adapter/README.md) is preserved separately. |
| [Earlier base-model report](gemma-local-2026-11-06/report.md) | Historical evidence of the use of `gemma3:4b`. The linked captures live under the original local report directory. |

## Previous paths

| Previous path | Current path |
| --- | --- |
| `dumpster/roadie-finetuning-20261106/Roadie_Recovery.ipynb` | [Pilot recovery notebook](../01-general-rag-pilot/archive/colab/Roadie_Recovery.ipynb) |
| Previous `01-general-rag-pilot/run-20261106-094913-UTC/` | [Dataset](../01-general-rag-pilot/dataset/), [training logs](../01-general-rag-pilot/training-logs/), [raw results](../01-general-rag-pilot/results/) and [supporting records](../01-general-rag-pilot/archive/run-20261106-094913-UTC/) |
| `fine-tuning/corrective/` | [Corrective script](../02-corrective-automotive/run_corrective.py) and [dataset](../02-corrective-automotive/dataset/) |
| `dumpster/corrective-20261106-111215-UTC/` and the previous `02-corrective-automotive/run-20261106-111215-UTC/` | [Training logs](../02-corrective-automotive/training-logs/), [raw results](../02-corrective-automotive/results/) and [supporting records](../02-corrective-automotive/archive/run-20261106-111215-UTC/) |
| `fine-tuning/deployment/` and the previous `02-corrective-automotive/deployment/` | [Corrective deployment archive](../02-corrective-automotive/archive/deployment/) |
| `fine-tuning/status.json` and `fine-tuning/review.json` | [Pilot historical notes](fine-tuning-documentation/) |

The historical deployment JSON retains its original repository paths. The relative GGUF reference in the Modelfile still resolves because both files moved together.
