# froggeric + turbo-brilliance chat template merger

Builds `chat_template_merged.jinja` from two parents:

- `chat_template_froggeric.jinja`: the [froggeric fixed Qwen template](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates), used as the base.
- `chat_template_turbo_brilliance.jinja`: the DavidAU turbo-brilliance template, embedded in the model GGUF. It adds the `{REASON:<mode>}` modes that [turbo-brilliance-agents](https://github.com/barrenechea/turbo-brilliance-agents) relies on.

## Usage

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

python3 merge.py                                         # merge the local parents, fetching any that are missing
python3 merge.py --froggeric-rev main                    # refresh froggeric first (branch, tag or commit)
python3 merge.py --turbo-brilliance-repo                 # refresh turbo-brilliance from the default GGUF repo
python3 merge.py --turbo-brilliance-repo DavidAU/<repo>  # or from another turbo-brilliance model
.venv/bin/python check.py                                # verify the result
```

`merge.py` authenticates with your Hugging Face token when one is available (`HF_TOKEN`, or the token saved by `hf auth login`), which avoids anonymous rate limits. All `.jinja` files are gitignored. The parents are fetched on the first run and kept locally until you refresh them. Fetching turbo-brilliance reads only the GGUF metadata header (a few MB), not the weights.

## What the merge does

1. Moves froggeric's `render_content` macro up, so the turbo-brilliance tag scan can use it.
2. Inserts the turbo-brilliance mode prompts and the `{REASON:}` tag scan before froggeric's `<|think_*|>` scan.
3. Moves the turbo-brilliance `default_effort` / `default_effort_instruct` lines to the top. They are the only server-wide default.
4. Selects the mode: a valid tag wins over everything. Otherwise a turbo-brilliance mode name in `reasoning_effort` (or in the defaults) applies. Anything else falls back to froggeric's effort handling.
5. Strips the tag inside each content part, so images in a tagged message keep their `add_vision_id` numbering.

Every edit is anchored on upstream text that must match exactly once. If upstream restructures, `merge.py` stops and names the anchor that broke, instead of writing a corrupt template.

## What `check.py` verifies

- With a tag, every turbo-brilliance mode renders exactly as turbo-brilliance does (tool-free chats).
- Without a tag, the output equals froggeric's across a matrix of `enable_thinking`, `reasoning_effort`, `tool_call_format`, tools, multiple system prompts and `<|think_*|>` tokens.
- Mode names in `reasoning_effort`, and edited defaults, behave as in turbo-brilliance.
- The turbo-brilliance-agents contract: last tag wins, a tag beats request settings, it survives tool turns, `{REASON:ioff}` gives instruct mode, and the tag is stripped.

Froggeric v22 to v22.2 merge cleanly but fail the "same as turbo-brilliance" checks on multi-turn chats. Before v22.3, froggeric dropped empty `<think>` blocks from past assistant turns, and turbo-brilliance keeps them.
