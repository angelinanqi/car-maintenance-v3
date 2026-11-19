# Corrective automotive fine-tuning

| What you’re looking for | Open this |
| --- | --- |
| **Dataset used** | [dataset.json](dataset/dataset.json) has the 176 training examples and 16 held-out examples. [training-selection.json](dataset/training-selection.json) has the exact 176 formatted rows passed to the trainer. |
| **Training script** | [run_corrective.py](run_corrective.py) is the script executed in Colab. [Colab upload cell](archive/colab/COLAB-CELL.txt) |
| **Training logs** | [training-log.json](training-logs/training-log.json) shows loss and learning rate at each update. [trainer-state.json](training-logs/trainer-state.json) records the 30 completed updates. [Final metrics](training-logs/training-metrics.json) · [Run settings](training-logs/config.json) |
| **Actual results** | [tuned-answers.json](results/tuned-answers.json) contains what the trained model actually said. [Base answers](results/base-answers.json) · [Evaluation inputs](results/evaluation-inputs.json) · [Comparison metrics](results/comparison-metrics.json) |
| **Trained weights** | [adapter_model.safetensors](results/adapter/adapter_model.safetensors) is the trained LoRA adapter. [Adapter configuration](results/adapter/adapter_config.json) |

The [archive](archive/README.md) holds the reports, data preparation checks, Colab notes and historical Ollama export.
