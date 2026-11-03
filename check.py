"""Renders the merged template against both parents and fails on any divergence from the merge contract."""

import itertools
import json
import re
import sys
from pathlib import Path

import minijinja
from jinja2.ext import loopcontrols
from jinja2.sandbox import ImmutableSandboxedEnvironment

ROOT = Path(__file__).parent
MODE_TAG = "{REASON:"


def tag(mode):
    return f"{MODE_TAG}{mode}}}"


def raise_exception(message):
    raise ValueError(message)


def compile_template(source):
    env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, extensions=[loopcontrols])
    env.filters["tojson"] = lambda value, **kw: json.dumps(value, ensure_ascii=False, **kw)
    env.globals["raise_exception"] = raise_exception
    return env.from_string(source)


FROGGERIC_SOURCE = (ROOT / "chat_template_froggeric.jinja").read_text()
TURBO_BRILLIANCE_SOURCE = (ROOT / "chat_template_turbo_brilliance.jinja").read_text()
MERGED_SOURCE = (ROOT / "chat_template_merged.jinja").read_text()
FROGGERIC = compile_template(FROGGERIC_SOURCE)
TURBO_BRILLIANCE = compile_template(TURBO_BRILLIANCE_SOURCE)
MERGED = compile_template(MERGED_SOURCE)

MODES = re.findall(r"'([^']+)'", re.search(r"set reason_mods = \[(.*?)\]", TURBO_BRILLIANCE_SOURCE).group(1))
DEFAULT_EFFORT = re.search(r"set default_effort = '(\w+)'", TURBO_BRILLIANCE_SOURCE).group(1)
DEFAULT_INSTRUCT_EFFORT = re.search(r"set default_effort_instruct = '(\w+)'", TURBO_BRILLIANCE_SOURCE).group(1)
FROGGERIC_EFFORTS = ("xhigh", "medium", "low", "off")

TOOLS = [{"type": "function", "function": {"name": "read", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]
TOOL_TURN = [
    {"role": "assistant", "content": "", "reasoning_content": "need file", "tool_calls": [{"function": {"name": "read", "arguments": {"path": "a.py"}}}]},
    {"role": "tool", "content": "print(1)"},
    {"role": "tool", "content": "Error: not found"},
]


def user(text):
    return {"role": "user", "content": text}


def render(template, messages, **kwargs):
    return template.render(messages=messages, add_generation_prompt=True, **kwargs)


def tagged_chats(mode):
    return [
        [user(f"{tag(mode)} hi")],
        [{"role": "system", "content": "Be terse."}, user(f"hi {tag(mode)}")],
        [user(f"{tag('low')} a"), {"role": "assistant", "content": "b"}, user(f"{tag(mode)} c")],
        [user([{"type": "text", "text": f"{tag(mode)} look"}, {"type": "image"}])],
    ]


def untagged_chats():
    return [
        [user("hi")],
        [{"role": "system", "content": "A"}, {"role": "developer", "content": "B"}, user("hi")],
        [user("<|think_off|> hi")],
        [user("<|think_max|> hi")],
        [user("do it"), *TOOL_TURN],
        [user("q"), {"role": "assistant", "content": "<think>r</think>a"}, user("q2")],
        [user("{REASON:nonsense} hi")],
    ]


KWARG_MATRIX = [
    dict(zip(("enable_thinking", "reasoning_effort", "tool_call_format"), combo))
    for combo in itertools.product((None, True, False), (None, "low", "medium", "high", "none"), (None, "json"))
]


def drop_none(kwargs):
    return {key: value for key, value in kwargs.items() if value is not None}


def check_tagged_modes_match_turbo_brilliance():
    for mode, prefix, chat in itertools.product(MODES, ("", "i"), range(4)):
        messages = tagged_chats(prefix + mode)[chat]
        yield f"tag {prefix}{mode} chat#{chat}", render(MERGED, messages), render(TURBO_BRILLIANCE, messages)


def check_untagged_matches_froggeric():
    for kwargs, messages, tools in itertools.product(KWARG_MATRIX, untagged_chats(), (None, TOOLS)):
        merged_kwargs = drop_none({**kwargs, "tools": tools})
        default_effort = DEFAULT_INSTRUCT_EFFORT if kwargs["enable_thinking"] is False else DEFAULT_EFFORT
        froggeric_kwargs = {"reasoning_effort": default_effort, **merged_kwargs}
        yield f"no tag {merged_kwargs} {messages[-1]['content']!r}", render(MERGED, messages, **merged_kwargs), render(FROGGERIC, messages, **froggeric_kwargs)


def check_request_modes_match_turbo_brilliance():
    messages = [user("hi")]
    for mode, enable_thinking in itertools.product(set(MODES) - set(FROGGERIC_EFFORTS), (True, False)):
        kwargs = {"reasoning_effort": mode, "enable_thinking": enable_thinking}
        yield f"reasoning_effort={mode} thinking={enable_thinking}", render(MERGED, messages, **kwargs), render(TURBO_BRILLIANCE, messages, **kwargs)


def with_default(source, setting, mode):
    return compile_template(re.sub(rf"set {setting} = '\w+'", f"set {setting} = '{mode}'", source))


def check_edited_defaults_match_turbo_brilliance():
    messages = [user("hi")]
    for setting, enable_thinking in (("default_effort", True), ("default_effort_instruct", False)):
        merged = render(with_default(MERGED_SOURCE, setting, "house"), messages, enable_thinking=enable_thinking)
        turbo_brilliance = render(with_default(TURBO_BRILLIANCE_SOURCE, setting, "house"), messages, enable_thinking=enable_thinking)
        yield f"{setting}='house'", merged, turbo_brilliance


def check_tagged_images_keep_vision_ids():
    image = {"type": "image"}
    tagged = [user([{"type": "text", "text": f"{tag('coder')} look"}, image]), {"role": "assistant", "content": "ok"}, user([image, "and this"])]
    untagged = [user([{"type": "text", "text": "look"}, image]), *tagged[1:]]
    expected = render(MERGED, untagged, add_vision_id=True, reasoning_effort="coder")
    yield "vision ids count images in tagged messages", render(MERGED, tagged, add_vision_id=True), expected


def render_minijinja(source, messages, **kwargs):
    env = minijinja.Environment(trim_blocks=True, lstrip_blocks=True)
    env.add_function("raise_exception", raise_exception)
    return env.render_str(source, messages=messages, add_generation_prompt=True, **kwargs)


def check_minijinja_matches_jinja2():
    chats = [*tagged_chats("coder"), *tagged_chats("ioff"), *untagged_chats()]
    for messages, tools in itertools.product(chats, (None, TOOLS)):
        kwargs = drop_none({"tools": tools})
        yield f"minijinja {messages[-1]['content']!r} tools={bool(tools)}", render_minijinja(MERGED_SOURCE, messages, **kwargs), render(MERGED, messages, **kwargs)
    system_only = [{"role": "system", "content": "x"}]
    yield "minijinja system-only request", render_minijinja(MERGED_SOURCE, system_only), render(MERGED, system_only)


def check_agents_contract():
    coder_prompt = render(TURBO_BRILLIANCE, [user(f"{tag('coder')} x")])
    tag_beats_kwargs = render(MERGED, [user(f"{tag('coder')} x")], reasoning_effort="low", enable_thinking=False)
    yield "tag beats request kwargs", tag_beats_kwargs, coder_prompt
    first_tag_kept = render(MERGED, [user(f"{tag('coder')} x"), *TOOL_TURN], tools=TOOLS)
    yield "tag survives tool turns", first_tag_kept.count("Talks like: Concise technical architect"), 1
    compaction = render(MERGED, [user(f"{tag('coder')} x"), {"role": "assistant", "content": "y"}, user(f"{tag('ioff')} summarize")])
    yield "ioff compaction is instruct with no mode prompt", compaction.startswith("<|im_start|>user") and compaction.endswith("<think>\n\n</think>\n\n"), True
    yield "tag stripped", MODE_TAG in tag_beats_kwargs, False


def main():
    checks = (
        check_tagged_modes_match_turbo_brilliance,
        check_untagged_matches_froggeric,
        check_request_modes_match_turbo_brilliance,
        check_edited_defaults_match_turbo_brilliance,
        check_tagged_images_keep_vision_ids,
        check_minijinja_matches_jinja2,
        check_agents_contract,
    )
    failures = 0
    total = 0
    for check in checks:
        for name, actual, expected in check():
            total += 1
            if actual != expected:
                failures += 1
                print(f"FAIL {check.__name__}: {name}")
    print(f"{total - failures}/{total} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
