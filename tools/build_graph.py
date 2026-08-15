#!/usr/bin/env python3
"""สร้าง graphify graph โดยรวม AST ของโค้ด เข้ากับ OpenAPI spec

ทำหน้าที่เดียวกับที่ graphify/cli.py:3594-3628 ทำให้ --postgres และ --cargo คือ
เอาผลจากแหล่งที่ไม่ใช่ AST มา merge ต่อท้ายก่อน build

ต้องมีสคริปต์นี้เพราะ pipeline ปกติของ graphify ลบ .graphify_extract.json ทิ้ง
ตอน cleanup จึงไป merge ทีหลังไม่ได้ - ต้อง merge ระหว่าง build เท่านั้น

ใช้แทน `graphify update .` เสมอสำหรับ repo นี้ ไม่งั้น node ของ API จะหายไป
แล้วชนกับ shrink-guard (#479) ในรอบถัดไป

    python tools/build_graph.py
    python tools/build_graph.py --scope full
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphify.analyze import god_nodes, suggest_questions, surprising_connections
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.detect import detect, save_manifest
from graphify.export import to_json
from graphify.extract import collect_files, extract
from graphify.report import generate

from openapi_graphify import drift_report, introspect_openapi, print_resolution, split_report

_OUT = Path("graphify-out")


def _ast_extract(detection: dict[str, Any], root: Path, spec_rel: str) -> dict[str, Any]:
    """AST extraction ของไฟล์โค้ด โดยกันไฟล์ spec ออก

    spec เป็น .json ซึ่งอยู่ใน CODE_EXTENSIONS ถ้าปล่อยเข้าไปจะได้ 0 node
    พร้อม warning #1666 ทุกรอบ - มันถูกอ่านผ่าน introspect_openapi อยู่แล้ว
    """
    code_files: list[Path] = []
    for entry in detection.get("files", {}).get("code", []):
        path = Path(entry)
        for candidate in (collect_files(path) if path.is_dir() else [path]):
            try:
                if candidate.resolve().relative_to(root).as_posix() == spec_rel:
                    continue
            except ValueError:
                pass
            code_files.append(candidate)

    if not code_files:
        return {"nodes": [], "edges": [], "input_tokens": 0, "output_tokens": 0}
    return extract(code_files, cache_root=root)


# ชื่อที่อ่านรู้เรื่องตามโฟลเดอร์ ใช้ตอนต้องตั้งชื่อ community เอง
_DIR_ROLE = {"commands": "Command", "api": "API Client", "utils": "View"}

# ชื่อที่ลงท้ายด้วย " (2)" คือชื่อที่ถูกเติมเลขอัตโนมัติตอนชนกัน
_AUTO_SUFFIX = re.compile(r"\s\(\d+\)$")


def _derive_name(members: list[str], nodes_by_id: dict[str, dict]) -> str | None:
    """ตั้งชื่อ community จากไฟล์ต้นทางที่พบมากที่สุด

    ใช้เมื่อสืบชื่อเดิมไม่ได้ หรือชื่อเดิมไปชนกับ community อื่น การเติมเลขต่อท้าย
    ชื่อที่ชนกัน (เช่น "Paginated Embed View (3)") ทำให้รายงานเข้าใจผิด
    ว่าเป็นกลุ่มเดียวกัน ทั้งที่คนละเรื่อง
    """
    files = Counter(
        nodes_by_id.get(m, {}).get("source_file", "") for m in members
    )
    files.pop("", None)
    if not files:
        return None
    dominant = Path(files.most_common(1)[0][0])
    stem = dominant.stem.strip("_").replace("_", " ").title()
    role = _DIR_ROLE.get(dominant.parent.name)
    return f"{stem} {role}" if role else stem


def _carry_labels(
    graph_path: Path, communities: dict[int, list[str]], spec_rel: str, nodes_by_id: dict[str, dict]
) -> dict[int, str]:
    """ตั้งชื่อ community ใหม่โดยสืบจากชื่อเดิมเท่าที่สืบได้

    Louvain เปลี่ยนเลข community ทุกครั้งที่กราฟเปลี่ยน การ map ด้วยเลขตรงๆ จึงผิด
    วิธีนี้ดูว่า node ใน community ใหม่ เคยอยู่ใต้ชื่อเดิมอันไหนมากที่สุด
    ถ้าหลาย community อ้างชื่อเดิมเดียวกัน ให้ community ที่มี node ของชื่อนั้นมากที่สุด
    เป็นผู้ได้ไป ที่เหลือตั้งชื่อใหม่จากไฟล์ต้นทางแทน
    """
    previous: dict[str, str] = {}
    if graph_path.is_file():
        try:
            old = json.loads(graph_path.read_text(encoding="utf-8"))
            for node in old.get("nodes", []):
                name = node.get("community_name")
                # ชื่อที่ลงท้ายด้วย "(N)" คือชื่อที่สคริปต์เติมเลขให้ตอนชนกัน ไม่ใช่ชื่อที่คนตั้ง
                # ถ้าสืบต่อ ชื่อพวกนี้จะกลายเป็นชื่อถาวรและวนซ้ำไปเรื่อยๆ
                if (
                    isinstance(name, str)
                    and not name.startswith("Community ")
                    and not _AUTO_SUFFIX.search(name)
                ):
                    previous[node.get("id")] = name
        except (OSError, json.JSONDecodeError):
            pass

    # เสนอชื่อพร้อมคะแนน = จำนวน node ที่เคยอยู่ใต้ชื่อนั้น
    claims: dict[int, tuple[str, int]] = {}
    labels: dict[int, str] = {}
    for cid, members in communities.items():
        spec_members = sum(
            1 for m in members if nodes_by_id.get(m, {}).get("source_file") == spec_rel
        )
        if spec_rel and spec_members * 2 > len(members):
            labels[cid] = "MangaUpdates API Surface"
            continue
        votes = Counter(previous[m] for m in members if m in previous)
        if votes:
            name, score = votes.most_common(1)[0]
            claims[cid] = (name, score)

    winners: dict[str, int] = {}
    for cid, (name, score) in sorted(claims.items()):
        best = winners.get(name)
        if best is None or score > claims[best][1]:
            winners[name] = cid

    for cid, members in communities.items():
        if cid in labels:
            continue
        claimed = claims.get(cid)
        if claimed and winners.get(claimed[0]) == cid:
            labels[cid] = claimed[0]
        else:
            labels[cid] = _derive_name(members, nodes_by_id) or f"Community {cid}"

    # เหลือชื่อซ้ำได้อีกถ้าสองกลุ่มมาจากไฟล์เดียวกันจริงๆ - ตอนนั้นเลขจึงมีความหมาย
    seen: Counter[str] = Counter()
    for cid in sorted(labels):
        base = labels[cid]
        seen[base] += 1
        if seen[base] > 1:
            labels[cid] = f"{base} ({seen[base]})"
    return labels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="build graphify graph พร้อม OpenAPI spec")
    parser.add_argument("--root", default=".")
    parser.add_argument("--spec", default="docs/mangaupdates-openapi.json")
    parser.add_argument("--scope", choices=("used", "tag", "full"), default="used")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--no-openapi", action="store_true", help="ข้าม spec (build เฉพาะโค้ด)")
    parser.add_argument("--no-drift", action="store_true", help="ไม่ต้องเขียนรายงาน drift")
    parser.add_argument("--force", action="store_true",
                        help="เขียนทับแม้กราฟใหม่จะเล็กกว่าเดิม (ข้าม shrink-guard #479)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    _OUT.mkdir(parents=True, exist_ok=True)
    spec_path = Path(args.spec)
    spec_rel = (
        spec_path.resolve().relative_to(root).as_posix() if spec_path.is_file() else ""
    )

    detection = detect(root)
    print(f"[build] detect: {detection['total_files']} files, ~{detection['total_words']:,} words")

    ast_result = _ast_extract(detection, root, spec_rel)
    print(f"[build] AST: {len(ast_result['nodes'])} nodes, {len(ast_result['edges'])} edges")

    api_graph: dict[str, Any] = {"nodes": [], "edges": []}
    api_report: dict[str, Any] = {}
    if not args.no_openapi:
        if not spec_path.is_file():
            print(f"error: ไม่พบไฟล์ spec: {spec_path}", file=sys.stderr)
            return 1
        try:
            result = introspect_openapi(
                spec_path, root, scope=args.scope, tags=args.tag,
                graph_path=_OUT / "graph.json",
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        api_graph, api_report = split_report(result)
        print_resolution(api_report, args.scope, api_graph)

    # merge - ลำดับเดียวกับ cli.py:3622-3628 คือ AST ก่อน แหล่งอื่นต่อท้าย
    seen = {n["id"] for n in ast_result["nodes"]}
    merged_nodes = list(ast_result["nodes"])
    for node in api_graph["nodes"]:
        if node["id"] not in seen:
            merged_nodes.append(node)
            seen.add(node["id"])

    extraction = {
        "nodes": merged_nodes,
        "edges": list(ast_result["edges"]) + list(api_graph["edges"]),
        "hyperedges": [],
        "input_tokens": ast_result.get("input_tokens", 0),
        "output_tokens": ast_result.get("output_tokens", 0),
    }
    print(f"[build] merged: {len(merged_nodes)} nodes, {len(extraction['edges'])} edges "
          f"({len(ast_result['nodes'])} AST + {len(api_graph['nodes'])} openapi)")

    G = build_from_json(extraction, root=str(root), directed=False)
    if G.number_of_nodes() == 0:
        print("error: กราฟว่าง - extraction ไม่ได้ node เลย", file=sys.stderr)
        return 1

    communities = cluster(G)
    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    nodes_by_id = {n["id"]: n for n in merged_nodes}
    labels = _carry_labels(_OUT / "graph.json", communities, spec_rel, nodes_by_id)
    questions = suggest_questions(G, communities, labels)

    wrote = to_json(G, communities, str(_OUT / "graph.json"),
                    force=args.force, community_labels=labels)
    if not wrote:
        print("error: ไม่ยอมเขียนทับ graph.json เพราะกราฟใหม่เล็กกว่าเดิม (#479)\n"
              "       ถ้าตั้งใจให้เล็กลงจริง (ลบโค้ดออก) ให้ใส่ --force", file=sys.stderr)
        return 1

    tokens = {"input": extraction["input_tokens"], "output": extraction["output_tokens"]}
    report = generate(G, communities, cohesion, labels, gods, surprises,
                      detection, tokens, str(root), suggested_questions=questions)
    (_OUT / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    (_OUT / ".graphify_labels.json").write_text(
        json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False), encoding="utf-8"
    )
    (_OUT / ".graphify_analysis.json").write_text(
        json.dumps(
            {
                "communities": {str(k): v for k, v in communities.items()},
                "cohesion": {str(k): v for k, v in cohesion.items()},
                "gods": gods,
                "surprises": surprises,
                "questions": questions,
            },
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    if api_report and not args.no_drift:
        lines = drift_report(api_report["_spec"], api_report["_resolved"], root)
        (_OUT / "API_DRIFT.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"[build] drift report -> {_OUT / 'API_DRIFT.md'}")

    # manifest: stamp เฉพาะไฟล์โค้ด (AST เป็น deterministic) ไม่มี semantic ในโปรเจกต์นี้
    corpus = {"code": detection["files"].get("code", [])}
    save_manifest(corpus, str(_OUT / "manifest.json"), root=root,
                  scan_corpus={f for fl in detection["files"].values() for f in fl})

    cost_path = _OUT / "cost.json"
    cost = (
        json.loads(cost_path.read_text(encoding="utf-8"))
        if cost_path.is_file()
        else {"runs": [], "total_input_tokens": 0, "total_output_tokens": 0}
    )
    cost["runs"].append({
        "date": datetime.now(timezone.utc).isoformat(),
        "input_tokens": tokens["input"],
        "output_tokens": tokens["output"],
        "files": detection.get("total_files", 0),
    })
    cost["total_input_tokens"] += tokens["input"]
    cost["total_output_tokens"] += tokens["output"]
    cost_path.write_text(json.dumps(cost, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[build] graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, "
          f"{len(communities)} communities")
    print(f"[build] wrote {_OUT / 'graph.json'} และ {_OUT / 'GRAPH_REPORT.md'}")
    print("[build] สร้าง HTML ต่อด้วย: graphify export html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
