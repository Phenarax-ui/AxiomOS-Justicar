"""
curriculum.py - the concept library. Pure data, no logic, no model.

This is your mastery-engine v2 CONCEPTS dict, lifted out unchanged into
its own file. Keeping the *what you're learning* separate from the *how
the tutor drills it* means you can add or edit a concept here without
touching the engine - and the engine can be tested without the curriculum.

Each concept has:
  label         - human name shown to you
  domain        - which course it belongs to ('python', ...)
  brief         - the ground-truth explanation (the grader checks against this)
  syntax_anchor - a minimal correct example
  common_errors - the usual ways it goes wrong
"""

CONCEPTS = {

    # ════════════════════════════════════════════════════════════════
    # PYTHON — FOUNDATIONS
    # ════════════════════════════════════════════════════════════════

    "lists": {
        "label": "Lists",
        "domain": "python",
        "brief": "Python's default rule is that a name points to one value. A list breaks that rule — one name now points to multiple values in a fixed order. The order is the rule. Every list operation either reads that order or modifies it. Index 0 is the first slot. Negative indexes count backward from the end.",
        "syntax_anchor": "my_list = ['a', 'b', 'c']  →  my_list[0]  →  'a'  |  my_list[-1]  →  'c'",
        "common_errors": [
            "Forgetting quotes around strings",
            "Missing commas between items",
            "Using () instead of []",
            "Index out of range — list has no item at that position",
        ],
    },
    "list_methods_iteration": {
        "label": "List Methods & Iteration",
        "domain": "python",
        "brief": "A list's order rule can be changed. append adds a new slot at the end. remove deletes a slot by value. pop removes a slot by position and hands you what was in it. A for-loop is a rule that says: execute this block once for every slot in the list, in order. You don't control when it stops — the list does.",
        "syntax_anchor": "my_list.append('x')  |  my_list.pop(0)  |  for item in my_list:",
        "common_errors": [
            "Forgetting the colon after for",
            "Indentation errors inside the loop",
            "remove() raises ValueError if item not in list",
        ],
    },
    "dictionaries": {
        "label": "Dictionaries",
        "domain": "python",
        "brief": "A list's rule is order — you find things by position. A dictionary breaks that rule. You find things by name instead. Every entry is a key-value pair. The key is the name, the value is what it points to. There is no order, no index — only lookup by key. .get() modifies the lookup rule to return a default instead of crashing when the key doesn't exist.",
        "syntax_anchor": "my_dict = {'key': value}  →  my_dict.get('key', default)",
        "common_errors": [
            "Using [] without .get() causes KeyError if key missing",
            "Forgetting quotes around string keys",
            "Keys must be immutable — strings, numbers, tuples",
        ],
    },
    "while_loops": {
        "label": "While Loops",
        "domain": "python",
        "brief": "Python's default rule is that code runs once, top to bottom. A while loop breaks that rule — it says keep running this block until the condition becomes False. The condition is checked before every pass. If you never change what the condition checks, the rule never ends. You are responsible for breaking it.",
        "syntax_anchor": "while condition:\n    # body\n    # update condition",
        "common_errors": [
            "Forgetting to update the condition — infinite loop",
            "Forgetting the colon",
            "Using = instead of == in condition",
        ],
    },
    "functions": {
        "label": "Functions",
        "domain": "python",
        "brief": "Python's default rule is that code runs exactly once, in the order it appears. A function breaks that rule — it lets you name a block and run it whenever you want, as many times as you want, with different inputs each time. Parameters are the inputs. return is the output. Without return, the function hands back None — silence, not an error.",
        "syntax_anchor": "def func_name(param):\n    # body\n    return result",
        "common_errors": [
            "Forgetting return — function returns None silently",
            "Variable scope — variables inside don't exist outside",
            "Calling before defining",
        ],
    },
    "file_io": {
        "label": "File I/O",
        "domain": "python",
        "brief": "Python's default rule is that data only exists while the program runs. File I/O breaks that rule — it lets you write data so it survives after the program ends, and read data that existed before it started. The mode is the rule you set for how the file can be touched. with handles the cleanup rule automatically — the file closes when the block ends whether something goes wrong or not.",
        "syntax_anchor": "with open('file.txt', 'r') as f:\n    content = f.read()",
        "common_errors": [
            "'r' read, 'w' write (overwrites), 'a' append, 'r+' read+write",
            "File not found — check path carefully",
            "Forgetting to strip() whitespace when reading lines",
        ],
    },
    "error_handling": {
        "label": "Error Handling",
        "domain": "python",
        "brief": "Python's default rule when something goes wrong is to crash and stop. try/except breaks that rule — it says if this specific thing goes wrong, run this block instead of stopping. You are setting a contingency rule. Be specific about which exception you catch — a bare except is a rule that says catch everything, which hides problems you didn't intend to handle. finally is a rule that always runs regardless of whether anything went wrong.",
        "syntax_anchor": "try:\n    risky_code()\nexcept ValueError as e:\n    handle(e)\nfinally:\n    cleanup()",
        "common_errors": [
            "Bare except: catches everything including KeyboardInterrupt — be specific",
            "Swallowing errors silently — always log what went wrong",
            "finally always runs — use it for cleanup",
        ],
    },
    "classes": {
        "label": "Classes",
        "domain": "python",
        "brief": "A function lets you reuse a block of behavior. A class lets you reuse a whole ruleset — bundling data and behavior together into a blueprint. Every time you create an instance you're stamping out a new object that follows that blueprint's rules. __init__ is the rule that runs when a new instance is created. self is the rule that says this method belongs to this specific instance, not the blueprint.",
        "syntax_anchor": "class MyClass:\n    def __init__(self, param):\n        self.param = param\n    def method(self):\n        return self.param",
        "common_errors": [
            "Forgetting self as first parameter in every method",
            "Confusing the class with an instance of it",
            "Forgetting to call __init__ logic via super() when inheriting",
        ],
    },
    "modules": {
        "label": "Modules",
        "domain": "python",
        "brief": "Python's default rule is that everything lives in one file. Modules break that rule — they let you split code across files and pull specific rules in from elsewhere. import brings in another file's ruleset. from...import pulls in a specific rule by name. This lets you build complex systems out of smaller independent rulesets without them interfering with each other.",
        "syntax_anchor": "import module_name  |  from module import thing  |  import module as alias",
        "common_errors": [
            "Module not found — check the file is in the same directory or installed",
            "Circular imports — A imports B which imports A",
            "from module import * pollutes namespace — avoid it",
        ],
    },

    # ════════════════════════════════════════════════════════════════
    # PYTHON — INTERMEDIATE
    # ════════════════════════════════════════════════════════════════

    "strings_advanced": {
        "label": "String Manipulation",
        "domain": "python",
        "brief": "Strings follow one core rule: they cannot be changed. Every method that looks like it modifies a string is actually creating a new one and handing it back. Slicing is a rule that creates a new string from a range of positions. f-strings are a rule that lets other values be inserted into a string at the moment it's created. split and join are inverse rules — one breaks a string into a list, the other collapses a list back into a string.",
        "syntax_anchor": "s[1:4]  |  s.split(',')  |  ','.join(list)  |  f'{name} is {age}'",
        "common_errors": [
            "Strings are immutable — methods return new strings, don't modify in place",
            "s.strip() removes whitespace from both ends",
            "split() without argument splits on any whitespace",
        ],
    },
    "list_comprehensions": {
        "label": "List Comprehensions",
        "domain": "python",
        "brief": "A for-loop that builds a list is a two-step rule: loop, then append. A list comprehension collapses that into one rule written in one line. The structure is always the same: what to keep, where to get it from, and optionally what condition filters it. It's not new behavior — it's a more compact way to write the same transformation rule.",
        "syntax_anchor": "[expr for item in iterable if condition]",
        "common_errors": [
            "Condition is optional — [x for x in lst] is valid",
            "Can nest but deeply nested comprehensions hurt readability",
            "Use () for generator expressions when you don't need the whole list at once",
        ],
    },
    "nested_data_structures": {
        "label": "Nested Data Structures",
        "domain": "python",
        "brief": "Lists and dicts can contain other lists and dicts. The rule stacks — you're applying lookup rules inside lookup rules. A dict of dicts means you look up by key to get another ruleset, then look up again inside that. Real world data almost always has this shape. The deeper you go, the more important it is to use .get() at every level — one missing key anywhere in the chain crashes the whole lookup.",
        "syntax_anchor": "data['users'][0]['name']  |  for user in data['users']:  user.get('role')",
        "common_errors": [
            "KeyError on nested access — use .get() at every level",
            "Modifying a nested dict modifies the original — use copy.deepcopy() if needed",
            "Printing nested structures — use json.dumps(data, indent=2) for readability",
        ],
    },
    "function_advanced": {
        "label": "Advanced Functions",
        "domain": "python",
        "brief": "Basic functions have a fixed input rule — call with exactly the right arguments. Advanced functions let you modify that rule. Default arguments create a fallback rule when an argument isn't provided. *args breaks the fixed count rule — it accepts any number of positional arguments as a tuple. **kwargs does the same for named arguments as a dict. Functions are also objects — they can be passed as arguments, returned from other functions, and stored in variables.",
        "syntax_anchor": "def func(a, b=10, *args, **kwargs):  |  func(1, key='val')",
        "common_errors": [
            "Mutable default arguments are shared across calls — use None and set inside",
            "*args is a tuple. **kwargs is a dict",
            "Keyword arguments must come after positional arguments",
        ],
    },
    "scope_closures": {
        "label": "Scope and Closures",
        "domain": "python",
        "brief": "Python has a rule for which names are visible where: Local first, then Enclosing, then Global, then Built-in. This is the LEGB rule — the search order Python uses when you reference a name. A closure is what happens when a function captures a name from its enclosing scope and carries it with it. The global and nonlocal keywords modify the default scope rule — they tell Python to write to an outer layer instead of creating a new local one.",
        "syntax_anchor": "global x  |  nonlocal x  |  def outer():\n    x = 1\n    def inner(): return x",
        "common_errors": [
            "Reading a global is fine. Assigning to it without global keyword creates a local",
            "Closures capture by reference not value — late binding in loops is a classic bug",
            "nonlocal needed to assign to enclosing (not global) scope",
        ],
    },
    "iterators_generators": {
        "label": "Iterators and Generators",
        "domain": "python",
        "brief": "A list holds all its values in memory at once. An iterator breaks that rule — it produces one value at a time, on demand, and forgets the previous one. A generator is a function that follows the iterator rule using yield. yield is a pause rule — it hands a value out and freezes the function's state until the next value is requested. This makes generators memory efficient for large or infinite sequences because nothing exists until it's asked for.",
        "syntax_anchor": "def gen():\n    yield value  |  next(iterator)  |  for x in gen():",
        "common_errors": [
            "Generators can only be iterated once — exhausted after first pass",
            "yield pauses the function — execution resumes on next next() call",
            "Use itertools for common iterator patterns",
        ],
    },
    "decorators": {
        "label": "Decorators",
        "domain": "python",
        "brief": "A decorator is a rule that modifies another rule. It intercepts a function at the moment it's defined and wraps new behavior around it without touching the original function's code. The @ syntax is shorthand for passing a function into another function that returns a modified version. This lets you add logging, timing, access control, or any repeated behavior to multiple functions without duplicating code inside each one.",
        "syntax_anchor": "@decorator\ndef func():  |  def decorator(func):\n    def wrapper(*a, **kw): return func(*a, **kw)\n    return wrapper",
        "common_errors": [
            "Forgetting functools.wraps — preserves original function metadata",
            "Decorator is applied at definition time not call time",
            "Decorators with arguments need three levels of nesting",
        ],
    },
    "context_managers": {
        "label": "Context Managers",
        "domain": "python",
        "brief": "Some operations have a setup rule and a teardown rule that must always run as a pair — open a file, close the file. A context manager enforces that pairing. The with statement is the rule that says: run setup, execute the block, run teardown no matter what happens in between — even if it crashes. __enter__ is the setup rule. __exit__ is the teardown rule. contextlib.contextmanager lets you write the same thing as a generator using yield as the dividing point.",
        "syntax_anchor": "with open('f') as f:  |  from contextlib import contextmanager\n@contextmanager\ndef cm(): yield",
        "common_errors": [
            "__exit__ receives exception info — return True to suppress, False/None to reraise",
            "contextmanager: yield exactly once",
            "Multiple context managers: with A() as a, B() as b:",
        ],
    },
    "comprehensions_advanced": {
        "label": "Dict and Set Comprehensions",
        "domain": "python",
        "brief": "The comprehension rule that builds lists also works for dicts and sets. A dict comprehension applies a transformation rule to produce key-value pairs instead of a flat list. A set comprehension applies the same rule but enforces the uniqueness rule — no duplicates survive. Both follow the same structure as list comprehensions, just with different brackets and different output rules.",
        "syntax_anchor": "{k: v for k, v in items}  |  {x for x in lst if x > 0}",
        "common_errors": [
            "Dict comprehension needs both key and value expressions",
            "Sets have no duplicates — useful for deduplication",
            "frozenset for immutable sets usable as dict keys",
        ],
    },
    "working_with_json": {
        "label": "Working with JSON",
        "domain": "python",
        "brief": "JSON is a text format with its own ruleset for representing data. Python dicts and JSON objects look similar but follow different rules. json.loads applies the translation rule from JSON text to a Python dict. json.dumps applies the reverse rule. The key rule difference: JSON requires string keys and uses null/true/false instead of Python's None/True/False. Violating JSON's rules produces a JSONDecodeError.",
        "syntax_anchor": "json.loads(string)  |  json.dumps(obj, indent=2)  |  json.load(f)  |  json.dump(obj, f)",
        "common_errors": [
            "JSON keys must be strings — Python allows other types but JSON doesn't",
            "None becomes null, True becomes true in JSON",
            "json.JSONDecodeError if string is not valid JSON — wrap in try/except",
        ],
    },
    "working_with_files_advanced": {
        "label": "Advanced File Operations",
        "domain": "python",
        "brief": "Basic file I/O reads and writes content. Advanced file operations let you apply rules to the filesystem itself — create directories, check if paths exist, rename or delete files. pathlib.Path is the modern ruleset for this. It treats filesystem paths as objects with methods rather than strings you manipulate manually. exist_ok=True modifies the mkdir rule to say don't crash if it already exists.",
        "syntax_anchor": "from pathlib import Path  |  Path('dir').mkdir(parents=True, exist_ok=True)  |  p.read_text()",
        "common_errors": [
            "pathlib.Path is the modern way — cleaner than os.path string manipulation",
            "exist_ok=True prevents error if directory already exists",
            "Binary mode 'rb'/'wb' for images, executables — text mode for text",
        ],
    },
    "working_with_csv": {
        "label": "Working with CSV",
        "domain": "python",
        "brief": "CSV is a text format where the rule is: values separated by commas, rows separated by newlines. The csv module applies that parsing rule so you don't write it yourself. DictReader modifies the rule further — it uses the first row as a header and gives you each subsequent row as a dict keyed by column name instead of a list of positions. Every value comes out as a string — converting to numbers is your rule to apply.",
        "syntax_anchor": "import csv\nwith open('f.csv') as f:\n    reader = csv.DictReader(f)\n    for row in reader: print(row)",
        "common_errors": [
            "newline='' needed on open() when writing CSV on Windows",
            "DictReader uses first row as header by default",
            "All values are strings — convert numbers explicitly",
        ],
    },
    "command_line_args": {
        "label": "Command Line Arguments",
        "domain": "python",
        "brief": "When Python runs a script, everything typed after the filename is available as raw strings in sys.argv. argparse applies a parsing rule to that raw input — it turns loose strings into named, typed, validated arguments your script can actually use. Each add_argument call defines a new input rule: what it's called, what type it expects, whether it's required. parse_args() enforces all those rules at once and crashes with a helpful message if any are violated.",
        "syntax_anchor": "import argparse\np = argparse.ArgumentParser()\np.add_argument('--name')\nargs = p.parse_args()",
        "common_errors": [
            "sys.argv[0] is the script name — arguments start at [1]",
            "add_argument with required=True raises error if missing",
            "type=int converts argument string to int automatically",
        ],
    },
    "http_requests": {
        "label": "HTTP Requests",
        "domain": "python",
        "brief": "HTTP is a ruleset for how computers ask each other for data. GET is the rule for fetching. POST is the rule for sending. The requests library applies those rules without you writing the network code. The response follows its own ruleset — a status code tells you whether the rule was followed successfully. raise_for_status() is a rule that says crash immediately on failure codes rather than silently handing you broken data.",
        "syntax_anchor": "import requests\nr = requests.get(url)\nr.raise_for_status()\ndata = r.json()",
        "common_errors": [
            "raise_for_status() raises exception on 4xx/5xx — call it before using response",
            "Wrap in try/except requests.exceptions.RequestException for network errors",
            "Pass params={} for query string, json={} for POST body",
        ],
    },
    "regular_expressions": {
        "label": "Regular Expressions",
        "domain": "python",
        "brief": "A regular expression is a rule written in a pattern language that describes what a string is allowed to look like. re.search applies that rule and returns the first match. re.findall returns every match. re.sub applies a replacement rule everywhere the pattern matches. The pattern itself is a miniature ruleset — dots, brackets, quantifiers are all rules about what characters are allowed at each position.",
        "syntax_anchor": "import re\nre.search(pattern, string)  |  re.findall(pattern, string)  |  re.sub(pattern, repl, string)",
        "common_errors": [
            "Use raw strings r'pattern' to avoid backslash confusion",
            "search() finds first match anywhere. match() only at start. fullmatch() entire string",
            "Compile with re.compile() if using same pattern many times",
        ],
    },

    # ════════════════════════════════════════════════════════════════
    # PYTHON — ADVANCED
    # ════════════════════════════════════════════════════════════════

    "oop_advanced": {
        "label": "OOP — Inheritance and Polymorphism",
        "domain": "python",
        "brief": "A class defines a ruleset. Inheritance lets a new class start with another class's full ruleset and then modify it. The child class inherits every rule from the parent. Override a method to replace a specific rule with a new one. super() is how you call the parent's version of a rule from inside the child's override — extend the rule rather than replace it entirely. Duck typing is Python's rule that says if it behaves like the right thing, it is the right thing.",
        "syntax_anchor": "class Child(Parent):\n    def method(self):\n        super().method()\n        # extend",
        "common_errors": [
            "Forgetting super().__init__() loses parent setup",
            "Multiple inheritance follows MRO — Method Resolution Order",
            "isinstance() checks type including subclasses",
        ],
    },
    "dunder_methods": {
        "label": "Dunder Methods",
        "domain": "python",
        "brief": "Python's built-in types follow rules that make them work with operators and built-in functions — len() on a list, + between two strings. Dunder methods let your custom classes follow those same rules. __str__ is the rule for how your object becomes a readable string. __len__ is the rule for what len() returns. __eq__ is the rule for what == means. You're not adding new behavior — you're hooking into Python's existing ruleset and telling it how your object participates.",
        "syntax_anchor": "def __str__(self): return 'human readable'  |  def __len__(self): return len(self.data)",
        "common_errors": [
            "__str__ is for humans. __repr__ is for developers/debugging",
            "__eq__ should also implement __hash__ if object is hashable",
            "Implement __iter__ and __next__ to make objects iterable",
        ],
    },
    "error_handling_advanced": {
        "label": "Advanced Error Handling",
        "domain": "python",
        "brief": "Basic error handling catches built-in exceptions. Advanced error handling lets you define your own exception rules — custom exception classes that carry specific meaning for your system. Raising a custom exception is declaring that a specific rule was violated. Exception chaining with raise...from preserves the original cause so you know which rule broke first. Logging is a separate rule layer — it records what happened without changing how the program responds to it.",
        "syntax_anchor": "class MyError(Exception): pass  |  raise MyError('msg') from original_err  |  import logging",
        "common_errors": [
            "raise from None suppresses chained exception context",
            "Custom exceptions should inherit from Exception not BaseException",
            "Log the exception, don't just print — use logging.exception() inside except",
        ],
    },
    "testing": {
        "label": "Testing with pytest",
        "domain": "python",
        "brief": "A test is a rule written in code that says this function, given this input, must produce this output. pytest is the engine that enforces those rules automatically every time you run it. If the rule is violated the test fails and tells you exactly where. assert is the enforcement mechanism — it crashes with a clear message when the rule isn't met. Tests are rules about your rules — a second layer that catches when your code stops behaving as intended.",
        "syntax_anchor": "def test_something():\n    assert func(input) == expected\n\n# run: pytest test_file.py",
        "common_errors": [
            "Test functions must start with test_",
            "pytest.raises() to test that exceptions are raised correctly",
            "Fixtures provide reusable setup — @pytest.fixture",
        ],
    },
    "type_hints": {
        "label": "Type Hints",
        "domain": "python",
        "brief": "Python's default rule is that any name can hold any type — it doesn't check. Type hints let you declare the intended type rule without enforcing it at runtime. They're documentation that tools like mypy can read and use to catch rule violations before the code runs. Optional[X] is the rule that says this value can be X or it can be absent. They don't change how Python executes your code — they change what tools can tell you about it.",
        "syntax_anchor": "def func(name: str, count: int) -> list[str]:  |  from typing import Optional, Union",
        "common_errors": [
            "Type hints don't enforce anything at runtime — Python still runs wrong types",
            "Use Optional[X] for values that can be None",
            "list[str] syntax requires Python 3.9+ — use List[str] from typing for older",
        ],
    },
    "dataclasses": {
        "label": "Dataclasses",
        "domain": "python",
        "brief": "A regular class requires you to manually write the rules for initialization, string representation, and equality comparison. A dataclass reads your field declarations and generates those rules automatically. The @dataclass decorator is modifying the class rule — it intercepts the class at definition and stamps in the boilerplate methods you would have written by hand. frozen=True adds an immutability rule — instances can't be modified after creation.",
        "syntax_anchor": "from dataclasses import dataclass\n@dataclass\nclass Point:\n    x: float\n    y: float",
        "common_errors": [
            "Mutable default values need field(default_factory=list)",
            "frozen=True makes instances immutable and hashable",
            "post_init for validation logic after auto-generated __init__",
        ],
    },
    "concurrency_basics": {
        "label": "Concurrency Basics",
        "domain": "python",
        "brief": "Python's default rule is that code runs one instruction at a time in sequence. Concurrency breaks that rule — it lets multiple things appear to happen simultaneously. Threading applies a rule that says run these functions in overlapping time slices, sharing the same memory. Multiprocessing applies a stricter rule — separate memory, true parallelism, but higher cost. asyncio applies a cooperative rule — tasks voluntarily pause at await points so others can run. Which rule fits depends on whether your bottleneck is waiting for I/O or burning CPU.",
        "syntax_anchor": "import threading\nt = threading.Thread(target=func)\nt.start()\nt.join()",
        "common_errors": [
            "GIL limits true parallelism in threading — use multiprocessing for CPU work",
            "Race conditions when threads share data — use locks",
            "asyncio needs async def and await — mixing sync and async is tricky",
        ],
    },
    "working_with_databases": {
        "label": "SQLite with Python",
        "domain": "python",
        "brief": "A database applies a persistent ruleset to structured data — tables define what shape data must be, queries define what you want back. sqlite3 lets Python talk to a database that lives in a single file. The cursor is the object that carries your query rule to the database and returns the result. Parameterized queries with ? are a security rule — they prevent user input from being interpreted as query rules, which is how SQL injection attacks work.",
        "syntax_anchor": "import sqlite3\nconn = sqlite3.connect('db.sqlite3')\nc = conn.cursor()\nc.execute('SELECT * FROM t WHERE id=?', (id,))",
        "common_errors": [
            "Never use string formatting in SQL — use ? placeholders to prevent injection",
            "commit() required after INSERT/UPDATE/DELETE or changes don't persist",
            "fetchone() returns one row or None. fetchall() returns list of rows",
        ],
    },
    "virtual_environments": {
        "label": "Virtual Environments and Packaging",
        "domain": "python",
        "brief": "Python's default rule is that installed packages are shared globally across all projects. A virtual environment breaks that rule — it creates an isolated ruleset of installed packages that only applies inside that environment. This prevents one project's dependency rules from conflicting with another's. pip is the tool that modifies the environment's ruleset by installing or removing packages. requirements.txt is a snapshot of the current ruleset so someone else can reproduce it exactly.",
        "syntax_anchor": "python3 -m venv venv  |  source venv/bin/activate  |  pip install pkg  |  pip freeze > requirements.txt",
        "common_errors": [
            "Always activate the venv before installing — otherwise installs globally",
            "requirements.txt lets others reproduce your exact environment",
            "deactivate exits the environment and restores the global rule",
        ],
    },
}
