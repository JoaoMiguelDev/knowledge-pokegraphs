import json
import tempfile
import unittest
from pathlib import Path

from kg import KnowledgeGraph


class KnowledgeGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = KnowledgeGraph()
        self.graph.add_node("bulbasaur", "Pokemon", dex_number=1)
        self.graph.add_node("ivysaur", "Pokemon", dex_number=2)
        self.graph.add_node("venusaur", "Pokemon", dex_number=3)
        self.graph.add_node("grass", "Type")
        self.graph.add_node("overgrow", "Ability")
        self.graph.add_edge("bulbasaur", "evolves_to", "ivysaur")
        self.graph.add_edge("ivysaur", "evolves_to", "venusaur")
        self.graph.add_edge("bulbasaur", "has_type", "grass")
        self.graph.add_edge(
            "bulbasaur", "has_ability", "overgrow", is_hidden=False, slot=1
        )

    def test_add_node_and_validate_arguments(self) -> None:
        self.assertIn("bulbasaur", self.graph.nodes)
        self.assertEqual(self.graph.nodes["bulbasaur"]["properties"]["dex_number"], 1)
        with self.assertRaises(ValueError):
            self.graph.add_node("bulbasaur", "Pokemon")
        with self.assertRaises(ValueError):
            self.graph.add_node("", "Pokemon")
        with self.assertRaises(ValueError):
            self.graph.add_node("missing-type", "Item")

    def test_add_edge_checks_endpoints_and_duplicates(self) -> None:
        with self.assertRaises(KeyError):
            self.graph.add_edge("unknown", "evolves_to", "bulbasaur")
        with self.assertRaises(KeyError):
            self.graph.add_edge("bulbasaur", "evolves_to", "unknown")
        with self.assertRaises(ValueError):
            self.graph.add_edge("bulbasaur", "", "ivysaur")
        with self.assertRaises(ValueError):
            self.graph.add_edge("bulbasaur", "evolves_to", "ivysaur")
        self.assertEqual(
            self.graph.adj["bulbasaur"]["has_ability"]["overgrow"],
            {"is_hidden": False, "slot": 1},
        )

    def test_remove_edge_and_missing_edge(self) -> None:
        self.assertFalse(
            self.graph.remove_edge("bulbasaur", "evolves_to", "venusaur")
        )
        self.assertTrue(
            self.graph.remove_edge("bulbasaur", "evolves_to", "ivysaur")
        )
        self.assertEqual(self.graph.get_neighbors("bulbasaur", "evolves_to"), [])
        self.assertFalse(
            self.graph.remove_edge("bulbasaur", "evolves_to", "ivysaur")
        )
        self.assertNotIn("evolves_to", self.graph.adj["bulbasaur"])

    def test_remove_node_cascades_incoming_and_outgoing_edges(self) -> None:
        self.assertTrue(self.graph.remove_node("ivysaur"))
        self.assertNotIn("ivysaur", self.graph.nodes)
        self.assertNotIn("ivysaur", self.graph.adj)
        self.assertEqual(self.graph.get_neighbors("bulbasaur", "evolves_to"), [])
        self.assertEqual(self.graph.get_incoming("venusaur", "evolves_to"), [])
        self.assertTrue(self.graph.remove_node("venusaur"))
        self.assertFalse(self.graph.remove_node("missing"))
        self.assertTrue(self.graph.validate())

    def test_get_node_returns_copy_and_none_for_missing(self) -> None:
        node = self.graph.get_node("bulbasaur")
        self.assertEqual(node["id"], "bulbasaur")
        node["properties"]["dex_number"] = 99
        self.assertEqual(
            self.graph.get_node("bulbasaur")["properties"]["dex_number"], 1
        )
        self.assertIsNone(self.graph.get_node("missing"))

    def test_outgoing_and_incoming_neighbor_queries(self) -> None:
        self.assertEqual(
            self.graph.get_neighbors("bulbasaur"),
            ["ivysaur", "grass", "overgrow"],
        )
        self.assertEqual(
            self.graph.get_neighbors("bulbasaur", "has_type"), ["grass"]
        )
        self.assertEqual(self.graph.get_neighbors("missing"), [])
        self.assertEqual(
            self.graph.get_incoming("ivysaur", "evolves_to"), ["bulbasaur"]
        )
        self.assertEqual(self.graph.get_incoming("missing"), [])
        incoming = self.graph.incoming_edges("overgrow", "has_ability")
        self.assertEqual(incoming[0]["source"], "bulbasaur")
        self.assertEqual(
            incoming[0]["properties"], {"is_hidden": False, "slot": 1}
        )
        incoming[0]["properties"]["slot"] = 8
        self.assertEqual(
            self.graph.adj["bulbasaur"]["has_ability"]["overgrow"]["slot"], 1
        )

    def test_triple_query_with_wildcards(self) -> None:
        self.assertEqual(len(self.graph.query()), 4)
        self.assertEqual(
            self.graph.query(source="bulbasaur", relation="has_type")[0]["target"],
            "grass",
        )
        self.assertEqual(
            self.graph.query(target="venusaur", relation="evolves_to")[0]["source"],
            "ivysaur",
        )
        self.assertEqual(self.graph.query(source="missing"), [])

    def test_bfs_returns_shortest_path_or_none(self) -> None:
        self.assertEqual(
            self.graph.find_path("bulbasaur", "venusaur"),
            ["bulbasaur", "ivysaur", "venusaur"],
        )
        self.assertEqual(self.graph.find_path("grass", "grass"), ["grass"])
        self.assertIsNone(self.graph.find_path("venusaur", "bulbasaur"))
        self.assertIsNone(self.graph.find_path("missing", "bulbasaur"))

    def test_describe_includes_node_incoming_and_outgoing_edges(self) -> None:
        description = self.graph.describe("ivysaur")
        self.assertEqual(description["node"]["id"], "ivysaur")
        self.assertEqual(description["incoming"][0]["source"], "bulbasaur")
        self.assertEqual(description["outgoing"][0]["target"], "venusaur")
        self.assertIsNone(self.graph.describe("missing"))

    def test_validate_rejects_relation_with_wrong_node_types(self) -> None:
        self.assertTrue(self.graph.validate())
        self.graph.add_edge("bulbasaur", "has_type", "ivysaur")
        with self.assertRaisesRegex(ValueError, "violates schema"):
            self.graph.validate()

    def test_json_round_trip_preserves_graph_and_metadata(self) -> None:
        self.graph.meta = {"generated_by": "unit-test"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "graph.json"
            self.graph.save_to_json(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            loaded = KnowledgeGraph.load_from_json(path)

        self.assertEqual(loaded.nodes, self.graph.nodes)
        self.assertEqual(loaded.adj, self.graph.adj)
        self.assertEqual(loaded.meta["generated_by"], "unit-test")
        self.assertEqual(loaded.meta["counts"], {"nodes": 5, "edges": 4})
        self.assertEqual(len(data["edges"]), 4)

    def test_load_rejects_bad_graph_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps({"nodes": [], "edges": "invalid"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "nodes and edges lists"):
                KnowledgeGraph.load_from_json(path)

            path.write_text(
                json.dumps(
                    {
                        "nodes": [{"id": "p", "type": "Pokemon", "properties": {}}],
                        "edges": [
                            {
                                "source": "p",
                                "relation": "has_type",
                                "target": "missing",
                                "properties": {},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unknown target"):
                KnowledgeGraph.load_from_json(path)

    def test_loads_and_validates_generated_project_graph(self) -> None:
        path = Path(__file__).parents[1] / "data" / "kg.json"
        graph = KnowledgeGraph.load_from_json(path)
        self.assertEqual(len(graph.nodes), graph.meta["counts"]["nodes"])
        self.assertEqual(len(graph.query()), graph.meta["counts"]["edges"])
        self.assertTrue(graph.validate())
        self.assertEqual(
            graph.find_path("bulbasaur", "venusaur"),
            ["bulbasaur", "ivysaur", "venusaur"],
        )


if __name__ == "__main__":
    unittest.main()
