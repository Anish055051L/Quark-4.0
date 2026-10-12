# QUARK 4.0 — Interpreter

import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import random
import time
import sys
import re
import ast
import operator
from typing import Any

try:
    import pygame
    HAS_PYGAME = True
    pygame.mixer.init()
except ImportError:
    HAS_PYGAME = False

variables = {}
functions = {}
function_visibility = {}
CURRENT_MODULE = None

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.lexers import PygmentsLexer
    from prompt_toolkit.styles import Style
    from pygments.lexer import RegexLexer
    from pygments import token

    class QuarkLexer(RegexLexer):
        name = "Quark"
        aliases = ["quark"]
        tokens = {
            "root": [
                (r"\s+", token.Text),
                (r"#.*$", token.Comment),
                (r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', token.String),
                (
                    r"\b(?:help|print|math|let|repeat|if|then|game|loop|fn|"
                    r"call|public|private|input|type|vector_push|vector_pop|list|time|wait|"
                    r"random|read|run|write|append|clear|import|stop|exit|kill|play)\b",
                    token.Keyword,
                ),
                (r"\b(?:true|false|none)\b", token.Name.Builtin),
                (r"\b\d+(?:\.\d+)?\b", token.Number),
                (r"[+\-*/%=<>!]+", token.Operator),
                (r"\b[A-Za-z_]\w*\b", token.Name.Variable),
                (r".", token.Text),
            ]
        }

    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    PromptSession = None
    PygmentsLexer = None
    Style = None
    QuarkLexer = None

def make_session():
    if not HAS_PROMPT_TOOLKIT:
        return None
    try:
        style = Style.from_dict({
            "pygments.keyword": "#FFA500 bold",
            "pygments.name.variable": "#00BFFF bold",
            "pygments.string": "#FFFFFF",
            "pygments.number": "#FFFFFF bold",
            "pygments.name.builtin": "#00BFFF",
            "pygments.comment": "#808080 italic",
            "pygments.operator": "#FF4500",
        })
        return PromptSession(lexer=PygmentsLexer(QuarkLexer), style=style)
    except Exception as exc:
        print(f"Warning: syntax highlighting disabled ({exc}).")
        return None

print("Welcome To Quark 4.0, The Future Of Programming!")
time.sleep(0.2)
print("Initialising Shell...")
time.sleep(0.2)
print("Done!")

session = make_session()
running = True

class QuarkVector:
    def __init__(self, elements=(), mode="stack"):
        self.elements = list(elements)
        self.mode = mode.lower()

    def push(self, val):
        self.elements.append(val)

    def pop(self):
        if not self.elements:
            return None
        return self.elements.pop()

    def dequeue(self):
        if not self.elements:
            return None
        return self.elements.pop(0)

    def peek(self):
        if not self.elements:
            return None
        return self.elements[-1] if self.mode == "stack" else self.elements[0]

    def length(self):
        return len(self.elements)

    def __getitem__(self, index):
        return self.elements[index]

    def __setitem__(self, index, val):
        self.elements[index] = val

    def __repr__(self):
        inner = ", ".join(repr(e) if isinstance(e, str) else str(e) for e in self.elements)
        return f"[{inner}]" if self.mode == "stack" else f"{{{inner}}}"

def sanitize_line(text):
    return str(text).replace("\xa0", " ").strip()

def split_print_items(arg):
    items, current = [], []
    depth = 0
    quote = None
    escaped = False

    for char in arg:
        if quote is not None:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
            current.append(char)
        elif char in "([{":
            depth += 1
            current.append(char)
        elif char in ")]}":
            depth = max(0, depth - 1)
            current.append(char)
        elif char == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(char)

    if current or arg.endswith(","):
        items.append("".join(current).strip())
    return items

def parse_literal(val_str):
    val_str = val_str.strip()

    if len(val_str) >= 2 and val_str[0] == val_str[-1] and val_str[0] in ("'", '"'):
        try:
            value = ast.literal_eval(val_str)
            if isinstance(value, str):
                return value
        except (ValueError, SyntaxError):
            return val_str[1:-1]

    if val_str.startswith("[") and val_str.endswith("]"):
        inner = val_str[1:-1].strip()
        if not inner:
            return QuarkVector([], "stack")
        return QuarkVector([parse_literal(x.strip()) for x in split_print_items(inner)], "stack")

    if val_str.startswith("{") and val_str.endswith("}"):
        inner = val_str[1:-1].strip()
        if not inner:
            return QuarkVector([], "queue")
        return QuarkVector([parse_literal(x.strip()) for x in split_print_items(inner)], "queue")

    lowered = val_str.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "none":
        return None

    try:
        return int(val_str)
    except ValueError:
        pass
    try:
        return float(val_str)
    except ValueError:
        pass
    return val_str

def safe_substitute(text, local_variables=None):
    scope = variables if local_variables is None else local_variables
    strings = []

    def protect(match):
        strings.append(match.group(0))
        return f"__QUARK_STRING_{len(strings) - 1}__"

    protected = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', protect, text)

    def replace_vector_index(match):
        name, index_text = match.group(1), match.group(2)
        value = scope.get(name)
        if isinstance(value, QuarkVector):
            try:
                index = int(index_text)
                return repr(value[index])
            except (IndexError, ValueError):
                return "None"
        return match.group(0)

    protected = re.sub(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*(-?\d+)\s*\)",
        replace_vector_index,
        protected,
    )

    for name, value in sorted(scope.items(), key=lambda pair: len(pair[0]), reverse=True):
        if callable(value):
            continue
        pattern = rf"\b{re.escape(name)}\b"
        if isinstance(value, QuarkVector):
            replacement = repr(value)
        else:
            replacement = repr(value)
        protected = re.sub(pattern, lambda _m, r=replacement: r, protected)

    def restore(match):
        return strings[int(match.group(1))]

    return re.sub(r"__QUARK_STRING_(\d+)__", restore, protected)

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_}
_CMP_OPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
}

def safe_eval(expression):
    tree = ast.parse(expression, mode="eval")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool, type(None))):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](visit(node.operand))
        if isinstance(node, ast.BoolOp):
            values = [visit(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
        if isinstance(node, ast.Compare):
            left = visit(node.left)
            for op_node, comparator in zip(node.ops, node.comparators):
                right = visit(comparator)
                op_func = _CMP_OPS.get(type(op_node))
                if op_func is None or not op_func(left, right):
                    return False
                left = right
            return True
        if isinstance(node, (ast.List, ast.Tuple)):
            return [visit(item) for item in node.elts]
        raise ValueError("Unsupported expression syntax")

    return visit(tree)

def evaluate_expression(expression):
    substituted = safe_substitute(expression)
    return safe_eval(substituted)

def eval_condition(condition_expr):
    condition = safe_substitute(condition_expr)
    try:
        return bool(safe_eval(condition))
    except Exception:
        match = re.match(r"^\s*(.*?)\s*(==|!=|>=|<=|>|<)\s*(.*?)\s*$", condition)
        if match:
            left, op, right = match.groups()
            def parse_side(side):
                side = side.strip()
                try:
                    return safe_eval(side)
                except Exception:
                    return side.strip("'\"")
            left_value, right_value = parse_side(left), parse_side(right)
            func = {
                "==": operator.eq, "!=": operator.ne, ">=": operator.ge,
                "<=": operator.le, ">": operator.gt, "<": operator.lt,
            }[op]
            try:
                return bool(func(left_value, right_value))
            except TypeError:
                return False
        print("Condition Error: unsupported condition syntax //Found By QuarkSaviour!")
        return False

def is_function_declaration(line):
    line = sanitize_line(line)
    return (line.startswith("fn ") or line.startswith("public fn ") or
            line.startswith("private fn ")) and line != "fn end"


def parse_function_declaration(line):
    line = sanitize_line(line)
    visibility = "private"
    if line.startswith("public fn "):
        visibility = "public"
        name = line[len("public fn "):].strip()
    elif line.startswith("private fn "):
        name = line[len("private fn "):].strip()
    elif line.startswith("fn ") and line != "fn end":
        name = line[3:].strip()
    else:
        raise ValueError("Invalid function declaration")
    if not re.fullmatch(r"[A-Za-z_]\w*", name):
        raise ValueError(f"Invalid function name: {name}")
    return name, visibility


def resolve_function_name(name, module_name=None):
    if "::" in name:
        module, function = name.split("::", 1)
        return f"{module}::{function}", True
    if module_name:
        namespaced = f"{module_name}::{name}"
        if namespaced in functions:
            return namespaced, False
    return name, False


def find_matching_block_end(code_lines, start_idx, start_keyword, end_keyword):
    depth = 0
    for i in range(start_idx, len(code_lines)):
        line = sanitize_line(code_lines[i])
        if start_keyword == "fn" and is_function_declaration(line):
            depth += 1
        elif start_keyword == "game loop" and line.startswith("game loop"):
            depth += 1
        elif line == end_keyword:
            depth -= 1
            if depth == 0:
                return i
    return -1

def parse_random_args(arg):
    values = safe_substitute(arg).split()
    if len(values) != 2:
        raise ValueError("expected two integers")
    low, high = map(int, values)
    return low, high

def run_code(code_lines, module_name=None):
    global CURRENT_MODULE
    previous_module = CURRENT_MODULE
    CURRENT_MODULE = module_name
    line_idx = 0
    total_lines = len(code_lines)
    loop_stack = []

    while line_idx < total_lines:
        line = sanitize_line(code_lines[line_idx])
        if not line or line.startswith("#"):
            line_idx += 1
            continue

        if is_function_declaration(line):
            try:
                local_name, visibility = parse_function_declaration(line)
            except ValueError as exc:
                print(f"Function Syntax Error: {exc}")
                line_idx += 1
                continue
            end_idx = find_matching_block_end(code_lines, line_idx, "fn", "fn end")
            if end_idx < 0:
                print(f"Syntax Error: Missing 'fn end' for function '{local_name}' //Found By QuarkSaviour!")
                CURRENT_MODULE = previous_module
                return
            full_name = f"{module_name}::{local_name}" if module_name else local_name
            functions[full_name] = code_lines[line_idx + 1:end_idx]
            function_visibility[full_name] = visibility
            line_idx = end_idx + 1
            continue

        if line.startswith("call "):
            requested_name = line[5:].strip()
            full_name, qualified = resolve_function_name(requested_name, module_name)
            if full_name in functions:
                if qualified and function_visibility.get(full_name) != "public":
                    print(f"Function Access Error: '{requested_name}' is private and cannot be called through module scope.")
                elif module_name is None and "::" not in requested_name and "::" in full_name:
                    print(f"Function Error: '{requested_name}' is not available in this scope.")
                else:
                    run_code(functions[full_name], module_name=full_name.split("::", 1)[0] if "::" in full_name else module_name)
            else:
                print(f"Function Error: '{requested_name}' is not defined //Found By QuarkSaviour!")
            line_idx += 1
            continue

        if line.startswith("game loop"):
            condition_expr = line[len("game loop"):].strip()
            # An omitted condition means an infinite loop; a supplied condition is checked each iteration.
            if not condition_expr or eval_condition(condition_expr):
                if not loop_stack or loop_stack[-1] != line_idx:
                    loop_stack.append(line_idx)
                line_idx += 1
                continue

            if loop_stack and loop_stack[-1] == line_idx:
                loop_stack.pop()
            end_idx = find_matching_block_end(code_lines, line_idx, "game loop", "loop end")
            if end_idx < 0:
                print("Syntax Error: Missing 'loop end' //Found By QuarkSaviour!")
                return
            line_idx = end_idx + 1
            continue

        if line == "loop end":
            if loop_stack:
                line_idx = loop_stack[-1]
            else:
                print("Syntax Error: 'loop end' without a matching 'game loop'.")
                line_idx += 1
            continue

        execute(line)
        line_idx += 1
    CURRENT_MODULE = previous_module

def parse_print_item(item):
    item = sanitize_line(item)
    if not item:
        return ""

    if item.startswith("math "):
        try:
            return str(evaluate_expression(item[5:]))
        except Exception:
            return "Error //Found By QuarkSaviour!"

    if item.startswith("random "):
        try:
            low, high = parse_random_args(item[7:])
            return str(random.randint(low, high))
        except Exception:
            return "Error //Found By QuarkSaviour!"

    if item in variables:
        return str(variables[item])

    if item.startswith("'") and item.endswith("'") and len(item) > 1:
        inner = item[1:-1]
        if inner == "time":
            return time.strftime("%H:%M:%S")
        if inner in variables:
            return str(variables[inner])
        return inner

    if item.startswith('"') and item.endswith('"'):
        try:
            return ast.literal_eval(item)
        except Exception:
            return item[1:-1]

    if re.fullmatch(r"[A-Za-z_]\w*\s*\(\s*-?\d+\s*\)", item):
        return safe_substitute(item)
    return item

def execute(line):
    line = sanitize_line(line)
    if not line or line.startswith("#"):
        return

    parts = line.split(" ", 1)
    cmd = parts[0].strip()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "math":
        try:
            print(evaluate_expression(arg))
        except Exception as exc:
            print(f"Math Error: {exc} //Found By QuarkSaviour!")

    elif cmd in ("stop", "exit", "kill"):
        print("Shell stopped. Thank you for using Quark!")
        raise SystemExit

    elif cmd == "let":
        if "=" not in arg:
            print("Usage: let variable = value")
            return
        name_part, value_part = map(str.strip, arg.split("=", 1))
        vec_match = re.fullmatch(r"([A-Za-z_]\w*)\s*\(\s*(.*?)\s*\)", name_part)

        if vec_match:
            v_name, idx_expr = vec_match.groups()
            if v_name not in variables or not isinstance(variables[v_name], QuarkVector):
                print(f"Error: '{v_name}' is not a valid vector //Found By QuarkSaviour!")
                return
            try:
                idx = int(evaluate_expression(idx_expr))
                variables[v_name][idx] = parse_literal(safe_substitute(value_part))
            except Exception as exc:
                print(f"Vector Index Error: {exc} //Found By QuarkSaviour!")
            return

        if not re.fullmatch(r"[A-Za-z_]\w*", name_part):
            print(f"Invalid variable name: {name_part}")
            return

        if value_part.startswith("math "):
            try:
                variables[name_part] = evaluate_expression(value_part[5:])
            except Exception as exc:
                print(f"Math Error: {exc} //Found By QuarkSaviour!")
        elif value_part.startswith("random "):
            try:
                low, high = parse_random_args(value_part[7:])
                variables[name_part] = random.randint(low, high)
            except Exception:
                print("Error: Usage 'let var = random <min> <max>' //Found By QuarkSaviour!")
        else:
            variables[name_part] = parse_literal(safe_substitute(value_part))

    elif cmd == "print":
        if not arg:
            print()
        else:
            print(*[parse_print_item(item) for item in split_print_items(arg)])

    elif cmd == "type":
        target = arg.strip()
        if target not in variables:
            print(f"Error: Variable '{target}' not found //Found By QuarkSaviour!")
        else:
            value = variables[target]
            if isinstance(value, bool):
                print("boolean")
            elif isinstance(value, QuarkVector):
                print(f"vector ({value.mode})")
            elif isinstance(value, int):
                print("integer")
            elif isinstance(value, float):
                print("float")
            elif isinstance(value, str):
                print("string")
            elif value is None:
                print("none")
            else:
                print("unknown")

    elif cmd == "vector_push":
        v_parts = arg.split(" ", 1)
        if len(v_parts) != 2:
            print("Usage: vector_push <vector> <value>")
            return
        v_name, v_val = v_parts[0].strip(), v_parts[1].strip()
        if v_name in variables and isinstance(variables[v_name], QuarkVector):
            variables[v_name].push(parse_literal(safe_substitute(v_val)))
        else:
            print(f"Error: '{v_name}' is not a valid vector //Found By QuarkSaviour!")

    elif cmd == "vector_pop":
        if " -> " not in arg:
            print("Usage: vector_pop <vector> -> <variable>")
            return
        v_name, dest_var = map(str.strip, arg.split(" -> ", 1))
        if v_name in variables and isinstance(variables[v_name], QuarkVector):
            vec = variables[v_name]
            variables[dest_var] = vec.pop() if vec.mode == "stack" else vec.dequeue()
        else:
            print(f"Error: '{v_name}' is not a valid vector //Found By QuarkSaviour!")

    elif cmd == "repeat":
        if not arg:
            print("Usage: repeat <count> <command>")
            return
        first_token, _, remaining_cmd = arg.partition(" ")
        try:
            count = int(safe_substitute(first_token))
            command_to_run = remaining_cmd
        except ValueError:
            count = 1
            command_to_run = arg
        if count < 0:
            print("Repeat count cannot be negative.")
            return
        if command_to_run:
            for _ in range(count):
                run_code([command_to_run])

    elif cmd == "random":
        try:
            low, high = parse_random_args(arg)
            print(random.randint(low, high))
        except Exception:
            print("Usage: random <min> <max> //Found By QuarkSaviour!")

    elif cmd == "help":
        help_command()

    elif cmd == "clear":
        result = os.system("cls" if os.name == "nt" else "clear")
        if result != 0:
            print("\n" * 100)

    elif cmd == "time":
        print(time.strftime("%H:%M:%S"))

    elif cmd == "wait":
        if not HAS_PYGAME:
            print("Audio Error: pygame is not installed or available //Found By QuarkSaviour!")
            return
        target = safe_substitute(arg.strip())
        filepath = parse_literal(target)
        
        if os.path.isfile(filepath):
            try:
                sound_obj = pygame.mixer.Sound(filepath)
                duration = sound_obj.get_length()
                time.sleep(duration)
                return
            except Exception as exc:
                print(f"Audio Error: {exc} //Found By QuarkSaviour!")
                return

        try:
            seconds = float(target)
            if seconds < 0:
                raise ValueError
            time.sleep(seconds)
        except ValueError:
            print("Usage: wait <seconds> or wait <audio_file>")

    elif cmd == "play":
        if not HAS_PYGAME:
            print("Audio Error: pygame is not installed or available //Found By QuarkSaviour!")
            return
        target = safe_substitute(arg.strip())
        filepath = parse_literal(target)
        if not os.path.isfile(filepath):
            print(f"Audio Error: File '{filepath}' not found //Found By QuarkSaviour!")
            return
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
        except Exception as exc:
            print(f"Audio Error: {exc} //Found By QuarkSaviour!")

    elif cmd in ("run", "game"):
        target = safe_substitute(arg.strip())
        filename = target
        if cmd == "game" and not target.endswith(".qk"):
            filename += ".qk"
        try:
            with open(filename, "r", encoding="utf-8") as file:
                lines = file.readlines()
            if not lines:
                print(f"Warning: '{filename}' is empty!")
            else:
                run_code(lines)
        except FileNotFoundError:
            print(f"Error: '{filename}' does not exist //Found By QuarkSaviour!")
        except OSError as exc:
            print(f"File Error: {exc}")

    elif cmd == "read":
        target = safe_substitute(arg.strip())
        try:
            with open(target, "r", encoding="utf-8") as file:
                print(file.read().strip())
        except FileNotFoundError:
            print(f"Error: '{target}' does not exist //Found By QuarkSaviour!")
        except OSError as exc:
            print(f"Read Error: {exc}")

    elif cmd in ("write", "append"):
        mode = "w" if cmd == "write" else "a"
        filename, _, content = arg.partition(" ")
        filename = safe_substitute(filename.strip())
        content = content.strip()

        if content == "time":
            text_to_save = time.strftime("%H:%M:%S")
        elif content.startswith("math "):
            try:
                text_to_save = str(evaluate_expression(content[5:]))
            except Exception:
                text_to_save = "Error"
        else:
            text_to_save = content
            if text_to_save.startswith('"') and text_to_save.endswith('"'):
                text_to_save = parse_print_item(text_to_save)
            else:
                text_to_save = safe_substitute(text_to_save)

        try:
            with open(filename, mode, encoding="utf-8") as file:
                file.write(text_to_save + "\n")
        except OSError as exc:
            print(f"{cmd.capitalize()} Error: {exc} //Found By QuarkSaviour!")

    elif cmd == "list":
        print("--- VARIABLES ---")
        for key, value in variables.items():
            print(f"{key} = {value}")
        print("--- FUNCTIONS ---")
        for name in functions:
            print(f"fn {name}")

    elif cmd == "input":
        if " -> " in arg:
            prompt_text, var_name = map(str.strip, arg.split(" -> ", 1))
            prompt_text = parse_print_item(prompt_text)
        else:
            var_name = arg.strip()
            prompt_text = f"Enter {var_name}: "
        if not re.fullmatch(r"[A-Za-z_]\w*", var_name):
            print("Input destination must be a valid variable name.")
            return
        raw_val = input(str(prompt_text) + ("" if str(prompt_text).endswith(" ") else " "))
        variables[var_name] = parse_literal(raw_val)

    elif cmd == "if":
        condition, separator, command = arg.partition(" then ")
        if not separator:
            print("Usage: if <condition> then <command>")
            return
        if eval_condition(condition):
            run_code([command])

    elif cmd == "import":
        mod_name = arg.strip()
        loaded = False
        for filename in (mod_name, mod_name + ".qm", mod_name + ".qk"):
            if os.path.isfile(filename):
                try:
                    with open(filename, "r", encoding="utf-8") as file:
                        run_code(file.readlines(), module_name=mod_name)
                    loaded = True
                    break
                except OSError as exc:
                    print(f"Import Error: {exc} //Found By QuarkSaviour!")
                    loaded = True
                    break
        if not loaded:
            print(f"Module '{mod_name}' not found. //Found By QuarkSaviour!")

    else:
        print(f"Unknown command: {cmd} //Found By QuarkSaviour!")

def help_command():
    print("""Quark 4.0 Commands:
help
print <item1>, <item2>
math <expression>
let var = value / math <expression> / random <min> <max>
repeat <count> <command>
if <condition> then <command>
game loop <condition> ... loop end   (condition checked each iteration)
game loop ... loop end               (infinite loop; stop with Ctrl+C)
fn <name> ... fn end                 (private by default)
private fn <name> ... fn end         (explicitly private)
public fn <name> ... fn end          (export from an imported module)
call <name>                          (call a local function)
call module::name                    (call a public imported function)
input <prompt> -> <var>  (or input <var>)
type <var>
vector_push <vector> <value>
vector_pop <vector> -> <var>
list
time
wait <seconds> or wait <audio_file>
play <file>
random <min> <max>
read <file>
run <file>
game <file>  (runs a .qk file; legacy alias for run)
write <file> <content>
append <file> <content>
clear
import <module> (.qk or .qm)
stop / exit / kill

Function visibility:
- Functions are private by default, including plain 'fn name'.
- 'private fn name' explicitly marks a private function.
- Only 'public fn name' can be accessed as module::name.
- Inside a module, its functions can call its own private functions by name.
""")

def get_input(prompt):
    if session is not None:
        return session.prompt(prompt)
    return input(prompt)

def interactive_shell():
    global running
    while running:
        try:
            user_input = sanitize_line(get_input(">>> "))
            if not user_input:
                continue

            if user_input.startswith("game loop") or is_function_declaration(user_input):
                buffer = [user_input]
                is_loop = user_input.startswith("game loop")
                start_keyword = "game loop" if is_loop else "fn"
                end_keyword = "loop end" if is_loop else "fn end"
                depth = 1

                while depth > 0:
                    sub_line = sanitize_line(get_input("... "))
                    buffer.append(sub_line)
                    if start_keyword == "fn" and is_function_declaration(sub_line):
                        depth += 1
                    elif start_keyword == "game loop" and sub_line.startswith("game loop"):
                        depth += 1
                    elif sub_line == end_keyword:
                        depth -= 1
                run_code(buffer)
            else:
                run_code([user_input])

        except (KeyboardInterrupt, EOFError):
            print("\nQuark shell stopped. Thank you for using Quark!")
            break
        except SystemExit:
            break
        except Exception as exc:
            print(f"Runtime Error: {type(exc).__name__}: {exc} //Found By QuarkSaviour!")

if __name__ == "__main__":
    interactive_shell()
