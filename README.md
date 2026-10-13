# Quark 4.0

Quark is a small, command-oriented interpreted language implemented in Python. This release preserves the existing Quark 4.0 commands and adds Python-style function parameters, argument passing, safer expression evaluation, diagnostic categories, and configurable warning/error bypasses.

## Requirements

- Python 3.10 or newer is recommended.
- `pygame` is optional and is used for audio commands and audio-backed timed input.
- `prompt_toolkit` and `pygments` are optional and provide shell syntax highlighting. Without them, Quark falls back to ordinary terminal input.

Run the interpreter with:

```bash
python Quark_4.0_Final.py
```

## Quick start

```quark
let x = 10
let y = 25
print "Sum:", math x + y

fn add(a, b)
    let result = math a + b
    print result
fn end

call add(x, y)
call add(2, 3)
```

Function arguments are evaluated from left to right. Arguments can be literals, existing variables, vectors, or an explicit `math <expression>` argument. The number of arguments must exactly match the declared parameter count. Parameter values are available as variables during the call and their previous values are restored after the call. Nested calls are supported. **Return values are not currently supported.**

## Function syntax

```quark
fn greet(name)
    print "Hello", name
fn end

call greet("World")
```

Multiple parameters:

```quark
fn describe(name, age)
    print name, "is", age
fn end

let person = "Anish"
let years = 16
call describe(person, years)
call describe("Guest", 18)
```

A function with no parameters keeps the legacy syntax:

```quark
fn announce
    print "Ready!"
fn end

call announce
```

Function visibility is private by default. Use `public fn name(...)` to expose a function through module scope, or `private fn name(...)` to explicitly keep it private. Imported public functions can be called as `call module::name(arguments...)`. A module's functions can call its own private functions by name.

## Commands

| Command | Purpose |
|---|---|
| `help` | Show the built-in command and safety reference |
| `print <items>` | Print comma-separated values or text |
| `math <expression>` | Evaluate a supported arithmetic expression |
| `let name = value` | Create or update a variable |
| `let name = math <expression>` | Store a calculated result |
| `let name = random <min> <max>` | Store a random integer in the inclusive range |
| `type <name>` | Show a variable's data type |
| `input <prompt> -> <name>` | Read a value into a variable; `input <name>` is also supported |
| `if <condition> then <command>` | Run one command when the condition is true |
| `repeat <count> <command>` | Repeat a command |
| `game loop <condition> ... loop end` | Repeat while the condition is true |
| `game loop ... loop end` | Infinite loop; stop with Ctrl+C |
| `vector_push <vector> <value>` | Add an item to a vector |
| `vector_pop <vector> -> <name>` | Remove an item and store it in a variable |
| `list` | List variables and declared functions |
| `time` | Print the current time |
| `wait <seconds>` | Wait for a number of seconds |
| `play <file>` | Play an audio file (requires `pygame`) |
| `read <file>` | Print a text file's contents |
| `write <file> <content>` | Write a line to a text file |
| `append <file> <content>` | Append a line to a text file |
| `run <file>` | Run a Quark script file |
| `game <file>` | Legacy alias for running a `.qk` script |
| `import <module>` | Import a `.qk` or `.qm` module file |
| `random <min> <max>` | Print a random integer in the inclusive range |
| `clear` | Clear the terminal where supported |
| `stop`, `exit`, `kill` | Exit the shell |

Quark files commonly use `.qk`; module files can use `.qm` or `.qk`.

## Vectors

Square brackets create stack-style vectors and curly braces create queue-style vectors:

```quark
let stack = [10, 20, 30]
let queue = {"first", "second"}
vector_push stack 40
vector_pop stack -> last
print stack(0)
```

Vector indices are checked. Invalid indices report an error instead of silently returning `none`. Mixing types in a vector may produce a warning.

## Bypass controls

Global bypass settings remain active until turned off:

```quark
bypass::warning
bypass::warning off
bypass::error
bypass::error off

bypass::warning(datatype)
bypass::warning(datatype) off
bypass::error(math)
bypass::error(math) off
```

- `bypass::warning` hides all warnings while statements still execute.
- `bypass::warning(category)` hides only that warning category.
- `bypass::error` hides all error diagnostics; it does **not** automatically skip failed statements or roll back side effects.
- `bypass::error(category)` hides only the selected error category.
- `off` and `reset` disable the corresponding global setting.

Per-statement bypasses are also available:

```quark
bypass::warning(datatype) let score = "excellent"
bypass::error math 1 / 0
bypass::error(vector) let missing = stack(999)
```

A per-statement warning bypass hides matching warnings for that line and still executes it. A per-statement error bypass suppresses the failed statement's diagnostics/output and attempts to restore interpreter variables and function definitions. It cannot undo external side effects such as files already written or audio already played.

Warning categories: `datatype`, `performance`, `vector`, `general`.

Error categories: `syntax`, `math`, `name`, `type`, `vector`, `audio`, `file`, `input`, `function`, `import`, `runtime`, `performance`, `general`.

Warnings include a short hint for the relevant `bypass::warning(...)` category and the global `bypass::warning` command. In interactive terminals, warnings are bright yellow and errors are bright red when ANSI colours are supported. Redirected output remains uncoloured; setting `NO_COLOR` disables colour output.

## Timed input and audio

```quark
bypass::input(wait 3) input "Choose within 3 seconds (Y/N)" -> choice
bypass::input(play sample.mp3) input "Your choice?" -> choice
bypass::input(play sample.mp3 wait 3) input "Your choice?" -> choice
bypass::input(play sample.mp3 wait timer.mp3) input "Your choice?" -> choice
```

- `wait 3` sets a three-second timeout. If time expires, the destination variable is unchanged.
- `play sample.mp3` plays audio while waiting; responding early stops playback.
- `wait timer.mp3` uses the second audio file's duration as the timeout.
- Audio options require `pygame`. Timed input is intended for a real interactive terminal; IDE consoles and redirected stdin may not support it correctly.

## Safety and limitations

- Expressions are evaluated with a restricted syntax; arbitrary Python execution is not permitted through the expression evaluator.
- Expression length, syntax-tree size, exponent magnitude, and integer result size are limited.
- These protections are interpreter/runtime safeguards, not a formal guarantee of memory safety. Python manages memory for the interpreter itself.
- Functions currently support parameters and argument passing but not `return` statements, default parameters, keyword arguments, or Python-style closures.
- The interpreter is a small custom language, not a drop-in Python implementation. Use the syntax documented by `help` and this README.

## License

No license is specified in this source package. Add a license file before publishing if you want to grant explicit reuse or distribution permissions.
