"""Interactive, filtered visualizations for the Pokémon knowledge graph."""

from pathlib import Path
import re
import unicodedata

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from kg import KnowledgeGraph


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "kg.json"
FIGURES_PATH = ROOT / "figuras"
NODE_COLORS = {
    "Pokemon": "#ef5350",
    "Type": "#42a5f5",
    "Ability": "#66bb6a",
}
RELATION_COLORS = {
    "double_damage_to": "#d32f2f",
    "half_damage_to": "#1976d2",
    "no_damage_to": "#616161",
    "evolves_to": "#8e24aa",
    "has_type": "#ef6c00",
    "has_ability": "#388e3c",
}
STAT_LABELS = {
    "hp": "HP",
    "attack": "Attack",
    "defense": "Defense",
    "sp_attack": "Special Attack",
    "sp_defense": "Special Defense",
    "speed": "Speed",
}


def _node_types(graph: KnowledgeGraph, node_type: str) -> list[str]:
    return [
        node_id
        for node_id, node in graph.nodes.items()
        if node["type"] == node_type
    ]


def _edge_records(graph: KnowledgeGraph, relation: str) -> list[tuple[str, str, dict]]:
    return [
        (source, target, properties)
        for source, relations in graph.adj.items()
        for target, properties in relations.get(relation, {}).items()
    ]


def _add_edge(
    projection: nx.Graph,
    source: str,
    relation: str,
    target: str,
    properties: dict,
) -> None:
    projection.add_edge(
        source,
        target,
        relation=relation,
        properties=dict(properties),
    )


def type_chart_projection(graph: KnowledgeGraph) -> nx.DiGraph:
    """Create the 18-node attacker-to-defender type-chart projection."""
    projection = nx.DiGraph()
    for type_id in _node_types(graph, "Type"):
        projection.add_node(type_id, node_type="Type")

    chart_relations = (
        "double_damage_to",
        "half_damage_to",
        "no_damage_to",
    )
    for relation in chart_relations:
        for source, target, properties in _edge_records(graph, relation):
            _add_edge(projection, source, relation, target, properties)
    return projection


def _draw_type_chart(graph: KnowledgeGraph) -> None:
    """Draw type effectiveness as a readable attacker-by-defender matrix."""
    standard_order = [
        "normal", "fire", "water", "electric", "grass", "ice",
        "fighting", "poison", "ground", "flying", "psychic", "bug",
        "rock", "ghost", "dragon", "dark", "steel", "fairy",
    ]
    available = set(_node_types(graph, "Type"))
    types = [type_id for type_id in standard_order if type_id in available]
    types.extend(sorted(available.difference(types)))
    index = {type_id: position for position, type_id in enumerate(types)}

    # Category codes map to immunity, resistance, neutral, and weakness.
    categories = np.full((len(types), len(types)), 2, dtype=int)
    annotations = []
    labels = {
        "no_damage_to": (0, "0x"),
        "half_damage_to": (1, "0.5x"),
        "double_damage_to": (3, "2x"),
    }
    for relation, (category, label) in labels.items():
        for source, target, _ in _edge_records(graph, relation):
            if source not in index or target not in index:
                continue
            row, column = index[source], index[target]
            categories[row, column] = category
            annotations.append((column, row, label))

    colors = ["#4b5563", "#93c5fd", "#f3f4f6", "#f87171"]
    colormap = ListedColormap(colors)
    figure, axis = plt.subplots(figsize=(13, 11))
    axis.imshow(
        categories,
        cmap=colormap,
        vmin=-0.5,
        vmax=3.5,
        aspect="equal",
    )
    for column, row, label in annotations:
        text_color = "white" if categories[row, column] in {0, 3} else "#1f2937"
        axis.text(
            column,
            row,
            label,
            ha="center",
            va="center",
            fontsize=8,
            color=text_color,
            fontweight="bold",
        )

    axis.set_xticks(range(len(types)), labels=types, rotation=45, ha="left")
    axis.set_yticks(range(len(types)), labels=types)
    axis.xaxis.tick_top()
    axis.xaxis.set_label_position("top")
    axis.set_xlabel("Defending type")
    axis.set_ylabel("Attacking type")
    axis.set_title("Type effectiveness (attackers vs. defenders)", pad=28)
    axis.set_xticks(np.arange(-0.5, len(types), 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(types), 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=1.5)
    axis.tick_params(which="minor", bottom=False, left=False)

    legend = [
        Patch(facecolor=colors[0], label="0x — no damage"),
        Patch(facecolor=colors[1], label="0.5x — not very effective"),
        Patch(facecolor=colors[2], label="1x — neutral (blank cell)"),
        Patch(facecolor=colors[3], label="2x — super effective"),
    ]
    figure.legend(
        handles=legend,
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 0.015),
    )
    figure.tight_layout(rect=(0, 0.07, 1, 1))


def evolution_projection(graph: KnowledgeGraph, pokemon: str) -> nx.DiGraph:
    """Return the complete evolution chain containing a Pokémon."""
    pokemon_id = _find_node(graph, pokemon, "Pokemon")
    projection = nx.DiGraph()
    evolution_edges = _edge_records(graph, "evolves_to")
    undirected = nx.Graph()
    undirected.add_edges_from((source, target) for source, target, _ in evolution_edges)

    if pokemon_id in undirected:
        chain_nodes = nx.node_connected_component(undirected, pokemon_id)
    else:
        chain_nodes = {pokemon_id}

    for node_id in chain_nodes:
        projection.add_node(node_id, node_type="Pokemon")
    for source, target, properties in evolution_edges:
        if source in chain_nodes and target in chain_nodes:
            _add_edge(projection, source, "evolves_to", target, properties)
    return projection


def type_pokemon_projection(graph: KnowledgeGraph, type_name: str) -> nx.Graph:
    """Create a small bipartite view of one type and its Pokémon."""
    type_id = _find_node(graph, type_name, "Type")
    projection = nx.Graph()
    projection.add_node(type_id, node_type="Type")
    for pokemon_id in graph.get_incoming(type_id, "has_type"):
        projection.add_node(pokemon_id, node_type="Pokemon")
        projection.add_edge(
            pokemon_id,
            type_id,
            relation="has_type",
            properties={},
        )
    return projection


def ability_pokemon_projection(graph: KnowledgeGraph, ability: str) -> nx.Graph:
    """Create a small bipartite view of one ability and its Pokémon."""
    ability_id = _find_node(graph, ability, "Ability")
    projection = nx.Graph()
    projection.add_node(ability_id, node_type="Ability")
    for pokemon_id in graph.get_incoming(ability_id, "has_ability"):
        projection.add_node(pokemon_id, node_type="Pokemon")
        edge = graph.adj[pokemon_id]["has_ability"][ability_id]
        projection.add_edge(
            pokemon_id,
            ability_id,
            relation="has_ability",
            properties=dict(edge),
        )
    return projection


def pokemon_neighborhood_projection(graph: KnowledgeGraph, pokemon: str) -> nx.DiGraph:
    """Show one Pokémon and its directly related nodes and edges."""
    pokemon_id = _find_node(graph, pokemon, "Pokemon")
    projection = nx.DiGraph()
    projection.add_node(pokemon_id, node_type="Pokemon")

    for relation, targets in graph.adj[pokemon_id].items():
        for target, properties in targets.items():
            projection.add_node(target, node_type=graph.nodes[target]["type"])
            _add_edge(projection, pokemon_id, relation, target, properties)

    for edge in graph.incoming_edges(pokemon_id):
        source = edge["source"]
        projection.add_node(source, node_type=graph.nodes[source]["type"])
        _add_edge(
            projection,
            source,
            edge["relation"],
            pokemon_id,
            edge["properties"],
        )
    return projection


def _find_node(graph: KnowledgeGraph, text: str, node_type: str) -> str:
    normalized = text.strip().casefold()
    for node_id, node in graph.nodes.items():
        if node["type"] == node_type and node_id.casefold() == normalized:
            return node_id
    raise ValueError(f"{node_type} not found: {text}")


def _draw_projection(
    projection: nx.Graph,
    title: str,
    *,
    circular: bool = False,
) -> None:
    if not projection.nodes:
        raise ValueError("there are no nodes to visualize")

    plt.figure(figsize=(max(10, len(projection) * 0.35), 8))
    if circular:
        positions = nx.circular_layout(projection)
    elif projection.number_of_edges() == 0:
        positions = nx.circular_layout(projection)
    else:
        positions = nx.spring_layout(projection, seed=42, k=1.1, iterations=100)

    node_colors = [
        NODE_COLORS.get(projection.nodes[node].get("node_type"), "#90a4ae")
        for node in projection.nodes
    ]
    nx.draw_networkx_nodes(
        projection,
        positions,
        node_color=node_colors,
        node_size=1050 if len(projection) <= 35 else 550,
        edgecolors="white",
        linewidths=0.8,
    )
    nx.draw_networkx_labels(
        projection,
        positions,
        font_size=8 if len(projection) <= 35 else 6,
        font_weight="bold",
    )

    if projection.is_directed():
        relations = {
            projection.edges[source, target].get("relation")
            for source, target in projection.edges
        }
        for relation in relations:
            edges = [
                (source, target)
                for source, target in projection.edges
                if projection.edges[source, target].get("relation") == relation
            ]
            nx.draw_networkx_edges(
                projection,
                positions,
                edgelist=edges,
                edge_color=RELATION_COLORS.get(relation, "#78909c"),
                width=1.3,
                alpha=0.7,
                arrows=True,
                arrowsize=14,
                connectionstyle="arc3,rad=0.08",
            )
    else:
        edge_colors = [
            RELATION_COLORS.get(
                projection.edges[source, target].get("relation"), "#78909c"
            )
            for source, target in projection.edges
        ]
        nx.draw_networkx_edges(
            projection,
            positions,
            edge_color=edge_colors,
            width=1.5,
            alpha=0.7,
        )

    edge_labels = {}
    for source, target, data in projection.edges(data=True):
        if data.get("relation") in {
            "double_damage_to",
            "half_damage_to",
            "no_damage_to",
        }:
            multiplier = data.get("properties", {}).get("multiplier")
            edge_labels[source, target] = f"{multiplier:g}x"
    if edge_labels:
        nx.draw_networkx_edge_labels(
            projection,
            positions,
            edge_labels=edge_labels,
            font_size=7,
            rotate=False,
            label_pos=0.55,
        )

    plt.title(title, fontsize=14)
    plt.axis("off")
    plt.tight_layout()


def _draw_stat_ranking(graph: KnowledgeGraph, stat: str) -> None:
    pokemon = [
        (node_id, node["properties"].get(stat))
        for node_id, node in graph.nodes.items()
        if node["type"] == "Pokemon"
    ]
    ranked = sorted(
        ((name, value) for name, value in pokemon if isinstance(value, (int, float))),
        key=lambda item: (-item[1], item[0]),
    )[:10]
    if not ranked:
        raise ValueError(f"no Pokémon have a numeric {stat} value")

    names = [name for name, _ in reversed(ranked)]
    values = [value for _, value in reversed(ranked)]
    plt.figure(figsize=(10, 6))
    plt.barh(names, values, color="#ef5350")
    plt.xlabel(STAT_LABELS[stat])
    plt.title(f"Top 10 Pokémon — {STAT_LABELS[stat]}")
    plt.tight_layout()


def _save_prompt() -> None:
    answer = input("Save this image to figuras/? [y/N]: ").strip().casefold()
    if answer not in {"y", "yes", "s", "sim"}:
        return
    FIGURES_PATH.mkdir(parents=True, exist_ok=True)
    filename = re.sub(r"[^a-z0-9]+", "-", _slug(plt.gca().get_title())).strip("-")
    output = FIGURES_PATH / f"{filename or 'visualizacao'}.png"
    plt.savefig(output, dpi=200, bbox_inches="tight")
    print(f"Saved: {output}")


def _slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.casefold()


def _ask_node(graph: KnowledgeGraph, node_type: str, label: str) -> str:
    while True:
        raw_value = input(f"{label} (or ? to list): ")
        if raw_value is None:
            raise EOFError("input ended while selecting a graph node")
        value = raw_value.strip()
        if value == "?":
            available = sorted(_node_types(graph, node_type))
            for start in range(0, len(available), 8):
                print(", ".join(available[start : start + 8]))
            continue
        if not value:
            print("Enter a name or ? to list options.")
            continue
        try:
            return _find_node(graph, value, node_type)
        except ValueError:
            matches = [
                node_id
                for node_id in _node_types(graph, node_type)
                if value.casefold() in node_id.casefold()
            ]
            if len(matches) == 1:
                return matches[0]
            if matches:
                print("Matches: " + ", ".join(sorted(matches)))
            else:
                print(f"{label} not found. Try again or enter ? to list options.")
    raise RuntimeError("node selection ended unexpectedly")


def _ask_choice(prompt: str, choices: dict[str, str]) -> str | None:
    value = input(prompt).strip().casefold()
    if value in {"0", "q", "quit", "exit"}:
        return None
    if value not in choices:
        print("Invalid choice.")
        return ""
    return choices[value]


def run_menu(graph: KnowledgeGraph) -> None:
    """Run the interactive visualization menu."""
    choices = {
        "1": "type_chart",
        "2": "evolution",
        "3": "type_pokemon",
        "4": "ability_pokemon",
        "5": "pokemon_neighborhood",
        "6": "stats",
    }
    while True:
        print(
            "\n=== Knowledge Pokemon Graphs: visualizer ===\n"
            "1. Type effectiveness chart (18 types)\n"
            "2. Evolution chain for one Pokemon\n"
            "3. Pokemon that have one type\n"
            "4. Pokemon that have one ability\n"
            "5. One Pokemon and its direct connections\n"
            "6. Top 10 Pokemon by stat\n"
            "0. Exit"
        )
        selected = _ask_choice("Choose a view: ", choices)
        if selected is None:
            return
        if selected == "":
            continue

        try:
            if selected == "type_chart":
                _draw_type_chart(graph)
            elif selected == "evolution":
                pokemon = _ask_node(graph, "Pokemon", "Pokemon name")
                projection = evolution_projection(graph, pokemon)
                _draw_projection(projection, f"Evolution chain: {pokemon}")
            elif selected == "type_pokemon":
                node = _ask_node(graph, "Type", "Type name")
                projection = type_pokemon_projection(graph, node)
                _draw_projection(projection, f"Pokémon with type: {node}")
            elif selected == "ability_pokemon":
                node = _ask_node(graph, "Ability", "Ability name")
                projection = ability_pokemon_projection(graph, node)
                _draw_projection(projection, f"Pokémon with ability: {node}")
            elif selected == "pokemon_neighborhood":
                pokemon = _ask_node(graph, "Pokemon", "Pokemon name")
                projection = pokemon_neighborhood_projection(graph, pokemon)
                _draw_projection(projection, f"Connections of {pokemon}")
            else:
                stat = _ask_choice(
                    "Choose a stat (hp, attack, defense, sp_attack, sp_defense, speed): ",
                    {key: key for key in STAT_LABELS},
                )
                if stat is None:
                    continue
                if stat == "":
                    continue
                _draw_stat_ranking(graph, stat)

            _save_prompt()
            plt.show()
        except ValueError as error:
            print(error)
        finally:
            plt.close("all")


def main() -> None:
    graph = KnowledgeGraph.load_from_json(DATA_PATH)
    print(f"Loaded {len(graph.nodes)} nodes and {len(graph.query())} edges.")
    run_menu(graph)


if __name__ == "__main__":
    main()
