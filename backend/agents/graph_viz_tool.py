"""
OpenAI function tool for visualizing PuppyGraph lineage query results.

- visualize_lineage: Executes a Gremlin query against PuppyGraph and renders
  the resulting lineage graph inline using matplotlib/networkx.
"""

import json
import math
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


def _hierarchical_layout(G: nx.DiGraph, n_nodes: int) -> dict:
    """Compute a left-to-right hierarchical layout (source → destination).

    Uses topological generations so each layer contains nodes at the same
    depth from the source.  Falls back to spring layout for cyclic graphs
    or disconnected components that cannot be topologically sorted.
    """
    try:
        # Assign each node a layer based on its topological generation.
        for layer, nodes in enumerate(nx.topological_generations(G)):
            for node in nodes:
                G.nodes[node]["subset"] = layer

        pos = nx.multipartite_layout(G, subset_key="subset", align="horizontal")

        # multipartite_layout stacks layers vertically by default.
        # Rotate 90° so flow goes left → right (swap x and y, flip y).
        pos = {n: (y, -x) for n, (x, y) in pos.items()}

    except nx.NetworkXUnfeasible:
        # Graph has cycles — fall back to spring layout.
        k_spacing = 2.0 + 0.5 * math.sqrt(n_nodes)
        pos = nx.spring_layout(G, k=k_spacing, seed=42, iterations=80)

    return pos


def _draw_lineage_graph(G: nx.DiGraph, title: str = "Table Lineage Graph") -> None:
    """Draw a lineage graph with labeled nodes and edges using matplotlib.

    Sizes, spacing, and fonts scale dynamically based on the number of
    nodes/edges so the graph stays readable regardless of result size.
    """

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    # -- Dynamic sizing ----------------------------------------------------
    # Figure grows with node count so nodes don't pile up.
    base_w, base_h = 12, 7
    scale = max(1.0, math.sqrt(n_nodes / 6))
    fig_w = min(base_w * scale, 28)
    fig_h = min(base_h * scale, 18)

    # Node sizes proportional to degree (number of connections).
    degrees = dict(G.degree())
    max_deg = max(degrees.values()) if degrees else 1
    MIN_NODE_SIZE = 2000
    MAX_NODE_SIZE = 6000
    node_sizes = []
    for nid in G.nodes():
        ratio = degrees[nid] / max_deg if max_deg > 0 else 0
        node_sizes.append(MIN_NODE_SIZE + ratio * (MAX_NODE_SIZE - MIN_NODE_SIZE))

    # Font size: scale down as the graph gets denser.
    label_font = max(7, min(11, int(12 - n_nodes * 0.25)))
    edge_label_font = max(6, label_font - 2)

    # Arrow margin: use the *largest* node size so arrows always clear.
    max_node_size = max(node_sizes) if node_sizes else MIN_NODE_SIZE
    node_radius_pts = math.sqrt(max_node_size)

    # -- Colour palette ----------------------------------------------------
    # Per-type node colours: table → red, workflow → blue, fallback → grey
    TYPE_COLORS = {
        "table":    {"fill": "#F8D6D6", "edge": "#D94A4A"},
        "workflow": {"fill": "#D6D9F8", "edge": "#4A4AD9"},
    }
    DEFAULT_TYPE_COLOR = {"fill": "#E0E0E0", "edge": "#888888"}

    node_fill_colors = []
    node_edge_colors = []
    for nid in G.nodes():
        ntype = G.nodes[nid].get("node_label", "").lower()
        palette = TYPE_COLORS.get(ntype, DEFAULT_TYPE_COLOR)
        node_fill_colors.append(palette["fill"])
        node_edge_colors.append(palette["edge"])

    NODE_EDGE_WIDTH = 2.0
    LABEL_COLOR = "#1A1A1A"
    EDGE_COLOR = "#666666"
    EDGE_WIDTH = 1.8
    ARROW_SIZE = 25
    EDGE_LABEL_COLOR = "#444444"
    TITLE_COLOR = "#222222"

    # -- Layout (hierarchical left-to-right) ---------------------------------
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor="white")
    ax.set_facecolor("white")

    pos = _hierarchical_layout(G, n_nodes)

    # -- Label wrapping ----------------------------------------------------
    node_labels = {}
    for nid, data in G.nodes(data=True):
        raw = data.get("label", nid)
        if len(raw) > 14 and "_" in raw:
            parts = raw.split("_")
            mid = len(parts) // 2
            raw = "_".join(parts[:mid]) + "\n" + "_".join(parts[mid:])
        node_labels[nid] = raw

    # -- Nodes (sized by degree) -------------------------------------------
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=node_fill_colors, node_size=node_sizes,
        edgecolors=node_edge_colors, linewidths=NODE_EDGE_WIDTH,
    )
    nx.draw_networkx_labels(
        G, pos, ax=ax,
        labels=node_labels, font_size=label_font,
        font_weight="bold", font_color=LABEL_COLOR,
        font_family="sans-serif",
    )

    # -- Edges (with visible arrows) ---------------------------------------
    edge_labels = nx.get_edge_attributes(G, "label")
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=ARROW_SIZE,
        edge_color=EDGE_COLOR,
        width=EDGE_WIDTH,
        connectionstyle="arc3,rad=0.08",
        min_source_margin=node_radius_pts,
        min_target_margin=node_radius_pts,
    )
    # Only draw edge labels when graph is small enough to read them.
    if n_edges <= 30:
        nx.draw_networkx_edge_labels(
            G, pos, ax=ax,
            edge_labels=edge_labels, font_size=edge_label_font,
            font_color=EDGE_LABEL_COLOR,
            font_family="sans-serif",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8),
        )

    # -- Title and chrome --------------------------------------------------
    ax.set_title(title, fontsize=16, fontweight="bold", color=TITLE_COLOR, pad=20)
    ax.axis("off")
    fig.tight_layout()
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
