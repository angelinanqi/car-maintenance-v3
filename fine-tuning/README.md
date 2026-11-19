# MyRoadie fine-tuning

MyRoadie tested whether fine-tuning could help Gemma 3 4B answer questions using passages retrieved from automotive manuals. The goal was to preserve the instructions and precautions in the source, cite the relevant evidence, and say when the evidence did not give a requested procedure or specification. Both experiments adapted the answer generator. MyRoadie still retrieves the manuals and guides at question time.

**The submitted application uses the original Gemma 3 4B instruction-tuned model**, configured as `gemma3:4b` in Ollama. The two adapters are experimental artifacts. The submitted thesis §4.4.8 is the source of truth for the methodology and model decision. The run folders provide the supporting data, settings and outputs. [Application configuration](../app.config.json#L87)

## The two experiments

| Experiment | What was tested | Recorded result |
| --- | --- | --- |
| [01 General RAG pilot](01-general-rag-pilot/README.md) | Fine-tune on a subset of the public Pints AI Finetune-RAG dataset to practise answering from supplied evidence. | 50 optimiser updates. Validation loss fell from 1.4362 to 0.7550. The answer comparison still showed repetition, incomplete answers and unsupported automotive repair steps. |
| [02 Corrective automotive](02-corrective-automotive/README.md) | Reload the original Gemma checkpoint and train a fresh QLoRA adapter on owner-manual excerpts that target the pilot's failures. | 30 optimiser updates. Several answers preserved more source details or identified missing procedures. Unnecessary quotation and an incomplete source remained problems. The small comparison gave limited evidence for changing the selected model. |

QLoRA keeps the quantised base weights fixed and trains a small set of additional weights called a LoRA adapter. Each experiment produced its own adapter.

## Datasets and splits

| Experiment | Training | Validation during the experiment | Held-out answer comparison |
| --- | --- | --- | --- |
| General RAG pilot | 320 prepared examples from Pints AI Finetune-RAG. The public dataset spans several topics and uses synthetic reference answers. | 24 examples. The notebook measured validation loss before and after training. | 12 public test examples. Three separate Roadie development probes also tested automotive behaviour. |
| Corrective automotive | 176 examples from five vehicle owner manuals. There were 112 source-preservation, 32 procedure-gap and 32 specification-gap targets. | The trainer ran with evaluation disabled. | 16 examples were prepared from two different source documents. The main comparison used 12. The three earlier development probes were repeated separately as exposed regression checks. |

The datasets and update budgets kept the work manageable on a Colab GPU. The pilot grouped shared source files or identical chunks before splitting. The corrective split used different source documents and checked for exact passage overlap. The corrective targets came from templates applied to extracted manual text, and the source extraction sometimes omitted details. Synthetic targets, small held-out sets and the reuse of development probes limit what the results say about real-world reliability. [Pints AI dataset card](https://huggingface.co/datasets/pints-ai/Finetune-RAG) · [Pilot split manifest](01-general-rag-pilot/archive/run-20261106-094913-UTC/dataset-manifest.json) · [Corrective split manifest](02-corrective-automotive/archive/data-prep/manifest.json)

## Finding the evidence

- The [pilot file guide](01-general-rag-pilot/README.md) links to the executed Colab notebook, dataset, training logs and raw results.
- The [corrective file guide](02-corrective-automotive/README.md) links directly to the dataset, training script, logs, generated answers and trained adapter.
- [Archive](archive/README.md) contains older instructions, saved report copies and a list of moved paths. Some notes describe the corrective adapter's temporary Ollama deployment under `roadie-gemma3-ft`.

For the viva, open the pilot comparison and the corrective technical review side by side. The pilot's lower validation loss shows that the model predicted the held-out target text better. Reading the generated answers exposed problems the loss could not measure. The corrective run addressed some of those problems, while the submitted application retained the original model. [Pilot answer comparison](01-general-rag-pilot/archive/run-20261106-094913-UTC/comparison.md) · [Corrective technical review](02-corrective-automotive/archive/run-20261106-111215-UTC/technical-review.md)
