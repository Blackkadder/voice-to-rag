"""
OpenAI function tool for visualizing PuppyGraph lineage query results.

- visualize_lineage: Executes a Gremlin query against PuppyGraph and renders
  the resulting lineage graph inline using matplotlib/networkx.
"""

import json
import os

import matplotlib.pyplot as plt
import networkx as nx
from gremlin_python.structure.graph import Edge, Path, Vertex
from puppygraph import PuppyGraphClient, PuppyGraphHostConfig


# ---------------------------------------------------------------------------
# Helpers for adding graph elements
# ---------------------------------------------------------------------------

def _short_name(node_id: str) -> str:
    """Derive a short display label from a fully-qualified node ID."""
    node_id = str(node_id)
    return node_id.split(".")[-1].rstrip("]") if "." in node_id else node_id


def _add_vertex(G: nx.DiGraph, vertex: Vertex) -> None:
    """Add a Gremlin Vertex to the NetworkX graph."""
    vid = str(vertex.id)
    label = vertex.label if vertex.label else "unknown"
    G.add_node(vid, label=_short_name(vid), full_id=vid, node_label=label)


def _add_node_from_id(G: nx.DiGraph, node_id: str) -> None:
    """Add a node by its string ID (fallback when only IDs are returned)."""
    node_id = str(node_id)
    if node_id not in G:
        G.add_node(node_id, label=_short_name(node_id), full_id=node_id, node_label="table")


def _add_edge(G: nx.DiGraph, edge: Edge) -> None:
    """Add a Gremlin Edge (and its endpoint vertices) to the NetworkX graph."""
    out_id = str(edge.outV.id)
    in_id = str(edge.inV.id)
    # Ensure endpoint vertices exist in the graph
    _add_vertex(G, edge.outV)
    _add_vertex(G, edge.inV)
    G.add_edge(out_id, in_id, label=edge.label)


def _add_path(G: nx.DiGraph, path: Path) -> None:
    """Add all vertices and edges from a Gremlin Path.

    Gremlin Path.objects is an interleaved list: [Vertex, Edge, Vertex, Edge, ...]
    """
    for obj in path.objects:
        if isinstance(obj, Vertex):
            _add_vertex(G, obj)
        elif isinstance(obj, Edge):
            _add_edge(G, obj)


# ---------------------------------------------------------------------------
# Gremlin results → NetworkX conversion
# ---------------------------------------------------------------------------

def _results_to_graph(results: list) -> nx.DiGraph:
    """
    Convert PuppyGraph Gremlin query results into a NetworkX directed graph.

    Handles multiple result shapes:
      - Path objects  (from .path() traversals)
      - Vertex objects
      - Edge objects
      - Scalar ID strings (from .id() traversals)
    """
    G = nx.DiGraph()

    for item in results:
        if isinstance(item, Path):
            _add_path(G, item)
        elif isinstance(item, Vertex):
            _add_vertex(G, item)
        elif isinstance(item, Edge):
            _add_edge(G, item)
        elif isinstance(item, str):
            _add_node_from_id(G, item)

    return G


def _draw_lineage_graph(G: nx.DiGraph, title: str = "Table Lineage Graph", figsize=(14, 8)) -> None:
    """Draw a lineage graph with labeled nodes and edges using matplotlib."""
    plt.figure(figsize=figsize)

    pos = nx.spring_layout(G, k=2.5, seed=42)

    # Draw nodes
    node_labels = nx.get_node_attributes(G, "label")
    nx.draw_networkx_nodes(
        G, pos, node_color="lightblue", node_size=3000,
        edgecolors="black", linewidths=1.5,
    )
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=10, font_weight="bold")

    # Draw edges with relationship type labels
    edge_labels = nx.get_edge_attributes(G, "label")
    nx.draw_networkx_edges(
        G, pos, arrows=True, arrowsize=25, edge_color="gray",
        width=2, connectionstyle="arc3,rad=0.1",
    )
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=9, font_color="red")

    plt.title(title, fontsize=14, fontweight="bold")
    plt.axis("off")
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------

def visualize_lineage(gremlin_query: str) -> str:
    """
    Execute a Gremlin query against PuppyGraph and render the resulting
    lineage graph inline (matplotlib).

    Args:
        gremlin_query: The Gremlin query string to execute and visualize.

    Returns:
        A text summary of the rendered graph (node/edge counts and node names).
    """
    host = os.getenv("PUPPYGRAPH_HOST", "localhost")
    client = PuppyGraphClient(PuppyGraphHostConfig(host))

    try:
        results = client.gremlin_query(gremlin_query)
    except Exception as e:
        return json.dumps({"error": f"Query failed: {e}"})

    if not results:
        return json.dumps({"message": "Query returned no results — nothing to visualize."})

    G = _results_to_graph(results)

    if G.number_of_nodes() == 0:
        return json.dumps({"message": "No nodes found in query results — nothing to visualize."})

    _draw_lineage_graph(G, title="Table Lineage Graph")

    # Build a human-readable summary for the LLM
    node_names = [data.get("label", nid) for nid, data in G.nodes(data=True)]
    summary = (
        f"Lineage graph rendered: {G.number_of_nodes()} nodes "
        f"({', '.join(node_names)}), {G.number_of_edges()} edges."
    )
    return summary


# ---------------------------------------------------------------------------
# OpenAI function-calling tool spec
# ---------------------------------------------------------------------------

VISUALIZE_LINEAGE_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "visualize_lineage",
        "description": (
            "Execute a PuppyGraph Gremlin query and render the resulting "
            "lineage graph as an inline visualization. Call this after "
            "execute_gremlin when the user asks about lineage, data flow, "
            "or graph relationships and would benefit from a visual diagram."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "gremlin_query": {
                    "type": "string",
                    "description": (
                        "The PuppyGraph Gremlin query string whose results "
                        "should be visualized as a lineage graph."
                    ),
                },
            },
            "required": ["gremlin_query"],
        },
    },
}
