# General RAG pilot

| What you’re looking for | Open this |
| --- | --- |
| **Dataset used** | [train.jsonl](dataset/train.jsonl) has the exact 320 prepared training rows. [Validation](dataset/validation.jsonl) has 24 examples and [public test](dataset/test.jsonl) has 12. [Pints AI Finetune-RAG on Hugging Face](https://huggingface.co/datasets/pints-ai/Finetune-RAG) · [Saved split manifest](archive/run-20261106-094913-UTC/dataset-manifest.json) |
| **Training notebook** | [EditedRoadie_Gemma3_QLoRA.ipynb](EditedRoadie_Gemma3_QLoRA.ipynb) is the executed Colab notebook with saved outputs. |
| **Training logs** | [training-log.json](training-logs/training-log.json) shows loss and learning rate at each update. [Trainer state](training-logs/trainer-state.json) records the 50 completed updates. [Final metrics](training-logs/training-metrics.json) · [Run settings](training-logs/config.json) |
| **Actual results** | [Tuned answers](results/tuned-answers.json) · [Base answers](results/base-answers.json) · [Evaluation inputs](results/evaluation-inputs.json) · [Comparison metrics](results/comparison-metrics.json) · [Base validation loss](results/base-validation-loss.json) · [Tuned validation loss](results/tuned-validation-loss.json) |
| **Trained weights** | The adapter and checkpoints are listed in the [pilot Drive folder](https://drive.google.com/drive/folders/1YdSE2quUOldMF8wULoc6jnt9iGiEvpgr). |

The [archive](archive/README.md) holds the comparison report, Python notebook export, recovery notebook, and Colab environment records.
