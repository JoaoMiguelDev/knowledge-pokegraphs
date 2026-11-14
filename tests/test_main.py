import unittest
from pathlib import Path

from kg import KnowledgeGraph
from main import (
    describe_pokemon,
    effective_attacking_types,
    find_evolution_path,
    immunity_edges,
    pokemon_sharing_type_and_ability,
    top_pokemon_by_stat,
)


class ConsultationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = KnowledgeGraph.load_from_json(
            Path(__file__).parents[1] / "data" / "kg.json"
        )

    def test_describe_returns_pokemon_and_connections(self) -> None:
        result = describe_pokemon(self.graph, "charizard")
        self.assertEqual(result["node"]["id"], "charizard")
        self.assertEqual(result["node"]["type"], "Pokemon")
        self.assertTrue(
            any(edge["target"] == "fire" for edge in result["outgoing"])
        )

    def test_evolution_path_uses_directed_evolves_to_edges(self) -> None:
        self.assertEqual(
            find_evolution_path(self.graph, "bulbasaur", "venusaur"),
            ["bulbasaur", "ivysaur", "venusaur"],
        )
        self.assertIsNone(
            find_evolution_path(self.graph, "venusaur", "bulbasaur")
        )

    def test_type_effectiveness_combines_dual_type_multipliers(self) -> None:
        results = dict(effective_attacking_types(self.graph, "charizard"))
        self.assertEqual(results["rock"], 4.0)
        self.assertEqual(results["water"], 2.0)

    def test_top_five_stat_ordering(self) -> None:
        results = top_pokemon_by_stat(self.graph, "speed")
        self.assertEqual(len(results), 5)
        self.assertEqual(
            results,
            sorted(results, key=lambda item: (-item[1], item[0])),
        )

    def test_shared_type_and_ability_intersection(self) -> None:
        matches = pokemon_sharing_type_and_ability(self.graph, "bulbasaur")
        self.assertTrue(matches)
        for pokemon, shared_types, shared_abilities in matches:
            self.assertNotEqual(pokemon, "bulbasaur")
            self.assertTrue(shared_types)
            self.assertTrue(shared_abilities)

    def test_immunities_are_filtered_by_predicate(self) -> None:
        results = immunity_edges(self.graph)
        self.assertEqual(len(results), 8)
        self.assertTrue(all(edge["relation"] == "no_damage_to" for edge in results))

    def test_graph_supports_runtime_node_add_and_remove(self) -> None:
        graph = KnowledgeGraph()
        graph.add_node("temporary", "Pokemon", name="temporary")
        self.assertIn("temporary", graph.nodes)
        self.assertTrue(graph.remove_node("temporary"))
        self.assertNotIn("temporary", graph.nodes)


if __name__ == "__main__":
    unittest.main()
