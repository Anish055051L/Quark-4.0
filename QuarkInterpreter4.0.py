# QUARK 4.0: MASTER GAMING & VECTOR SUPPORT
import random
import time
import sys
import os
import re

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.lexers import PygmentsLexer
    from pygments.lexer import RegexLexer
    from pygments import token
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

variables = {}
functions = {}

print("Welcome To Quark 4.0, The Future Of Programming! ")
time.sleep(1)
print("Initialising Shell... ")
time.sleep(1)
print("Done!")

running = True

# CUSTOM PYGMENTS LEXER FOR REAL-TIME COLORING
# Setup Interactive Session with Real-Time Bright Color Highlighting
if HAS_PROMPT_TOOLKIT:
    from prompt_toolkit.styles import Style
    # High-contrast, vibrant RGB hex styles for the Quark shell
    custom_style = Style.from_dict({
        'keyword': '#FFA500 bold',          # Bright Orange for Keywords
        'name.variable': '#00BFFF bold',      # Light/Sky Blue for Variables & Vectors
        'string': '#FFFFFF',                  # Bright White for Strings
        'number': '#FFFFFF bold',             # Bright White for Numbers
        'name.builtin': '#00BFFF',            # Light Blue for Builtins (true/false/none)
        'comment': '#808080 italic',          # Muted Gray for Comments
        'operator': '#FF4500',                # Orangey-Red for Operators
    })
    session = PromptSession(lexer=PygmentsLexer(QuarkLexer), style=custom_style)
else:
    session = None

# VECTOR DATA STRUCTURE CLASS
class QuarkVector:
    def __init__(self, elements, mode="stack"):
        self.elements = list(elements)
        self.mode = mode.lower()  # "stack" or "queue"

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
        inner = ", ".join(str(e) for e in self.elements)
        if self.mode == "stack":
            return f"[{inner}]"
        else:
            return f"{{{inner}}}"

def sanitize_line(text):
    return text.replace('\xa0', ' ').strip()

def safe_substitute(text, local_variables=None):
    scope = variables if local_variables is None else local_variables
    strings = []

    def protect(match):
        strings.append(match.group(0))
        return f"__QUARK_STRING_{len(strings)-1}__"

    protected = re.sub(r'"[^"]*"|\'[^\']*\'', protect, text)

    # Replace vector index calls like a(1) first
    def replace_vector_index(m):
        v_name = m.group(1)
        idx = int(m.group(2))
        if v_name in scope and isinstance(scope[v_name], QuarkVector):
            try:
                return str(scope[v_name][idx])
            except IndexError:
                return "IndexError"
        return m.group(0)

    protected = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*(\d+)\s*\)', replace_vector_index, protected)

    for name, value in sorted(scope.items(), key=lambda x: len(x[0]), reverse=True):
        if isinstance(value, QuarkVector):
            pattern = rf"\b{re.escape(name)}\b"
            protected = re.sub(pattern, repr(value), protected)
            continue
        if callable(value):
            continue

        pattern = rf"\b{re.escape(name)}\b"
        protected = re.sub(
            pattern,
            repr(value) if isinstance(value, str) else str(value),
            protected
        )

    def restore(match):
        return strings[int(match.group(1))]

    return re.sub(r"__QUARK_STRING_(\d+)__", restore, protected)

def parse_literal(val_str):
    val_str = val_str.strip()
    
    if val_str.startswith("[") and val_str.endswith("]"):
        inner = val_str[1:-1].strip()
        if not inner:
            return QuarkVector([], "stack")
        raw_items = [item.strip() for item in inner.split(",")]
        parsed_items = [parse_literal(item) for item in raw_items]
        return QuarkVector(parsed_items, "stack")
        
    elif val_str.startswith("{") and val_str.endswith("}"):
        inner = val_str[1:-1].strip()
        if not inner:
            return QuarkVector([], "queue")
        raw_items = [item.strip() for item in inner.split(",")]
        parsed_items = [parse_literal(item) for item in raw_items]
        return QuarkVector(parsed_items, "queue")

    if val_str.lower() == "true": return True
    if val_str.lower() == "false": return False
    if val_str.lower() == "none": return None

    try:
        return int(val_str)
    except ValueError:
        pass

    try:
        return float(val_str)
    except ValueError:
        pass

    return val_str

def split_print_items(arg):
    items = []
    current = []
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
        elif char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
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

def parse_print_item(item):
    item = sanitize_line(item)

    if item.startswith("math "):
        expr = safe_substitute(item[5:])
        try:
            return str(eval(expr))
        except Exception:
            return "Error //Found By QuarkSaviour!"

    elif item.startswith("random "):
        try:
            low, high = map(int, safe_substitute(item[7:]).split())
            return str(random.randint(low, high))
        except ValueError:
            return "Error //Found By QuarkSaviour!"

    def replace_quoted_var(match):
        var_name = match.group(1)
        if var_name == "time":
            return time.strftime("%H:%M:%S")
        val = variables.get(var_name, f"'{var_name}'")
        return str(val)

    if item.startswith("'") and item.endswith("'") and len(item) > 1:
        inner = item[1:-1]
        if inner == "time":
            return time.strftime("%H:%M:%S")
        val = variables.get(inner, item)
        return str(val)

    item = re.sub(r"'([a-zA-Z_][a-zA-Z0-9_]*)'", replace_quoted_var, item)
    return item

def eval_condition(condition_expr):
    condition = safe_substitute(condition_expr)

    def quote_words(expr):
        for op in ("==", "!=", ">=", "<=", ">", "<"):
            if op in expr:
                left, right = expr.split(op, 1)
                left, right = left.strip(), right.strip()
                try:
                    eval(left)
                except Exception:
                    if not left.isdigit() and not (left.startswith('"') or left.startswith("'")):
                        left = f"'{left}'"
                try:
                    eval(right)
                except Exception:
                    if not right.isdigit() and not (right.startswith('"') or right.startswith("'")):
                        right = f"'{right}'"
                return f"{left} {op} {right}"
        return expr

    try:
        return bool(eval(condition))
    except (SyntaxError, NameError):
        try:
            return bool(eval(quote_words(condition)))
        except Exception as e:
            print(f"Condition Error: {e} //Found By QuarkSaviour!")
            return False
    except Exception as e:
        print(f"Condition Error: {e} //Found By QuarkSaviour!")
        return False

def find_matching_block_end(code_lines, start_idx, start_keyword, end_keyword):
    depth = 0
    for i in range(start_idx, len(code_lines)):
        l = sanitize_line(code_lines[i])
        if start_keyword == "fn" and l.startswith("fn ") and not l.startswith("fn end"):
            depth += 1
        elif start_keyword == "game loop" and l.startswith("game loop"):
            depth += 1
        elif l == end_keyword:
            depth -= 1
            if depth == 0:
                return i
    return start_idx

def run_code(code_lines):
    line_idx = 0
    total_lines = len(code_lines)
    loop_stack = []

    while line_idx < total_lines:
        line = sanitize_line(code_lines[line_idx])

        if not line or line.startswith("#"):
            line_idx += 1
            continue

        if line.startswith("fn ") and not line.startswith("fn end"):
            func_name = line[3:].strip()
            end_idx = find_matching_block_end(code_lines, line_idx, "fn", "fn end")
            if end_idx == line_idx:
                print(f"Syntax Error: Missing 'fn end' for function '{func_name}' //Found By QuarkSaviour!")
                break
            functions[func_name] = code_lines[line_idx + 1 : end_idx]
            line_idx = end_idx + 1
            continue

        elif line.startswith("call "):
            func_name = line[5:].strip()
            if func_name in functions:
                run_code(functions[func_name])
            else:
                print(f"Function Error: '{func_name}' is not defined //Found By QuarkSaviour!")

        elif line.startswith("game loop"):
            condition_expr = line[len("game loop"):].strip()
            if eval_condition(condition_expr):
                if not loop_stack or loop_stack[-1] != line_idx:
                    loop_stack.append(line_idx)
            else:
                if loop_stack and loop_stack[-1] == line_idx:
                    loop_stack.pop()
                end_idx = find_matching_block_end(code_lines, line_idx, "game loop", "loop end")
                if end_idx == line_idx:
                    print("Syntax Error: Missing 'loop end' //Found By QuarkSaviour!")
                    break
                line_idx = end_idx

        elif line == "loop end":
            if loop_stack:
                line_idx = loop_stack[-1] - 1

        else:
            execute(line)

        line_idx += 1

def execute(line):
    line = sanitize_line(line)
    if not line or line.startswith("#"):
        return

    parts = line.split(" ", 1)
    cmd = parts[0].strip()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "math":
        expression = safe_substitute(arg)
        try:
            print(eval(expression))
        except Exception as e:
            print(f"Math Error: {e} //Found By QuarkSaviour!")

    elif cmd in ("stop", "exit", "kill"):
        print("Shell Stopped Working. Thank You For Using Quark! ")
        sys.exit()

    elif cmd == "let":
        if "=" in arg:
            name_part, value_part = arg.split("=", 1)
            name_part = name_part.strip()
            value_part = value_part.strip()
            vec_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*(.*?)\s*\)$", name_part)
            if vec_match:
                v_name = vec_match.group(1)
                idx_expr = vec_match.group(2)
                if v_name in variables and isinstance(variables[v_name], QuarkVector):
                    try:
                        idx = int(eval(safe_substitute(idx_expr)))
                        val_subbed = safe_substitute(value_part)
                        variables[v_name][idx] = parse_literal(val_subbed)
                    except Exception as e:
                        print(f"Vector Index Error: {e} //Found By QuarkSaviour!")
                else:
                    print(f"Error: '{v_name}' is not a valid vector //Found By QuarkSaviour!")
            else:
                if value_part.startswith("math "):
                    expression = safe_substitute(value_part[5:])
                    try:
                        variables[name_part] = eval(expression)
                    except Exception as e:
                        print(f"Math Error: {e} //Found By QuarkSaviour!")
                elif value_part.startswith("random "):
                    try:
                        low, high = map(int, safe_substitute(value_part[7:]).split())
                        variables[name_part] = random.randint(low, high)
                    except ValueError:
                        print("Error: Usage 'let var = random <min> <max>' //Found By QuarkSaviour!")
                else:
                    subbed = safe_substitute(value_part)
                    variables[name_part] = parse_literal(subbed)

    elif cmd == "print":
        if not arg:
            print()
            return
        output = [parse_print_item(item) for item in split_print_items(arg)]
        print(*output)

    elif cmd == "type":
        target_var = arg.strip()
        if target_var in variables:
            val = variables[target_var]
            if isinstance(val, QuarkVector):
                print(f"vector ({val.mode})")
            elif isinstance(val, int):
                print("integer")
            elif isinstance(val, float):
                print("float")
            elif isinstance(val, str):
                print("string")
            elif isinstance(val, bool):
                print("boolean")
            else:
                print("unknown")
        else:
            print(f"Error: Variable '{target_var}' not found //Found By QuarkSaviour!")

    elif cmd == "vector_push":
        v_parts = arg.split(" ", 1)
        if len(v_parts) == 2:
            v_name, v_val = v_parts[0].strip(), v_parts[1].strip()
            if v_name in variables and isinstance(variables[v_name], QuarkVector):
                variables[v_name].push(parse_literal(v_val))
            else:
                print(f"Error: '{v_name}' is not a valid vector //Found By QuarkSaviour!")

    elif cmd == "vector_pop":
        if " -> " in arg:
            v_name, dest_var = arg.split(" -> ", 1)
            v_name, dest_var = v_name.strip(), dest_var.strip()
            if v_name in variables and isinstance(variables[v_name], QuarkVector):
                vec = variables[v_name]
                ans = vec.pop() if vec.mode == "stack" else vec.dequeue()
                variables[dest_var] = ans
            else:
                print(f"Error: '{v_name}' is not a valid vector //Found By QuarkSaviour!")

    elif cmd == "repeat":
        if not arg:
            print("Usage: repeat <count> <command> //Found By QuarkSaviour!")
            return
        first_token, _, remaining_cmd = arg.partition(" ")
        first_token_sub = safe_substitute(first_token)
        try:
            count = int(first_token_sub)
            command_to_run = remaining_cmd
        except ValueError:
            count = 1
            command_to_run = arg

        if command_to_run:
            for _ in range(count):
                run_code([command_to_run])

    elif cmd == "random":
        try:
            low, high = map(int, safe_substitute(arg).split())
            print(random.randint(low, high))
        except ValueError:
            print("Usage: random <min> <max> //Found By QuarkSaviour!")

    elif cmd == "help":
        help()

    elif cmd == "clear":
        result = os.system("cls" if os.name == "nt" else "clear")
        if result != 0:
            print("\n" * 100)

    elif cmd == "time":
        print(time.strftime("%H:%M:%S"))

    elif cmd == "wait":
        try:
            time.sleep(float(safe_substitute(arg)))
        except ValueError:
            print("Usage: wait <seconds> //Found By QuarkSaviour!")

    elif cmd in ("run", "game"):
        target = safe_substitute(arg.strip())
        ext = ".qk" if cmd == "game" and not target.endswith(".qk") else ""
        filename = target + ext
        try:
            with open(filename, "r", encoding="utf-8") as file:
                lines = file.readlines()
                if not lines:
                    print(f"Warning: '{filename}' is empty! //Found By QuarkSaviour!")
                else:
                    run_code(lines)
        except FileNotFoundError:
            print(f"Error: '{filename}' does not exist //Found By QuarkSaviour!")

    elif cmd == "read":
        target = safe_substitute(arg.strip())
        try:
            with open(target, "r", encoding="utf-8") as file:
                print(file.read().strip())
        except FileNotFoundError:
            print(f"Error: '{target}' does not exist //Found By QuarkSaviour!")

    elif cmd in ("write", "append"):
        mode = "w" if cmd == "write" else "a"
        filename, _, content = arg.partition(" ")
        filename = safe_substitute(filename.strip())
        content = content.strip()

        if content == "time":
            text_to_save = time.strftime("%H:%M:%S")
        elif content.startswith("math "):
            try:
                text_to_save = str(eval(safe_substitute(content[5:])))
            except Exception:
                text_to_save = "Error"
        else:
            text_to_save = safe_substitute(content)

        try:
            with open(filename, mode, encoding="utf-8") as file:
                file.write(text_to_save + "\n")
        except Exception as e:
            print(f"{cmd.capitalize()} Error: {e} //Found By QuarkSaviour!")

    elif cmd == "list":
        print("--- VARIABLES ---")
        for k, v in variables.items():
            print(f"{k} = {v}")
        print("--- FUNCTIONS ---")
        for k in functions:
            print(f"fn {k}")

    elif cmd == "input":
        if " -> " in arg:
            prompt_text, var_name = arg.split(" -> ", 1)
            var_name = var_name.strip()

            def replace_quoted_var(match):
                var = match.group(1)
                if var == "time":
                    return time.strftime("%H:%M:%S")
                return str(variables.get(var, f"'{var}'"))

            prompt_text = prompt_text.strip()
            prompt_text = re.sub(r"'([a-zA-Z_][a-zA-Z0-9_]*)'", replace_quoted_var, prompt_text)
            raw_val = input(prompt_text + " ")
            variables[var_name] = parse_literal(raw_val)
        else:
            var_name = arg.strip()
            raw_val = input(f"Enter {var_name}: ")
            variables[var_name] = parse_literal(raw_val)

    elif cmd == "if":
        condition, _, command = arg.partition(" then ")
        if eval_condition(condition):
            run_code([command])

    elif cmd == "import":
        mod_name = arg.strip()
        loaded = False
        extensions = ["", ".qm", ".qk"]
        for ext in extensions:
            filename = mod_name + ext
            if os.path.isfile(filename):
                try:
                    with open(filename, "r", encoding="utf-8") as file:
                        lines = file.readlines()
                        run_code(lines)
                        loaded = True
                        break
                except Exception as e:
                    print(f"Import Error: {e} //Found By QuarkSaviour!")
                    loaded = True
                    break
        if not loaded:
            print(f"Module '{mod_name}' not found. //Found By QuarkSaviour!")

    else:
        print(f"Unknown command: {cmd} //Found By QuarkSaviour!")

def help():
    print("""Commands:
help
print <item1>, <item2>
math <expression>
let var = value / math / random
repeat <count> <command>
if <condition> then <command>
game loop <condition> ... loop end
fn <name> ... fn end
call <name>
input <prompt> -> <var>  (or input <var>)
type <var>
vector_push <vector> <val>
vector_pop <vector> -> <var>
list
time
wait <seconds>
random <min> <max>
read <file>
run / game <file>
write / append <file> <content>
clear
import <module> (.qk or .qm)
stop / exit / kill
""")

# Setup Interactive Session with Real-Time Color Highlighting
if HAS_PROMPT_TOOLKIT:
    from prompt_toolkit.styles import Style
    custom_style = Style.from_dict({
        'keyword': 'ansiyellow bold',
        'name.variable': 'ansicyan',
        'string': 'ansigreen',
        'number': 'ansimagenta',
        'comment': 'ansigray italic',
    })
    session = PromptSession(lexer=PygmentsLexer(QuarkLexer), style=custom_style)
else:
    session = None

while running:
    try:
        if HAS_PROMPT_TOOLKIT:
            user_input = session.prompt(">>> ")
        else:
            user_input = input(">>> ")
            
        sanitized_input = sanitize_line(user_input)
        
        if not sanitized_input:
            continue

        if (sanitized_input.startswith("game loop") or sanitized_input.startswith("fn ")) and not sanitized_input.startswith("fn end"):
            buffer = [sanitized_input]
            depth = 1
            start_kw = "game loop" if sanitized_input.startswith("game loop") else "fn"
            end_kw = "loop end" if start_kw == "game loop" else "fn end"

            while depth > 0:
                if HAS_PROMPT_TOOLKIT:
                    sub_line = sanitize_line(session.prompt("... "))
                else:
                    sub_line = sanitize_line(input("... "))
                buffer.append(sub_line)
                if start_kw == "fn" and sub_line.startswith("fn ") and not sub_line.startswith("fn end"):
                    depth += 1
                elif start_kw == "game loop" and sub_line.startswith("game loop"):
                    depth += 1
                elif sub_line == end_kw:
                    depth -= 1

            run_code(buffer)
        else:
            run_code([sanitized_input])

    except (KeyboardInterrupt, EOFError):
        print("\nShell Stopped Working. Thank You For Using Quark!")
        sys.exit()
