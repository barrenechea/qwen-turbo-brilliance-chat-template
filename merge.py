"""Builds chat_template_merged.jinja: the froggeric template with the turbo-brilliance {REASON:<mode>} layer spliced in."""

import argparse
import functools
import json
import os
import re
import struct
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
FROGGERIC_PATH = ROOT / "chat_template_froggeric.jinja"
TURBO_BRILLIANCE_PATH = ROOT / "chat_template_turbo_brilliance.jinja"
MERGED_PATH = ROOT / "chat_template_merged.jinja"
FROGGERIC_REPO = "froggeric/Qwen-Fixed-Chat-Templates"
TURBO_BRILLIANCE_REPO = "DavidAU/Qwen3.8-Flash-Next-Abliterated-Uncensored-Turbo-Brilliance-50x-Reasoning-Instruct-GSQ-RCO-GGUF"
GGUF_CHUNK_BYTES = 8 * 1024 * 1024
GGUF_SCALAR_FORMATS = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
GGUF_STRING = 8
GGUF_ARRAY = 9

MODE_SELECTION = """{%- set _tag_mode = store.reasoning_effort if l_car == '8' else '' %}
{%- set _request_mode = _effort_raw if (_effort_raw in instruction_map and _effort_raw not in ('xhigh', 'medium', 'low', 'off')) else '' %}
{%- set _mode = _tag_mode or _request_mode %}
{%- if _tag_mode %}
    {%- set ns_state.thinking = store.enable_thinking %}
{%- endif %}
{%- set reasoning_instructions = '' %}
{%- if _mode %}
    {%- set reasoning_instructions = instruction_map[_mode] %}
{%- elif ns_state.thinking %}
"""

TAG_STRIP_KEEPING_CONTENT_PARTS = """    {%- if msg.content is string %}
      {%- set clean_content = msg.content.replace(tag, "") | trim %}
    {%- else %}
      {%- set parts = namespace(items=[]) %}
      {%- for item in msg.content %}
        {%- if item is mapping and 'text' in item and item.text is string %}
          {%- set parts.items = parts.items + [{"type": "text", "text": item.text.replace(tag, "")}] %}
        {%- elif item is string %}
          {%- set parts.items = parts.items + [item.replace(tag, "")] %}
        {%- else %}
          {%- set parts.items = parts.items + [item] %}
        {%- endif %}
      {%- endfor %}
      {%- set clean_content = parts.items %}
    {%- endif %}
    {%- set store.messages = store.messages + [{"role": msg.role, "content": clean_content}] %}
"""


class AnchorError(Exception):
    pass


def replace_once(text: str, pattern: str, replacement: str, anchor: str) -> str:
    """Replaces the single regex match of an anchor and fails if upstream moved it."""
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE | re.DOTALL))
    if len(matches) != 1:
        raise AnchorError(f"anchor '{anchor}' matched {len(matches)} times, expected exactly 1")
    match = matches[0]
    return text[: match.start()] + match.expand(replacement) + text[match.end() :]


def extract_once(text: str, pattern: str, anchor: str) -> str:
    """Returns the single regex match of an anchor."""
    matches = re.findall(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if len(matches) != 1:
        raise AnchorError(f"anchor '{anchor}' matched {len(matches)} times, expected exactly 1")
    return matches[0]


def extract_mode_layer(turbo_brilliance: str) -> tuple[str, str]:
    """Cuts the turbo-brilliance modes and tag scan, with the default-effort lines returned separately."""
    layer = extract_once(turbo_brilliance, r"^\{#-+#\}\n\{#- Custom Reasoning //.*?(?=^\{# --- REASONING ACTIVATION)", "turbo-brilliance mode layer")
    defaults_pattern = r"^\{#- QWEN [\d.]+ DEFAULTs -#\}\n\{%- set default_effort_instruct = '\w+' %\}\n\{%- set default_effort = '\w+' %\}\n"
    defaults = extract_once(layer, defaults_pattern, "turbo-brilliance default effort lines")
    layer = layer.replace(defaults, "")
    layer = replace_once(
        layer,
        r"^ *\{%- set clean_txt = txt\.replace\(tag, \"\"\) \| trim %\}\n *\{%- set store\.messages = store\.messages \+ \[\{\"role\": msg\.role, \"content\": clean_txt\}\] %\}\n",
        TAG_STRIP_KEEPING_CONTENT_PARTS.replace("\\", "\\\\"),
        "turbo-brilliance tag strip",
    )
    return defaults, layer


def guard_empty_reverse_slice(froggeric: str) -> str:
    """Guards the reverse scan against an empty _msgs, which panics minijinja in vLLM's Rust frontend."""
    # https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates/discussions/109
    return re.sub(
        r"^(?<!\{%- if _msgs %\}\n)(\{%- for message in _msgs\[::-1\] %\}\n.*?^\{%- endfor %\}\n)",
        r"{%- if _msgs %}\n\1{%- endif %}\n",
        froggeric,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )


def merge(froggeric: str, turbo_brilliance: str, version: str) -> str:
    """Applies the merge recipe and stops at the first upstream change it cannot anchor."""
    defaults, mode_layer = extract_mode_layer(turbo_brilliance)
    preamble = extract_once(froggeric, r"^\{%- macro render_content\(.*?\{%- endmacro %\}\n\{%- if not messages %\}\n.*?\{%- endif %\}\n", "froggeric render_content + empty check")
    merged = guard_empty_reverse_slice(froggeric.replace(preamble, ""))
    merged = replace_once(merged, r'^\{%- set template_version = "[^"]+" %\}', f'{{%- set template_version = "qwen-turbo-brilliance-chat-template-{version}" %}}', "froggeric template_version")
    merged = re.sub(r"^\{%- set _default_reasoning_effort = '\w+' %\}\n", "", merged, flags=re.MULTILINE)
    merged = replace_once(
        merged,
        r"^(\{%- set _effort_raw = [^\n]*? else )(?:_default_reasoning_effort|'\w+')( %\}\n)",
        defaults.replace("\\", "\\\\") + r"\1(default_effort if enable_thinking else default_effort_instruct)\2",
        "froggeric effort fallback",
    )
    merged = replace_once(merged, r"^(\{%- for msg in messages %\}\n)", (preamble + mode_layer).replace("\\", "\\\\") + r"\1", "froggeric think-token scan")
    merged = replace_once(merged, r"^\{%- set reasoning_instructions = '' %\}\n\{%- if ns_state\.thinking %\}\n", MODE_SELECTION.replace("\\", "\\\\"), "froggeric reasoning_instructions")
    return merged


@functools.cache
def find_hf_token() -> str | None:
    """Finds the hf CLI's token, so requests get authenticated rate limits."""
    if token := os.environ.get("HF_TOKEN"):
        return token
    token_path = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "token"
    return token_path.read_text().strip() if token_path.exists() else None


def fetch(url: str, byte_range: tuple[int, int] | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"Range": f"bytes={byte_range[0]}-{byte_range[1]}"} if byte_range else {})
    if token := find_hf_token():
        # Downloads redirect to signed CDN URLs that reject a second auth mechanism, so the token must not follow redirects.
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request) as response:
        return response.read()


def resolve_revision(repo: str, revision: str = "main") -> str:
    """Pins a branch, tag or commit of an HF model repo to its full commit hash."""
    sha = json.loads(fetch(f"https://huggingface.co/api/models/{repo}/revision/{revision}"))["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError(f"{repo}@{revision} resolved to an unexpected commit id: {sha!r}")
    return sha


def fetch_froggeric(revision: str) -> str:
    """Downloads froggeric's chat_template.jinja at any HF revision (branch, tag or commit)."""
    return fetch(f"https://huggingface.co/{FROGGERIC_REPO}/resolve/{revision}/chat_template.jinja").decode()


class RemoteGguf:
    """Sequential reader over a remote GGUF file that downloads only the bytes it consumes."""

    def __init__(self, url: str):
        self.url = url
        self.buffer = b""
        self.offset = 0

    def read(self, size: int) -> bytes:
        while len(self.buffer) - self.offset < size:
            start = len(self.buffer)
            self.buffer += fetch(self.url, (start, start + max(GGUF_CHUNK_BYTES, size) - 1))
        chunk = self.buffer[self.offset : self.offset + size]
        self.offset += size
        return chunk

    def unpack(self, fmt: str):
        return struct.unpack("<" + fmt, self.read(struct.calcsize(fmt)))[0]

    def read_string(self) -> str:
        return self.read(self.unpack("Q")).decode()

    def read_value(self, value_type: int):
        if value_type == GGUF_STRING:
            return self.read_string()
        if value_type == GGUF_ARRAY:
            element_type, count = self.unpack("I"), self.unpack("Q")
            if element_type in GGUF_SCALAR_FORMATS:
                return self.read(count * struct.calcsize(GGUF_SCALAR_FORMATS[element_type]))
            return [self.read_value(element_type) for _ in range(count)]
        return self.unpack(GGUF_SCALAR_FORMATS[value_type])

    def find_metadata(self, wanted_key: str) -> str:
        if self.read(4) != b"GGUF":
            raise ValueError(f"{self.url} is not a GGUF file")
        self.unpack("I")
        self.unpack("Q")
        for _ in range(self.unpack("Q")):
            key = self.read_string()
            value = self.read_value(self.unpack("I"))
            if key == wanted_key:
                return value
        raise KeyError(f"{wanted_key} not found in {self.url}")


def fetch_turbo_brilliance(repo: str, revision: str) -> str:
    """Reads the chat template from the first GGUF's header without downloading the weights."""
    files = json.loads(fetch(f"https://huggingface.co/api/models/{repo}/tree/{revision}"))
    ggufs = sorted(entry["path"] for entry in files if entry["path"].endswith(".gguf") and not entry["path"].startswith("mmproj"))
    if not ggufs:
        raise FileNotFoundError(f"no model GGUF in {repo}")
    return RemoteGguf(f"https://huggingface.co/{repo}/resolve/{revision}/{ggufs[0]}").find_metadata("tokenizer.chat_template")


def describe_checkout() -> str:
    """Names a local build after the checked-out commit."""
    result = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() or "dev"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--froggeric-rev", help=f"refresh {FROGGERIC_PATH.name} from {FROGGERIC_REPO} at this revision (main, a tag or a commit)")
    parser.add_argument("--turbo-brilliance-repo", nargs="?", const=TURBO_BRILLIANCE_REPO, help=f"refresh {TURBO_BRILLIANCE_PATH.name} from a turbo-brilliance GGUF repo (default {TURBO_BRILLIANCE_REPO})")
    parser.add_argument("--version", help="release version, written as template_version qwen-turbo-brilliance-chat-template-<version> (default: the checked-out commit's 7-digit hash)")
    args = parser.parse_args()
    version = args.version or describe_checkout()
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.-]*", version):
        parser.error(f"--version must be letters, digits, dots and hyphens, got {version!r}")
    if args.froggeric_rev or not FROGGERIC_PATH.exists():
        froggeric_sha = resolve_revision(FROGGERIC_REPO, args.froggeric_rev or "main")
        FROGGERIC_PATH.write_text(fetch_froggeric(froggeric_sha))
        print(f"froggeric={froggeric_sha}")
    if args.turbo_brilliance_repo or not TURBO_BRILLIANCE_PATH.exists():
        turbo_brilliance_repo = args.turbo_brilliance_repo or TURBO_BRILLIANCE_REPO
        turbo_brilliance_sha = resolve_revision(turbo_brilliance_repo)
        TURBO_BRILLIANCE_PATH.write_text(fetch_turbo_brilliance(turbo_brilliance_repo, turbo_brilliance_sha))
        print(f"turbo_brilliance={turbo_brilliance_sha}")
    MERGED_PATH.write_text(merge(FROGGERIC_PATH.read_text(), TURBO_BRILLIANCE_PATH.read_text(), version))
    print(f"wrote {MERGED_PATH.name} ({version})", file=sys.stderr)


if __name__ == "__main__":
    main()
