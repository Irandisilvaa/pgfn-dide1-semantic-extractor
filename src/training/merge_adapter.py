from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description="Mescla adapter LoRA no base model e salva modelo HF autônomo.")
    p.add_argument("--base-model", default="Qwen/Qwen3-4B")
    p.add_argument("--adapter", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--max-shard-size", default="4GB")
    args = p.parse_args()

    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    print("Carregando base model em CPU...")
    base = AutoModelForCausalLM.from_pretrained(args.base_model, device_map="cpu", torch_dtype="auto", low_cpu_mem_usage=True)
    model = PeftModel.from_pretrained(base, args.adapter)
    print("Mesclando LoRA...")
    merged = model.merge_and_unload()
    merged.save_pretrained(output, safe_serialization=True, max_shard_size=args.max_shard_size)
    tokenizer = AutoTokenizer.from_pretrained(args.adapter)
    tokenizer.save_pretrained(output)

    hashes = {str(p.relative_to(output)): sha256(p) for p in output.rglob("*") if p.is_file()}
    (output / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    (output / "MERGE_MANIFEST.json").write_text(json.dumps({
        "base_model": args.base_model,
        "adapter": args.adapter,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "format": "Hugging Face safetensors merged model",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Modelo mesclado salvo em:", output)


if __name__ == "__main__":
    main()
