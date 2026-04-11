import json
import numpy as np
import torch
from torch.utils.data import Dataset as TorchDataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
)
from sklearn.metrics import accuracy_score, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
MODEL_NAME  = "microsoft/deberta-v3-base"
INPUT_FILE  = "arxiv_queries.jsonl"
OUTPUT_DIR  = "router_model"
MAX_LENGTH  = 128
BATCH_SIZE  = 64
EPOCHS      = 15
LR          = 2e-5
WEIGHT_DECAY= 0.02

LABEL2ID = {
    "entity_lookup"  : 0,
    "relation_filter": 1,
    "multi_hop"      : 2,
    "sparse"         : 3,
    "dense"          : 4,
    "hybrid"         : 5,
}
ID2LABEL = {v: k for k, v in LABEL2ID.items()}


# ─────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────
def load_data(filepath):
    queries, labels = [], []
    with open(filepath) as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            for q in record["queries"]:
                label = q.get("kg_strategy") or q.get("rag_strategy")
                if label in LABEL2ID:
                    queries.append(q["query"])
                    labels.append(LABEL2ID[label])
    return queries, labels


class RouterDataset(TorchDataset):
    def __init__(self, input_ids, attention_mask, labels):
        self.input_ids      = input_ids
        self.attention_mask = attention_mask
        self.labels         = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            "input_ids"     : self.input_ids[idx],
            "attention_mask": self.attention_mask[idx],
            "labels"        : self.labels[idx],
        }


# ─────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {"accuracy": accuracy_score(labels, preds)}


def plot_confusion_matrix(trainer, dataset):
    preds  = trainer.predict(dataset)
    y_pred = np.argmax(preds.predictions, axis=-1)
    y_true = preds.label_ids
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d",
                xticklabels=LABEL2ID.keys(),
                yticklabels=LABEL2ID.keys())
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title("Confusion Matrix")
    plt.tight_layout()
    plt.savefig("confusion_matrix.png")
    print("Confusion matrix saved → confusion_matrix.png")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    queries, labels = load_data(INPUT_FILE)
    print(f"Loaded {len(queries)} examples.")
    print("Label distribution:", {ID2LABEL[k]: v for k, v in Counter(labels).items()})

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    encodings = tokenizer(
        queries,
        truncation=True,
        padding="max_length",
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )

    input_ids      = encodings["input_ids"]
    attention_mask = encodings["attention_mask"]
    labels_tensor  = torch.tensor(labels, dtype=torch.long)

    # stratified 90/10 split
    from sklearn.model_selection import train_test_split
    indices = list(range(len(queries)))
    train_idx, val_idx = train_test_split(indices, test_size=0.1, stratify=labels, random_state=42)
    train_ds = RouterDataset(input_ids[train_idx], attention_mask[train_idx], labels_tensor[train_idx])
    val_ds   = RouterDataset(input_ids[val_idx],   attention_mask[val_idx],   labels_tensor[val_idx])

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(LABEL2ID),
        label2id=LABEL2ID,
        id2label=ID2LABEL,
        torch_dtype=torch.float32,
        ignore_mismatched_sizes=True,
    ).float()

    args = TrainingArguments(
        output_dir                  = OUTPUT_DIR,
        num_train_epochs            = EPOCHS,
        per_device_train_batch_size = BATCH_SIZE,
        per_device_eval_batch_size  = BATCH_SIZE,
        learning_rate               = LR,
        warmup_steps                = 100,
        weight_decay                = WEIGHT_DECAY,
        eval_strategy               = "epoch",
        save_strategy               = "epoch",
        load_best_model_at_end      = True,
        metric_for_best_model       = "accuracy",
        logging_steps               = 10,
        fp16                        = False,
        report_to                   = "none",
    )

    trainer = Trainer(
        model           = model,
        args            = args,
        train_dataset   = train_ds,
        eval_dataset    = val_ds,
        compute_metrics = compute_metrics,
        callbacks       = [EarlyStoppingCallback(early_stopping_patience=2)],
    )

    trainer.train()
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    plot_confusion_matrix(trainer, val_ds)


if __name__ == "__main__":
    main()