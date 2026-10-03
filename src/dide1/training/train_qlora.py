"""Treinamento opcional após existir GOLD suficiente.
Requer requirements-train.txt. O base model deve estar autorizado/local quando necessário.
"""
from __future__ import annotations
import argparse, json, os
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--base-model", required=True, help="Path local ou identificador HF autorizado")
    p.add_argument("--train", required=True)
    p.add_argument("--val", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--epochs", type=float, default=2.0)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=8)
    p.add_argument("--max-length", type=int, default=4096)
    p.add_argument("--seed", type=int, default=42)
    args=p.parse_args()

    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
    from peft import LoraConfig
    from trl import SFTTrainer
    import torch

    out=Path(args.output); out.mkdir(parents=True, exist_ok=True)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16)
    tok = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.base_model, quantization_config=bnb, device_map="auto", torch_dtype="auto")
    peft = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM", target_modules="all-linear")
    ds = load_dataset("json", data_files={"train":args.train,"validation":args.val})

    def fmt(ex):
        return tok.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)

    targs = TrainingArguments(
        output_dir=str(out / "checkpoints"), num_train_epochs=args.epochs,
        learning_rate=args.lr, per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=1, gradient_accumulation_steps=args.grad_accum,
        logging_steps=10, save_steps=100, eval_steps=100, eval_strategy="steps",
        save_strategy="steps", bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
        gradient_checkpointing=True, seed=args.seed, report_to="none",
        remove_unused_columns=False,
    )
    trainer = SFTTrainer(
        model=model, tokenizer=tok, train_dataset=ds["train"], eval_dataset=ds["validation"],
        peft_config=peft, args=targs, formatting_func=fmt, max_seq_length=args.max_length,
    )
    trainer.train()
    final = out / "adapter_final"
    trainer.model.save_pretrained(final)
    tok.save_pretrained(final)
    (out / "training_manifest.json").write_text(json.dumps(vars(args), indent=2, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__": main()
