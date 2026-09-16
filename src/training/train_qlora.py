from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import platform
import subprocess
import sys


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def latest_checkpoint(path: Path) -> str | None:
    checkpoints = []
    if path.exists():
        for p in path.glob("checkpoint-*"):
            try:
                step = int(p.name.split("-")[-1])
                checkpoints.append((step, p))
            except Exception:
                pass
    return str(max(checkpoints)[1]) if checkpoints else None


def main() -> None:
    p = argparse.ArgumentParser(description="QLoRA do DIDE1-SLM. Salva checkpoints + adapter final + tokenizer + manifest + hashes.")
    p.add_argument("--base-model", default="Qwen/Qwen3-4B")
    p.add_argument("--train", default="runtime/private_gold/sft_train.jsonl")
    p.add_argument("--val", default="runtime/private_gold/sft_val.jsonl")
    p.add_argument("--run-name", default="dide1-slm-v1")
    p.add_argument("--output-root", default="artifacts/models")
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--learning-rate", type=float, default=2e-4)
    p.add_argument("--max-length", type=int, default=2048)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=8)
    p.add_argument("--lora-r", type=int, default=32)
    p.add_argument("--lora-alpha", type=int, default=64)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    p.add_argument("--save-steps", type=int, default=50)
    p.add_argument("--eval-steps", type=int, default=50)
    p.add_argument("--logging-steps", type=int, default=5)
    p.add_argument("--seed", type=int, default=20260916)
    p.add_argument("--resume", action="store_true", help="Retoma automaticamente do checkpoint-* mais recente.")
    args = p.parse_args()

    # Lazy imports: o repositório continua utilizável sem dependências de treino.
    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        Trainer,
        TrainingArguments,
    )

    run_dir = Path(args.output_root) / args.run_name
    ckpt_dir = run_dir / "checkpoints"
    final_dir = run_dir / "adapter_final"
    run_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    def load_jsonl(path: str) -> list[dict]:
        out = []
        with Path(path).open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    train_rows = load_jsonl(args.train)
    val_rows = load_jsonl(args.val)
    if not train_rows:
        raise SystemExit("Dataset de treino vazio.")
    if not val_rows:
        raise SystemExit("Dataset de validação vazio.")

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    compute_dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=compute_dtype,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    lora = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)

    def encode_row(row: dict) -> dict:
        messages = row["messages"]
        prompt_messages = messages[:-1]
        full = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        prompt = tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True)
        full_enc = tokenizer(full, truncation=True, max_length=args.max_length, add_special_tokens=False)
        prompt_enc = tokenizer(prompt, truncation=True, max_length=args.max_length, add_special_tokens=False)
        labels = list(full_enc["input_ids"])
        prompt_len = min(len(prompt_enc["input_ids"]), len(labels))
        labels[:prompt_len] = [-100] * prompt_len
        full_enc["labels"] = labels
        return full_enc

    train_ds = Dataset.from_list(train_rows).map(encode_row, remove_columns=list(train_rows[0].keys()))
    val_ds = Dataset.from_list(val_rows).map(encode_row, remove_columns=list(val_rows[0].keys()))

    def collate(features: list[dict]) -> dict:
        max_len = max(len(f["input_ids"]) for f in features)
        input_ids, attention_mask, labels = [], [], []
        for f in features:
            pad = max_len - len(f["input_ids"])
            input_ids.append(f["input_ids"] + [tokenizer.pad_token_id] * pad)
            attention_mask.append(f["attention_mask"] + [0] * pad)
            labels.append(f["labels"] + [-100] * pad)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }

    kwargs = dict(
        output_dir=str(ckpt_dir),
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=True,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        eval_steps=args.eval_steps,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        fp16=(compute_dtype == torch.float16),
        bf16=(compute_dtype == torch.bfloat16),
        report_to="none",
        seed=args.seed,
        data_seed=args.seed,
        optim="paged_adamw_8bit",
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        remove_unused_columns=False,
    )
    sig = inspect.signature(TrainingArguments.__init__)
    if "eval_strategy" in sig.parameters:
        kwargs["eval_strategy"] = "steps"
    else:
        kwargs["evaluation_strategy"] = "steps"
    kwargs["save_strategy"] = "steps"

    training_args = TrainingArguments(**kwargs)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collate,
    )

    resume_from = latest_checkpoint(ckpt_dir) if args.resume else None
    train_result = trainer.train(resume_from_checkpoint=resume_from)
    eval_metrics = trainer.evaluate()

    final_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(final_dir, safe_serialization=True)
    tokenizer.save_pretrained(final_dir)
    trainer.save_state()

    metrics = {**train_result.metrics, **{f"final_{k}": v for k, v in eval_metrics.items()}}
    (run_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        git_commit = None

    import transformers, peft
    manifest = {
        "run_name": args.run_name,
        "git_commit": git_commit,
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "peft": peft.__version__,
        "base_model": args.base_model,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "train_file": args.train,
        "val_file": args.val,
        "train_sha256": sha256_file(Path(args.train)),
        "val_sha256": sha256_file(Path(args.val)),
        "train_examples": len(train_rows),
        "val_examples": len(val_rows),
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "max_length": args.max_length,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "lora_dropout": args.lora_dropout,
        "resume_from_checkpoint": resume_from,
        "adapter_final": str(final_dir),
        "checkpoint_dir": str(ckpt_dir),
        "important": "O adapter_final + o mesmo base_model reconstituem o modelo treinado. Faça cópia institucional destes arquivos.",
    }
    (run_dir / "training_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    hashes = {}
    for path in final_dir.rglob("*"):
        if path.is_file():
            hashes[str(path.relative_to(run_dir))] = sha256_file(path)
    (run_dir / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")

    print("=== TREINO CONCLUÍDO ===")
    print("Adapter final:", final_dir)
    print("Checkpoints:", ckpt_dir)
    print("Manifest:", run_dir / "training_manifest.json")
    print("Hashes:", run_dir / "SHA256SUMS.json")
    print("NÃO apague o base model nem adapter_final. Para artefato autônomo, rode merge_adapter.py.")


if __name__ == "__main__":
    main()
