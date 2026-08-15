#!/usr/bin/env python3
"""เทสต์ตัวแปลง OpenAPI -> graphify

ใช้ unittest ของ stdlib เพราะโปรเจกต์ยังไม่มี test framework และไม่อยากเพิ่ม dependency
ทุกเทสต์ใช้ spec/โค้ดสังเคราะห์ในโฟลเดอร์ชั่วคราว ไม่แตะไฟล์จริงของโปรเจกต์

    python -m unittest discover -s tools -p "test_*.py" -v
"""

from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openapi_graphify import (  # noqa: E402
    Operation,
    _fold_str,
    _module_constants,
    _normalize_template,
    _reachable_schemas,
    _resolve_caller_id,
    _schema_properties,
    _schema_properties_deep,
    _strip_server_base,
    drift_report,
    find_call_sites,
    introspect_openapi,
    match_operation,
)


def _mini_spec() -> dict:
    """สเปกสังเคราะห์ ตั้งใจให้ path parameter ชื่อ `id` ไม่ตรงกับตัวแปรในโค้ด"""
    return {
        "openapi": "3.0.0",
        "info": {"title": "Example API", "version": "1.0.0"},
        "servers": [{"url": "https://api.example.com/v1"}],
        "paths": {
            "/series/search": {
                "post": {
                    "tags": ["series"],
                    "summary": "search",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SearchRequest"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/SearchResponse"}
                                }
                            }
                        }
                    },
                }
            },
            "/series/{id}": {
                "get": {
                    "tags": ["series"],
                    "summary": "detail",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/SeriesModel"}
                                }
                            }
                        }
                    },
                }
            },
            "/unused/{other_id}": {"delete": {"tags": ["misc"], "responses": {}}},
        },
        "components": {
            "schemas": {
                "SearchRequest": {"properties": {"search": {"type": "string"}}},
                "SearchResponse": {
                    "properties": {"results": {"$ref": "#/components/schemas/SeriesModel"}}
                },
                "SeriesModel": {
                    "properties": {
                        "title": {"type": "string"},
                        "image": {"$ref": "#/components/schemas/ImageModel"},
                    }
                },
                "ImageModel": {"properties": {"url": {"type": "string"}}},
                "Orphan": {"properties": {"nope": {"type": "string"}}},
            }
        },
    }


_CLIENT_SOURCE = '''\
import aiohttp

SEARCH_URL = "https://api.example.com/v1/series/search"
SERIES_URL = "https://api.example.com/v1/series"


async def _request_json(session, method, url, *, json_payload=None):
    """ตัวห่อ - url/method เป็น parameter จึงไม่ใช่จุดยิง endpoint จริง"""
    async with session.request(method, url, json=json_payload) as resp:
        return await resp.json()


async def fetch_series_detail(session, series_id):
    async def _fetch():
        return await _request_json(session, "get", f"{SERIES_URL}/{series_id}")

    series = await _fetch()
    image = series.get("image") or {}
    return {"title": series.get("title"), "image": image.get("url")}


async def search_series(session, name):
    data = await _request_json(session, "post", SEARCH_URL, json_payload={"search": name})
    if not data.get("results"):
        data = await _request_json(session, "post", SEARCH_URL, json_payload={"search": name})
    return data
'''


class TestPathTemplateMatching(unittest.TestCase):
    """ความเสี่ยงอันดับหนึ่ง: ชื่อ path parameter ในโค้ดไม่ตรงกับในสเปก"""

    def test_param_name_does_not_affect_match(self):
        self.assertEqual(_normalize_template("/series/{id}"), "/series/{}")
        self.assertEqual(_normalize_template("/series/{series_id}"), "/series/{}")

    def test_trailing_slash_ignored(self):
        self.assertEqual(_normalize_template("/series/"), "/series")

    def test_match_operation_across_param_names(self):
        ops = [
            Operation(path="/series/{id}", method="GET", tags=[], summary="", line=1),
            Operation(path="/series/search", method="POST", tags=[], summary="", line=2),
        ]
        found = match_operation("GET", "/series/{series_id}", ops)
        self.assertIsNotNone(found)
        self.assertEqual(found.path, "/series/{id}")

    def test_method_must_also_match(self):
        ops = [Operation(path="/series/{id}", method="GET", tags=[], summary="", line=1)]
        self.assertIsNone(match_operation("DELETE", "/series/{series_id}", ops))

    def test_different_segment_count_does_not_match(self):
        ops = [Operation(path="/series/{id}", method="GET", tags=[], summary="", line=1)]
        self.assertIsNone(match_operation("GET", "/series/{id}/comments", ops))

    def test_literal_segment_must_match(self):
        ops = [Operation(path="/series/{id}", method="GET", tags=[], summary="", line=1)]
        self.assertIsNone(match_operation("GET", "/authors/{id}", ops))


class TestStringFolding(unittest.TestCase):
    def _fold(self, expr: str) -> str | None:
        consts = _module_constants(ast.parse(_CLIENT_SOURCE))
        return _fold_str(ast.parse(expr, mode="eval").body, consts)

    def test_module_constant(self):
        self.assertEqual(self._fold("SEARCH_URL"), "https://api.example.com/v1/series/search")

    def test_fstring_with_constant_and_variable(self):
        self.assertEqual(
            self._fold('f"{SERIES_URL}/{series_id}"'),
            "https://api.example.com/v1/series/{series_id}",
        )

    def test_string_concat(self):
        self.assertEqual(
            self._fold('SERIES_URL + "/latest"'), "https://api.example.com/v1/series/latest"
        )

    def test_unknown_name_is_unresolvable(self):
        self.assertIsNone(self._fold("mystery_url"))


class TestServerBase(unittest.TestCase):
    def test_strips_full_url(self):
        bases = ["https://api.example.com/v1", "/v1"]
        self.assertEqual(
            _strip_server_base("https://api.example.com/v1/series/{id}", bases), "/series/{id}"
        )

    def test_strips_bare_path_prefix(self):
        self.assertEqual(
            _strip_server_base("/v1/series", ["https://api.example.com/v1", "/v1"]), "/series"
        )

    def test_unknown_host_falls_back_to_path(self):
        self.assertEqual(_strip_server_base("https://other.test/foo/bar", ["/v1"]), "/foo/bar")


class TestSchemaReachability(unittest.TestCase):
    def test_transitive_closure_excludes_orphan(self):
        reachable = _reachable_schemas(_mini_spec(), ["SearchResponse"])
        self.assertEqual(reachable, {"SearchResponse", "SeriesModel", "ImageModel"})

    def test_unknown_seed_is_ignored(self):
        self.assertEqual(_reachable_schemas(_mini_spec(), ["DoesNotExist"]), set())


class TestCallerIdResolution(unittest.TestCase):
    def test_walks_up_to_existing_node(self):
        # graphify ไม่สร้าง node ให้ฟังก์ชันซ้อนใน จึงต้องถอยไปหาฟังก์ชันแม่
        known = {"api_client_fetch_series_detail"}
        self.assertEqual(
            _resolve_caller_id("api/_client", "fetch_series_detail._fetch", known),
            "api_client_fetch_series_detail",
        )

    def test_exact_match_preferred(self):
        known = {"api_client_search_series"}
        self.assertEqual(
            _resolve_caller_id("api/_client", "search_series", known), "api_client_search_series"
        )

    def test_returns_none_when_nothing_matches(self):
        self.assertIsNone(_resolve_caller_id("api/_client", "ghost", {"something_else"}))

    def test_no_known_ids_means_no_verification(self):
        self.assertEqual(
            _resolve_caller_id("api/_client", "search_series", None), "api_client_search_series"
        )


class TestWrapperDetection(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "client.py").write_text(_CLIENT_SOURCE, encoding="utf-8")
        self.sites = find_call_sites([self.root / "client.py"], self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_passthrough_wrapper_is_flagged(self):
        wrappers = [s for s in self.sites if s.is_wrapper]
        self.assertEqual(len(wrappers), 1)
        self.assertEqual(wrappers[0].enclosing, "_request_json")

    def test_concrete_call_sites_are_not_flagged(self):
        concrete = [s for s in self.sites if not s.is_wrapper]
        self.assertEqual(len(concrete), 3)

    def test_nested_function_chain_is_recorded(self):
        nested = next(s for s in self.sites if s.enclosing.endswith("._fetch"))
        self.assertEqual(
            nested.func_chain, ["fetch_series_detail", "fetch_series_detail._fetch"]
        )


class TestIntrospectEndToEnd(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "client.py").write_text(_CLIENT_SOURCE, encoding="utf-8")
        self.spec = self.root / "spec.json"
        self.spec.write_text(json.dumps(_mini_spec(), indent=2), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, **kwargs):
        return introspect_openapi(self.spec, self.root, **kwargs)

    def test_used_scope_only_keeps_called_operations(self):
        labels = {n["label"] for n in self._run(scope="used")["nodes"]}
        self.assertIn("GET /series/{id}", labels)
        self.assertIn("POST /series/search", labels)
        self.assertNotIn("DELETE /unused/{other_id}", labels)

    def test_full_scope_keeps_everything(self):
        labels = {n["label"] for n in self._run(scope="full")["nodes"]}
        self.assertIn("DELETE /unused/{other_id}", labels)

    def test_tag_scope_selects_by_tag(self):
        labels = {n["label"] for n in self._run(scope="tag", tags=["misc"])["nodes"]}
        self.assertIn("DELETE /unused/{other_id}", labels)
        # endpoint ที่โค้ดเรียกจริงต้องติดมาด้วยเสมอ แม้ tag จะไม่ตรง
        self.assertIn("GET /series/{id}", labels)

    def test_orphan_schema_excluded_from_used_scope(self):
        labels = {n["label"] for n in self._run(scope="used")["nodes"]}
        self.assertNotIn("Orphan", labels)

    def test_repeated_call_sites_collapse_into_one_edge(self):
        # search_series ยิง POST /series/search สองครั้ง (retry) ต้องได้ edge เดียว
        # แต่เก็บบรรทัดไว้ครบ
        calls = [
            e for e in self._run(scope="used")["edges"] if e["relation"] == "calls_endpoint"
        ]
        search = [e for e in calls if e["target"].endswith("post_series_search")]
        self.assertEqual(len(search), 1)
        self.assertIn(",", search[0]["source_location"])

    def test_wrapper_produces_no_unresolved(self):
        result = self._run(scope="used")
        self.assertEqual(len(result["_unresolved"]), 0)
        self.assertEqual(len(result["_wrappers"]), 1)

    def test_nested_call_site_uses_full_qualname_without_graph(self):
        # ไม่ส่ง graph.json => ไม่มีอะไรให้ยืนยัน จึงใช้ชื่อเต็ม ไม่ไต่ขึ้น
        result = introspect_openapi(self.spec, self.root, scope="used", graph_path=None)
        sources = {e["source"] for e in result["edges"] if e["relation"] == "calls_endpoint"}
        self.assertIn("client_fetch_series_detail_fetch", sources)

    def test_schema_edges_present(self):
        relations = {e["relation"] for e in self._run(scope="used")["edges"]}
        self.assertEqual(
            relations, {"calls_endpoint", "accepts", "responds_with", "references"}
        )

    def test_all_edges_marked_extracted(self):
        for edge in self._run(scope="used")["edges"]:
            self.assertEqual(edge["confidence"], "EXTRACTED")

    def test_every_edge_endpoint_has_a_node_or_is_a_call_site(self):
        result = self._run(scope="used")
        node_ids = {n["id"] for n in result["nodes"]}
        for edge in result["edges"]:
            self.assertIn(edge["target"], node_ids)
            if edge["relation"] != "calls_endpoint":
                self.assertIn(edge["source"], node_ids)

    def test_bad_scope_rejected(self):
        with self.assertRaises(ValueError):
            self._run(scope="everything")

    def test_missing_spec_raises(self):
        with self.assertRaises(FileNotFoundError):
            introspect_openapi(self.root / "nope.json", self.root)


# หัวรายงานก็มีคำว่า 'สเปกไม่มี' อยู่ในคำอธิบาย ต้องเทียบกับบรรทัดที่ฟ้องจริง ๆ
_DRIFT_FINDING = "**โค้ดอ่านแต่สเปกไม่มี:"


class TestSchemaDrift(unittest.TestCase):
    """key ที่ซ้อนอยู่ในสเปกต้องไม่ถูกฟ้องว่า 'สเปกไม่มี'"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "client.py").write_text(_CLIENT_SOURCE, encoding="utf-8")
        self.spec_path = self.root / "spec.json"
        self.spec_path.write_text(json.dumps(_mini_spec(), indent=2), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _report_text(self) -> str:
        report = introspect_openapi(self.spec_path, self.root, scope="used")
        return "\n".join(drift_report(report["_spec"], report["_resolved"], self.root))

    def test_deep_properties_follow_refs(self):
        self.assertEqual(
            _schema_properties_deep(_mini_spec(), "SeriesModel"), {"title", "image", "url"}
        )

    def test_top_level_properties_stay_shallow(self):
        self.assertEqual(_schema_properties(_mini_spec(), "SeriesModel"), {"title", "image"})

    def test_self_referencing_schema_does_not_loop(self):
        spec = {
            "components": {
                "schemas": {
                    "Node": {
                        "properties": {
                            "name": {"type": "string"},
                            "child": {"$ref": "#/components/schemas/Node"},
                        }
                    }
                }
            }
        }
        self.assertEqual(_schema_properties_deep(spec, "Node"), {"name", "child"})

    def test_nested_key_is_not_reported_as_missing(self):
        # client.py อ่าน image.url ซึ่งอยู่ลึกลงไปหนึ่งชั้น ไม่ใช่ drift
        text = self._report_text()
        self.assertIn("GET /series/{id}", text)
        self.assertNotIn(_DRIFT_FINDING, text)

    def test_key_absent_from_spec_is_still_reported(self):
        (self.root / "other.py").write_text(
            _CLIENT_SOURCE.replace(
                'return {"title": series.get("title"), "image": image.get("url")}',
                'return {"ghost": series.get("ghost_field")}',
            ),
            encoding="utf-8",
        )
        text = self._report_text()
        self.assertIn(_DRIFT_FINDING, text)
        self.assertIn("ghost_field", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
