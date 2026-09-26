"""
Static check: inside MainWindow.__init__ and _build_ui, flag any `self.X`
that is READ before it is ASSIGNED.

This is the exact class of bug that produced:
    AttributeError: 'MainWindow' object has no attribute 'config'
and it can't be caught by compileall, so check it explicitly.
"""
import ast
import sys

PATH = 'quickytdl/ui/main_window.py'

# Attributes that legitimately come from QMainWindow or are set elsewhere.
INHERITED = {
    'setWindowTitle', 'resize', 'setWindowIcon', 'setCentralWidget',
    'statusBar', 'close', 'show', 'centralWidget', 'setMinimumSize',
    'setStyleSheet', 'setContextMenuPolicy', 'setAcceptDrops', 'style',
    'font', 'palette', 'update', 'width', 'height', 'setWindowState',
}


def attr_events(fn):
    """Yield (lineno, name, 'store'|'load') for self.X in source order."""
    events = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == 'self':
            kind = 'store' if isinstance(node.ctx, ast.Store) else 'load'
            events.append((node.lineno, node.col_offset, node.attr, kind))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


def call_lines(fn, name):
    """Line numbers where `self.<name>()` is called inside fn."""
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) \
                and node.func.value.id == 'self' and node.func.attr == name:
            out.append(node.lineno)
    return out


def check(fn, methods, preassigned, deferred_assigns=None):
    """Return list of (lineno, attr) read before assignment."""
    assigned = set(preassigned)
    problems = []
    # Names referenced only inside lambdas/nested funcs run later, so skip them.
    lambda_lines = set()
    for node in ast.walk(fn):
        # NB: skip `fn` itself - it is a FunctionDef, and including it would
        # mark every line in the body as deferred, silently disabling the
        # whole check.
        if node is fn:
            continue
        if isinstance(node, (ast.Lambda, ast.FunctionDef)):
            for sub in ast.walk(node):
                if hasattr(sub, 'lineno'):
                    lambda_lines.add(sub.lineno)

    deferred_assigns = deferred_assigns or {}
    for lineno, _col, attr, kind in attr_events(fn):
        # A helper called earlier in the body (e.g. self._build_ui()) has
        # already created its widgets by the time we reach this line.
        for call_line, names in deferred_assigns.items():
            if lineno > call_line:
                assigned |= names
        if kind == 'store':
            assigned.add(attr)
            continue
        if attr in assigned or attr in methods or attr in INHERITED:
            continue
        if lineno in lambda_lines:
            continue  # deferred execution
        problems.append((lineno, attr))
    return problems


def main():
    src = open(PATH, encoding='utf-8').read()
    tree = ast.parse(src)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
    methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}

    init = next(n for n in cls.body
                if isinstance(n, ast.FunctionDef) and n.name == '__init__')
    build = next((n for n in cls.body
                  if isinstance(n, ast.FunctionDef) and n.name == '_build_ui'), None)

    failed = False

    # Attributes created by helpers that __init__ calls.
    deferred = {}
    for helper in ('_build_ui', '_connect_signals'):
        hfn = next((n for n in cls.body
                    if isinstance(n, ast.FunctionDef) and n.name == helper), None)
        if hfn is None:
            continue
        names = {a for _l, _c, a, k in attr_events(hfn) if k == 'store'}
        for cl in call_lines(init, helper):
            deferred.setdefault(cl, set()).update(names)

    probs = check(init, methods, preassigned=set(), deferred_assigns=deferred)
    print("__init__:")
    if probs:
        failed = True
        for lineno, attr in probs:
            print(f"  FAIL line {lineno}: self.{attr} read before assignment")
    else:
        print("  OK - no attribute read before assignment")

    if build is not None:
        # _build_ui runs after __init__ body up to its call site, so treat
        # everything __init__ assigns as available.
        init_assigned = {a for _l, _c, a, k in attr_events(init) if k == 'store'}
        probs = check(build, methods, preassigned=init_assigned)
        print("_build_ui:")
        if probs:
            failed = True
            for lineno, attr in probs:
                print(f"  FAIL line {lineno}: self.{attr} read before assignment")
        else:
            print("  OK - no attribute read before assignment")

    print("\nRESULT:", "FAILED" if failed else "PASSED")
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
