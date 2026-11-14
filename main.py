"""Interactive terminal demo for the Pokémon knowledge graph."""

from collections import deque
from pathlib import Path

from kg import KnowledgeGraph


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "kg.json"
STATS = ("hp", "attack", "defense", "sp_attack", "sp_defense", "speed")
STAT_LABELS = {
    "hp": "HP",
    "attack": "Attack",
    "defense": "Defense",
    "sp_attack": "Special Attack",
    "sp_defense": "Special Defense",
    "speed": "Speed",
}


def _find_node(graph: KnowledgeGraph, name: str, node_type: str) -> str:
    node_id = name.strip().casefold()
    for candidate, node in graph.nodes.items():
        if candidate.casefold() == node_id and node["type"] == node_type:
            return candidate
    raise ValueError(f"{node_type} not found: {name}")


def _pokemon_types(graph: KnowledgeGraph, pokemon: str) -> list[str]:
    return graph.get_neighbors(pokemon, "has_type")


def effective_attacking_types(
    graph: KnowledgeGraph, pokemon: str
) -> list[tuple[str, float]]:
    """Return attack types ranked by their combined effectiveness on a Pokémon."""
    pokemon_id = _find_node(graph, pokemon, "Pokemon")
    defending_types = _pokemon_types(graph, pokemon_id)
    type_ids = [
        node_id
        for node_id, node in graph.nodes.items()
        if node["type"] == "Type"
    ]

    effectiveness = []
    for attack_type in type_ids:
        multiplier = 1.0
        for defending_type in defending_types:
            if defending_type in graph.adj[attack_type].get("double_damage_to", {}):
                multiplier *= 2.0
            elif defending_type in graph.adj[attack_type].get("half_damage_to", {}):
                multiplier *= 0.5
            elif defending_type in graph.adj[attack_type].get("no_damage_to", {}):
                multiplier = 0.0
        effectiveness.append((attack_type, multiplier))

    return sorted(effectiveness, key=lambda item: (-item[1], item[0]))


def top_pokemon_by_stat(
    graph: KnowledgeGraph, stat: str, limit: int = 5
) -> list[tuple[str, int | float]]:
    """Return Pokémon ranked by a numeric base stat."""
    if stat not in STATS:
        raise ValueError(f"unknown stat: {stat}")
    pokemon = [
        (node_id, node["properties"].get(stat))
        for node_id, node in graph.nodes.items()
        if node["type"] == "Pokemon"
    ]
    ranked = [
        (node_id, value)
        for node_id, value in pokemon
        if isinstance(value, (int, float))
    ]
    return sorted(ranked, key=lambda item: (-item[1], item[0]))[:limit]


def pokemon_sharing_type_and_ability(
    graph: KnowledgeGraph, pokemon: str
) -> list[tuple[str, list[str], list[str]]]:
    """Find Pokémon sharing at least one type and one ability with the given one."""
    pokemon_id = _find_node(graph, pokemon, "Pokemon")
    selected_types = set(graph.get_neighbors(pokemon_id, "has_type"))
    selected_abilities = set(graph.get_neighbors(pokemon_id, "has_ability"))
    matches = []

    for candidate, node in graph.nodes.items():
        if candidate == pokemon_id or node["type"] != "Pokemon":
            continue
        shared_types = selected_types.intersection(
            graph.get_neighbors(candidate, "has_type")
        )
        shared_abilities = selected_abilities.intersection(
            graph.get_neighbors(candidate, "has_ability")
        )
        if shared_types and shared_abilities:
            matches.append(
                (candidate, sorted(shared_types), sorted(shared_abilities))
            )
    return sorted(matches)


def immunity_edges(graph: KnowledgeGraph) -> list[dict]:
    """Return type-chart immunities (no_damage_to edges)."""
    return graph.query(relation="no_damage_to")


def describe_pokemon(graph: KnowledgeGraph, pokemon: str) -> dict:
    """Describe a Pokémon and its directly connected graph nodes."""
    pokemon_id = _find_node(graph, pokemon, "Pokemon")
    description = graph.describe(pokemon_id)
    if description is None:
        raise ValueError(f"Pokemon not found: {pokemon}")
    return description


def find_evolution_path(
    graph: KnowledgeGraph, source: str, target: str
) -> list[str] | None:
    """Find the shortest directed path using only evolves_to edges."""
    source_id = _find_node(graph, source, "Pokemon")
    target_id = _find_node(graph, target, "Pokemon")
    queue = deque([source_id])
    previous: dict[str, str | None] = {source_id: None}

    while queue:
        current = queue.popleft()
        if current == target_id:
            path = []
            while current is not None:
                path.append(current)
                current = previous[current]
            return list(reversed(path))
        for child in graph.get_neighbors(current, "evolves_to"):
            if child not in previous:
                previous[child] = current
                queue.append(child)
    return None


def _print_description(description: dict) -> None:
    node = description["node"]
    print(f"\n{node['id']} ({node['type']})")
    for key, value in node["properties"].items():
        print(f"  {key}: {value}")
    print("  Connections:")
    for edge in description["outgoing"]:
        print(f"    -{edge['relation']}-> {edge['target']} {edge['properties']}")
    for edge in description["incoming"]:
        print(f"    <-{edge['relation']}- {edge['source']} {edge['properties']}")
    if not description["outgoing"] and not description["incoming"]:
        print("    (none)")


def _ask_pokemon(graph: KnowledgeGraph, prompt: str = "Pokemon name: ") -> str:
    while True:
        try:
            return _find_node(graph, input(prompt), "Pokemon")
        except ValueError as error:
            print(error)


def _show_describe(graph: KnowledgeGraph) -> None:
    _print_description(describe_pokemon(graph, _ask_pokemon(graph)))


def _show_evolution_path(graph: KnowledgeGraph) -> None:
    source = _ask_pokemon(graph, "Starting Pokemon: ")
    target = _ask_pokemon(graph, "Destination Pokemon: ")
    path = find_evolution_path(graph, source, target)
    if path is None:
        print(f"No directed evolution path from {source} to {target}.")
        return
    print(" -> ".join(path))


def _show_effective_types(graph: KnowledgeGraph) -> None:
    pokemon = _ask_pokemon(graph)
    defending_types = _pokemon_types(graph, pokemon)
    print(f"\nMost effective attacking types against {pokemon}:")
    if defending_types:
        print(f"Defending types: {', '.join(defending_types)}")
    ranked = effective_attacking_types(graph, pokemon)
    best_multiplier = ranked[0][1] if ranked else 1.0
    if best_multiplier <= 1:
        print("  No type is super effective.")
    else:
        for type_id, multiplier in ranked:
            if multiplier != best_multiplier:
                break
            print(f"  {type_id}: {multiplier:g}x")
    print("Combined multipliers are calculated across both defending types.")


def _show_top_stats(graph: KnowledgeGraph) -> None:
    print("Stats: " + ", ".join(STATS))
    stat = input("Choose a stat: ").strip().casefold()
    if stat not in STATS:
        print(f"Unknown stat: {stat}")
        return
    print(f"\nTop 5 Pokemon by {STAT_LABELS[stat]}:")
    for rank, (pokemon, value) in enumerate(top_pokemon_by_stat(graph, stat), 1):
        print(f"  {rank}. {pokemon}: {value}")


def _show_shared(graph: KnowledgeGraph) -> None:
    pokemon = _ask_pokemon(graph)
    matches = pokemon_sharing_type_and_ability(graph, pokemon)
    print(f"\nPokemon sharing at least one type and ability with {pokemon}:")
    if not matches:
        print("  No matches.")
        return
    for candidate, types, abilities in matches:
        print(
            f"  {candidate}: type(s) {', '.join(types)}; "
            f"ability/abilities {', '.join(abilities)}"
        )


def _show_immunities(graph: KnowledgeGraph) -> None:
    print("\nType immunities (attacking type -> immune defending type):")
    for edge in immunity_edges(graph):
        print(f"  {edge['source']} -> {edge['target']}")


def _add_node_interactively(graph: KnowledgeGraph) -> None:
    node_type = input("Node type (Pokemon, Type, Ability): ").strip()
    node_id = input("Node name/ID: ").strip().casefold()
    try:
        graph.add_node(node_id, node_type, name=node_id)
    except ValueError as error:
        print(f"Could not add node: {error}")
        return
    print(f"Added {node_type} node '{node_id}'.")
    print("This change is in memory only and will not modify data/kg.json.")


def _remove_node_interactively(graph: KnowledgeGraph) -> None:
    node_id = input("Node name/ID to remove: ").strip().casefold()
    if graph.remove_node(node_id):
        print(f"Removed '{node_id}' and all incident edges.")
        print("This change is in memory only and will not modify data/kg.json.")
    else:
        print(f"Node not found: {node_id}")


def run_menu(graph: KnowledgeGraph) -> None:
    """Run all seven required graph consultations."""
    actions = {
        "1": ("Describe Pokemon", _show_describe),
        "2": ("Evolution path (BFS)", _show_evolution_path),
        "3": ("Most effective type vs. Pokemon", _show_effective_types),
        "4": ("Top 5 Pokemon by stat", _show_top_stats),
        "5": ("Pokemon sharing type and ability", _show_shared),
        "6": ("Type immunities (no_damage_to)", _show_immunities),
    }

    while True:
        print(
            "\n=== Knowledge PokeGraphs ===\n"
            "1. Describe a Pokemon\n"
            "2. Evolution path between two Pokemon (BFS)\n"
            "3. Most effective attacking type against a Pokemon\n"
            "4. Top 5 Pokemon by stat\n"
            "5. Pokemon sharing a type and ability\n"
            "6. Type immunities (no_damage_to)\n"
            "7. Add or remove a node\n"
            "0. Exit"
        )
        choice = input("Choose a consultation: ").strip()
        if choice in {"0", "q", "quit", "exit"}:
            return
        if choice == "7":
            operation = input("Add or remove a node? [a/r]: ").strip().casefold()
            if operation in {"a", "add"}:
                _add_node_interactively(graph)
            elif operation in {"r", "remove"}:
                _remove_node_interactively(graph)
            else:
                print("Choose 'a' to add or 'r' to remove.")
            continue

        action = actions.get(choice)
        if action is None:
            print("Invalid choice.")
            continue
        try:
            action[1](graph)
        except (KeyError, ValueError) as error:
            print(f"Could not complete consultation: {error}")


def main() -> None:
    graph = KnowledgeGraph.load_from_json(DATA_PATH)
    print(f"Loaded {len(graph.nodes)} nodes and {len(graph.query())} edges.")
    run_menu(graph)


if __name__ == "__main__":
    main()
