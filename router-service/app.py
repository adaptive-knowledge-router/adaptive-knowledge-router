import os
import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_DIR = os.getenv("MODEL_DIR", "./router_model")
MAX_LENGTH = 128

ID2LABEL = {
    0: "entity_lookup",
    1: "relation_filter",
    2: "multi_hop",
    3: "sparse",
    4: "dense",
    5: "hybrid",
}


app = FastAPI(title="Router Service")

tokenizer = None
model = None


@app.on_event("startup")
def load_model():
    global tokenizer, model
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.eval()


class PredictRequest(BaseModel):
    query: str


class PredictResponse(BaseModel):
    strategy: str
    confidence: float
    probabilities: dict[str, float]


@app.post("/router/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    inputs = tokenizer(
        req.query,
        truncation=True,
        padding="max_length",
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )

    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0].numpy()

    pred_id = int(np.argmax(probs))
    strategy = ID2LABEL[pred_id]
    confidence = float(probs[pred_id])

    return PredictResponse(
        strategy=strategy,
        confidence=confidence,
        probabilities={ID2LABEL[i]: float(probs[i]) for i in range(len(ID2LABEL))},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
