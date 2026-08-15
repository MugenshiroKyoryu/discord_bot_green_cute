#!/usr/bin/env python3
"""แปลง OpenAPI spec เป็น node/edge ที่ graphify เข้าใจ

graphify มี AST extractor สำหรับโค้ด แต่ไม่มีตัวอ่าน JSON เชิงความหมาย
ไฟล์ spec จึงได้ 0 node ถ้าปล่อยให้สแกนตามปกติ (warning #1666)

โมดูลนี้ลอกโครงมาจาก graphify/cargo_introspect.py:47-109 คือคืน
``{"nodes": [...], "edges": [...]}`` รูปแบบเดียวกับที่ graphify/cli.py:3618-3628
เอาไป merge ต่อจากผล AST

สิ่งที่ผลิต:
  - node ของ operation  เช่น ``POST /series/search``
  - node ของ schema     เช่น ``SeriesModelV1``
  - edge accepts / responds_with / references ระหว่างสองอย่างข้างบน
  - edge calls_endpoint จากฟังก์ชันในโค้ดไปยัง operation ที่มันยิงจริง

รันเดี่ยว:
    python tools/openapi_graphify.py --spec docs/mangaupdates-openapi.json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

# graphify.ids คือ single source of truth ของการตั้ง node id
# ถ้าไม่ใช้ตัวนี้ id จะเพี้ยนจาก AST extractor แล้ว edge จะไปเกาะ ghost node (#811, #1033)
try:
    from graphify.ids import make_id
except ModuleNotFoundError:  # pragma: no cover - เผื่อรันนอก env ที่มี graphify
    print(
        "error: import graphify.ids ไม่ได้ - รันด้วย interpreter ที่ติดตั้ง graphify\n"
        "       (ดู path ใน graphify-out/.graphify_python)",
        file=sys.stderr,
    )
    raise

_CONFIDENCE_EXTRACTED = "EXTRACTED"

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

# ฟังก์ชันใน api/_client.py ที่ห่อ aiohttp ไว้ — ตัว resolver มองหา call ชื่อพวกนี้
# รูปแบบ: ชื่อฟังก์ชัน -> (index ของ arg ที่เป็น method, index ของ arg ที่เป็น url)
_REQUEST_HELPERS: dict[str, tuple[int, int]] = {
    "_request_json": (1, 2),
    "request": (0, 1),  # session.request(method, url)
}

# placeholder ที่ใช้แทนค่าที่ resolve ไม่ได้ตอนคลี่ f-string
_UNRESOLVED = "{}"

# โฟลเดอร์ที่ไม่ต้องไล่หา call site
_SKIP_DIRS = {".venv", "venv", "__pycache__", "graphify-out", "tools", ".git"}


# --------------------------------------------------------------------------
# ส่วนอ่าน spec
# --------------------------------------------------------------------------


def _load_spec(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"ไม่พบไฟล์ spec: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"spec ไม่ใช่ JSON ที่ถูกต้อง ({path}): {exc}") from exc


def _server_bases(spec: dict[str, Any]) -> list[str]:
    """คืน base path ของ server เรียงจากยาวไปสั้น เพื่อให้ตัด prefix ตัวยาวก่อน"""
    bases: list[str] = []
    for server in spec.get("servers", []) or []:
        url = server.get("url") if isinstance(server, dict) else None
        if not isinstance(url, str):
            continue
        # เก็บทั้ง url เต็มและเฉพาะ path ("/v1") เพราะโค้ดอาจ hardcode อย่างใดอย่างหนึ่ง
        bases.append(url.rstrip("/"))
        match = re.match(r"https?://[^/]+(/.*)$", url.rstrip("/"))
        if match:
            bases.append(match.group(1))
    return sorted(set(bases), key=len, reverse=True)


def _ref_name(ref: str) -> str | None:
    """``#/components/schemas/Foo`` -> ``Foo``"""
    prefix = "#/components/schemas/"
    return ref[len(prefix):] if ref.startswith(prefix) else None


def _iter_refs(obj: Any) -> Iterator[str]:
    """ไล่หา $ref ทุกตัวใน dict/list ที่ซ้อนกัน"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "$ref" and isinstance(value, str):
                name = _ref_name(value)
                if name:
                    yield name
            else:
                yield from _iter_refs(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_refs(item)


def _reachable_schemas(spec: dict[str, Any], seeds: Iterable[str]) -> set[str]:
    """transitive closure ของ schema ที่อ้างถึงกันผ่าน $ref"""
    schemas = spec.get("components", {}).get("schemas", {})
    seen: set[str] = set()
    queue = [s for s in seeds if s in schemas]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        for ref in _iter_refs(schemas.get(name, {})):
            if ref in schemas and ref not in seen:
                queue.append(ref)
    return seen


# --------------------------------------------------------------------------
# หาเลขบรรทัดใน spec เพื่อให้ source_location ชี้ของจริง
# --------------------------------------------------------------------------


def _section_key_lines(raw: str, section: str) -> dict[str, int]:
    """map key -> เลขบรรทัด สำหรับ key ที่อยู่ใต้ ``"<section>":`` หนึ่งชั้น

    spec ถูก pretty-print ด้วย indent คงที่ จึงระบุชั้นได้จากจำนวนช่องว่างหน้า key
    ถ้าไฟล์เป็น minified จะคืน dict ว่าง แล้ว caller fallback ไป "L1"
    """
    lines = raw.splitlines()
    section_pattern = re.compile(r'^(\s*)"' + re.escape(section) + r'"\s*:')
    key_pattern = re.compile(r'^(\s*)"([^"]+)"\s*:')

    start = None
    section_indent = 0
    for lineno, line in enumerate(lines, 1):
        match = section_pattern.match(line)
        if match:
            start = lineno
            section_indent = len(match.group(1))
            break
    if start is None:
        return {}

    result: dict[str, int] = {}
    child_indent: int | None = None
    for lineno in range(start + 1, len(lines) + 1):
        line = lines[lineno - 1]
        if not line.strip():
            continue
        match = key_pattern.match(line)
        if match is None:
            continue
        indent = len(match.group(1))
        if indent <= section_indent:
            break  # ออกจาก section แล้ว
        if child_indent is None:
            child_indent = indent
        if indent == child_indent:
            result.setdefault(match.group(2), lineno)
    return result


# --------------------------------------------------------------------------
# โมเดล operation
# --------------------------------------------------------------------------


@dataclass
class Operation:
    path: str
    method: str  # ตัวใหญ่ เช่น GET
    tags: list[str]
    summary: str
    line: int
    accepts: list[str] = field(default_factory=list)
    responds_with: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.method} {self.path}"

    @property
    def node_id(self) -> str:
        return make_id("openapi", "op", self.method, self.path)


def _collect_operations(spec: dict[str, Any], path_lines: dict[str, int]) -> list[Operation]:
    operations: list[Operation] = []
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in _HTTP_METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            operations.append(
                Operation(
                    path=path,
                    method=method.upper(),
                    tags=[t for t in op.get("tags", []) if isinstance(t, str)],
                    summary=(op.get("summary") or "").strip(),
                    line=path_lines.get(path, 1),
                    accepts=sorted(set(_iter_refs(op.get("requestBody", {})))),
                    responds_with=sorted(set(_iter_refs(op.get("responses", {})))),
                )
            )
    return operations


# --------------------------------------------------------------------------
# ตัว resolve call site: โค้ด -> operation
# --------------------------------------------------------------------------


@dataclass
class CallSite:
    source_file: str  # relative posix
    line: int
    enclosing: str  # ชื่อฟังก์ชันที่ห่ออยู่ (qualname คั่นด้วยจุด)
    method: str | None
    url_template: str | None
    raw_expr: str  # ไว้แสดงตอนเตือน
    # โซ่ฟังก์ชันที่ครอบอยู่ นอกสุด -> ในสุด เช่น
    # ["fetch_series_detail", "fetch_series_detail._fetch"]
    func_chain: list[str] = field(default_factory=list)
    # True เมื่อ url/method มาจาก parameter ของฟังก์ชันที่ครอบอยู่ แปลว่านี่คือ
    # ตัวห่อ (เช่น _request_json เอง) ไม่ใช่จุดยิง endpoint จริง จึงไม่นับเป็น
    # unresolved - มันไม่มี endpoint ให้จับคู่ตั้งแต่แรก
    is_wrapper: bool = False


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """เก็บ ``NAME = "literal"`` ระดับ module ไว้ทำ constant folding"""
    consts: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                consts[target.id] = node.value.value
    return consts


def _fold_str(node: ast.AST, consts: dict[str, str]) -> str | None:
    """คลี่ expression เป็น string template

    รองรับ literal, ชื่อ constant ระดับ module, f-string และการบวก string
    ค่าที่ resolve ไม่ได้ (เช่นตัวแปร runtime) จะกลายเป็น ``{ชื่อตัวแปร}``
    ซึ่งตรงกับรูปแบบ path parameter ของ OpenAPI พอดี
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None

    if isinstance(node, ast.Name):
        return consts.get(node.id)

    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                inner = value.value
                if isinstance(inner, ast.Name) and inner.id in consts:
                    parts.append(consts[inner.id])
                elif isinstance(inner, ast.Name):
                    parts.append("{" + inner.id + "}")  # path parameter
                else:
                    folded = _fold_str(inner, consts)
                    parts.append(folded if folded is not None else _UNRESOLVED)
            else:
                return None
        return "".join(parts)

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _fold_str(node.left, consts)
        right = _fold_str(node.right, consts)
        if left is None or right is None:
            return None
        return left + right

    return None


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _function_params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    a = func.args
    names = {arg.arg for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs)}
    if a.vararg:
        names.add(a.vararg.arg)
    if a.kwarg:
        names.add(a.kwarg.arg)
    return names


@dataclass
class Scope:
    """บริบทของ node หนึ่งตัว: อยู่ในฟังก์ชันไหน เห็น parameter อะไร"""

    qualname: str  # ฟังก์ชันชั้นในสุดที่ครอบอยู่ (มีชื่อ class คั่นถ้าเป็น method)
    params: set[str]
    # โซ่ qualname ของฟังก์ชันที่ครอบอยู่ เรียงนอกสุด -> ในสุด (ไม่นับ class)
    # ใช้ตอนหาว่าควรผูก edge หรืออ่าน key จากฟังก์ชันชั้นไหน
    func_chain: list[str]


def _scopes(tree: ast.Module) -> dict[ast.AST, Scope]:
    """map node -> Scope ของฟังก์ชันที่ครอบมันอยู่

    ฟังก์ชันซ้อนในฟังก์ชันจะได้ qualname ของตัวในสุด ส่วน class ใส่ชื่อคั่นให้ด้วย
    เพื่อให้ตรงกับที่ AST extractor ของ graphify ใช้ตั้ง node id
    """
    mapping: dict[ast.AST, Scope] = {}

    def walk(node: ast.AST, stack: list[str], scope: Scope) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = ".".join(stack + [child.name])
                inner = Scope(
                    qualname=qualname,
                    params=scope.params | _function_params(child),
                    func_chain=scope.func_chain + [qualname],
                )
                mapping[child] = inner
                walk(child, stack + [child.name], inner)
            elif isinstance(child, ast.ClassDef):
                walk(child, stack + [child.name], scope)
            else:
                if scope.qualname:
                    mapping[child] = scope
                walk(child, stack, scope)

    walk(tree, [], Scope(qualname="", params=set(), func_chain=[]))
    return mapping


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*.py")
        if not any(part in _SKIP_DIRS for part in p.parts)
    )


def find_call_sites(py_files: Iterable[Path], root: Path) -> list[CallSite]:
    sites: list[CallSite] = []
    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError) as exc:
            print(f"warning: อ่าน/parse {py_file} ไม่ได้: {exc}", file=sys.stderr)
            continue

        consts = _module_constants(tree)
        scopes = _scopes(tree)
        rel = py_file.relative_to(root).as_posix()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if name not in _REQUEST_HELPERS:
                continue
            method_idx, url_idx = _REQUEST_HELPERS[name]
            if len(node.args) <= max(method_idx, url_idx):
                continue

            method_node = node.args[method_idx]
            url_node = node.args[url_idx]
            scope = scopes.get(node) or Scope(qualname="", params=set(), func_chain=[])

            def _from_param(arg: ast.AST, params: set[str] = scope.params) -> bool:
                return isinstance(arg, ast.Name) and arg.id in params and arg.id not in consts

            sites.append(
                CallSite(
                    source_file=rel,
                    line=node.lineno,
                    enclosing=scope.qualname,
                    func_chain=list(scope.func_chain),
                    method=(_fold_str(method_node, consts) or "").upper() or None,
                    url_template=_fold_str(url_node, consts),
                    raw_expr=ast.unparse(url_node),
                    is_wrapper=_from_param(url_node) or _from_param(method_node),
                )
            )
    return sites


def _strip_server_base(url: str, bases: list[str]) -> str:
    for base in bases:
        if url.startswith(base):
            remainder = url[len(base):]
            return remainder if remainder.startswith("/") else "/" + remainder
    # ไม่ตรง base ไหนเลย - ตัด scheme+host ทิ้งถ้ามี
    match = re.match(r"https?://[^/]+(/.*)$", url)
    return match.group(1) if match else url


def _normalize_template(path: str) -> str:
    """ทำให้ชื่อ path parameter ไม่มีผลต่อการ match

    สเปกเขียน ``/series/{id}`` แต่โค้ดสร้าง ``/series/{series_id}``
    ถ้าเทียบ string ตรงๆ จะพลาดทุกครั้ง
    """
    return re.sub(r"\{[^}]*\}", "{}", path.rstrip("/")) or "/"


def match_operation(
    method: str, path_template: str, operations: Iterable[Operation]
) -> Operation | None:
    target = _normalize_template(path_template)
    for op in operations:
        if op.method == method and _normalize_template(op.path) == target:
            return op
    return None


# --------------------------------------------------------------------------
# ตรวจ schema drift (heuristic)
# --------------------------------------------------------------------------


def _schema_properties(spec: dict[str, Any], schema_name: str) -> set[str]:
    schema = spec.get("components", {}).get("schemas", {}).get(schema_name, {})
    props = schema.get("properties")
    return set(props) if isinstance(props, dict) else set()


def _schema_properties_deep(spec: dict[str, Any], schema_name: str) -> set[str]:
    """ชื่อ property ทุกชั้นที่เข้าถึงได้จาก schema นี้ ตาม $ref ต่อไปด้วย

    ใช้เช็คว่า key ที่โค้ดอ่านมีในสเปกไหม เพราะโค้ดอ่านแบบ ``series["anime"]["start"]``
    แล้วเห็นแค่ชื่อ ``start`` ซึ่งไม่มีทางอยู่ชั้นบนสุด
    """
    schemas = spec.get("components", {}).get("schemas", {})
    names: set[str] = set()
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return

        ref = node.get("$ref")
        if isinstance(ref, str):
            target = _ref_name(ref)
            # กัน schema ที่อ้างวนกลับมาหาตัวเอง
            if target and target not in seen:
                seen.add(target)
                walk(schemas.get(target, {}))
            return

        props = node.get("properties")
        if isinstance(props, dict):
            for key, sub in props.items():
                names.add(key)
                walk(sub)

        for key in ("items", "allOf", "anyOf", "oneOf", "additionalProperties"):
            if key in node:
                walk(node[key])

    seen.add(schema_name)
    walk(schemas.get(schema_name, {}))
    return names


def _read_keys_in_function(py_file: Path, func_qualname: str) -> set[str]:
    """เก็บ key ที่โค้ดอ่านจริงในฟังก์ชัน: ``x.get("k")`` และ ``x["k"]``"""
    if not func_qualname:
        return set()
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()

    scopes = _scopes(tree)
    keys: set[str] = set()
    for node in ast.walk(tree):
        scope = scopes.get(node)
        if scope is None or not scope.qualname.startswith(func_qualname):
            continue
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            keys.add(node.args[0].value)
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            keys.add(node.slice.value)
    return keys


def drift_report(
    spec: dict[str, Any], resolved: list[tuple[CallSite, Operation]], root: Path
) -> list[str]:
    lines = [
        "# Schema drift check (heuristic)",
        "",
        "เทียบ key ที่โค้ดอ่าน กับ property ของ response schema",
        "ฝั่ง 'สเปกไม่มี' เทียบกับ property ทุกชั้น (ตาม $ref) จึงไม่ฟ้อง key ที่ซ้อนลึก",
        "ฝั่ง 'โค้ดไม่ได้ใช้' เทียบเฉพาะชั้นบนสุด ไม่งั้นจะยาวจนอ่านไม่ไหว",
        "เทียบด้วยชื่อ key ล้วน ไม่ได้ดูว่าอยู่ถูกที่ - key ชื่อซ้ำข้ามชั้นจึงหลุดได้",
        "",
    ]
    for site, op in resolved:
        # response ไหลออกไปถูกอ่านในฟังก์ชันชั้นนอก ไม่ใช่ closure ที่ยิง request
        # (เช่น _fetch ยิง แต่ fetch_series_detail เป็นคนอ่าน key) จึงอ่านจากชั้นนอกสุด
        scope = site.func_chain[0] if site.func_chain else site.enclosing
        lines.append(f"## {op.label}")
        lines.append(f"- call site: `{site.source_file}:{site.line}` ใน `{site.enclosing}()`")
        if scope != site.enclosing:
            lines.append(f"- อ่าน key จากขอบเขต `{scope}()`")
        if not op.responds_with:
            lines.append("- สเปกไม่ได้ระบุ response schema ข้ามการตรวจ")
            lines.append("")
            continue
        props: set[str] = set()
        deep_props: set[str] = set()
        for name in op.responds_with:
            props |= _schema_properties(spec, name)
            deep_props |= _schema_properties_deep(spec, name)
        read = _read_keys_in_function(root / site.source_file, scope)
        unknown = sorted(read - deep_props)
        unused = sorted(props - read)
        lines.append(f"- schema: {', '.join(op.responds_with)}")
        lines.append(
            f"- โค้ดอ่าน {len(read)} key · สเปกมี {len(props)} property ชั้นบนสุด "
            f"({len(deep_props)} รวมทุกชั้น)"
        )
        if unknown:
            lines.append(f"- **โค้ดอ่านแต่สเปกไม่มี: {', '.join(unknown)}**")
        else:
            lines.append("- key ที่โค้ดอ่าน อยู่ในสเปกครบ")
        if unused:
            preview = ", ".join(unused[:12])
            more = f" (+{len(unused) - 12})" if len(unused) > 12 else ""
            lines.append(f"- สเปกมีแต่โค้ดไม่ได้ใช้: {preview}{more}")
        lines.append("")
    return lines


# --------------------------------------------------------------------------
# ตัวหลัก
# --------------------------------------------------------------------------


def _graph_node_ids(graph_path: str | Path) -> set[str] | None:
    """คืน id ทุก node ใน graph.json หรือ None ถ้าอ่านไม่ได้ (แปลว่าไม่ต้องตรวจ)"""
    path = Path(graph_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {n.get("id") for n in data.get("nodes", []) if isinstance(n, dict)}


def _resolve_caller_id(module: str, qualname: str, known_ids: set[str] | None) -> str | None:
    """หา node id ของฟังก์ชันต้นทาง โดยไต่ขึ้นหาตัวที่มีอยู่จริงในกราฟ

    graphify ไม่ได้สร้าง node ให้ฟังก์ชันซ้อนใน (เช่น ``_fetch`` ใน
    ``fetch_series_detail``) ถ้ายืนยันชื่อเต็มอย่างเดียว edge จะไปเกาะ id ที่ไม่มีอยู่
    จึงตัดชื่อชั้นในสุดออกทีละชั้นจนกว่าจะเจอ node จริง
    """
    parts = [p for p in qualname.split(".") if p] if qualname else []
    while parts:
        candidate = make_id(module, *parts)
        if known_ids is None or candidate in known_ids:
            return candidate
        parts.pop()
    candidate = make_id(module)
    if known_ids is None or candidate in known_ids:
        return candidate
    return None


def introspect_openapi(
    spec_path: str | Path,
    root: str | Path = ".",
    scope: str = "used",
    tags: Iterable[str] = (),
    graph_path: str | Path | None = None,
) -> dict[str, Any]:
    """คืน node/edge จาก OpenAPI spec พร้อม edge เชื่อมไปยัง call site ในโค้ด

    คีย์ที่ขึ้นต้นด้วย ``_`` เป็นข้อมูลรายงาน ไม่ใช่ส่วนของกราฟ - caller ต้องดึงออก
    ก่อนส่งต่อให้ graphify merge
    """
    if scope not in ("used", "tag", "full"):
        raise ValueError(f"scope ไม่รู้จัก: {scope} (ใช้ used|tag|full)")

    root_path = Path(root).resolve()
    spec_file = Path(spec_path).resolve()
    spec = _load_spec(spec_file)
    raw = spec_file.read_text(encoding="utf-8")
    spec_rel = spec_file.relative_to(root_path).as_posix()

    path_lines = _section_key_lines(raw, "paths")
    schema_lines = _section_key_lines(raw, "schemas")
    operations = _collect_operations(spec, path_lines)
    bases = _server_bases(spec)

    # --- resolve call site ---
    sites = find_call_sites(_iter_py_files(root_path), root_path)

    resolved: list[tuple[CallSite, Operation]] = []
    unresolved: list[CallSite] = []
    wrappers: list[CallSite] = []
    for site in sites:
        if site.is_wrapper:
            wrappers.append(site)
            continue
        if not site.method or not site.url_template:
            unresolved.append(site)
            continue
        template = _strip_server_base(site.url_template, bases)
        op = match_operation(site.method, template, operations)
        if op is None:
            unresolved.append(site)
        else:
            resolved.append((site, op))

    # --- เลือก scope ---
    used_ops = {op.node_id for _site, op in resolved}
    wanted_tags = {t.lower() for t in tags}
    if scope == "used":
        selected = [op for op in operations if op.node_id in used_ops]
    elif scope == "tag":
        selected = [
            op for op in operations
            if op.node_id in used_ops or any(t.lower() in wanted_tags for t in op.tags)
        ]
    else:  # full
        selected = list(operations)

    seeds = {name for op in selected for name in (*op.accepts, *op.responds_with)}
    schemas = _reachable_schemas(spec, seeds)
    all_schemas = spec.get("components", {}).get("schemas", {})

    # --- สร้าง node ---
    nodes: list[dict[str, Any]] = []
    for op in sorted(selected, key=lambda o: (o.path, o.method)):
        nodes.append(
            {
                "id": op.node_id,
                "label": op.label,
                "source_file": spec_rel,
                "source_location": f"L{op.line}",
            }
        )
    for name in sorted(schemas):
        nodes.append(
            {
                "id": make_id("openapi", "schema", name),
                "label": name,
                "source_file": spec_rel,
                "source_location": f"L{schema_lines.get(name, 1)}",
            }
        )

    # --- สร้าง edge ---
    edges: list[dict[str, Any]] = []

    def add_spec_edge(source: str, target: str, relation: str, context: str, line: int) -> None:
        edges.append(
            {
                "source": source,
                "target": target,
                "relation": relation,
                "context": context,
                "weight": 1.0,
                "confidence": _CONFIDENCE_EXTRACTED,
                "source_file": spec_rel,
                "source_location": f"L{line}",
            }
        )

    for op in sorted(selected, key=lambda o: (o.path, o.method)):
        for name in op.accepts:
            if name in schemas:
                add_spec_edge(op.node_id, make_id("openapi", "schema", name),
                              "accepts", "openapi_request_body", op.line)
        for name in op.responds_with:
            if name in schemas:
                add_spec_edge(op.node_id, make_id("openapi", "schema", name),
                              "responds_with", "openapi_response", op.line)

    for name in sorted(schemas):
        for ref in sorted(set(_iter_refs(all_schemas.get(name, {})))):
            if ref in schemas and ref != name:
                add_spec_edge(make_id("openapi", "schema", name), make_id("openapi", "schema", ref),
                              "references", "openapi_schema_ref", schema_lines.get(name, 1))

    # --- edge เชื่อมโค้ดกับ operation ---
    known_ids = _graph_node_ids(graph_path) if graph_path else None
    missing_sources: list[str] = []
    # หลาย call site อาจยิง endpoint เดียวกันจากฟังก์ชันเดียวกัน (เช่น retry path)
    # รวมเป็น edge เดียวแล้วเก็บทุกบรรทัดไว้ ไม่งั้น build จะยุบให้เองแล้วนับเป็น
    # collapsed edge ใน diagnostic โดยที่เราเสียข้อมูลบรรทัดไปเปล่าๆ
    call_edges: dict[tuple[str, str], dict[str, Any]] = {}
    for site, op in resolved:
        module = site.source_file[:-3] if site.source_file.endswith(".py") else site.source_file
        caller_id = _resolve_caller_id(module, site.enclosing, known_ids)
        if caller_id is None:
            missing_sources.append(
                f"{make_id(module, *site.enclosing.split('.'))} "
                f"({site.source_file}:{site.line})"
            )
            continue
        key = (caller_id, op.node_id)
        existing = call_edges.get(key)
        if existing is not None:
            existing["source_location"] += f",L{site.line}"
            continue
        call_edges[key] = {
            "source": caller_id,
            "target": op.node_id,
            "relation": "calls_endpoint",
            "context": "http_call_site",
            "weight": 1.0,
            "confidence": _CONFIDENCE_EXTRACTED,
            "source_file": site.source_file,
            "source_location": f"L{site.line}",
        }
    edges.extend(call_edges.values())

    return {
        "nodes": nodes,
        "edges": edges,
        "_resolved": resolved,
        "_unresolved": unresolved,
        "_wrappers": wrappers,
        "_missing_sources": missing_sources,
        "_spec": spec,
        "_operation_count": len(operations),
        "_schema_count": len(all_schemas),
    }


def split_report(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """แยกส่วนกราฟ (nodes/edges) ออกจากส่วนรายงาน (คีย์ที่ขึ้นต้นด้วย _)"""
    graph = {k: v for k, v in result.items() if not k.startswith("_")}
    report = {k: v for k, v in result.items() if k.startswith("_")}
    return graph, report


def print_resolution(report: dict[str, Any], scope: str, graph: dict[str, Any]) -> None:
    print(f"[openapi] spec: {report['_operation_count']} operations, "
          f"{report['_schema_count']} schemas")
    print(f"[openapi] scope={scope} -> {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    print(f"[openapi] call sites: {len(report['_resolved'])} resolved, "
          f"{len(report['_unresolved'])} unresolved, "
          f"{len(report['_wrappers'])} wrapper (ไม่มี endpoint ตายตัว)")
    for site, op in report["_resolved"]:
        print(f"  OK  {site.source_file}:{site.line} {site.enclosing}() -> {op.label}")
    for site in report["_wrappers"]:
        print(f"  --  {site.source_file}:{site.line} {site.enclosing}() "
              f"url={site.raw_expr} - ตัวห่อ ส่ง url/method ผ่านเป็น parameter")

    # ห้ามเดา ห้ามข้ามเงียบ - unresolved ต้องโผล่ออกมาเสมอ
    for site in report["_unresolved"]:
        detail = site.url_template or site.raw_expr
        print(f"  ??  {site.source_file}:{site.line} {site.enclosing}() "
              f"method={site.method or '?'} url={detail} - จับคู่ operation ไม่ได้",
              file=sys.stderr)
    for entry in report["_missing_sources"]:
        print(f"  ??  node ต้นทางไม่มีในกราฟ: {entry} - ข้าม edge นี้", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="แปลง OpenAPI spec เป็น node/edge สำหรับ graphify",
    )
    parser.add_argument("--spec", default="docs/mangaupdates-openapi.json")
    parser.add_argument("--root", default=".")
    parser.add_argument("--scope", choices=("used", "tag", "full"), default="used")
    parser.add_argument("--tag", action="append", default=[], help="ใช้กับ --scope tag (ใส่ซ้ำได้)")
    parser.add_argument("--graph", default="graphify-out/graph.json",
                        help="ใช้ตรวจว่า node ต้นทางของ calls_endpoint มีจริง")
    parser.add_argument("--out", default="graphify-out/.graphify_openapi.json")
    parser.add_argument("--drift", action="store_true", help="เขียนรายงาน schema drift")
    parser.add_argument("--drift-out", default="graphify-out/API_DRIFT.md")
    args = parser.parse_args(argv)

    try:
        result = introspect_openapi(
            args.spec, args.root, scope=args.scope, tags=args.tag, graph_path=args.graph
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    graph, report = split_report(result)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    print_resolution(report, args.scope, graph)

    if args.drift:
        lines = drift_report(report["_spec"], report["_resolved"], Path(args.root).resolve())
        drift_path = Path(args.drift_out)
        drift_path.parent.mkdir(parents=True, exist_ok=True)
        drift_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"[openapi] drift report -> {drift_path}")

    print(f"[openapi] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
