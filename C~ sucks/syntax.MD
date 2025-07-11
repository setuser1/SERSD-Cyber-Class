C~ Language Syntax Reference
===========================

C~ is a C-inspired language with a simplified syntax, designed to be compiled to LLVM IR using the provided Python compiler.

---------------------------
BASIC SYNTAX
---------------------------

- Statements end with `:` (colon) or `;` (semicolon).
- Functions can use `expr` as a synonym for `void`.
- Variable declarations: `int x:`, `float y:`, `char arr[10]:`
- Assignment: `x = 5:`
- Comments: Use `//` for single-line comments.

---------------------------
CONTROL FLOW
---------------------------

- **if / xif / else** (xif is like `elif` in Python):

```
if (x == 1) {
    printf("one\n"):
}
xif (x == 2) {
    printf("two\n"):
}
else {
    printf("other\n"):
}
```

- **while** loops:

```
while x < 10 {
    printf("{x}"):
    x = x + 1:
}
```

---------------------------
FUNCTIONS
---------------------------

- Declaration:
```
int add(int a, int b) {
    int result:
    result = a + b:
    return result:
}
```
- `expr` is used for functions that do not return a value (like `void` in C).

---------------------------
INPUT/OUTPUT
---------------------------

- Print: `printf("Hello\n"):`
- Print variable: `printf("{x}"):`
- Print string variable: `printf("{str}"):
- Input: `scanf("%d", &x):`

---------------------------
ARRAYS AND STRINGS
---------------------------

- Declare array: `int arr[10]:`
- Assign string: `char str[10]: str = "hello":`
- Access element: `x = arr[0]:`
- Assign element: `arr[0] = 5:`

---------------------------
EXPRESSIONS
---------------------------

- Arithmetic: `+`, `-`, `*`, `/`
- Assignment: `x = y + 2:`
- Function call: `y = add(x, 5):`

---------------------------
RETURN
---------------------------

- Return value: `return x:`
- Return nothing: `return:`

---------------------------
EXAMPLE PROGRAM
---------------------------

```
expr print_menu() {
    printf("Menu\n"):
    printf("1. Add\n"):
    printf("2. Subtract\n"):
    printf("3. Exit\n"):
}

int add(int a, int b) {
    int result:
    result = a + b:
    return result:
}

int main() {
    int choice:
    int x:
    int y:
    int result:
    int running:
    running = 1:
    while (running == 1) {
        print_menu():
        scanf("%d", &choice):
        if (choice == 3) {
            running = 0:
            printf("Goodbye!\n"):
        }
        if (choice == 1) {
            printf("Enter first number: "):
            scanf("%d", &x):
            printf("Enter second number: "):
            scanf("%d", &y):
            result = add(x, y):
            printf("Result: {result}\n"):
        }
        if (choice == 2) {
            printf("Enter first number: "):
            scanf("%d", &x):
            printf("Enter second number: "):
            scanf("%d", &y):
            result = x - y:
            printf("Result: {result}\n"):
        }
    }
    return 0:
}
```

---------------------------
NOTES
---------------------------

- Format specifiers in `printf`/`scanf` are supported for compatibility, but you can print variables directly.
- Use `:` or `;` to end statements.
- Strings use double quotes.
- `xif` is used for `elif` (else-if) branches.

---------------------------
Enjoy using C~!
---------------------------
