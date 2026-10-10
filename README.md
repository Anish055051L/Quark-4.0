# Quark 4.0 — Master Gaming & Vector Support

>Please Package QuarkInterpreter4.0.py Into .exe File Using PyInstaller Or Run It With Console For The Colour Code To Work.

> **Quark 4.0** is a small, command-oriented interpreted language implemented in Python. It provides variables, arithmetic, conditionals, functions, loops, vectors, console input/output, random numbers, timing, and basic file/module operations.

**Status:** This README documents the implementation shown with Quark 4.0. Some advertised features (notably syntax highlighting and game-oriented commands) have limitations described below.

---

## Table of contents

- [1. Quick start](#1-quick-start)
- [2. Language overview](#2-language-overview)
- [3. Comments and whitespace](#3-comments-and-whitespace)
- [4. Variables and values](#4-variables-and-values)
- [5. Printing and expressions](#5-printing-and-expressions)
- [6. Vectors and data structures](#6-vectors-and-data-structures)
- [7. Conditions](#7-conditions)
- [8. Repetition and loops](#8-repetition-and-loops)
- [9. Functions](#9-functions)
- [10. Input and type inspection](#10-input-and-type-inspection)
- [11. Randomness and time](#11-randomness-and-time)
- [12. Files and modules](#12-files-and-modules)
- [13. Shell commands](#13-shell-commands)
- [14. Example programs](#14-example-programs)
- [15. Syntax highlighting](#15-syntax-highlighting)
- [16. Important implementation notes](#16-important-implementation-notes)
- [17. Feature summary](#17-feature-summary)

---

## 1. Quick start

Save Quark programs with a `.qk` extension, for example `hello.qk`:

```text
print "Hello from Quark 4.0!"
let name = "Quark"
print 'name'
```

Start the Python interpreter that contains the Quark implementation, then enter commands at the `>>>` prompt. Run a saved program with:

```text
game hello.qk
```

`game <file>` automatically adds `.qk` when the supplied filename does not already end in `.qk`. `run <file>` opens the filename exactly as supplied.

> **Important:** Quark is a custom command language, not Python syntax. The examples below use Quark commands.

## 2. Language overview

Quark reads one command per line. Commands are interpreted by the Python host program. Its main features are:

- Variables holding integers, floating-point numbers, strings, booleans, `none`, and vectors.
- Arithmetic expressions through `math`.
- Console output using `print`, and console input using `input`.
- Conditional execution with `if`.
- Counted repetition with `repeat`.
- Condition-controlled blocks using `game loop ... loop end`.
- Named code blocks using `fn ... fn end` and `call`.
- Stack- and queue-mode vectors.
- Random integers, time display, and delays.
- Basic reading, writing, appending, running, and importing of files.
- Optional interactive prompt and syntax-colouring support if its dependencies and lexer are correctly configured.

Quark stores variables and function definitions in interpreter-wide dictionaries. Functions do not currently declare parameters or return values.

## 3. Comments and whitespace

A line whose first non-whitespace character is `#` is treated as a comment:

```text
# This is a comment
let score = 0
```

Blank lines are ignored. Leading and trailing whitespace is stripped from each line. Quark does not currently document a general inline-comment syntax; use full comment lines for clarity.

## 4. Variables and values

### Assigning values

Use `let`:

```text
let score = 100
let speed = 4.5
let player = "Alex"
let alive = true
let target = none
```

Supported literal forms include:

| Value | Example |
|---|---|
| Integer | `42`, `-7` |
| Float | `3.14`, `0.5` |
| String | `"hello"` or `'hello'` |
| Boolean | `true`, `false` |
| Empty value | `none` |
| Stack-mode vector | `[1, 2, 3]` |
| Queue-mode vector | `{1, 2, 3}` |

Quark recognizes booleans and `none` case-insensitively when parsing a literal. The literal parser first tries integer and then floating-point conversion; otherwise it keeps the value as text.

### Assignment from an expression

Prefix the right-hand side with `math`:

```text
let x = 12
let y = math x * 3 + 2
print 'y'
```

### Random assignment

```text
let roll = random 1 6
```

This stores a random integer between the two inclusive endpoints.

### Updating a vector element

Vector indexes are **zero-based**:

```text
let nums = [10, 20, 30]
let nums(1) = 99
print nums(1)
```

The intended result of the last line is `99`. Index assignment is implemented through the special `let vector(index) = value` form.

### Inspecting a variable's type

```text
type score
type player
type alive
type nums
```

Output labels include `integer`, `float`, `string`, `boolean`, and `vector (stack)` or `vector (queue)`. Note that in Python, booleans are a subclass of integers; the current implementation checks `int` before `bool`, so `type alive` may report `integer` rather than `boolean`. This is an implementation quirk.

## 5. Printing and expressions

### Printing values

```text
print "Welcome!"
print "Score:", 'score'
print 'player', "is ready"
print
```

A comma separates print items. Quark prints the items separated by spaces. In the current implementation, quoted single-word names such as `'score'` are treated as variable references if a matching variable exists; otherwise they generally remain text. This is a custom Quark convention, not ordinary string interpolation.

For example:

```text
let score = 25
print 'score'
print 'not_a_variable'
```

### Arithmetic with `math`

```text
math 2 + 3
math 10 / 4
math (5 + 3) * 2
let area = math 3.14 * 5 * 5
print 'area'
```

The supported operations are those accepted by Python's `eval` in the host implementation, after Quark performs its textual variable substitution. This includes ordinary arithmetic operators such as `+`, `-`, `*`, `/`, `//`, `%`, and `**`.

**Safety note:** The implementation uses Python `eval()` on expressions. Do not run untrusted Quark programs or expressions. A future version should replace `eval()` with a restricted expression parser or AST evaluator.

### Random value in output

```text
random 1 100
print "Lucky number:", random 1 100
```

The standalone `random` command prints a random integer. `print` items beginning with `random` also support random integer output.

## 6. Vectors and data structures

Quark implements one custom class, `QuarkVector`. It wraps a Python list and adds a mode: `"stack"` or `"queue"`.

### Creating vectors

```text
let stack = [10, 20, 30]
let queue = {10, 20, 30}
```

- Square brackets `[...]` create a **stack-mode** vector.
- Curly braces `{...}` create a **queue-mode** vector.
- Empty vectors are `[]` and `{}`.
- Elements are parsed individually, so vectors can contain integers, floats, strings, booleans, `none`, or nested vectors.

### Stack behaviour (LIFO)

A stack is **last in, first out**. The most recently pushed item is removed first.

```text
let stack = [10, 20]
vector_push stack 30
vector_pop stack -> removed
print 'removed'
print stack
```

`vector_pop` removes the final element from a stack and assigns it to the destination variable. In this example, `removed` receives `30`.

### Queue behaviour (FIFO)

A queue is **first in, first out**. The oldest item is removed first.

```text
let queue = {10, 20}
vector_push queue 30
vector_pop queue -> first
print 'first'
print queue
```

For a queue-mode vector, `vector_pop` calls the vector's `dequeue()` method, removing the element at index `0`. Here, `first` receives `10`.

### Vector commands and operations

| Operation | Syntax | Meaning |
|---|---|---|
| Add to end | `vector_push v value` | Appends an item |
| Remove item | `vector_pop v -> result` | Stack: removes last; queue: removes first |
| Read item | `print v(0)` | Reads a zero-based index in supported expressions |
| Change item | `let v(0) = value` | Replaces an existing element |
| Inspect length | Not exposed as a Quark command | `QuarkVector.length()` exists in the Python implementation |

The underlying Python class also has `push`, `pop`, `dequeue`, `peek`, `length`, `__getitem__`, and `__setitem__` methods. These are host-language methods; not all are directly callable from Quark source.

### Empty vectors and bounds

- Removing from an empty vector returns `none` (`None` internally).
- Reading or assigning an out-of-range index is not a valid operation. The current read substitution may show `IndexError` as text, while assignment prints a vector index error.
- Queue removal uses Python `list.pop(0)`, which is \(O(n)\) because the remaining elements shift. For large queues, a deque-based implementation would be more efficient.

### Printing vectors

Stack-mode vectors display with square brackets, e.g. `[1, 2, 3]`. Queue-mode vectors display with curly braces, e.g. `{1, 2, 3}`.

## 7. Conditions

Use `if <condition> then <command>` to execute one command if the condition is true:

```text
let score = 75
if score >= 50 then print "Passed!"
if score < 50 then print "Keep practising!"
```

Common comparison operators are:

- `==` equal
- `!=` not equal
- `>` greater than
- `<` less than
- `>=` greater than or equal to
- `<=` less than or equal to

You can also use Python-style logical operators such as `and`, `or`, and `not` when the substituted expression remains valid.

**Current limitation:** `if` executes a single command after `then`; it is not a multi-line `if` block. Conditions are evaluated using Python `eval()` after substitution, so untrusted expressions are unsafe.

## 8. Repetition and loops

### Counted repetition

```text
repeat 5 print "Hello!"
```

This executes the command five times. The command after the count is run as a one-line Quark program each time.

A variable can be used for the count:

```text
let n = 3
repeat n print "Again!"
```

If the first token cannot be parsed as a count, the implementation treats the whole argument as a command and uses a count of one. Negative counts perform zero iterations because of Python's `range()` behaviour.

### Condition-controlled loop

```text
let counter = 0

game loop counter < 5
    print 'counter'
    let counter = math counter + 1
loop end
```

The body repeats while the condition is true. Update a variable used by the condition, or the loop may run forever.

### Nested blocks

The interpreter tracks nested `game loop` blocks and nested function definitions when finding matching end markers. Use the correct closing statement:

- `game loop ...` closes with `loop end`
- `fn ...` closes with `fn end`

**Loop caution:** Quark's current interpreter rechecks a loop condition when execution returns to the loop header. Ensure the body changes the condition so the loop can finish. Use `Ctrl+C` to interrupt the shell if necessary.

## 9. Functions

Functions are named blocks of Quark commands:

```text
fn greet
    print "Hello from a function!"
fn end

call greet
```

A function is registered when the interpreter encounters its definition, and its body is skipped until it is called. `call <name>` runs the saved body.

### Functions currently support

- Named definitions.
- Calls by name.
- Function bodies containing ordinary Quark commands.
- Nested function-definition matching while locating `fn end`.

### Not currently supported

- Parameters or arguments.
- Return values.
- Local scopes.
- Explicit `return`.
- First-class function values.

Variables live in the shared global `variables` dictionary, so functions operate on the same variable environment as the shell.

## 10. Input and type inspection

### Read input into a variable

```text
input username
```

The shell prompts `Enter username:` and stores the parsed input in `username`.

### Custom prompt

```text
input "What is your name?" -> username
print "Hello", 'username'
```

Input is passed through `parse_literal`, so entries such as `123`, `3.5`, `true`, `none`, `[1,2]`, or `{1,2}` become their corresponding values rather than always remaining strings.

### Type command

```text
type username
```

This prints the implementation's type label for the named variable. See the type caveat in [Variables and values](#4-variables-and-values).

## 11. Randomness and time

### Random integers

```text
random 1 6
let dice = random 1 6
print "Dice:", 'dice'
```

Both endpoints are inclusive.

### Current time

```text
time
print 'time'
```

The `time` command prints the host computer's local time in `HH:MM:SS` format. The special quoted token `'time'` is also handled by the print implementation.

### Delays

```text
print "Starting..."
wait 2
print "Two seconds later."
```

`wait <seconds>` pauses the interpreter for the specified number of seconds. Decimal durations are accepted, such as `wait 0.5`.

## 12. Files and modules

### Run a file

```text
run hello.qk
game hello
```

- `run <file>` uses the filename exactly as provided.
- `game <file>` adds `.qk` if the target does not already end in `.qk`.

### Read a file

```text
read notes.txt
```

The file's contents are printed with leading/trailing whitespace removed.

### Write or append

```text
write score.txt "Best score: 100"
append score.txt "Another result"
```

- `write` opens the file in write mode and replaces its existing contents.
- `append` adds a new line at the end.
- Each command writes one line.
- The current parser separates the filename from the content at the first space.

### Import a module

```text
import utilities
```

Quark searches for the exact name, then `<name>.qm`, then `<name>.qk`. If found, the file is read and its lines are executed. `.qm` and `.qk` are therefore the module/program extensions understood by this loader.

**Important:** Import executes the file; it is not a separate namespace or a compiled module system. Imported code shares the interpreter's variables and functions.

## 13. Shell commands

| Command | Purpose |
|---|---|
| `help` | Prints the built-in command list |
| `clear` | Clears the terminal where supported |
| `list` | Lists current variables and defined function names |
| `time` | Prints local time |
| `wait <seconds>` | Pauses execution |
| `random <min> <max>` | Prints a random integer |
| `read <file>` | Prints a file's contents |
| `write <file> <content>` | Replaces a file with one line |
| `append <file> <content>` | Appends one line |
| `run <file>` | Executes a file |
| `game <file>` | Executes a `.qk` file by default |
| `import <module>` | Executes a `.qm` or `.qk` module |
| `stop`, `exit`, `kill` | Exits the interpreter process |

`list` shows variables and the names of defined functions. `clear` uses `cls` on Windows and `clear` on other platforms, with a fallback of printing many blank lines.

## 14. Example programs

### A. Score tracker

```text
let score = 0
let score = math score + 10
let score = math score + 5
print "Final score:", 'score'
```

### B. Guess-the-number building block

This example demonstrates random numbers, input, comparison, and output. It is a small one-shot check, not a full retry game.

```text
let secret = random 1 10
input "Guess a number from 1 to 10:" -> guess
if guess == secret then print "Correct!"
if guess != secret then print "Not this time!"
print "The secret was:", 'secret'
```

### C. Countdown

```text
let count = 5
game loop count > 0
    print 'count'
    let count = math count - 1
    wait 1
loop end
print "Go!"
```

### D. Stack demonstration

```text
let inventory = ["key", "map"]
vector_push inventory "coin"
print inventory
vector_pop inventory -> item
print "Removed:", 'item'
print "Remaining:", inventory
```

### E. Queue demonstration

```text
let queue = {"A", "B"}
vector_push queue "C"
print queue
vector_pop queue -> next_item
print "Next:", 'next_item'
print "Remaining:", queue
```

### F. Function reuse

```text
fn announce
    print "Quark is running!"
fn end

call announce
call announce
```

## 15. Syntax highlighting

The Python implementation optionally imports `prompt_toolkit` and Pygments-related components. If the import fails, Quark falls back to Python's ordinary `input()` prompt.

The provided code creates a `PromptSession` with `PygmentsLexer(QuarkLexer)`, but **`QuarkLexer` is not defined in the pasted implementation**. As written, if `prompt_toolkit` imports successfully, the program will raise `NameError` while creating the session unless `QuarkLexer` is defined elsewhere. Define a Pygments `RegexLexer` subclass before constructing the session, or temporarily use `PromptSession()` without `PygmentsLexer`.

The file also creates the prompt session twice with different styles. The second setup overwrites the first, so only the second style would be active if the lexer issue is fixed.

## 16. Important implementation notes

This section distinguishes implemented behaviour from features that may sound broader than the current code.

1. **Not a graphical game engine yet.** The `game` command runs a `.qk` script, and `game loop` repeats commands. The shown implementation has no graphics, sprites, keyboard/mouse event system, audio, or rendering API.
2. **Expression evaluation uses Python `eval()`.** This is powerful but unsafe for untrusted input and is not a secure sandbox.
3. **Variable substitution is text-based.** It replaces variable names in expressions rather than using a full parser. Complex strings, overlapping names, and certain expressions can behave unexpectedly.
4. **Vector indexing is zero-based.** `v(0)` is the first element.
5. **No general expression grammar.** The language currently relies on substitution and Python expression parsing, so syntax and edge cases can inherit Python behaviour.
6. **`if` runs one command.** There is no `else` command or multi-line conditional block in the shown implementation.
7. **Functions share global state.** They have no parameters, return values, or local variable scope.
8. **Some vector methods are internal only.** `peek()` and `length()` exist in Python but have no dedicated Quark commands.
9. **Type detection quirk.** The `int` check happens before the `bool` check, so booleans can be reported as integers.
10. **Print and substitution are custom.** Quoted identifiers such as `'score'` are used to display variable values in several contexts. This is not conventional string interpolation.
11. **Error messages are best-effort.** Several errors are caught and printed with `QuarkSaviour`, but not every possible malformed input is handled uniformly.
12. **The prompt lexer must exist.** `QuarkLexer` is referenced but absent from the supplied source.

## 17. Feature summary

| Feature | Status in supplied implementation |
|---|---|
| Variables and literals | Implemented |
| Arithmetic expressions | Implemented through Python `eval()` after substitution |
| Console output/input | Implemented |
| Random integers | Implemented |
| Time and delays | Implemented |
| One-line conditions | Implemented |
| Counted repetition | Implemented |
| Condition-controlled loops | Implemented, with interpreter edge cases |
| Named functions | Implemented without parameters/returns |
| Stack-mode vectors | Implemented |
| Queue-mode vectors | Implemented |
| Vector indexing and assignment | Implemented in supported forms |
| File read/write/append | Implemented |
| Run `.qk` files | Implemented |
| Import `.qk` / `.qm` files | Implemented by executing their contents |
| Terminal clearing | Implemented with platform fallback |
| Real-time syntax highlighting | Intended, but `QuarkLexer` is missing in the supplied code |
| Graphics/game engine | Not present in the supplied code |

---

**Quark 4.0 motto:** *Write commands. Build logic. Make things happen.*

This README describes the code provided for Quark 4.0. If the implementation changes, update the documentation to match the actual parser and runtime behaviour.
