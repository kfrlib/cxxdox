import re

QUOTES = {"'", '"'}


def skip_literal(s, i):
    """If s[i] starts a char/string literal, return index just past its end; else None."""
    if i >= len(s) or s[i] not in QUOTES:
        return None
    q = s[i]
    j = i + 1
    n = len(s)
    while j < n:
        if s[j] == '\\':
            j += 2  # skip escaped char
            continue
        if s[j] == q:
            return j + 1
        j += 1
    return n  # unterminated: best effort, consume to end


def match_bracket(s, i):
    """Return index of the bracket that closes the opening bracket at s[i]."""
    pairs = {'<': '>', '(': ')', '[': ']'}
    stack = [s[i]]
    j = i + 1
    n = len(s)
    while j < n:
        lit_end = skip_literal(s, j)
        if lit_end is not None:
            j = lit_end
            continue
        c = s[j]
        if c in pairs:
            stack.append(c)
        elif stack and pairs[stack[-1]] == c:
            stack.pop()
            if not stack:
                return j
        j += 1
    return n - 1  # unbalanced input: best effort


def parse_cpp_identifier(s):
    """Best-effort split of a C++ id-expression into scope, name, tparams, params."""
    s = s.strip()
    pairs = {'<': '>', '(': ')', '[': ']'}
    closers = set(pairs.values())
    stack = []
    last_split = -1
    i, n = 0, len(s)

    # Find the last top-level "::" (i.e. not inside <>, (), [], or a literal)
    while i < n:
        lit_end = skip_literal(s, i)
        if lit_end is not None:
            i = lit_end
            continue
        c = s[i]
        if c in pairs:
            stack.append(c)
        elif c in closers:
            if stack and pairs[stack[-1]] == c:
                stack.pop()
        elif not stack and c == ':' and i + 1 < n and s[i + 1] == ':':
            last_split = i
            i += 2
            continue
        i += 1

    if last_split >= 0:
        scope, rest = s[:last_split + 2], s[last_split + 2:]
    else:
        scope, rest = '', s
    rest = rest.lstrip()

    # libclang synthesizes placeholder names like "(Unnamed enum at foo.hpp:5:1)"
    # or "(Anonymous struct at foo.hpp:5:1)" for anonymous entities. These look
    # like a parenthesized expression, so they must be recognized as the name
    # before falling back to the identifier regex (which would otherwise leave
    # them unmatched and let the paren be misread as a params list).
    m_unnamed = re.match(r'\((?:Unnamed|Anonymous) (?:union|struct|enum) at ', rest)
    if m_unnamed:
        j = match_bracket(rest, 0)
        name, rest = rest[:j + 1], rest[j + 1:]
    else:
        # Operator function names include tokens that normally introduce
        # template arguments or a parameter list.  Consume those tokens as
        # part of the name first, leaving a following (...) as the function
        # parameter list.
        m_operator = re.match(r'operator(?:\(\)|\[\]|[~!%^&*+\-=|<>/,]+)', rest)
        if m_operator:
            name = m_operator.group(0)
            rest = rest[m_operator.end():]
            # A trailing '<' may instead be the delimiter of explicit
            # template arguments, e.g. operator<<<T> means operator<< <T>.
            candidate = name.rfind('<')
            if candidate >= 0:
                possible_tparams = name[candidate:] + rest
                j = match_bracket(possible_tparams, 0)
                if j < len(possible_tparams) and possible_tparams[j] == '>':
                    name, rest = name[:candidate], possible_tparams
        else:
            m = re.match(r'~?[A-Za-z_][A-Za-z0-9_]*', rest)
            name = m.group(0) if m else ''
            rest = rest[m.end():] if m else rest

    tparams = params = ''
    rest = rest.lstrip()
    if rest.startswith('<'):
        j = match_bracket(rest, 0)
        tparams, rest = rest[:j + 1], rest[j + 1:]
    rest = rest.lstrip()
    if rest.startswith('('):
        j = match_bracket(rest, 0)
        params = rest[:j + 1]

    return scope, name, tparams, params


if __name__ == '__main__':
    tests = [
        "fn",
        "fn<T>",
        "fn<T>(const T&)",
        "fn(const T&)",
        "scope::fn",
        "scope::fn<A<T>>",
        "some_class<T, U<T>>",
        "std::unique_ptr<T[]>",
        "some_class<T, U<T>>::some_class(const some_class<T, U<T>>&)",
        "scope<T, U<T>>::fn(const T[])",
        "ns::Test1<std::integral_constant<int, square(7) * 2>>::method4()",
        "ns::Test1<Chars<'(', '[', '<'>>::fn()",
        'ns::Test1<String<"([<">>::fn()',
        'ns::Test1<String<"([<">>::fn(const String<"([<">&)',
        'ns::Test1<String<"([<">>',
        'func<std::integral_constant<int, stringHash("([<")>>(A<B()>, B<C[]>)',
        'ns::(Unnamed enum at library.hpp:5)::ERR_ACCESS',
        '(Unnamed enum at library.hpp:410:5)',
        'ns::(Unnamed enum at library.hpp:5)',
        'MyClass::operator()()',
        'MyClass::operator()(Args&&...)',
        'MyClass::operator<(T,T)',
        'MyClass::operator<<(T, T)',
        'operator<<T>(T, T)',
        'operator<<<T>(T, T)',
        'operator< <T> (T, T)',
        'operator<< <T> (T, T)',
        'func <T> (T)',
    ]

    rows = [parse_cpp_identifier(t) for t in tests]
    w = [max(len(r[i]) for r in rows + [("scope", "name", "tparams", "params")]) for i in range(4)]
    header = ("scope", "name", "tparams", "params")
    print("  ".join(h.ljust(w[i]) for i, h in enumerate(header)))
    print("  ".join("-" * w[i] for i in range(4)))
    for r in rows:
        print("  ".join(r[i].ljust(w[i]) for i in range(4)))
