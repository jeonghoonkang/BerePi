from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote
import xml.etree.ElementTree as ET

from pipeline_common import tokenize_for_rag

PROPFIND_BODY = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:getlastmodified />
    <d:getcontentlength />
    <d:resourcetype />
  </d:prop>
</d:propfind>
"""

DAV_NAMESPACE = {"d": "DAV:"}


@dataclass
class WebDavSettings:
    config_path: Path
    section_name: str
    hostname: str
    root: str
    username: str
    password: str
    verify_ssl: bool


@dataclass
class SyncedMarkdownFile:
    remote_path: str
    local_path: Path
    size_bytes: int


@dataclass
class RetrievedChunk:
    source: str
    chunk_id: int
    score: float
    content: str


def load_webdav_settings(config_path: Path, section_name: str = "target") -> WebDavSettings:
    """Load WebDAV settings from an ini-style config file."""
    parser = configparser.ConfigParser()
    read_files = parser.read(config_path)
    if not read_files:
        raise FileNotFoundError(f"WebDAV config file not found: {config_path}")
    if section_name not in parser:
        raise KeyError(f"WebDAV config section not found: {section_name}")

    section = parser[section_name]
    settings_section = parser["settings"] if "settings" in parser else {}
    hostname = section.get("webdav_hostname", "").strip().rstrip("/")
    root = section.get("webdav_root", "").strip().strip("/")
    username = section.get("username", "").strip()
    password = section.get("password", "").strip()
    verify_ssl = str(settings_section.get("verify_ssl", "true")).strip().lower() not in {"false", "0", "no"}

    if not hostname or not root or not username or not password:
        raise ValueError("WebDAV config is missing hostname, root, username, or password.")

    return WebDavSettings(
        config_path=config_path,
        section_name=section_name,
        hostname=hostname,
        root=root,
        username=username,
        password=password,
        verify_ssl=verify_ssl,
    )


def build_remote_url(settings: WebDavSettings, remote_path: str = "") -> str:
    """Build a direct WebDAV URL for a remote path."""
    normalized_path = remote_path.strip("/")
    base = f"{settings.hostname}/{settings.root}"
    if normalized_path:
        return f"{base}/{normalized_path}"
    return base


def propfind_list(settings: WebDavSettings, remote_path: str = "", depth: int = 1) -> list[dict]:
    """List WebDAV entries with PROPFIND depth 1."""
    import requests

    response = requests.request(
        "PROPFIND",
        build_remote_url(settings, remote_path),
        data=PROPFIND_BODY,
        headers={
            "Depth": str(depth),
            "Content-Type": "application/xml",
        },
        auth=(settings.username, settings.password),
        timeout=60,
        verify=settings.verify_ssl,
    )
    response.raise_for_status()

    document = ET.fromstring(response.text)
    entries: list[dict] = []
    root_url_suffix = f"/{settings.root.strip('/')}"
    current_path = remote_path.strip("/")

    for response_node in document.findall("d:response", DAV_NAMESPACE):
        href = response_node.findtext("d:href", default="", namespaces=DAV_NAMESPACE)
        propstat = response_node.find("d:propstat", DAV_NAMESPACE)
        if propstat is None:
            continue
        prop = propstat.find("d:prop", DAV_NAMESPACE)
        if prop is None:
            continue

        resource_type = prop.find("d:resourcetype", DAV_NAMESPACE)
        is_dir = resource_type is not None and resource_type.find("d:collection", DAV_NAMESPACE) is not None

        decoded_href = unquote(href)
        if root_url_suffix not in decoded_href:
            continue
        relative = decoded_href.split(root_url_suffix, maxsplit=1)[1].strip("/")
        if relative == current_path:
            continue

        entries.append(
            {
                "path": relative,
                "is_dir": is_dir,
                "size_bytes": int(prop.findtext("d:getcontentlength", default="0", namespaces=DAV_NAMESPACE) or 0),
            }
        )

    return entries


def list_markdown_files(settings: WebDavSettings, remote_subdir: str = "") -> list[str]:
    """Recursively list markdown files from a WebDAV directory."""
    queue = [remote_subdir.strip("/")]
    discovered: list[str] = []

    while queue:
        current = queue.pop(0)
        for entry in propfind_list(settings, current, depth=1):
            entry_path = str(entry["path"]).strip("/")
            if entry.get("is_dir"):
                queue.append(entry_path)
                continue
            lowered = entry_path.lower()
            if lowered.endswith(".md") or lowered.endswith(".markdown"):
                discovered.append(entry_path)

    return sorted(dict.fromkeys(discovered))


def download_markdown_file(settings: WebDavSettings, remote_path: str, destination: Path) -> SyncedMarkdownFile:
    """Download one remote markdown file into the local cache."""
    import requests

    response = requests.get(
        build_remote_url(settings, remote_path),
        auth=(settings.username, settings.password),
        timeout=120,
        verify=settings.verify_ssl,
    )
    response.raise_for_status()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    return SyncedMarkdownFile(
        remote_path=remote_path,
        local_path=destination,
        size_bytes=len(response.content),
    )


def sync_markdown_directory(
    settings: WebDavSettings,
    local_root: Path,
    remote_subdir: str = "",
) -> list[SyncedMarkdownFile]:
    """Sync markdown files from WebDAV into a local cache directory."""
    synced_files: list[SyncedMarkdownFile] = []
    for remote_path in list_markdown_files(settings, remote_subdir):
        relative = Path(remote_path)
        destination = local_root / relative
        synced_files.append(download_markdown_file(settings, remote_path, destination))
    return synced_files


def read_local_markdown_files(local_root: Path) -> list[tuple[str, str]]:
    """Load cached markdown files from the local sync directory."""
    if not local_root.exists():
        return []

    documents: list[tuple[str, str]] = []
    for path in sorted(local_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".markdown"}:
            continue
        documents.append((str(path.relative_to(local_root)), path.read_text(encoding="utf-8", errors="replace")))
    return documents


def chunk_markdown_text(text: str, chunk_size: int = 900, overlap: int = 180) -> list[str]:
    """Split markdown into overlapping text chunks."""
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(normalized)
    while start < text_length:
        end = min(text_length, start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def retrieve_markdown_chunks(
    question: str,
    documents: list[tuple[str, str]],
    max_chunks: int = 4,
) -> list[RetrievedChunk]:
    """Retrieve relevant markdown chunks using lightweight lexical scoring."""
    question_tokens = tokenize_for_rag(question)
    if not question_tokens:
        return []

    scored_chunks: list[RetrievedChunk] = []
    question_token_set = set(question_tokens)

    for source, content in documents:
        for index, chunk in enumerate(chunk_markdown_text(content)):
            chunk_tokens = tokenize_for_rag(chunk)
            if not chunk_tokens:
                continue
            chunk_token_set = set(chunk_tokens)
            overlap = question_token_set & chunk_token_set
            if not overlap:
                continue
            score = float(len(overlap)) / float(max(len(question_token_set), 1))
            phrase_bonus = 0.25 if question.lower() in chunk.lower() else 0.0
            scored_chunks.append(
                RetrievedChunk(
                    source=source,
                    chunk_id=index,
                    score=score + phrase_bonus,
                    content=chunk,
                )
            )

    scored_chunks.sort(key=lambda item: (-item.score, item.source, item.chunk_id))
    return scored_chunks[:max_chunks]


def format_retrieved_contexts(chunks: list[RetrievedChunk]) -> list[str]:
    """Format retrieved markdown chunks for prompt injection."""
    formatted: list[str] = []
    for chunk in chunks:
        formatted.append(
            "\n".join(
                [
                    f"[Markdown Source] {chunk.source}",
                    f"[Chunk] {chunk.chunk_id}",
                    f"[Score] {chunk.score:.3f}",
                    chunk.content,
                ]
            )
        )
    return formatted
