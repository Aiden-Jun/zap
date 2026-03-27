from clean_ollama import Client, Message, Role
import sys
import json
import subprocess
import re
import os


DEFAULT_MODEL = "qwen3.5:0.8b"
ZAPS_FILE = "zaps.json"
MCALLS_FILE = "mcalls.json"
SETTINGS_FILE = "settings.json"

_ZAP_DIR = os.path.dirname(os.path.abspath(__file__))
ZAPS_PATH = os.path.join(_ZAP_DIR, ZAPS_FILE)
MCALLS_PATH = os.path.join(_ZAP_DIR, MCALLS_FILE)
SETTINGS_PATH = os.path.join(_ZAP_DIR, SETTINGS_FILE)

if os.path.exists(ZAPS_PATH):
    with open(ZAPS_PATH, "r") as f:
        zaps = json.load(f)
else:
    zaps = {}

if os.path.exists(MCALLS_PATH):
    with open(MCALLS_PATH, "r") as f:
        mcalls = json.load(f)
else:
    mcalls = {}

if os.path.exists(SETTINGS_PATH):
    with open(SETTINGS_PATH, "r") as f:
        settings = json.load(f)
else:
    settings = {}


def run_shell(command: str) -> str:
    if not command.strip():
        return ""

    print(f"[RUN] {command}")

    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=sys.stdin,
            text=True,
            bufsize=1
        )

        output_lines = []

        for line in process.stdout:
            print(line, end="")
            output_lines.append(line)

        for line in process.stderr:
            print(line, end="", file=sys.stderr)

        process.wait()

        return "".join(output_lines).strip()

    except Exception as e:
        print(f"[ERROR] Shell command failed: {e}", file=sys.stderr)
        return ""


def run_ai(prompt: str, model_name: str) -> str:
    try:
        client = Client(model_name)
        messages = [Message(Role.USER, prompt)]
        _, response, _ = client.generate(messages)
        text = response.strip()
        print(f"[AI] {text}")
        return text
    except Exception as e:
        print(f"[ERROR] AI call failed: {e}", file=sys.stderr)
        return ""


def find_closing_paren(s: str, start: int) -> int:
    depth = 0
    in_quote = None

    for i in range(start, len(s)):
        ch = s[i]

        if in_quote:
            if ch == in_quote:
                in_quote = None
        else:
            if ch in ('"', "'"):
                in_quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
    return -1


def replace_o(cmd: str) -> str:
    while True:
        idx = cmd.find("%o(")
        if idx == -1:
            break
        close = find_closing_paren(cmd, idx + 2)
        if close == -1:
            print("[WARN] Unmatched %o( in command", file=sys.stderr)
            break
        shell_cmd = cmd[idx + 3:close]
        output = run_shell(shell_cmd)
        cmd = cmd[:idx] + output + cmd[close + 1:]
    return cmd


def split_args(s: str) -> list[str]:
    args = []
    depth = 0
    current = []
    in_quote = None

    for ch in s:
        if in_quote:
            current.append(ch)
            if ch == in_quote:
                in_quote = None
        else:
            if ch in ('"', "'"):
                in_quote = ch
                current.append(ch)
            elif ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                val = "".join(current).strip()
                if (val.startswith('"') and val.endswith('"')) or \
                        (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                args.append(val)
                current = []
            else:
                current.append(ch)

    if current or args:
        val = "".join(current).strip()
        if (val.startswith('"') and val.endswith('"')) or \
                (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        args.append(val)

    return args


def replace_g(cmd: str) -> str:
    pattern = re.compile(r"%g(\d+)\(")
    result = ""
    i = 0

    current_model = settings.get("model", DEFAULT_MODEL)

    while i < len(cmd):
        match = pattern.match(cmd, i)
        if match:
            mcall_key = match.group(1)
            close = find_closing_paren(cmd, match.end() - 1)
            if close == -1:
                print("[WARN] Unmatched %gN( in command", file=sys.stderr)
                result += cmd[i:]
                break

            raw_args = cmd[match.end():close]
            args = split_args(raw_args) if raw_args.strip() else []

            args = [replace_g(replace_o(a)) for a in args]

            if mcall_key not in mcalls:
                print(f"[ERROR] No mcall with key '{mcall_key}'", file=sys.stderr)
                result += ""
                i = close + 1
                continue

            prompt = mcalls[mcall_key]

            for idx in sorted(range(len(args)), reverse=True):
                prompt = re.sub(rf"%{idx}(?!\d)", lambda m: args[idx], prompt)

            unreplaced = re.findall(r"%\d+", prompt)
            if unreplaced:
                print(f"[WARN] Unreplaced mcall args in prompt: {unreplaced}", file=sys.stderr)

            ai_output = run_ai(prompt, current_model)

            if settings.get("double_check_ai_output"):
                approval = input("[Double check] Approve AI output? [y/n]: ")
                while approval.lower() not in ["y", "n"]:
                    print(f"[WARN] {approval} is not recognized")
                    approval = input("[Double check] Approve AI output? [y/n]: ")
                if approval.lower() == "n":
                    print("[Double check] AI output rejected")
                    quit()

            result += ai_output
            i = close + 1
        else:
            result += cmd[i]
            i += 1
    return result


def run_zap(name: str, args: list[str]):
    if name not in zaps:
        print(f"No zap named '{name}'")
        return

    for cmd in zaps[name]:
        for i in sorted(range(len(args)), reverse=True):
            cmd = re.sub(rf"%{i}(?!\d)", lambda m: args[i], cmd)

        unreplaced = re.findall(r"%\d+", cmd)
        if unreplaced:
            print(f"[WARN] Unreplaced args in command: {unreplaced}", file=sys.stderr)

        cmd = replace_g(cmd)

        cmd = replace_o(cmd)

        run_shell(cmd)


def main():
    if len(sys.argv) < 2:
        print("Usage: zap <command> [args...]")
        sys.exit(1)

    zap_name = sys.argv[1]
    zap_args = sys.argv[2:]
    run_zap(zap_name, zap_args)


if __name__ == "__main__":
    main()