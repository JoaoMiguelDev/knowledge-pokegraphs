"""
build_kg.py — Curadoria do Knowledge Graph a partir do cache da PokéAPI.

Lê os arquivos brutos de data/cache/ e produz data/kg.json, seguindo a
ontologia do projeto:

  Nós:     Pokemon, Type, Ability
  Arestas: has_type, has_ability, evolves_to,
           double_damage_to, half_damage_to, no_damage_to

Uso:
    python build_kg.py
"""
import glob
import json
import os
from collections import Counter
from datetime import datetime

CACHE = "data/cache"
OUT = "data/kg.json"

# Ontologia

NODE_TYPES = {"Pokemon", "Type", "Ability"}

SCHEMA = {
    ("Pokemon", "has_type", "Type"),
    ("Pokemon", "has_ability", "Ability"),
    ("Pokemon", "evolves_to", "Pokemon"),
    ("Type", "double_damage_to", "Type"),
    ("Type", "half_damage_to", "Type"),
    ("Type", "no_damage_to", "Type"),
}

TYPE_CHART_MAP = {
    "double_damage_to": 2.0,
    "half_damage_to": 0.5,
    "no_damage_to": 0.0,
}

ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
         "vi": 6, "vii": 7, "viii": 8, "ix": 9}

# Utils

def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def id_from_url(url: str) -> int:
    return int(url.rstrip("/").split("/")[-1])

def generation_number(gen_name: str) -> int:
    return ROMAN[gen_name.split("-", 1)[1]]

def add_node(nodes: dict, node_id: str, node_type: str, properties: dict) -> None:
    if node_id in nodes:
        raise ValueError(f"nó duplicado: {node_id}")
    if node_type not in NODE_TYPES:
        raise ValueError(f"tipo de nó inválido: {node_type}")
    nodes[node_id] = {
        "id": node_id,
        "type": node_type,
        "properties": {"name": node_id, **properties},
    }

def add_edge(edges: list, seen: set, source: str, relation: str,
             target: str, properties: dict) -> None:
    key = (source, relation, target)
    if key in seen:
        return
    seen.add(key)
    edges.append({
        "source": source,
        "relation": relation,
        "target": target,
        "properties": properties,
    })

# Extractors

def extract_types(nodes: dict, edges: list, seen: set) -> None:
    print("[1/4] Tipos + type chart...")
    for path in sorted(glob.glob(os.path.join(CACHE, "type_*.json"))):
        data = load(path)
        add_node(nodes, data["name"], "Type", {})
        for field, mult in TYPE_CHART_MAP.items():
            for target in data["damage_relations"][field]:
                add_edge(edges, seen, data["name"], field, target["name"],
                         {"multiplier": mult})

def extract_abilities(nodes: dict) -> None:
    print("[2/4] Habilidades...")
    for path in sorted(glob.glob(os.path.join(CACHE, "ability_*.json"))):
        data = load(path)
        add_node(nodes, data["name"], "Ability", {})

def extract_pokemon(nodes: dict, edges: list, seen: set) -> dict[int, str]:
    print("[3/4] Pokémon...")
    id_to_name: dict[int, str] = {}
    for path in sorted(glob.glob(os.path.join(CACHE, "pokemon_*.json"))):
        data = load(path)
        pid = data["id"]
        name = data["name"]
        id_to_name[pid] = name

        stats = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}
        species = load(os.path.join(CACHE, f"pokemon-species_{pid}.json"))

        properties = {
            "dex_number": pid,
            "generation": generation_number(species["generation"]["name"]),
            "hp": stats["hp"],
            "attack": stats["attack"],
            "defense": stats["defense"],
            "sp_attack": stats["special-attack"],
            "sp_defense": stats["special-defense"],
            "speed": stats["speed"],
        }
        add_node(nodes, name, "Pokemon", properties)

        for entry in data["types"]:
            add_edge(edges, seen, name, "has_type", entry["type"]["name"], {})

        for entry in data["abilities"]:
            add_edge(edges, seen, name, "has_ability", entry["ability"]["name"],
                     {"is_hidden": entry["is_hidden"], "slot": entry["slot"]})

    return id_to_name

def extract_evolutions(edges: list, seen: set, id_to_name: dict[int, str]) -> None:
    print("[4/4] Evoluções...")
    skipped: list[tuple[int, int]] = []

    def walk(node: dict) -> None:
        source = id_to_name.get(id_from_url(node["species"]["url"]))
        for child in node.get("evolves_to", []):
            target = id_to_name.get(id_from_url(child["species"]["url"]))
            if source and target:
                add_edge(edges, seen, source, "evolves_to", target, {})
            else:
                skipped.append((id_from_url(node["species"]["url"]),
                                id_from_url(child["species"]["url"])))
            walk(child)

    for path in sorted(glob.glob(os.path.join(CACHE, "evolution-chain_*.json"))):
        data = load(path)
        walk(data["chain"])

    if skipped:
        print(f"      [aviso] {len(skipped)} arestas ignoradas (espécie fora do grafo)")
        for s, t in skipped[:5]:
            print(f"        {s} -> {t}")
        if len(skipped) > 5:
            print(f"        ... e mais {len(skipped) - 5}")

# Validation

def validate(nodes: dict, edges: list) -> None:
    errors: list[str] = []
    for e in edges:
        src = nodes.get(e["source"])
        tgt = nodes.get(e["target"])
        if src is None:
            errors.append(f"aresta com origem ausente: {e['source']}")
            continue
        if tgt is None:
            errors.append(f"aresta com destino ausente: {e['target']}")
            continue
        if (src["type"], e["relation"], tgt["type"]) not in SCHEMA:
            errors.append(
                f"aresta viola o schema: "
                f"({src['type']}) -{e['relation']}-> ({tgt['type']})"
            )
    if errors:
        raise ValueError("validação falhou:\n" + "\n".join(errors))
    print("      ok")

# Relatório

def summary(nodes: dict, edges: list) -> None:
    node_types = Counter(n["type"] for n in nodes.values())
    relations = Counter(e["relation"] for e in edges)

    connected = set()
    for e in edges:
        connected.add(e["source"])
        connected.add(e["target"])
    isolated = [nid for nid in nodes if nid not in connected]

    print("\nResumo do grafo:")
    print(f"  Nós:     {len(nodes)}")
    for t, c in sorted(node_types.items()):
        print(f"    {t:10s} {c}")
    print(f"  Arestas: {len(edges)}")
    for r, c in sorted(relations.items()):
        print(f"    {r:20s} {c}")
    if isolated:
        print(f"  Nós isolados: {len(isolated)}")
        for nid in isolated:
            print(f"    - {nid}")

def main() -> None:
    nodes: dict = {}
    edges: list = []
    seen: set = set()

    extract_types(nodes, edges, seen)
    extract_abilities(nodes)
    id_to_name = extract_pokemon(nodes, edges, seen)
    extract_evolutions(edges, seen, id_to_name)

    print("\nValidando contra o schema...")
    validate(nodes, edges)

    def node_sort_key(n: dict):
        if n["type"] == "Pokemon":
            return (n["type"], n["properties"]["dex_number"])
        return (n["type"], n["id"])

    nodes_list = sorted(nodes.values(), key=node_sort_key)
    edges_list = sorted(edges, key=lambda e: (e["relation"], e["source"], e["target"]))

    kg = {
        "meta": {
            "generated_by": "build_kg.py",
            "build_date": datetime.now().isoformat(timespec="seconds"),
            "pokeapi_base": "https://pokeapi.co/api/v2",
            "counts": {
                "nodes": len(nodes_list),
                "edges": len(edges_list),
            },
        },
        "nodes": nodes_list,
        "edges": edges_list,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(kg, f, ensure_ascii=False, indent=2)

    summary(nodes, edges)
    print(f"\nEscrito: {OUT}")


if __name__ == "__main__":
    main()