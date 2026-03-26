# zap - Shell Orchestrator

zap is a lightweight automation engine that can turn complex shell command chains into simple reusable shortcuts. It allows you to define workflows in JSON that support dynamic arguments, command nesting, and variable substitution.

It also includes AI integration. This can be used to automatically name git commits as an example. The tool is designed to be flexible.


## Requirements

- [Ollama](https://ollama.com) installed on device with a model installed
- [Python](https://www.python.org/) installed on device


## Installation and setup

To install, first clone the repository, and make zap.py executable or add it to your PATH.
```bash
git clone https://github.com/Aiden-Jun/zap.git
```

MacOS
```bash
pip3 install -e 
```

Windows
```bash
pip install -e
```

### Set a model
In `mcalls.json`, edit the `model` variable to whatever Ollama model you want to use. The default is `qwen3.5:0.8b`.


## Usage

### Create a zap

In `zaps.json`, add a new entry with your zap name as the key and an array of commands as the value:

```json
{
  "myzap": [
    "echo Hello",
    "git status"
  ]
}
```

Then run it with:
```bash
zap myzap
```


## Syntax Reference

### Arguments

**`%0`, `%1`, `%2`, etc** are positional arguments passed to the zap.

```json
{
  "greet": ["echo Hello %0"]
}
```
```bash
zap greet World
```


### Shell Execution

**`%o(command)`** executes a shell command inline and substitutes the output.

```json
{
  "pwd-labeled": ["echo Current: %o(pwd)"]
}
```
```bash
zap pwd-labeled
```

The output of the nested command is captured and inserted into the parent command.


### AI Calls (mcalls)

**`%gN(args...)`** calls an AI prompt defined in `mcalls.json`.

- `N` is the key index referencing a prompt in `mcalls.json`
- Arguments are passed to the prompt using `%0`, `%1`, etc.

Define a mcall in `mcalls.json`:
```json
{
  "model": "qwen3.5:0.8b",
  "0": "Suggest a concise git commit message for: %0"
}
```

Use it in a zap:
```json
{
  "commit-msg": ["echo %g0(%o(git diff --staged))"]
}
```
```bash
git add .
zap commit-msg
```

This can be taken further by making an all-in-one zap.


## Processing Order

Commands are processed in this order:

1. **Argument substitution** (`%0`, `%1`, etc.) - replaced with zap arguments
2. **AI calls** (`%gN(...)`) - processed before shell execution, allowing AI output to be used as shell arguments
3. **Shell execution** (`%o(...)`) - shell commands run last