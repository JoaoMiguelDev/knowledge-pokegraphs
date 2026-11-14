"""In-memory knowledge graph backed by an adjacency list."""

import json
from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import Any


NODE_TYPES = {"Pokemon", "Type", "Ability"}

SCHEMA = {
    ("Pokemon", "has_type", "Type"),
    ("Pokemon", "has_ability", "Ability"),
    ("Pokemon", "evolves_to", "Pokemon"),
    ("Type", "double_damage_to", "Type"),
    ("Type", "half_damage_to", "Type"),
    ("Type", "no_damage_to", "Type"),
}


class KnowledgeGraph:
    """Directed, labeled graph stored as ``source -> relation -> target``.

    Node/edge insertion and direct node/edge lookup are O(1) on average,
    excluding the cost of copying property dictionaries. Operations that
    inspect the graph are documented with their complexity in docs/plan.md.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.adj: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
        self.meta: dict[str, Any] = {}

    def add_node(self, node_id: str, node_type: str, **props: Any) -> None:
        """Add a typed node in O(1) average time, excluding property copying."""
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("node id must be a non-empty string")
        if node_type not in NODE_TYPES:
            raise ValueError(f"invalid node type: {node_type}")
        if node_id in self.nodes:
            raise ValueError(f"node already exists: {node_id}")

        self.nodes[node_id] = {
            "type": node_type,
            "properties": deepcopy(props),
        }
        self.adj[node_id] = {}

    def add_edge(
        self,
        source: str,
        relation: str,
        target: str,
        **props: Any,
    ) -> None:
        """Add an edge in O(1) average time, excluding property copying."""
        if source not in self.nodes:
            raise KeyError(f"unknown source node: {source}")
        if target not in self.nodes:
            raise KeyError(f"unknown target node: {target}")
        if not isinstance(relation, str) or not relation:
            raise ValueError("relation must be a non-empty string")

        relations = self.adj[source].setdefault(relation, {})
        if target in relations:
            raise ValueError(f"edge already exists: {source} -{relation}-> {target}")
        relations[target] = deepcopy(props)

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and incident edges in O(V + E) time."""
        if node_id not in self.nodes:
            return False

        del self.nodes[node_id]
        del self.adj[node_id]
        for relations in self.adj.values():
            for targets in relations.values():
                targets.pop(node_id, None)
        return True

    def remove_edge(self, source: str, relation: str, target: str) -> bool:
        """Remove one edge in O(1) average time."""
        relations = self.adj.get(source, {}).get(relation)
        if relations is None or target not in relations:
            return False

        del relations[target]
        if not relations:
            del self.adj[source][relation]
        return True

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Return a defensive node copy in O(P) time, or None if absent."""
        node = self.nodes.get(node_id)
        if node is None:
            return None
        return {"id": node_id, **deepcopy(node)}

    def get_neighbors(self, node_id: str, relation: str | None = None) -> list[str]:
        """Return outgoing neighbors in O(degree(node)) time."""
        if node_id not in self.nodes:
            return []
        relations = self.adj[node_id]
        if relation is not None:
            return list(relations.get(relation, {}))
        return [
            target
            for targets in relations.values()
            for target in targets
        ]

    def incoming_edges(
        self, node_id: str, relation: str | None = None
    ) -> list[dict[str, Any]]:
        """Return incoming edges in O(E) time; reverse edges are not stored."""
        if node_id not in self.nodes:
            return []
        return [
            {
                "source": source,
                "relation": edge_relation,
                "target": node_id,
                "properties": deepcopy(properties),
            }
            for source, relations in self.adj.items()
            for edge_relation, targets in relations.items()
            if (relation is None or edge_relation == relation)
            for target, properties in targets.items()
            if target == node_id
        ]

    def get_incoming(self, node_id: str, relation: str | None = None) -> list[str]:
        """Return incoming source IDs in O(E) time."""
        return [edge["source"] for edge in self.incoming_edges(node_id, relation)]

    def query(
        self,
        source: str | None = None,
        relation: str | None = None,
        target: str | None = None,
    ) -> list[dict[str, Any]]:
        """Match edge patterns in O(E) time; None acts as a wildcard."""
        return [
            {
                "source": edge_source,
                "relation": edge_relation,
                "target": edge_target,
                "properties": deepcopy(properties),
            }
            for edge_source, relations in self.adj.items()
            if source is None or source == edge_source
            for edge_relation, targets in relations.items()
            if relation is None or relation == edge_relation
            for edge_target, properties in targets.items()
            if target is None or target == edge_target
        ]

    def find_path(self, source: str, target: str) -> list[str] | None:
        """Find a shortest path by BFS in O(V + E) time, or return None."""
        if source not in self.nodes or target not in self.nodes:
            return None
        if source == target:
            return [source]

        queue = deque([source])
        previous: dict[str, str | None] = {source: None}
        while queue:
            current = queue.popleft()
            for neighbor in self.get_neighbors(current):
                if neighbor in previous:
                    continue
                previous[neighbor] = current
                if neighbor == target:
                    path = [target]
                    parent = previous[path[-1]]
                    while parent is not None:
                        path.append(parent)
                        parent = previous[parent]
                    return list(reversed(path))
                queue.append(neighbor)
        return None

    def describe(self, node_id: str) -> dict[str, Any] | None:
        """Return node and incident edges in O(V + E) time, or None if absent."""
        node = self.get_node(node_id)
        if node is None:
            return None
        outgoing = [
            {
                "source": node_id,
                "relation": relation,
                "target": target,
                "properties": deepcopy(properties),
            }
            for relation, targets in self.adj[node_id].items()
            for target, properties in targets.items()
        ]
        return {
            "node": node,
            "incoming": self.incoming_edges(node_id),
            "outgoing": outgoing,
        }

    def validate(
        self, schema: set[tuple[str, str, str]] | None = None
    ) -> bool:
        """Check graph structure and ontology in O(V + E) time."""
        allowed = SCHEMA if schema is None else schema
        errors: list[str] = []
        for node_id, node in self.nodes.items():
            if node.get("type") not in NODE_TYPES:
                errors.append(f"invalid type for node {node_id}")

        for source, relations in self.adj.items():
            if source not in self.nodes:
                errors.append(f"edge source does not exist: {source}")
                continue
            for relation, targets in relations.items():
                for target in targets:
                    if target not in self.nodes:
                        errors.append(f"edge target does not exist: {target}")
                        continue
                    triple = (
                        self.nodes[source]["type"],
                        relation,
                        self.nodes[target]["type"],
                    )
                    if triple not in allowed:
                        errors.append(f"edge violates schema: {triple}")

        if errors:
            raise ValueError("graph validation failed:\n" + "\n".join(errors))
        return True

    @classmethod
    def load_from_json(cls, path: str | Path) -> "KnowledgeGraph":
        """Load/validate JSON in O(V + E) time plus property parsing."""
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict) or not isinstance(data.get("nodes"), list) or not isinstance(
            data.get("edges"), list
        ):
            raise ValueError("graph JSON must contain nodes and edges lists")

        graph = cls()
        graph.meta = deepcopy(data.get("meta", {}))
        for node in data["nodes"]:
            if not isinstance(node, dict) or not isinstance(node.get("properties", {}), dict):
                raise ValueError("each node must have an id, type, and properties object")
            try:
                graph.add_node(
                    node["id"],
                    node["type"],
                    **node.get("properties", {}),
                )
            except (KeyError, TypeError) as exc:
                raise ValueError(f"invalid node record: {node!r}: {exc}") from exc

        for edge in data["edges"]:
            if not isinstance(edge, dict) or not isinstance(edge.get("properties", {}), dict):
                raise ValueError("each edge must have source, relation, target, and properties")
            try:
                graph.add_edge(
                    edge["source"],
                    edge["relation"],
                    edge["target"],
                    **edge.get("properties", {}),
                )
            except (KeyError, TypeError) as exc:
                raise ValueError(f"invalid edge record: {edge!r}: {exc}") from exc
        graph.validate()
        return graph

    def save_to_json(self, path: str | Path) -> None:
        """Validate and save JSON in O(V + E) time plus serialization."""
        self.validate()
        meta = deepcopy(self.meta)
        meta["counts"] = {
            "nodes": len(self.nodes),
            "edges": sum(
                len(targets)
                for relations in self.adj.values()
                for targets in relations.values()
            ),
        }
        data = {
            "meta": meta,
            "nodes": [
                {"id": node_id, **deepcopy(node)}
                for node_id, node in self.nodes.items()
            ],
            "edges": self.query(),
        }
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
