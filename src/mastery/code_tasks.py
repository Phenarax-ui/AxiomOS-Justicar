"""
code_tasks.py - the WRITE-IT challenges, one per concept (pure data, no logic).

curriculum.py teaches and quizzes a concept. This is the capstone: once you've
shown you UNDERSTAND it (the quiz), the tutor hands you a small coding task from
here, you write the function in my_code/<concept>.py, and code_check.py RUNS it
against the tests to see if it actually works.

Kept separate from curriculum.py - the same way mastery.py is kept away from the
model - so you can add challenges without touching the concept library. Not every
concept needs one: only the keys listed here get a code challenge. Add more as you
go (that part's yours - it's good practice to design a task + its tests).

Each entry:
  task  - what to build, in plain words, with an example (shown to you)
  func  - the exact function name the tutor will call to test your code
  tests - list of (args_tuple, expected_return). Your function must RETURN the
          expected value for each input. Return values only - so write functions
          that return, don't print.
"""

CODE_TASKS = {

    "functions": {
        "task": ("Write a function  double(n)  that returns n times 2.\n"
                 "      Example:  double(5)  ->  10\n"
                 "      Write ONLY the function - don't call it, the tutor does."),
        "func": "double",
        "tests": [((5,), 10), ((0,), 0), ((-3,), -6)],
    },

    "lists": {
        "task": ("Write a function  first_item(items)  that returns the FIRST item of the list.\n"
                 "      Example:  first_item(['a', 'b', 'c'])  ->  'a'"),
        "func": "first_item",
        "tests": [((["a", "b", "c"],), "a"), (([10, 20],), 10)],
    },

    "list_methods_iteration": {
        "task": ("Write a function  add_exclaim(words)  that returns a NEW list with '!' added to\n"
                 "      the end of every word. Use a for-loop.\n"
                 "      Example:  add_exclaim(['hi', 'yo'])  ->  ['hi!', 'yo!']"),
        "func": "add_exclaim",
        "tests": [((["hi", "yo"],), ["hi!", "yo!"]), (([],), [])],
    },

    "dictionaries": {
        "task": ("Write a function  get_score(scores, name)  that returns the score for name from\n"
                 "      the dict, or 0 if name isn't in it.  (Hint: .get)\n"
                 "      Example:  get_score({'rex': 5}, 'rex')  ->  5   |   get_score({'rex': 5}, 'max')  ->  0"),
        "func": "get_score",
        "tests": [(({"rex": 5}, "rex"), 5), (({"rex": 5}, "max"), 0), (({}, "x"), 0)],
    },

    "while_loops": {
        "task": ("Write a function  count_down(n)  that uses a WHILE loop to return a list counting\n"
                 "      down from n to 1.\n"
                 "      Example:  count_down(3)  ->  [3, 2, 1]   |   count_down(0)  ->  []"),
        "func": "count_down",
        "tests": [((3,), [3, 2, 1]), ((1,), [1]), ((0,), [])],
    },

}
