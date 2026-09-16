from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from src.semantic.action_extractor import ActionOrientedExtractor
from src.semantic.local_llm import LocalLLMClient


def hid(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def main():
    p = argparse.ArgumentParser(
        description="Piloto local privado. Não envia dados para serviços externos."
    )
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--top-k", type=int, default=3)
    args = p.parse_args()

    client = LocalLLMClient()
    extractor = ActionOrientedExtractor(client)

    with Path(args.input).open(encoding="utf-8") as src, \
         Path(args.output).open("w", encoding="utf-8") as dst:
        for line_no, line in enumerate(src, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            decision = row["decisao"]
            source_id = str(row.get("id", f"linha-{line_no}"))
            result = extractor.extract(decision, top_k=args.top_k)
            dst.write(json.dumps({
                "id_hash": hid(source_id),
                "recortes": result["recortes"],
            }, ensure_ascii=False) + "\n")
            print(
                f"[{line_no}] id_hash={hid(source_id)} "
                f"recortes={len(result['recortes'])}"
            )


if __name__ == "__main__":
    main()
