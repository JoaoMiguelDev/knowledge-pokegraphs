"""
fetch.py — Coleta de dados da PokéAPI para o projeto Knowledge PokéGraphs.

Popula data/cache/ com respostas JSON brutas da PokéAPI v2, usando cache
em disco para evitar requisições repetidas. A execução é incremental: se
interrompida, basta rodar novamente — o que já foi baixado é reaproveitado.

Escopo:
  - 18 tipos (necessários para o type chart);
  - 151 Pokémon da Geração 1 (pokemon + species);
  - Pokémon satélites de outras gerações que fecham cadeias evolutivas
    iniciadas na Gen 1 (ex.: Crobat, Espeon, Pichu, Mime Jr.);
  - Habilidades referenciadas por todos os Pokémon acima.

Saídas:
  - data/cache/*.json    — respostas brutas (não versionadas)
  - data/log_fetch.txt   — log de execução (versionado, serve de evidência)

Uso:
    python fetch.py
"""

import json
import os
import time
from datetime import datetime

import requests

BASE = "https://pokeapi.co/api/v2"
CACHE = "data/cache"
LOG = "data/log_fetch.txt"
SLEEP = 0.1

# Utils

def cache_path(endpoint: str) -> str:
    return os.path.join(CACHE, endpoint.replace("/", "_") + ".json")

def id_from_url(url: str) -> int:
    return int(url.rstrip("/").split("/")[-1])

def fetch(endpoint: str, stats: dict) -> dict:
    path = cache_path(endpoint)
    if os.path.exists(path):
        stats["hits"] += 1
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    stats["requests"] += 1
    response = requests.get(f"{BASE}/{endpoint}", timeout=15)
    response.raise_for_status()
    data =  response.json()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    time.sleep(SLEEP)
    return data

def chain_species_ids(chain_data:dict) -> list[int]:
    ids: list[int] = []

    def walk(node:dict) -> None:
        ids.append(id_from_url(node["species"]["url"]))
        for child in node.get("evolves_to", []):
            walk(child)

    walk((chain_data["chain"]))
    return ids

# Pipeline

def collect_types(stats: dict) -> None:
    print("[1/5] Tipos (18)...")
    for type_id in range(1,19):
        fetch(f"type/{type_id}", stats)
    print("      ok")

def collect_gen1(stats: dict) -> set[int]:
    print("[2/5] Pokémon da Gen 1 (151)...")
    chains: set[int] = set()
    for pokemon_id in range(1, 152):
        if pokemon_id% 25 == 1:
            print(f"      {pokemon_id - 1}/151")
        fetch(f"pokemon/{pokemon_id}", stats)
        species = fetch(f"pokemon-species/{pokemon_id}", stats)
        chains.add(id_from_url(species["evolution_chain"]["url"]))
    print("      ok")
    return chains

def collect_satellites(chains: set[int], stats: dict) -> set[int]:
    print("[3/5] Cadeias evolutivas + satélites cross-gen...")
    satellites: set[int] = set()
    for chain_id in sorted(chains):
        chain_data = fetch(f"evolution-chain/{chain_id}", stats)
        for species_id in chain_species_ids(chain_data):
            if species_id > 151:
                satellites.add(species_id)

    for species_id in sorted(satellites):
        fetch(f"pokemon/{species_id}", stats)
        fetch(f"pokemon-species/{species_id}", stats)

    print(f"      {len(satellites)} satélites: {sorted(satellites)}")
    return satellites

def collect_abilities(gen1: set[int], satellites: set[int], stats: dict) -> set[int]:
    print("[4/5] Habilidades...")
    abilities: set[int] = set()
    for pokemon_id in sorted(gen1 | satellites):
        pokemon = fetch(f"pokemon/{pokemon_id}", stats)
        for entry in pokemon["abilities"]:
            abilities.add(id_from_url(entry["ability"]["url"]))
    for ability_id in sorted((abilities)):
        fetch(f"ability/{ability_id}", stats)
    print(f"      {len(abilities)} habilidades")
    return abilities

def write_log(stats:dict, satellites:set[int], abilities:set[int]) -> None:
    print("[5/5] Escrevendo log...")
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    cached = len([f for f in os.listdir(CACHE) if f.endswith(".json")])
    first_run = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8") as f:
        if first_run:
            f.write("Knowledge PokéGraphs — fetch log\n")
            f.write("=" * 50 + "\n")
        f.write(f"\n--- Run at {datetime.now().isoformat(timespec='seconds')} ---\n")
        f.write(f"Base URL: {BASE}\n")
        f.write(f"HTTP requests: {stats['requests']}\n")
        f.write(f"Cache hits: {stats['hits']}\n")
        f.write(f"Errors: {len(stats['errors'])}\n")
        for err in stats["errors"]:
            f.write(f"  - {err}\n")
        f.write(f"Satellite Pokémon: {len(satellites)}\n")
        f.write(f"Abilities: {len(abilities)}\n")
        f.write(f"Cached files: {cached}\n")
    print("      ok")

def main() -> None:
    os.makedirs(CACHE, exist_ok=True)
    stats: dict = {"requests": 0, "hits": 0, "errors": []}
    gen1: set[int] = set(range(1, 152))
    satellites: set[int] = set()
    abilities: set[int] = set()

    try:
        collect_types(stats)
        chains = collect_gen1(stats)
        satellites = collect_satellites(chains, stats)
        abilities = collect_abilities(gen1, satellites, stats)
    except Exception as exc:
        stats["errors"].append(repr(exc))
        raise
    finally:
        write_log(stats, satellites, abilities)

    print()
    print("Concluído.")
    print(f"  HTTP requests: {stats['requests']}")
    print(f"  Cache hits:    {stats['hits']}")
    print(f"  Satélites:     {len(satellites)}")
    print(f"  Habilidades:   {len(abilities)}")
    print(f"  Log:           {LOG}")


if __name__ == "__main__":
    main()