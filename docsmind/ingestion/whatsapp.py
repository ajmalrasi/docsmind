"""Private WhatsApp-export ingestion.

The raw export is converted into an anonymized JSONL file before it enters the
normal DocsMind pipeline. Sender display names are replaced with stable aliases,
phone numbers and email addresses are redacted, and no identity map is written.

At load time, consecutive messages are grouped into conversation windows. Each
window becomes a LlamaIndex ``Document`` with temporal and participant metadata,
so the existing sentence chunker can operate without losing chat provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable
from zipfile import ZipFile

from llama_index.core.schema import Document


WHATSAPP_JSONL_SUFFIX = ".whatsapp.jsonl"

_HEADER_RE = re.compile(
    r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+"
    r"(?P<time>[^\]]+)\]\s+(?P<sender>[^:]+):\s?(?P<text>.*)$"
)
_TIMESTAMPED_LINE_RE = re.compile(
    r"^\[\d{1,2}/\d{1,2}/\d{2,4},\s+[^\]]+\]\s+"
)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d \t().-]{7,}\d)(?!\w)")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_MEDIA_RE = re.compile(
    r"<?(?:image|video|audio|document|sticker|gif|media|contact card) omitted>?",
    re.IGNORECASE,
)
_DELETED_RE = re.compile(
    r"^(?:this message was deleted(?: by admin.*)?|you deleted this message)\.?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RawWhatsAppMessage:
    timestamp: datetime
    sender: str
    text: str


def _parse_timestamp(date_text: str, time_text: str) -> datetime:
    normalized_time = (
        time_text.replace("\u202f", " ").replace("\xa0", " ").strip().upper()
    )
    value = f"{date_text}, {normalized_time}"
    formats = (
        "%d/%m/%y, %I:%M:%S %p",
        "%d/%m/%Y, %I:%M:%S %p",
        "%d/%m/%y, %H:%M:%S",
        "%d/%m/%Y, %H:%M:%S",
        "%d/%m/%y, %I:%M %p",
        "%d/%m/%Y, %I:%M %p",
        "%d/%m/%y, %H:%M",
        "%d/%m/%Y, %H:%M",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported WhatsApp timestamp: {value!r}")


def parse_whatsapp_text(text: str) -> list[RawWhatsAppMessage]:
    """Parse bracket-style WhatsApp text, preserving multiline messages."""
    messages: list[RawWhatsAppMessage] = []
    current_timestamp: datetime | None = None
    current_sender: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_timestamp is not None and current_sender is not None:
            messages.append(
                RawWhatsAppMessage(
                    timestamp=current_timestamp,
                    sender=current_sender.strip(),
                    text="\n".join(current_lines).strip(),
                )
            )

    for line in text.splitlines():
        # WhatsApp inserts invisible bidi-control marks before many exported
        # lines. Remove them only for header detection; message content is
        # cleaned separately during redaction.
        candidate = line.lstrip("\u200e\u200f")
        match = _HEADER_RE.match(candidate)
        if match:
            flush()
            current_timestamp = _parse_timestamp(
                match.group("date"), match.group("time")
            )
            current_sender = match.group("sender")
            current_lines = [match.group("text")]
        elif _TIMESTAMPED_LINE_RE.match(candidate):
            # Timestamped system event (join/leave/encryption notice), not a
            # user-authored message. Do not merge it into the prior message.
            flush()
            current_timestamp = None
            current_sender = None
            current_lines = []
        elif current_timestamp is not None:
            current_lines.append(line)

    flush()
    return messages


def _identity_pattern(senders: Iterable[str]) -> re.Pattern[str] | None:
    # Short display names are often ordinary words and would destroy message
    # meaning if replaced globally. Phone-like identifiers are handled by the
    # phone regex; names of four or more characters are redacted when mentioned.
    names: set[str] = set()
    for sender in senders:
        display_name = re.sub(r"^[~\s\u202f]+", "", sender).strip()
        if len(display_name) >= 4 and any(ch.isalpha() for ch in display_name):
            names.add(display_name)
    if not names:
        return None
    alternatives = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
    return re.compile(alternatives, re.IGNORECASE)


def redact_message_text(
    text: str, identity_pattern: re.Pattern[str] | None = None
) -> str:
    """Remove structured PII while retaining message meaning for retrieval."""
    redacted = text.replace("\u200e", "").replace("\u200f", "")
    redacted = _EMAIL_RE.sub("[EMAIL]", redacted)
    redacted = _PHONE_RE.sub("[PHONE]", redacted)
    if identity_pattern is not None:
        redacted = identity_pattern.sub("[PERSON]", redacted)
    redacted = _MEDIA_RE.sub("", redacted)
    redacted = re.sub(r"[ \t]+", " ", redacted)
    redacted = re.sub(r"\n{3,}", "\n\n", redacted)
    return redacted.strip()


def prepare_whatsapp_export(
    input_zip: Path | str,
    output_jsonl: Path | str,
    *,
    chat_name: str,
) -> dict:
    """Create an anonymized JSONL corpus from a WhatsApp ZIP export.

    The alias mapping is deterministic by first appearance but is never saved.
    Re-running against the same export therefore produces the same aliases while
    leaving no reverse lookup from alias to the original display name.
    """
    input_zip = Path(input_zip)
    output_jsonl = Path(output_jsonl)

    with ZipFile(input_zip) as archive:
        text_members = [name for name in archive.namelist() if name.endswith(".txt")]
        if len(text_members) != 1:
            raise ValueError(
                f"Expected exactly one .txt chat export, found {len(text_members)}"
            )
        raw_bytes = archive.read(text_members[0])

    messages = parse_whatsapp_text(raw_bytes.decode("utf-8-sig"))
    if not messages:
        raise ValueError("No WhatsApp messages were parsed from the export")

    alias_by_sender: dict[str, str] = {}
    for message in messages:
        alias_by_sender.setdefault(
            message.sender, f"participant_{len(alias_by_sender) + 1:04d}"
        )

    identity_pattern = _identity_pattern(alias_by_sender)
    records: list[dict] = []
    skipped_empty = 0
    skipped_deleted = 0
    for index, message in enumerate(messages, start=1):
        normalized_text = message.text.replace("\u200e", "").replace("\u200f", "").strip()
        if _DELETED_RE.match(normalized_text):
            skipped_deleted += 1
            continue
        clean_text = redact_message_text(message.text, identity_pattern)
        if not clean_text:
            skipped_empty += 1
            continue
        records.append(
            {
                "id": f"msg_{index:06d}",
                "chat": chat_name,
                "timestamp": message.timestamp.isoformat(),
                "sender": alias_by_sender[message.sender],
                "text": clean_text,
            }
        )

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_jsonl.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )

    return {
        "chat": chat_name,
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "parsed_messages": len(messages),
        "written_messages": len(records),
        "participants": len(alias_by_sender),
        "skipped_deleted": skipped_deleted,
        "skipped_empty_or_media_only": skipped_empty,
        "first_timestamp": records[0]["timestamp"] if records else None,
        "last_timestamp": records[-1]["timestamp"] if records else None,
        "output": str(output_jsonl),
    }


def load_whatsapp_documents(
    path: Path | str,
    *,
    window_minutes: int = 10,
    max_messages: int = 20,
) -> list[Document]:
    """Load anonymized messages as conversation-window Documents."""
    path = Path(path)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not records:
        return []

    windows: list[list[dict]] = []
    current: list[dict] = []
    max_gap = timedelta(minutes=window_minutes)

    for record in records:
        timestamp = datetime.fromisoformat(record["timestamp"])
        if current:
            previous = datetime.fromisoformat(current[-1]["timestamp"])
            if len(current) >= max_messages or timestamp - previous > max_gap:
                windows.append(current)
                current = []
        current.append(record)
    if current:
        windows.append(current)

    documents: list[Document] = []
    for index, window in enumerate(windows, start=1):
        start = window[0]["timestamp"]
        end = window[-1]["timestamp"]
        chat = window[0]["chat"]
        participants = sorted({record["sender"] for record in window})
        text = "\n".join(
            f"[{record['timestamp']}] {record['sender']}: {record['text']}"
            for record in window
        )
        source = f"{chat}/{start[:10]}/window-{index:05d}"
        documents.append(
            Document(
                text=text,
                metadata={
                    "file_name": source,
                    "file_path": str(path),
                    "source_type": "whatsapp",
                    "chat": chat,
                    "start_time": start,
                    "end_time": end,
                    "participants": participants,
                    "message_ids": [record["id"] for record in window],
                },
            )
        )
    return documents
