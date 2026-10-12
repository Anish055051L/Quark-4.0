# Quark 4.0 — Master Gaming & Vector Support

> **Quark 4.0** is a command-oriented interpreted language written in Python. It supports variables, arithmetic, conditions, loops, functions, stack/queue vectors, file operations, module imports, syntax-coloured shell input, and basic audio playback.

**Version:** Quark 4.0  
**Program files:** `.qk`  
**Module files:** `.qm` or `.qk`

> **Running note:** For interactive syntax colouring, run Quark in a real terminal/console rather than an environment that strips ANSI colours or does not support interactive prompts. The optional prompt dependencies are `prompt_toolkit` and `Pygments`. Audio commands require `pygame` and a working audio device.

---

## Table of contents

1. [Quick start](#1-quick-start)
2. [Language overview](#2-language-overview)
3. [Comments and whitespace](#3-comments-and-whitespace)
4. [Variables and values](#4-variables-and-values)
5. [Printing and expressions](#5-printing-and-expressions)
6. [Vectors and data structures](#6-vectors-and-data-structures)
7. [Conditions](#7-conditions)
8. [Repetition and loops](#8-repetition-and-loops)
9. [Functions and visibility](#9-functions-and-visibility)
10. [Input and type inspection](#10-input-and-type-inspection)
11. [Randomness, time, and delays](#11-randomness-time-and-delays)
12. [Audio playback](#12-audio-playback)
13. [Files and modules](#13-files-and-modules)
14. [Shell commands](#14-shell-commands)
15. [Example programs](#15-example-programs)
16. [Syntax highlighting](#16-syntax-highlighting)
17. [Implementation notes and limitations](#17-implementation-notes-and-limitations)
18. [Feature summary](#18-feature-summary)

---

## 1. Quick start

Save a program as `hello.qk`:

```text
print "Hello from Quark 4.0!"
let name = "Quark"
print 'name'
```

Start Quark's Python interpreter and enter commands at the `>>>` prompt.

Run a saved file with either command:

```text
run hello.qk
game hello
```

- `run <file>` opens the exact filename supplied.
- `game <file>` is a legacy alias for running a file. If the filename does not end in `.qk`, Quark adds `.qk`.

For example, `game hello` runs `hello.qk`.

### Optional dependencies

- `prompt_toolkit` and `Pygments` enable syntax-coloured interactive input. Quark falls back to a normal input prompt if these imports are unavailable or session setup fails.
- `pygame` enables `play <file>` and audio-file support in `wait <file>`.

Install optional packages in the same Python environment used to launch Quark:

```bash
python -m pip install prompt_toolkit pygments pygame
```

Quark is its own command language; its syntax is not Python syntax.

---

## 2. Language overview

Quark reads commands and interprets them through its Python host program. The language includes:

- Variables and literals: integers, floats, strings, booleans, `none`, and vectors.
- Arithmetic expressions using `math`.
- Console output with `print` and input with `input`.
- Single-command conditions using `if`.
- Counted repetition using `repeat`.
- Conditional and infinite loops using `game loop ... loop end`.
- Named functions using `fn ... fn end`, with private-by-default visibility.
- Explicit `public fn` and `private fn` declarations.
- Module-qualified calls using `module::function`.
- Stack-mode and queue-mode vectors.
- Random integers, local time, delays, and audio playback.
- File reading, writing, appending, script execution, and module imports.
- Interactive syntax colouring when optional prompt dependencies are available.

Variables and functions are stored by the interpreter. Functions currently do not support parameters, return values, or local variable scopes.

---

## 3. Comments and whitespace

A line whose first non-whitespace character is `#` is a comment:

```text
# This is a comment
let score = 0
```

Blank lines are ignored, and leading/trailing whitespace is stripped. Use full-line comments for clarity; inline comments are not a documented general feature.

---

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

| Value | Example |
|---|---|
| Integer | `42`, `-7` |
| Float | `3.14`, `0.5` |
| String | `"hello"` or `'hello'` |
| Boolean | `true`, `false` |
| Empty value | `none` |
| Stack-mode vector | `[1, 2, 3]` |
| Queue-mode vector | `{1, 2, 3}` |

Boolean and `none` literals are case-insensitive. Quoted strings are parsed as strings; numeric-looking unquoted values are converted to integers or floats where possible. Other unquoted values are treated as text.

### Assignment using an expression

Prefix an expression with `math`:

```text
let x = 12
let y = math x * 3 + 2
print 'y'
```

### Random assignment

```text
let roll = random 1 6
```

Both endpoints are inclusive.

### Updating a vector element

Vector indexes are zero-based:

```text
let nums = [10, 20, 30]
let nums(1) = 99
print nums(1)
```

The final line prints `99`.

### Inspecting a variable's type

```text
type score
type player
type alive
type target
type nums
```

The type command distinguishes booleans before integers, so `true` and `false` are reported as `boolean`. Other labels include `integer`, `float`, `string`, `none`, `vector (stack)`, and `vector (queue)`.

---

## 5. Printing and expressions

### Printing values

```text
print "Welcome!"
print "Score:", 'score'
print 'player', "is ready"
print
```

Commas separate print items; output items are separated by spaces. A quoted single-word name such as `'score'` is treated as a variable reference when that variable exists. If it does not exist, the surrounding single quotes are removed and the contents are printed as text.

Double-quoted strings are parsed as string literals.

### Arithmetic with `math`

```text
math 2 + 3
math 10 / 4
math (5 + 3) * 2
let area = math 3.14 * 5 * 5
print 'area'
```

The expression evaluator supports arithmetic operators `+`, `-`, `*`, `/`, `//`, `%`, and `**`, comparisons, boolean operations, and unary `+`, `-`, and `not` in the supported expression forms. Variable substitution occurs before evaluation.

Quark uses a restricted Python AST evaluator for expressions instead of directly evaluating arbitrary Python code. Unsupported expression syntax raises an error rather than being executed as a general Python expression. This is a safer approach, but it should not be treated as a complete security sandbox.

### Random output

```text
random 1 100
print "Lucky number:", random 1 100
```

`random <min> <max>` prints a random integer, and `random` can also be used in `let` assignments and print items.

---

## 6. Vectors and data structures

Quark's `QuarkVector` wraps a list and records whether it behaves as a stack or a queue.

### Creating vectors

```text
let stack = [10, 20, 30]
let queue = {10, 20, 30}
```

- Square brackets create a **stack-mode** vector.
- Curly braces create a **queue-mode** vector.
- Empty vectors are `[]` and `{}`.
- Elements can include supported literals and nested vectors.

### Stack behaviour (LIFO)

A stack is last in, first out: the most recently added item is removed first.

```text
let stack = [10, 20]
vector_push stack 30
vector_pop stack -> removed
print 'removed'
print stack
```

`removed` receives `30`.

### Queue behaviour (FIFO)

A queue is first in, first out: the oldest item is removed first.

```text
let queue = {10, 20}
vector_push queue 30
vector_pop queue -> first
print 'first'
print queue
```

`first` receives `10`.

### Vector operations

| Operation | Syntax | Meaning |
|---|---|---|
| Add to end | `vector_push v value` | Appends an item |
| Remove item | `vector_pop v -> result` | Stack removes last; queue removes first |
| Read item | `print v(0)` | Reads a zero-based index in supported expressions |
| Change item | `let v(0) = value` | Replaces an existing element |

The Python-side class also defines `peek()` and `length()`, but these methods do not have dedicated Quark commands.

Removing an item from an empty vector returns `none`. Invalid vector names or assignments produce an error message. Queue removal uses list index zero, which can be slower than a dedicated deque for large queues.

---

## 7. Conditions

Use `if <condition> then <command>` to execute one command when the condition is true:

```text
let score = 75
if score >= 50 then print "Passed!"
if score < 50 then print "Keep practising!"
```

Supported comparisons include `==`, `!=`, `>`, `<`, `>=`, and `<=`. Boolean expressions can use `and`, `or`, and `not` where supported by the expression evaluator.

**Limitation:** `if` runs a single command after `then`. It is not a multi-line `if` block and there is no `else` command.

---

## 8. Repetition and loops

### Counted repetition

```text
repeat 5 print "Hello!"
```

This runs the command five times. The command after the count is executed as a one-line Quark program each time.

A variable can supply the count:

```text
let n = 3
repeat n print "Again!"
```

Negative repeat counts are rejected with a message. If the first token is not parsed as an integer count, Quark treats the full argument as a command and attempts to run it once.

### Condition-controlled loop

```text
let counter = 0

game loop counter < 5
    print 'counter'
    let counter = math counter + 1
loop end
```

The condition is checked each time execution reaches the loop header. The loop ends when the condition becomes false.

### Infinite loop

Omit the condition to repeat forever:

```text
game loop
    print "Still running..."
loop end
```

Stop an infinite loop with **Ctrl+C** in the shell.

### Nested blocks

Quark tracks nested `game loop` blocks and nested function declarations when looking for their matching end markers.

- `game loop ...` closes with `loop end`.
- `fn ...` / `public fn ...` / `private fn ...` closes with `fn end`.

Make sure each block has the matching closing statement.

---

## 9. Functions and visibility

Functions are named blocks of Quark commands. They are registered when Quark reads their declarations, and their bodies are skipped until called.

### Private by default

```text
fn greet
    print "Hello from Quark!"
fn end

call greet
```

A plain `fn name` declaration is **private by default**.

You can also mark the visibility explicitly:

```text
private fn helper
    print "This helper is private."
fn end
```

### Public functions

A function intended to be called from another imported module should be declared public:

```text
public fn greet
    print "Hello from the utilities module!"
fn end
```

### Calling functions

Use `call`:

```text
call greet
```

Function declarations and calls currently support names only. Parameters, return values, local scopes, and explicit `return` statements are not implemented. Functions share the interpreter's variable environment.

### Module scope with `::`

When a module is imported, its functions are registered under that module's name. Use `module::function` to call a **public** function exported by that module:

```text
import utilities
call utilities::greet
```

Only `public fn` functions can be called from outside a module using `module::function`. Private functions cannot be accessed this way. A module's own functions can call its private functions by their unqualified names.

For example, a `utilities.qm` module might contain:

```text
private fn format_message
    print "Formatting message..."
fn end

public fn greet
    call format_message
    print "Hello!"
fn end
```

Then another file or the shell can use:

```text
import utilities
call utilities::greet
```

**Note:** Importing executes the module file and registers its function definitions. It does not create a fully isolated namespace for variables; the interpreter uses shared global variable storage. The `module::function` mechanism qualifies function names and checks visibility.

---

## 10. Input and type inspection

### Read input into a variable

```text
input username
```

Quark prompts for the value and stores it in `username`.

### Custom prompt

```text
input "What is your name?" -> username
print "Hello", 'username'
```

Input is passed through the literal parser. Values such as `123`, `3.5`, `true`, `none`, `[1,2]`, and `{1,2}` can become numbers, booleans, `none`, or vectors instead of remaining strings. Use ordinary text when you want a string that does not resemble another literal.

### Type command

```text
type username
```

This prints the type label for a defined variable. If the variable does not exist, Quark prints an error.

---

## 11. Randomness, time, and delays

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

`time` prints the host computer's local time in `HH:MM:SS` format. The special print item `'time'` also displays the current time.

### Wait for a duration

```text
print "Starting..."
wait 2
print "Two seconds later."
```

`wait <seconds>` pauses execution for the given number of seconds. Decimal durations such as `wait 0.5` are accepted; negative durations are rejected.

The `wait` command can also wait for an audio file to finish, as described in the next section.

---

## 12. Audio playback

Audio support is optional and requires `pygame` to be installed and its mixer to initialize successfully.

### Play an audio file

```text
play sound.mp3
print "Playback has started."
```

`play <file>` loads an audio file into Pygame's music player and starts playback without waiting for it to finish. The following Quark command can run while the music is playing.

Use a valid path to an audio file supported by the installed Pygame/SDL audio backend. Relative paths are resolved from the program's current working directory.

### Wait for an audio file's duration

```text
play sound.mp3
wait sound.mp3
print "The track's duration has elapsed."
```

`wait <audio_file>` loads the file as a sound to obtain its duration, then pauses execution for that duration. It does **not** detect whether the music started with `play` has actually finished; it sleeps for the duration reported for the file.

### Wait for a number of seconds

```text
wait 2
wait 0.5
```

If Pygame is unavailable, the current implementation reports an audio-related error for `wait`, including when a numeric delay was requested. Therefore, numeric `wait` currently also depends on the Pygame import succeeding.

**Audio limitations:** Audio support is basic. There are no Quark commands for pausing, resuming, stopping, or changing the volume of playback. The actual supported file formats depend on the installed Pygame/SDL environment and available codecs.

---

## 13. Files and modules

### Run a file

```text
run hello.qk
game hello
```

- `run <file>` uses the filename exactly as supplied.
- `game <file>` adds `.qk` when needed and is a legacy alias for `run`.

### Read a file

```text
read notes.txt
```

Prints the file's contents with leading/trailing whitespace removed.

### Write or append

```text
write score.txt "Best score: 100"
append score.txt "Another result"
```

- `write` replaces the file's existing contents.
- `append` adds content at the end.
- Each command writes one line.
- The parser separates the filename from the content at the first space.

### Import a module

```text
import utilities
```

Quark checks for the exact filename, then `utilities.qm`, then `utilities.qk`. If a file is found, its lines are executed as a module and function definitions are registered under that module's name.

Use `module::function` to call public functions exported by an imported module. Importing is code execution, not compilation, and module variables are not isolated from the interpreter's global variable dictionary.

---

## 14. Shell commands

| Command | Purpose |
|---|---|
| `help` | Prints the built-in command list |
| `print <items>` | Prints values or text |
| `math <expression>` | Evaluates a supported expression |
| `let var = value` | Creates or updates a variable |
| `type <var>` | Prints the variable's type |
| `input <var>` | Reads input into a variable |
| `if <condition> then <command>` | Runs one command if true |
| `repeat <count> <command>` | Runs a command repeatedly |
| `game loop <condition> ... loop end` | Repeats while the condition is true |
| `game loop ... loop end` | Infinite loop; interrupt with Ctrl+C |
| `fn <name> ... fn end` | Defines a private function |
| `private fn <name> ... fn end` | Explicitly defines a private function |
| `public fn <name> ... fn end` | Defines a module-accessible function |
| `call <name>` | Calls a local function |
| `call module::name` | Calls a public function from an imported module |
| `vector_push <vector> <value>` | Adds an item to a vector |
| `vector_pop <vector> -> <var>` | Removes an item and stores it |
| `random <min> <max>` | Prints a random integer |
| `time` | Prints local time |
| `wait <seconds>` | Pauses for a duration, if Pygame is available |
| `play <file>` | Starts audio playback, if Pygame is available |
| `read <file>` | Prints a file's contents |
| `write <file> <content>` | Replaces a file with one line |
| `append <file> <content>` | Appends one line |
| `run <file>` | Executes a file using its exact filename |
| `game <file>` | Executes a `.qk` file by default |
| `import <module>` | Executes a `.qm` or `.qk` module |
| `list` | Lists variables and defined functions |
| `clear` | Clears the terminal where supported |
| `stop`, `exit`, `kill` | Exits the interpreter |

---

## 15. Example programs

### A. Score tracker

```text
let score = 0
let score = math score + 10
let score = math score + 5
print "Final score:", 'score'
```

### B. Guess-the-number check

```text
let secret = random 1 10
input "Guess a number from 1 to 10:" -> guess
if guess == secret then print "Correct!"
if guess != secret then print "Not this time!"
print "The secret was:", 'secret'
```

This is a one-guess example, not a retry loop.

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

This example uses `wait` and therefore requires Pygame to be available in the current implementation.

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

### F. Function visibility and modules

In `utilities.qm`:

```text
private fn internal_message
    print "This helper stays private."
fn end

public fn greet
    call internal_message
    print "Hello from utilities!"
fn end
```

Then run in the shell:

```text
import utilities
call utilities::greet
```

### G. Audio playback

```text
play sound.mp3
print "The audio has started."
wait sound.mp3
print "The file duration has elapsed."
```

Place `sound.mp3` in the current working directory or supply a valid path. This requires Pygame and working audio support.

### H. Infinite loop

```text
game loop
    print "Quark keeps going."
    wait 1
loop end
```

Interrupt with Ctrl+C. As noted above, the current `wait` implementation requires Pygame.

---

## 16. Syntax highlighting

Quark defines a `QuarkLexer` using Pygments' `RegexLexer` and creates a `PromptSession` with `PygmentsLexer(QuarkLexer)`. When `prompt_toolkit` and Pygments are available and the session initializes successfully, the interactive `>>>` prompt can colour:

- Quark keywords and commands.
- Strings.
- Numbers.
- Boolean and `none` literals.
- Comments beginning with `#`.
- Operators and variable-like names.

The shell falls back to ordinary `input()` if the optional imports are unavailable or syntax-colour session setup fails. In a console that does not support the prompt's styling, colours may not display as expected.

Syntax highlighting colours the interactive prompt; it does not add colour formatting to the contents of `.qk` files or turn Quark into a graphical editor.

---

## 17. Implementation notes and limitations

1. **Not a graphical game engine.** The `game` command is a legacy script-running alias, and `game loop` provides control flow. The implementation does not include sprites, graphics rendering, keyboard/mouse event handling, or a full game framework.
2. **Expression evaluator is restricted, not a complete parser.** Quark uses AST-based evaluation for supported arithmetic, comparisons, boolean expressions, and unary operations. Unsupported syntax is rejected.
3. **Variable substitution is text-based.** Names are substituted into expressions. Complex expressions, overlapping variable names, or unusual text may still behave unexpectedly.
4. **Vector indexing is zero-based.** `v(0)` is the first item.
5. **Conditions run one command.** There is no multi-line `if` block or `else` command.
6. **Functions are limited.** No parameters, return values, local scopes, or explicit `return` statements are supported.
7. **Module variables are shared.** Function names are module-qualified and public/private access is checked, but variables are held in shared interpreter state.
8. **Public/private applies to module-qualified calls.** Functions are private by default. Only `public fn` declarations are intended to be accessible through `module::function`.
9. **Audio is optional.** `play` and audio-file `wait` require Pygame and a working mixer. Numeric `wait` also checks for Pygame availability in this implementation.
10. **`wait <audio_file>` waits by duration.** It sleeps for the file's reported duration; it does not monitor the current music player's playback state.
11. **File paths use the current working directory.** Relative script, module, and audio paths depend on where Quark was launched.
12. **Error handling is best-effort.** QuarkSaviour-style messages are used for many errors, but not every malformed command produces a detailed source location.
13. **No compile step.** Quark programs are interpreted by the Python host program when run.
14. **Optional prompt dependencies.** If prompt setup fails, the shell continues without syntax highlighting when the fallback input path is available.

---

## 18. Feature summary

| Feature | Status in Quark 4.0 |
|---|---|
| Variables and literals | Implemented |
| Arithmetic expressions | Implemented with restricted AST evaluation |
| Console input/output | Implemented |
| Boolean and `none` type reporting | Implemented |
| Random integers | Implemented |
| Local time | Implemented |
| Numeric delays | Implemented when Pygame is available |
| One-line conditions | Implemented |
| Counted repetition | Implemented |
| Conditional loops | Implemented |
| Infinite loops | Implemented |
| Functions | Implemented without parameters or return values |
| Private functions by default | Implemented |
| Explicit private/public function declarations | Implemented |
| `module::function` calls | Implemented with public-function access checks |
| Stack-mode vectors | Implemented |
| Queue-mode vectors | Implemented |
| Vector indexing and assignment | Implemented in supported forms |
| File read/write/append | Implemented |
| Run `.qk` files | Implemented |
| Import `.qk` / `.qm` modules | Implemented by executing module contents |
| Audio playback with `play` | Implemented when Pygame/audio support is available |
| Wait for an audio file's duration | Implemented when Pygame/audio support is available |
| Interactive syntax highlighting | Implemented with optional `prompt_toolkit` and Pygments |
| Graphical game engine | Not included |

---

**Quark 4.0 motto:** *Write commands. Build logic. Make things happen.*

This README documents the supplied Quark 4.0 interpreter. If the implementation changes, update this file to match the runtime's actual behaviour.
