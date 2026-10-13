# QUARK 4.0 — Interpreter

import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import random
import time
import sys
import re
import ast
import operator
import copy
import builtins
import contextlib
import io
from typing import Any

# Audio is optional. Some systems have pygame installed but no usable audio
# device; that must not prevent the Quark shell from starting.
try:
    import pygame
    pygame.mixer.init()
    HAS_PYGAME = True
except Exception:
    HAS_PYGAME = False

variables = {}
functions = {}
function_visibility = {}
function_parameters = {}
CURRENT_MODULE = None
LAST_CALL_RESULT = None

class _FunctionReturnSignal:
    """Internal control-flow signal carrying a Quark function return value."""
    def __init__(self, value):
        self.value = value

# Diagnostic/bypass state is scoped to the statement currently being executed.
ACTIVE_BYPASS = set()
GLOBAL_BYPASS = set()
ERROR_COUNT = 0
WARNING_COUNT = 0
MAX_EXPRESSION_LENGTH = 4096
MAX_AST_NODES = 512
MAX_INTEGER_BITS = 100_000

ERROR_CATEGORIES = {
    "syntax", "math", "name", "type", "vector", "audio", "file",
    "input", "function", "import", "runtime", "performance", "general"
}
WARNING_CATEGORIES = {"datatype", "performance", "vector", "general"}


def _diagnostic_category(message):
    lower = message.lower().strip()
    if lower.startswith("datatype warning:"):
        return "warning", "datatype"
    if lower.startswith("performance warning:"):
        return "warning", "performance"
    if lower.startswith("vector warning:"):
        return "warning", "vector"
    if lower.startswith("warning:") or lower.startswith("input warning:"):
        return "warning", "general"
    if "math error:" in lower:
        return "error", "math"
    if "vector index error:" in lower or "valid vector" in lower:
        return "error", "vector"
    if "variable '" in lower and ("not found" in lower or "not defined" in lower):
        return "error", "name"
    if "typeerror" in lower or "type error:" in lower or "type mismatch" in lower:
        return "error", "type"
    if "audio error:" in lower:
        return "error", "audio"
    if "file error:" in lower or "read error:" in lower or "write error:" in lower:
        return "error", "file"
    if "function" in lower and "error:" in lower:
        return "error", "function"
    if "import error:" in lower or ("module '" in lower and "not found" in lower):
        return "error", "import"
    if "does not exist" in lower:
        return "error", "file"
    if "input error:" in lower or ("input" in lower and "must be" in lower):
        return "error", "input"
    if "condition error:" in lower or "syntax error:" in lower or "usage:" in lower or "invalid variable" in lower or "unknown command:" in lower:
        return "error", "syntax"
    if "runtime error:" in lower:
        return "error", "runtime"
    if "error:" in lower or lower.startswith("error"):
        return "error", "general"
    return None, None


def qprint(*args, **kwargs):
    """Print output, apply diagnostic bypasses, and colour diagnostics in terminals."""
    global ERROR_COUNT, WARNING_COUNT
    sep = kwargs.get("sep", " ")
    message = sep.join(str(a) for a in args)
    level, category = _diagnostic_category(message)
    if level == "error":
        ERROR_COUNT += 1
        if "error:*" in ACTIVE_BYPASS or f"error:{category}" in ACTIVE_BYPASS:
            return
    elif level == "warning":
        WARNING_COUNT += 1
        if "warning:*" in ACTIVE_BYPASS or f"warning:{category}" in ACTIVE_BYPASS:
            return
        hint_category = category if category in WARNING_CATEGORIES else "general"
        message += f" (Use bypass::warning({hint_category}) or bypass::warning to suppress.)"

    # Use bright ANSI colours only for interactive terminals; redirected output stays clean.
    stream = kwargs.get("file", sys.stdout)
    try:
        use_colour = bool(level and hasattr(stream, "isatty") and stream.isatty() and not os.environ.get("NO_COLOR"))
    except Exception:
        use_colour = False
    if use_colour:
        colour = "\033[91m" if level == "error" else "\033[93m"
        reset = "\033[0m"
        builtins.print(f"{colour}{message}{reset}", end=kwargs.get("end", "\n"), file=stream, flush=kwargs.get("flush", False))
    elif level:
        builtins.print(message, end=kwargs.get("end", "\n"), file=stream, flush=kwargs.get("flush", False))
    else:
        builtins.print(*args, **kwargs)


def value_type(value):
    if isinstance(value, bool): return "boolean"
    if isinstance(value, QuarkVector): return f"vector ({value.mode})"
    if isinstance(value, int): return "integer"
    if isinstance(value, float): return "float"
    if isinstance(value, str): return "string"
    if value is None: return "none"
    return type(value).__name__


def _safe_input(prompt, timeout=None, audio_file=None):
    """Read a line with an optional timeout; works in a normal terminal on Windows/POSIX."""
    start = time.monotonic()
    audio_started = False
    if audio_file:
        if not HAS_PYGAME:
            raise RuntimeError("pygame is required for bypass::input audio")
        if not os.path.isfile(audio_file):
            raise FileNotFoundError(f"Audio file '{audio_file}' was not found")
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        audio_started = True
    try:
        builtins.print(str(prompt) + ("" if str(prompt).endswith(" ") else " "), end="", flush=True)
        if os.name == "nt":
            import msvcrt
            chars = []
            while True:
                if timeout is not None and time.monotonic() - start >= timeout:
                    builtins.print()
                    return None
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\r", "\n"):
                        builtins.print()
                        return "".join(chars)
                    if ch == "\003":
                        raise KeyboardInterrupt
                    if ch == "\b":
                        if chars:
                            chars.pop()
                            builtins.print("\b \b", end="", flush=True)
                    elif ch not in ("\x00", "\xe0"):
                        chars.append(ch)
                        builtins.print(ch, end="", flush=True)
                else:
                    time.sleep(0.02)
        else:
            import select
            while True:
                remaining = None if timeout is None else max(0.0, timeout - (time.monotonic() - start))
                ready, _, _ = select.select([sys.stdin], [], [], min(0.05, remaining) if remaining is not None else 0.05)
                if ready:
                    return sys.stdin.readline().rstrip("\r\n")
                if timeout is not None and remaining <= 0:
                    builtins.print()
                    return None
    finally:
        if audio_started:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass


def _parse_bypass(line):
    """Return (policy, statement, input_options) for a bypass-prefixed statement."""
    match = re.match(r"^bypass::(error|warning)(?:\(([^)]*)\))?\s+(.+)$", line, re.I)
    if match:
        mode, category, statement = match.groups()
        category = category.strip().lower() if category else None
        if category and category not in (ERROR_CATEGORIES if mode.lower() == "error" else WARNING_CATEGORIES):
            qprint(f"Bypass Error: unknown {mode.lower()} category '{category}'. Use help for valid categories.")
            return set(), "", None
        policy = {f"{mode.lower()}:*" if category is None else f"{mode.lower()}:{category}"}
        return policy, statement.strip(), None
    match = re.match(r"^bypass::input\((.*?)\)\s+(.+)$", line, re.I)
    if match:
        options, statement = match.groups()
        timeout = None
        audio = None
        # Function parameters may be used in bypass options, e.g. wait n.
        # Resolve them before deciding whether `wait` is a timeout or audio file.
        options = safe_substitute(options.strip())
        audio_match = re.search(r"\bplay\s+(.+?)(?=\s+wait\s+|$)", options, re.I)
        wait_match = re.search(r"\bwait\s+(.+)$", options, re.I)
        if audio_match:
            audio = parse_literal(audio_match.group(1).strip())
        if wait_match:
            wait_value = wait_match.group(1).strip()
            if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", wait_value):
                timeout = float(wait_value)
            else:
                wait_file = parse_literal(wait_value)
                if not os.path.isfile(str(wait_file)):
                    qprint(f"Input Error: wait audio file '{wait_file}' does not exist.")
                    return set(), "", None
                if not HAS_PYGAME:
                    qprint("Audio Error: pygame is not installed or available.")
                    return set(), "", None
                timeout = float(pygame.mixer.Sound(str(wait_file)).get_length())
        if timeout is not None and timeout < 0:
            qprint("Input Error: timeout cannot be negative.")
            return set(), "", None
        return set(), statement.strip(), {"timeout": timeout, "audio": audio}
    return None, line, None


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
                    r"call|public|private|input|type|vector_push|vector_pop|list|time|wait|bypass|"
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
        qprint(f"Warning: syntax highlighting disabled ({exc}).")
        return None

qprint("Welcome To Quark 4.0, The Future Of Programming!")
time.sleep(0.2)
qprint("Initialising Shell...")
time.sleep(0.2)
qprint("Done!")

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
            except (IndexError, ValueError) as exc:
                raise IndexError(f"vector '{name}' index {index_text} is out of range") from exc
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
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError(f"expression exceeds {MAX_EXPRESSION_LENGTH} characters")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise ValueError(f"expression exceeds {MAX_AST_NODES} syntax nodes")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool, type(None))):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and abs(right) > 10000:
                raise ValueError("exponent magnitude exceeds the safety limit (10000)")
            result = _BIN_OPS[type(node.op)](left, right)
            if isinstance(result, int) and result.bit_length() > MAX_INTEGER_BITS:
                raise ValueError("integer result exceeds the safety limit")
            return result
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
    # Type comparisons must be handled before safe_substitute replaces variable
    # names with their values. `type x != integer` checks x itself; `type_of x`
    # checks the type of the variable whose name is stored in x.
    type_match = re.fullmatch(
        r"\s*type\s+([A-Za-z_]\w*)\s*(==|!=)\s*(integer|float|string|boolean|none|vector)\s*",
        condition_expr, re.I
    )
    if type_match:
        variable_name, op, expected = type_match.groups()
        actual_value = variables.get(variable_name, None)
        actual_type = value_type(actual_value)
        expected = expected.lower()
        if actual_type.startswith("vector"):
            actual_type = "vector"
        return (actual_type == expected) if op == "==" else (actual_type != expected)

    deref_type_match = re.fullmatch(
        r"\s*type_of\s+([A-Za-z_]\w*)\s*(==|!=)\s*(integer|float|string|boolean|none|vector)\s*",
        condition_expr, re.I
    )
    if deref_type_match:
        pointer_name, op, expected = deref_type_match.groups()
        target_name = variables.get(pointer_name)
        if isinstance(target_name, str) and target_name in variables:
            actual_type = value_type(variables[target_name])
        else:
            actual_type = "undefined"
        if actual_type.startswith("vector"):
            actual_type = "vector"
        expected = expected.lower()
        return (actual_type == expected) if op == "==" else (actual_type != expected)

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
        qprint("Condition Error: unsupported condition syntax //Found By QuarkSaviour!")
        return False

def is_function_declaration(line):
    line = sanitize_line(line)
    return (line.startswith("fn ") or line.startswith("public fn ") or
            line.startswith("private fn ")) and line != "fn end"


def parse_function_declaration(line):
    """Parse fn name or fn name(param1, param2), preserving private-by-default visibility."""
    line = sanitize_line(line)
    visibility = "private"
    if line.startswith("public fn "):
        visibility = "public"
        declaration = line[len("public fn "):].strip()
    elif line.startswith("private fn "):
        declaration = line[len("private fn "):].strip()
    elif line.startswith("fn ") and line != "fn end":
        declaration = line[3:].strip()
    else:
        raise ValueError("Invalid function declaration")

    match = re.fullmatch(r"([A-Za-z_]\w*)\s*(?:\((.*)\))?", declaration)
    if not match:
        raise ValueError("Use fn name or fn name(parameter1, parameter2)")
    name, params_text = match.groups()
    params = [] if params_text is None or not params_text.strip() else [p.strip() for p in split_print_items(params_text)]
    if any(not re.fullmatch(r"[A-Za-z_]\w*", param) for param in params):
        raise ValueError("Function parameters must be valid variable names")
    if len(set(params)) != len(params):
        raise ValueError("Function parameter names must be unique")
    return name, visibility, params


def _evaluate_call_argument(argument):
    """Evaluate a call argument as a literal, existing variable, or explicit math expression."""
    argument = argument.strip()
    if argument.startswith("math "):
        return evaluate_expression(argument[5:].strip())
    substituted = safe_substitute(argument)
    return parse_literal(substituted)


def _parse_function_call(text):
    """Return (name, argument strings); no parentheses means a legacy zero-argument call."""
    text = text.strip()
    match = re.fullmatch(r"([A-Za-z_]\w*(?:::[A-Za-z_]\w*)?)\s*(?:\((.*)\))?", text)
    if not match:
        raise ValueError("Use call name or call name(argument1, argument2)")
    name, args_text = match.groups()
    args = [] if args_text is None or not args_text.strip() else split_print_items(args_text)
    if any(not arg for arg in args):
        raise ValueError("Function arguments cannot be empty")
    return name, args


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
    global CURRENT_MODULE, LAST_CALL_RESULT
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

        # A return exits only the current function invocation. Its value is
        # carried back to the caller, which makes recursive functions possible.
        if line == "return" or line.startswith("return "):
            expression = line[6:].strip() if line.startswith("return ") else ""
            try:
                if not expression:
                    return_value = None
                elif expression.startswith("math "):
                    return_value = evaluate_expression(expression[5:].strip())
                elif expression.startswith("call "):
                    run_code([expression])
                    return_value = LAST_CALL_RESULT
                else:
                    return_value = parse_literal(safe_substitute(expression))
            except Exception as exc:
                qprint(f"Function Return Error: {exc} //Found By QuarkSaviour!")
                return_value = None
            CURRENT_MODULE = previous_module
            return _FunctionReturnSignal(return_value)

        if is_function_declaration(line):
            try:
                local_name, visibility, parameters = parse_function_declaration(line)
            except ValueError as exc:
                qprint(f"Function Syntax Error: {exc}")
                line_idx += 1
                continue
            end_idx = find_matching_block_end(code_lines, line_idx, "fn", "fn end")
            if end_idx < 0:
                qprint(f"Syntax Error: Missing 'fn end' for function '{local_name}' //Found By QuarkSaviour!")
                CURRENT_MODULE = previous_module
                return
            full_name = f"{module_name}::{local_name}" if module_name else local_name
            functions[full_name] = code_lines[line_idx + 1:end_idx]
            function_visibility[full_name] = visibility
            function_parameters[full_name] = parameters
            line_idx = end_idx + 1
            continue

        if line.startswith("call "):
            try:
                requested_name, argument_texts = _parse_function_call(line[5:].strip())
            except ValueError as exc:
                qprint(f"Function Syntax Error: {exc}")
                line_idx += 1
                continue
            full_name, qualified = resolve_function_name(requested_name, module_name)
            if full_name not in functions:
                qprint(f"Function Error: '{requested_name}' is not defined //Found By QuarkSaviour!")
                line_idx += 1
                continue
            if qualified and function_visibility.get(full_name) != "public":
                qprint(f"Function Access Error: '{requested_name}' is private and cannot be called through module scope.")
                line_idx += 1
                continue
            if module_name is None and "::" not in requested_name and "::" in full_name:
                qprint(f"Function Error: '{requested_name}' is not available in this scope.")
                line_idx += 1
                continue

            parameters = function_parameters.get(full_name, [])
            if len(argument_texts) != len(parameters):
                qprint(f"Function Argument Error: '{requested_name}' expects {len(parameters)} argument(s), got {len(argument_texts)}.")
                line_idx += 1
                continue
            try:
                argument_values = [_evaluate_call_argument(arg) for arg in argument_texts]
            except Exception as exc:
                qprint(f"Function Argument Error: could not evaluate arguments for '{requested_name}': {exc}")
                line_idx += 1
                continue

            # Bind parameters for this call and restore their prior values afterward.
            # This supports nested calls and avoids leaking parameter names into caller scope.
            missing = object()
            previous_values = {param: variables.get(param, missing) for param in parameters}
            try:
                for param, value in zip(parameters, argument_values):
                    variables[param] = value
                call_result = run_code(functions[full_name], module_name=full_name.split("::", 1)[0] if "::" in full_name else module_name)
                LAST_CALL_RESULT = call_result.value if isinstance(call_result, _FunctionReturnSignal) else None
            finally:
                for param, old_value in previous_values.items():
                    if old_value is missing:
                        variables.pop(param, None)
                    else:
                        variables[param] = old_value
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
                qprint("Syntax Error: Missing 'loop end' //Found By QuarkSaviour!")
                return
            line_idx = end_idx + 1
            continue

        if line == "loop end":
            if loop_stack:
                line_idx = loop_stack[-1]
            else:
                qprint("Syntax Error: 'loop end' without a matching 'game loop'.")
                line_idx += 1
            continue

        execution_result = execute(line)
        if isinstance(execution_result, _FunctionReturnSignal):
            CURRENT_MODULE = previous_module
            return execution_result
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

def _execute_impl(line):
    line = sanitize_line(line)
    if not line or line.startswith("#"):
        return

    parts = line.split(" ", 1)
    cmd = parts[0].strip()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "math":
        try:
            qprint(evaluate_expression(arg))
        except Exception as exc:
            qprint(f"Math Error: {exc} //Found By QuarkSaviour!")

    elif cmd in ("stop", "exit", "kill"):
        qprint("Shell stopped. Thank you for using Quark!")
        raise SystemExit

    elif cmd == "let":
        if "=" not in arg:
            qprint("Usage: let variable = value")
            return
        name_part, value_part = map(str.strip, arg.split("=", 1))
        vec_match = re.fullmatch(r"([A-Za-z_]\w*)\s*\(\s*(.*?)\s*\)", name_part)

        if vec_match:
            v_name, idx_expr = vec_match.groups()
            if v_name not in variables or not isinstance(variables[v_name], QuarkVector):
                qprint(f"Error: '{v_name}' is not a valid vector //Found By QuarkSaviour!")
                return
            try:
                idx = int(evaluate_expression(idx_expr))
                variables[v_name][idx] = parse_literal(safe_substitute(value_part))
            except Exception as exc:
                qprint(f"Vector Index Error: {exc} //Found By QuarkSaviour!")
            return

        if not re.fullmatch(r"[A-Za-z_]\w*", name_part):
            qprint(f"Invalid variable name: {name_part}")
            return

        if value_part.startswith("call "):
            global LAST_CALL_RESULT
            run_code([value_part])
            variables[name_part] = LAST_CALL_RESULT
        elif value_part.startswith("math "):
            try:
                variables[name_part] = evaluate_expression(value_part[5:])
            except Exception as exc:
                qprint(f"Math Error: {exc} //Found By QuarkSaviour!")
        elif value_part.startswith("random "):
            try:
                low, high = parse_random_args(value_part[7:])
                variables[name_part] = random.randint(low, high)
            except Exception:
                qprint("Error: Usage 'let var = random <min> <max>' //Found By QuarkSaviour!")
        else:
            variables[name_part] = parse_literal(safe_substitute(value_part))

    elif cmd == "print":
        if not arg:
            qprint()
        else:
            qprint(*[parse_print_item(item) for item in split_print_items(arg)])

    elif cmd == "type":
        target = arg.strip()
        if target not in variables:
            qprint(f"Error: Variable '{target}' not found //Found By QuarkSaviour!")
        else:
            value = variables[target]
            if isinstance(value, bool):
                qprint("boolean")
            elif isinstance(value, QuarkVector):
                qprint(f"vector ({value.mode})")
            elif isinstance(value, int):
                qprint("integer")
            elif isinstance(value, float):
                qprint("float")
            elif isinstance(value, str):
                qprint("string")
            elif value is None:
                qprint("none")
            else:
                qprint("unknown")

    elif cmd == "vector_push":
        v_parts = arg.split(" ", 1)
        if len(v_parts) != 2:
            qprint("Usage: vector_push <vector> <value>")
            return
        v_name, v_val = v_parts[0].strip(), v_parts[1].strip()
        if v_name in variables and isinstance(variables[v_name], QuarkVector):
            variables[v_name].push(parse_literal(safe_substitute(v_val)))
        else:
            qprint(f"Error: '{v_name}' is not a valid vector //Found By QuarkSaviour!")

    elif cmd == "vector_pop":
        if " -> " not in arg:
            qprint("Usage: vector_pop <vector> -> <variable>")
            return
        v_name, dest_var = map(str.strip, arg.split(" -> ", 1))
        if v_name in variables and isinstance(variables[v_name], QuarkVector):
            vec = variables[v_name]
            variables[dest_var] = vec.pop() if vec.mode == "stack" else vec.dequeue()
        else:
            qprint(f"Error: '{v_name}' is not a valid vector //Found By QuarkSaviour!")

    elif cmd == "repeat":
        if not arg:
            qprint("Usage: repeat <count> <command>")
            return
        first_token, _, remaining_cmd = arg.partition(" ")
        try:
            count = int(safe_substitute(first_token))
            command_to_run = remaining_cmd
        except ValueError:
            count = 1
            command_to_run = arg
        if count < 0:
            qprint("Error: repeat count cannot be negative.")
            return
        if command_to_run:
            for _ in range(count):
                run_code([command_to_run])

    elif cmd == "random":
        try:
            low, high = parse_random_args(arg)
            qprint(random.randint(low, high))
        except Exception:
            qprint("Usage: random <min> <max> //Found By QuarkSaviour!")

    elif cmd == "help":
        help_command()

    elif cmd == "clear":
        result = os.system("cls" if os.name == "nt" else "clear")
        if result != 0:
            qprint("\n" * 100)

    elif cmd == "time":
        qprint(time.strftime("%H:%M:%S"))

    elif cmd == "wait":
        if not HAS_PYGAME:
            qprint("Audio Error: pygame is not installed or available //Found By QuarkSaviour!")
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
                qprint(f"Audio Error: {exc} //Found By QuarkSaviour!")
                return

        try:
            seconds = float(target)
            if seconds < 0:
                raise ValueError
            time.sleep(seconds)
        except ValueError:
            qprint("Usage: wait <seconds> or wait <audio_file>")

    elif cmd == "play":
        if not HAS_PYGAME:
            qprint("Audio Error: pygame is not installed or available //Found By QuarkSaviour!")
            return
        target = safe_substitute(arg.strip())
        filepath = parse_literal(target)
        if not os.path.isfile(filepath):
            qprint(f"Audio Error: File '{filepath}' not found //Found By QuarkSaviour!")
            return
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
        except Exception as exc:
            qprint(f"Audio Error: {exc} //Found By QuarkSaviour!")

    elif cmd in ("run", "game"):
        target = safe_substitute(arg.strip())
        filename = target
        if cmd == "game" and not target.endswith(".qk"):
            filename += ".qk"
        try:
            with open(filename, "r", encoding="utf-8") as file:
                lines = file.readlines()
            if not lines:
                qprint(f"Warning: '{filename}' is empty!")
            else:
                run_code(lines)
        except FileNotFoundError:
            qprint(f"Error: '{filename}' does not exist //Found By QuarkSaviour!")
        except OSError as exc:
            qprint(f"File Error: {exc}")

    elif cmd == "read":
        target = safe_substitute(arg.strip())
        try:
            with open(target, "r", encoding="utf-8") as file:
                qprint(file.read().strip())
        except FileNotFoundError:
            qprint(f"Error: '{target}' does not exist //Found By QuarkSaviour!")
        except OSError as exc:
            qprint(f"Read Error: {exc}")

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
            qprint(f"{cmd.capitalize()} Error: {exc} //Found By QuarkSaviour!")

    elif cmd == "list":
        qprint("--- VARIABLES ---")
        for key, value in variables.items():
            qprint(f"{key} = {value}")
        qprint("--- FUNCTIONS ---")
        for name in functions:
            qprint(f"fn {name}")

    elif cmd == "input":
        if " -> " in arg:
            prompt_text, var_name = map(str.strip, arg.split(" -> ", 1))
            prompt_text = parse_print_item(prompt_text)
        else:
            var_name = arg.strip()
            prompt_text = f"Enter {var_name}: "
        # A function may receive the destination variable's name as a string:
        # `fn read_value(prompt, target)` with `input prompt -> target`.
        if var_name in variables and isinstance(variables[var_name], str):
            candidate = variables[var_name].strip()
            if re.fullmatch(r"[A-Za-z_]\w*", candidate) and candidate != var_name:
                var_name = candidate
        if not re.fullmatch(r"[A-Za-z_]\w*", var_name):
            qprint("Input destination must be a valid variable name.")
            return
        raw_val = input(str(prompt_text) + ("" if str(prompt_text).endswith(" ") else " "))
        new_value = parse_literal(raw_val)
        if var_name in variables and value_type(variables[var_name]) != value_type(new_value):
            qprint(f"Datatype Warning: input changes '{var_name}' from {value_type(variables[var_name])} to {value_type(new_value)}.")
        variables[var_name] = new_value

    elif cmd == "if":
        condition, separator, command = arg.partition(" then ")
        if not separator:
            qprint("Usage: if <condition> then <command>")
            return
        if eval_condition(condition):
            # Preserve the current module namespace for one-line commands.
            # Without this, a recursive call inside an imported module's
            # single-line if loses its module context and appears undefined.
            nested_result = run_code([command], module_name=CURRENT_MODULE)
            if isinstance(nested_result, _FunctionReturnSignal):
                return nested_result

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
                    qprint(f"Import Error: {exc} //Found By QuarkSaviour!")
                    loaded = True
                    break
        if not loaded:
            qprint(f"Module '{mod_name}' not found. //Found By QuarkSaviour!")

    else:
        qprint(f"Unknown command: {cmd} //Found By QuarkSaviour!")


def _warn_before_statement(line):
    """Emit conservative runtime warnings without blocking valid statements."""
    line = sanitize_line(line)
    match = re.match(r"^let\s+([A-Za-z_]\w*)\s*=\s*(.+)$", line)
    if match:
        name, rhs = match.groups()
        if name in variables:
            old_type = value_type(variables[name])
            try:
                if rhs.startswith("math "):
                    new_value = evaluate_expression(rhs[5:])
                elif rhs.startswith("random "):
                    lo, hi = parse_random_args(rhs[7:])
                    new_value = random.randint(lo, hi)
                else:
                    new_value = parse_literal(safe_substitute(rhs))
                new_type = value_type(new_value)
                if old_type != new_type:
                    qprint(f"Datatype Warning: '{name}' changes from {old_type} to {new_type}.")
            except Exception:
                # The normal execution path will report the actual error.
                pass
    repeat_match = re.match(r"^repeat\s+(\d+)\s+", line)
    if repeat_match and int(repeat_match.group(1)) >= 10000:
        qprint("Performance Warning: large repeat count may take time.")
    push_match = re.match(r"^vector_push\s+(\w+)\s+(.+)$", line)
    if push_match:
        name, value_expr = push_match.groups()
        if name in variables and isinstance(variables[name], QuarkVector) and variables[name].elements:
            try:
                new_value = parse_literal(safe_substitute(value_expr))
                old_types = {value_type(v) for v in variables[name].elements}
                if value_type(new_value) not in old_types:
                    qprint(f"Vector Warning: '{name}' will contain mixed data types.")
            except Exception:
                pass
    if re.match(r"^vector_pop\s+\w+\s*->", line):
        name = line.split()[1] if len(line.split()) > 1 else ""
        if name in variables and isinstance(variables[name], QuarkVector) and variables[name].mode == "queue":
            qprint("Performance Warning: queue removal may be slow for large vectors.")


def _handle_global_bypass(line):
    """Handle persistent bypass commands that do not wrap a statement.

    Bare bypass::error / bypass::warning enables global suppression. Append
    off/reset to disable it, or use (category) to target one category.
    """
    global GLOBAL_BYPASS
    match = re.fullmatch(
        r"bypass::(error|warning)(?:\(([^)]*)\))?(?:\s+(on|off|reset))?",
        line.strip(), re.I
    )
    if not match:
        return False
    mode, category, action = match.groups()
    mode = mode.lower()
    category = category.strip().lower() if category else None
    action = (action or "on").lower()
    valid_categories = ERROR_CATEGORIES if mode == "error" else WARNING_CATEGORIES
    if category and category not in valid_categories:
        qprint(f"Bypass Error: unknown {mode} category '{category}'. Use help for valid categories.")
        return True
    key = f"{mode}:*" if category is None else f"{mode}:{category}"
    if action in ("off", "reset"):
        if category is None:
            GLOBAL_BYPASS = {item for item in GLOBAL_BYPASS if not item.startswith(mode + ":")}
        else:
            GLOBAL_BYPASS.discard(key)
    else:
        GLOBAL_BYPASS.add(key)
    if action in ("off", "reset"):
        qprint(f"Global {mode} bypass disabled" + (f" for '{category}'" if category else "") + ".")
    else:
        qprint(f"Global {mode} bypass enabled" + (f" for '{category}'" if category else "") + ".")
    return True


def execute(line):
    """Execute one statement with optional global/per-line bypass and rollback."""
    global ACTIVE_BYPASS, ERROR_COUNT, WARNING_COUNT
    line = sanitize_line(line)
    if _handle_global_bypass(line):
        return
    policy, statement, input_options = _parse_bypass(line)
    if policy is None:
        policy, statement, input_options = set(), line, None
    if not statement:
        return
    old_policy = ACTIVE_BYPASS
    before_errors = ERROR_COUNT
    before_warnings = WARNING_COUNT
    snapshot = None
    capture = None
    result = None
    try:
        ACTIVE_BYPASS = set(GLOBAL_BYPASS) | set(policy)
        if any(p.startswith("error:") for p in policy):
            snapshot = (copy.deepcopy(variables), copy.deepcopy(functions), copy.deepcopy(function_visibility), copy.deepcopy(function_parameters))
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                _warn_before_statement(statement)
                try:
                    if input_options is not None:
                        result = _execute_input_with_options(statement, input_options)
                    else:
                        result = _execute_impl(statement)
                except Exception as exc:
                    if isinstance(exc, IndexError):
                        qprint(f"Vector Index Error: {exc} //Found By QuarkSaviour!")
                    elif isinstance(exc, TypeError):
                        qprint(f"Type Error: {exc} //Found By QuarkSaviour!")
                    else:
                        qprint(f"Runtime Error: {type(exc).__name__}: {exc} //Found By QuarkSaviour!")
            if ERROR_COUNT > before_errors:
                variables.clear(); variables.update(snapshot[0])
                functions.clear(); functions.update(snapshot[1])
                function_visibility.clear(); function_visibility.update(snapshot[2])
                function_parameters.clear(); function_parameters.update(snapshot[3])
                # The failed statement is intentionally skipped, including its partial output.
            else:
                builtins.print(capture.getvalue(), end="")
        else:
            _warn_before_statement(statement)
            if input_options is not None:
                result = _execute_input_with_options(statement, input_options)
            else:
                result = _execute_impl(statement)
    except Exception as exc:
        if isinstance(exc, IndexError):
            qprint(f"Vector Index Error: {exc} //Found By QuarkSaviour!")
        elif isinstance(exc, TypeError):
            qprint(f"Type Error: {exc} //Found By QuarkSaviour!")
        else:
            qprint(f"Runtime Error: {type(exc).__name__}: {exc} //Found By QuarkSaviour!")
        if snapshot is not None:
            variables.clear(); variables.update(snapshot[0])
            functions.clear(); functions.update(snapshot[1])
            function_visibility.clear(); function_visibility.update(snapshot[2])
            function_parameters.clear(); function_parameters.update(snapshot[3])
    finally:
        ACTIVE_BYPASS = old_policy
    return result


def _execute_input_with_options(statement, options):
    """Execute an input command with optional timeout/audio; other commands are rejected."""
    line = sanitize_line(statement)
    if not line.startswith("input "):
        # Shorthand supported: bypass::input(wait 3) Prompt text -> variable
        line = "input " + line
    arg = line[6:].strip()
    if " -> " in arg:
        prompt_text, var_name = map(str.strip, arg.split(" -> ", 1))
        prompt_text = parse_print_item(prompt_text)
        # Permit a function parameter to name the destination variable:
        # `... text -> val`, where val contains the string "name".
        if var_name in variables and isinstance(variables[var_name], str):
            candidate = variables[var_name].strip()
            if re.fullmatch(r"[A-Za-z_]\w*", candidate):
                var_name = candidate
    else:
        var_name = arg
        prompt_text = f"Enter {var_name}: "
    if not re.fullmatch(r"[A-Za-z_]\w*", var_name):
        qprint("Input Error: input destination must be a valid variable name.")
        return
    raw_val = _safe_input(prompt_text, options.get("timeout"), options.get("audio"))
    if raw_val is None:
        qprint("Input Warning: time expired; '{0}' was not changed.".format(var_name))
        return
    old_value = variables.get(var_name, None)
    new_value = parse_literal(raw_val)
    if var_name in variables and value_type(old_value) != value_type(new_value):
        qprint(f"Datatype Warning: input changes '{var_name}' from {value_type(old_value)} to {value_type(new_value)}.")
    variables[var_name] = new_value


def help_command():
    qprint("""Quark 4.0 — Commands and Safety Reference

CORE COMMANDS
help
print <item1>, <item2>
math <expression>
let var = value / math <expression> / random <min> <max>
repeat <count> <command>
if <condition> then <command>
game loop <condition> ... loop end   (condition checked each iteration)
game loop ... loop end               (infinite loop; stop with Ctrl+C)
fn <name> ... fn end                 (private, zero parameters)
fn <name>(a, b) ... fn end           (declare parameters)
private fn <name>(a, b) ... fn end   (explicitly private)
public fn <name>(a, b) ... fn end    (export from an imported module)
call <name>                          (call a zero-parameter function)
call <name>(value1, value2)          (pass arguments to parameters)
call module::name(args...)           (call a public imported function)
return <value>                       (return a value from a function)
let result = call name(args...)      (store a function return value)
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

BYPASS — GLOBAL OR PER STATEMENT
bypass::error
  Globally hide all error diagnostics for later statements. Statements still run;
  this mode does not automatically skip failed statements or roll back their effects.
bypass::error off
  Turn off global error suppression. 'bypass::error reset' is an alias.
bypass::error(math)
  Globally hide only math errors. Use 'bypass::error(math) off' to turn that filter off.
bypass::warning
  Globally hide all warning diagnostics for later statements.
bypass::warning off
  Turn off global warning suppression. 'bypass::warning reset' is an alias.
bypass::warning(datatype)
  Globally hide only datatype warnings. Use 'bypass::warning(datatype) off' to turn it off.

Per-statement forms (only affect the statement on the same line):
bypass::error <statement>
  If that statement reports an error, suppress its diagnostics/output and skip it;
  interpreter state is rolled back where practical.
bypass::error(<category>) <statement>
  Same behaviour for one error category only. Other error categories still show.
bypass::warning <statement>
  Hide warnings for that statement but still execute it.
bypass::warning(<category>) <statement>
  Hide only the named warning category; other warnings remain visible.
bypass::input(wait <seconds>) input <prompt> -> <var>
  Wait for input up to the given number of seconds. Timeout leaves the variable unchanged.
bypass::input(play <audio_file>) input <prompt> -> <var>
  Play audio while waiting; entering a response early stops playback.
bypass::input(play <audio_file> wait <seconds>) input <prompt> -> <var>
  Play audio and time out after the given seconds unless input arrives first.
bypass::input(play <audio_file> wait <audio_file>) input <prompt> -> <var>
  Use the second audio file's duration as the timeout; first audio plays during input.
Examples:
  bypass::input(wait 3) input "Decide Within 3 Seconds Player! (Y/N)" -> choice
  bypass::input(play sample.mp3 wait 3) input "Your choice?" -> choice
  bypass::warning(datatype) let score = "excellent"
  bypass::error
  bypass::error off
  bypass::warning(datatype)
  bypass::warning(datatype) off

ERROR CATEGORIES
syntax, math, name, type, vector, audio, file, input, function, import,
runtime, performance, general
Use: bypass::error(math) math 1 / 0

WARNING CATEGORIES
 datatype  — variable or input changes its value type
 performance — very large repeat counts or potentially slow queue operations
 vector — a vector becomes mixed-type
 general — other non-fatal warnings
Use: bypass::warning(datatype) <statement>

SAFETY NOTES
- Expressions use a restricted syntax; arbitrary Python execution is not allowed.
- Expression length, syntax-tree size, exponent magnitude, and integer result size are limited.
- Vector indexing is checked; invalid indices report an error rather than silently becoming none.
- Per-statement bypass applies only to its prefixed statement. Bare bypass commands persist globally until switched off.
- Bypass hides diagnostics; it does not disable the underlying checks. Global error bypass does not skip failed statements or roll back side effects.
- Quark is implemented in Python, so these are interpreter/runtime safeguards, not a formal proof of memory safety.

FUNCTION PARAMETERS
- Declare parameters with parentheses: fn greet(name, age) ... fn end.
- Pass arguments in the same order: call greet("Anish", 16).
- Functions can return values with `return`; assign them with `let result = call name(args...)`. Recursive calls are supported.
- Arguments can be literals, existing variables, vectors, or 'math <expression>'.
- Argument count must exactly match the declared parameter count.
- Parameter values are available as variables inside the function and are restored after the call.
- Nested and recursive calls are supported. Use `return <value>` and `let result = call name(args...)` to pass results back.

FUNCTION VISIBILITY
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
            qprint("\nQuark shell stopped. Thank you for using Quark!")
            break
        except SystemExit:
            break
        except Exception as exc:
            qprint(f"Runtime Error: {type(exc).__name__}: {exc} //Found By QuarkSaviour!")

if __name__ == "__main__":
    interactive_shell()
