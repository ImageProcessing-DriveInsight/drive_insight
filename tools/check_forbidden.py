"""Static A-12 check; never import or execute the inspected Python source."""

import argparse
import ast
from dataclasses import asdict, dataclass, field
import io
import json
from pathlib import Path
import tokenize

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_CV2_IO = frozenset({
    "imread", "imwrite", "imdecode", "imencode", "imreadmulti", "imwritemulti",
    "imcount", "VideoCapture", "VideoWriter", "VideoWriter_fourcc",
})
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    column: int
    code: str
    message: str


@dataclass
class ScanResult:
    files: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def exit_code(self):
        if any(f.code.endswith("_ERROR") for f in self.findings):
            return 2
        return 1 if self.findings else 0


def _qualified(node, bindings):
    if isinstance(node, ast.Name):
        return bindings.get(node.id, node.id if node.id in ("getattr", "__import__") else None)
    if isinstance(node, ast.Attribute):
        base = _qualified(node.value, bindings)
        if base:
            return (base + "." + node.attr).replace("cv2.cv2", "cv2")
    if isinstance(node, ast.Call):
        fn = _qualified(node.func, bindings)
        if fn in ("__import__", "importlib.import_module") and node.args:
            name = node.args[0]
            if isinstance(name, ast.Constant) and isinstance(name.value, str):
                if name.value == "cv2" or name.value.startswith("cv2."):
                    return name.value.replace("cv2.cv2", "cv2")
        if fn == "getattr" and len(node.args) >= 2:
            base = _qualified(node.args[0], bindings)
            if base and (base == "cv2" or base.startswith("cv2.")):
                member = node.args[1]
                suffix = member.value if isinstance(member, ast.Constant) and isinstance(member.value, str) else "<dynamic>"
                return base + "." + suffix
    return None


def _scope_nodes(body):
    for node in body:
        yield node
        if not isinstance(node, _SCOPES):
            yield from _scope_nodes(ast.iter_child_nodes(node))


def _bindings(body, inherited, parameters=()):
    """Lexical, flow-insensitive alias collection; retain known CV aliases conservatively."""
    nodes = list(_scope_nodes(body))
    bindings = inherited.copy()
    for node in nodes:
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bindings[node.id] = None
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings[node.name] = None
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = None
    for arg in parameters:
        bindings[arg.arg] = None
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "cv2" or name.startswith("cv2.") or name == "importlib":
                    bindings[alias.asname or name.split(".")[0]] = (name if alias.asname else name.split(".")[0]).replace("cv2.cv2", "cv2")
        elif isinstance(node, ast.ImportFrom) and not node.level:
            if node.module in ("cv2", "cv2.cv2", "importlib"):
                for alias in node.names:
                    bindings[alias.asname or alias.name] = (node.module + "." + alias.name).replace("cv2.cv2", "cv2")
    assignments = [n for n in nodes if isinstance(n, (ast.Assign, ast.AnnAssign, ast.NamedExpr))]
    for _ in range(len(assignments) + 1):
        changed = False
        for node in assignments:
            value = _qualified(node.value, bindings) if node.value is not None else None
            if not value:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and bindings.get(target.id) != value:
                    bindings[target.id] = value
                    changed = True
        if not changed:
            break
    return bindings


class _Checker(ast.NodeVisitor):
    def __init__(self, tree, path):
        self.path = path
        self.scopes = [("module", _bindings(tree.body, {}))]
        self.parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        self.findings = set()

    def report(self, node, code, message):
        self.findings.add(Finding(self.path, node.lineno, node.col_offset + 1, code, message))

    def check_member(self, node, name, called=False):
        if not name or not name.startswith("cv2."):
            return
        member = name.removeprefix("cv2.")
        if member in ALLOWED_CV2_IO or (not called and member.isupper()):
            return
        self.report(node, "CV2_FORBIDDEN", f"OpenCV member is not allowed image/video IO: {name}")

    def visit_Attribute(self, node):
        parent = self.parents.get(node)
        if not (isinstance(parent, ast.Attribute) and parent.value is node):
            name = _qualified(node, self.scopes[-1][1])
            if name != "cv2":
                self.check_member(node, name)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.check_member(node, _qualified(node, self.scopes[-1][1]))

    def visit_ImportFrom(self, node):
        if not node.level and node.module and (node.module == "cv2" or node.module.startswith("cv2.")):
            for alias in node.names:
                if alias.name == "*":
                    self.report(node, "CV2_STAR_IMPORT", "Wildcard cv2 imports cannot be checked reliably")
                elif alias.name != "cv2":
                    self.check_member(node, (node.module + "." + alias.name).replace("cv2.cv2", "cv2"))

    def visit_Call(self, node):
        bindings = self.scopes[-1][1]
        self.check_member(node.func, _qualified(node.func, bindings), called=True)
        fn = _qualified(node.func, bindings)
        value = _qualified(node, bindings)
        if fn in ("__import__", "importlib.import_module") and value:
            self.report(node, "CV2_DYNAMIC_IMPORT", "Use an explicit cv2 import for static review")
        if fn == "getattr" and len(node.args) >= 2:
            self.check_member(node, value)
            attr = node.args[1]
            if isinstance(attr, ast.Constant) and isinstance(attr.value, str) and "_stub" in attr.value:
                self.report(node, "STUB_IDENTIFIER", f"Dynamic attribute contains _stub: {attr.value}")
        self.generic_visit(node)

    def _function(self, node):
        for expr in node.decorator_list:
            self.visit(expr)
        self.visit(node.args)
        if node.returns:
            self.visit(node.returns)
        inherited = next(bindings for kind, bindings in reversed(self.scopes) if kind != "class")
        args = node.args
        parameters = args.posonlyargs + args.args + args.kwonlyargs + ([args.vararg] if args.vararg else []) + ([args.kwarg] if args.kwarg else [])
        self.scopes.append(("function", _bindings(node.body, inherited, parameters)))
        for child in node.body:
            self.visit(child)
        self.scopes.pop()

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def visit_ClassDef(self, node):
        for child in node.bases + node.keywords + node.decorator_list:
            self.visit(child)
        self.scopes.append(("class", _bindings(node.body, self.scopes[-1][1])))
        for child in node.body:
            self.visit(child)
        self.scopes.pop()

    def visit_Lambda(self, node):
        self.visit(node.args)
        args = node.args
        parameters = args.posonlyargs + args.args + args.kwonlyargs + ([args.vararg] if args.vararg else []) + ([args.kwarg] if args.kwarg else [])
        self.scopes.append(("function", _bindings([node.body], self.scopes[-1][1], parameters)))
        self.visit(node.body)
        self.scopes.pop()


def check_source(source, path="<source>"):
    """Return sorted findings, including parse errors, without running the source."""
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as exc:
        return [Finding(path, getattr(exc, "lineno", None) or 1, getattr(exc, "offset", None) or 1,
                        "PARSE_ERROR", str(exc))]
    checker = _Checker(tree, path)
    checker.visit(tree)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME and "_stub" in token.string:
            checker.findings.add(Finding(path, token.start[0], token.start[1] + 1,
                                         "STUB_IDENTIFIER", f"Identifier contains _stub: {token.string}"))
    return sorted(checker.findings)


def scan_paths(paths=None):
    """Recursively scan explicit .py files/directories; relative paths use project root."""
    result = ScanResult()
    files = set()
    for value in ([ROOT / "src"] if paths is None else paths):
        path = Path(value)
        path = path if path.is_absolute() else ROOT / path
        try:
            if path.is_symlink():
                raise ValueError("Symlink scan roots are not supported")
            if path.is_dir():
                found = list(path.rglob("*.py"))
                if not found:
                    raise ValueError("No Python source files in directory")
                files.update(found)
            elif path.is_file() and path.suffix == ".py":
                files.add(path)
            else:
                raise ValueError("Expected an existing Python file or directory")
        except (OSError, ValueError) as exc:
            result.findings.append(Finding(str(path), 1, 1, "SCAN_ERROR", str(exc)))
    if paths is not None and not paths:
        result.findings.append(Finding("<input>", 1, 1, "SCAN_ERROR", "No scan paths supplied"))
    for path in sorted(files):
        path = path.absolute()
        label = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
        result.files.append(label)
        try:
            if path.is_symlink():
                raise OSError("Symlink source files are not supported")
            with tokenize.open(path) as stream:
                source = stream.read()
            result.findings.extend(check_source(source, label))
        except (OSError, UnicodeError, SyntaxError) as exc:
            result.findings.append(Finding(label, 1, 1, "READ_ERROR", str(exc)))
    result.findings = sorted(set(result.findings))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Files/directories relative to project root (default: src)")
    parser.add_argument("--json", action="store_true", help="Emit one JSON report to stdout")
    args = parser.parse_args(argv)
    result = scan_paths(args.paths or None)
    if args.json:
        print(json.dumps({"files_scanned": len(result.files), "files": result.files,
                          "findings": [asdict(f) for f in result.findings], "exit_code": result.exit_code},
                         ensure_ascii=False, indent=2))
    else:
        for finding in result.findings:
            print(f"{finding.path}:{finding.line}:{finding.column}: {finding.code}: {finding.message}")
        print(f"Scanned {len(result.files)} Python files; {len(result.findings)} findings")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
