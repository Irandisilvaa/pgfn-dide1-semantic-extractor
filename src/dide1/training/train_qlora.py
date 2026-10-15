"""Treinamento opcional após existir GOLD suficiente.
Requer requirements-train.txt. O base model deve estar autorizado/local quando necessário.
"""
from __future__ import annotations
import argparse, json, os
from pathlib import Path


def principal():
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
    argumentos=p.parse_args()

    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
    from peft import LoraConfig
    from trl import SFTTrainer
    import torch

    saida=Path(argumentos.output); saida.mkdir(parents=True, exist_ok=True)
    configuracao_bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16)
    tokenizador = AutoTokenizer.from_pretrained(argumentos.base_model, use_fast=True)
    if tokenizador.pad_token is None: tokenizador.pad_token = tokenizador.eos_token
    modelo = AutoModelForCausalLM.from_pretrained(argumentos.base_model, quantization_config=configuracao_bnb, device_map="auto", torch_dtype="auto")
    configuracao_peft = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM", target_modules="all-linear")
    conjunto_dados = load_dataset("json", data_files={"train":argumentos.train,"validation":argumentos.val})

    def formatar_exemplo(exemplo):
        return tokenizador.apply_chat_template(exemplo["messages"], tokenize=False, add_generation_prompt=False)

    argumentos_treinamento = TrainingArguments(
        output_dir=str(saida / "checkpoints"), num_train_epochs=argumentos.epochs,
        learning_rate=argumentos.lr, per_device_train_batch_size=argumentos.batch_size,
        per_device_eval_batch_size=1, gradient_accumulation_steps=argumentos.grad_accum,
        logging_steps=10, save_steps=100, eval_steps=100, eval_strategy="steps",
        save_strategy="steps", bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
        gradient_checkpointing=True, seed=argumentos.seed, report_to="none",
        remove_unused_columns=False,
    )
    treinador = SFTTrainer(
        model=modelo, tokenizer=tokenizador, train_dataset=conjunto_dados["train"], eval_dataset=conjunto_dados["validation"],
        peft_config=configuracao_peft, args=argumentos_treinamento, formatting_func=formatar_exemplo, max_seq_length=argumentos.max_length,
    )
    treinador.train()
    modelo_final = saida / "adapter_final"
    treinador.model.save_pretrained(modelo_final)
    tokenizador.save_pretrained(modelo_final)
    (saida / "training_manifest.json").write_text(json.dumps(vars(argumentos), indent=2, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__": principal()
