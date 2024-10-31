
def remove_padding(s):
    lines = s.splitlines()
    minpadding = 100
    for l in lines:
        if len(l) > 0:
            minpadding = min(minpadding, len(l) - len(l.lstrip(' ')))
    if minpadding == 100:
        return s

    lines = [l[minpadding:] for l in lines]
    return '\n'.join(lines)
