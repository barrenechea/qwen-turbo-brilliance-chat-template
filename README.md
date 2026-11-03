# Turbo-Brilliance Chat Template for Qwen 3.5, 3.6 & 3.8

A drop-in `chat_template.jinja` for Qwen 3.5, 3.6 and 3.8, including [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next), Qwen's preview of the Qwen4 architecture. It combines two templates:

- **[froggeric's fixed Qwen template](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates)** as the base: tool calling (XML or JSON), thinking control, history handling and engine fixes.
- **DavidAU's [Turbo-Brilliance](https://huggingface.co/collections/DavidAU/turbo-brilliance-ai-constructs-50x-reasoning-instruct-6ad18e0e214376f367ecccd1) reasoning modes**: 41 modes (personas, reasoning frameworks, expert panels) you switch per prompt with `{REASON:<mode>}`.

The modes are plain system prompts, so they work on every supported model. DavidAU tuned them on Qwen 3.8, and the default `xhigh` effort uses Qwen 3.8's steering sentence.

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
- Tags in system messages are ignored.
- Without a tag, a mode name also works as `reasoning_effort` (e.g. through `chat_template_kwargs`) on engines that pass it through.
- Without a mode, thinking defaults to `xhigh` effort. To change that, edit `default_effort` / `default_effort_instruct` at the top of the template.

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
- stops a system-only request from crashing vLLM's Rust frontend ([froggeric#109](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates/discussions/109)).

## Works with

[turbo-brilliance-agents](https://github.com/barrenechea/turbo-brilliance-agents): opencode subagents that each run on one Turbo-Brilliance mode.

## Credits and license

- Base template by [froggeric](https://huggingface.co/froggeric), Apache-2.0.
- Turbo-Brilliance modes and prompts by [DavidAU](https://huggingface.co/DavidAU) (David Belton), under his terms. See the notice in the template and his [model cards](https://huggingface.co/DavidAU).
