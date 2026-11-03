# Turbo-Brilliance Chat Template for Qwen 3.5, 3.6 & 3.8

A drop-in `chat_template.jinja` for Qwen 3.5, 3.6 and 3.8, including [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next), Qwen's preview of the Qwen4 architecture. It combines two templates:

- **[froggeric's fixed Qwen template](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates)** as the base: tool calling (XML or JSON), thinking control, history handling and engine fixes.
- **DavidAU's [Turbo-Brilliance](https://huggingface.co/collections/DavidAU/turbo-brilliance-ai-constructs-50x-reasoning-instruct-6ad18e0e214376f367ecccd1) reasoning modes**: 41 modes (personas, reasoning frameworks, expert panels) you switch per prompt with `{REASON:<mode>}`.

The modes are plain system prompts, so they work on every supported model. DavidAU tuned them on Qwen 3.8, and the `x` modes and `xhigh` use Qwen 3.8's steering sentence.

## Usage

**llama.cpp**

```sh
llama-server -m model.gguf --jinja --chat-template-file chat_template.jinja
```

**vLLM**

```sh
vllm serve <model> --chat-template chat_template.jinja
```

**transformers**

```python
tokenizer.chat_template = open("chat_template.jinja").read()
```

**[Strata](https://github.com/Niko1221/Strata)**

The Strata app and CLI both read the template from the model's prepared pack. Set the model up, stop it, replace the template and start it again. `strata models list` shows where your models are.

```sh
# Linux / macOS
cp chat_template.jinja <pack>/tokenizer/chat_template.jinja
```

```powershell
# Windows (PowerShell)
Copy-Item chat_template.jinja <pack>\tokenizer\chat_template.jinja
```

For a source install, use the `tokenizer` folder named in your config JSON.

## Selecting a mode

Put a tag anywhere in a **user** message. The template removes it before the model sees the prompt.

| Tag | Effect |
|---|---|
| `{REASON:coder}` | `coder` mode with thinking on |
| `{REASON:icoder}` | `coder` mode with thinking off (instruct) |
| `{REASON:off}` | no mode prompt, thinking on |
| `{REASON:ioff}` | no mode prompt, thinking off |

- The last tagged user message wins, so a tag in the first message stays active through every tool call.
- A tag overrides request settings such as `enable_thinking` and `reasoning_effort`.
- The first tag in a message counts. A second tag, or any tag after an unknown one, stays as text. The tag must sit inside one text part.
- Tags in system messages are ignored and left as text.
- Tool results sent as user messages wrapped in `<tool_response>` cannot carry a tag, so fetched content cannot switch modes or thinking. Results sent with the `tool` role were never scanned.
- Without a tag, a mode name also works as `reasoning_effort` (e.g. through `chat_template_kwargs`) on engines that pass it through.
- Without a mode, thinking is on at `medium` effort, which adds no system prompt. To change that, edit `default_effort` / `default_effort_instruct` near the top of the template. Leave the `{REASON:help}` text alone: the tag system switches itself off when that text is edited.

## Modes

| Group | Modes |
|---|---|
| Reasoning frameworks | `omni`, `deeptree`, `hyper`, `socrates`, `logic`, `einstein`, `spoon`, `ultra` |
| Same frameworks combined with xhigh effort | `xomni`, `xdeeptree`, `xhyper`, `xsocrates`, `xlogic`, `xeinstein`, `xspoon`, `xhelp` |
| Experts and agents | `holodeck`, `prompt`, `musk`, `curie`, `007`, `joe` |
| Characters and points of view | `pkd`, `neo`, `stark`, `matlock`, `house`, `vader`, `joker`, `quinn` |
| Multi-persona specialists | `brainstorm`, `business`, `coder`, `comedy`, `story`, `teacher` |
| Qwen effort levels | `xhigh`, `medium`, `low` |
| Other | `help`, `off` |

Send `{REASON:help}` and the model explains each mode and which fits your task.

## What every release is checked for

- With a tag, every mode renders byte for byte like DavidAU's template.
- Without a tag, the output matches froggeric's template across thinking, effort, tool-call format, tools, multiple system prompts and inline `<|think_*|>` tokens.
- Jinja2 (transformers) and minijinja (vLLM's Rust frontend) render the same prompt. llama.cpp was checked by hand and matches.

On top of both parents, it also:

- keeps `add_vision_id` image numbering right when a tagged message has images,
- stops a system-only request from crashing vLLM's Rust frontend ([froggeric#109](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates/discussions/109)),
- ignores tags inside tool results that arrive as `<tool_response>` user messages.

## Changelog

<details>
<summary>Update history</summary>

> **2026-11-03 Update (v2): Medium default, tag hardening.**
> 1. **Default effort is `medium`:** an untagged request no longer injects the `xhigh` steering sentence, so the model reasons at its natural length. This follows froggeric's v22.1 change after the runaway-reasoning reports ([froggeric#72](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates/discussions/72)). `{REASON:xhigh}` and the `x` modes still inject it.
> 2. **Tags in tool results are inert:** a tool result that a client sends as a user message wrapped in `<tool_response>` can no longer switch the mode or turn thinking off. Fetched pages cannot steer the template.
> 3. **A tag must sit inside one text part:** a tag split across two text parts is left as plain text instead of selecting a mode and leaking the tag.
> 4. **Documented tag rules:** first tag wins, tags in system messages are ignored and left as text, do not edit the `{REASON:help}` text.
> 5. **Checks (860 -> 985):** tool-result inertness and split tags are covered. Verified byte for byte against Jinja2 on llama.cpp 0.8.0 and on minijinja 2.24 and 3.0.5.
>
> **2026-11-03 Update (v1): First release.**
> 1. **froggeric v22.5 + Turbo-Brilliance:** froggeric's fixed Qwen template with DavidAU's 41 `{REASON:<mode>}` modes spliced in. Tagged renders match DavidAU's template, untagged renders match froggeric's.
> 2. **Vision ids:** `add_vision_id` numbering stays right when a tagged message has images.
> 3. **vLLM Rust frontend crash fix:** a system-only request no longer panics minijinja ([froggeric#109](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates/discussions/109)).
> 4. **Verified on** Jinja2 (transformers), minijinja (vLLM's Rust frontend) and llama.cpp.

</details>

## Works with

[turbo-brilliance-agents](https://github.com/barrenechea/turbo-brilliance-agents): opencode subagents that each run on one Turbo-Brilliance mode.

## Credits and license

- Base template by [froggeric](https://huggingface.co/froggeric), Apache-2.0.
- Turbo-Brilliance modes and prompts by [DavidAU](https://huggingface.co/DavidAU) (David Belton), under his terms. See the notice in the template and his [model cards](https://huggingface.co/DavidAU).
