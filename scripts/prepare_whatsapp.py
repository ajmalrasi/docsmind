"""Prepare a private WhatsApp export for DocsMind ingestion.

Usage:
    python -m scripts.prepare_whatsapp --input /path/chat.zip \
        --output data/private/whatsapp/vagbay.whatsapp.jsonl --chat VAGBAY
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from docsmind.ingestion.whatsapp import prepare_whatsapp_export


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chat", required=True)
    args = parser.parse_args()

    report = prepare_whatsapp_export(
        args.input,
        args.output,
        chat_name=args.chat,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
