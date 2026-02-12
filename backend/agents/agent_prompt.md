This is a PuppyGraph schema. Answer the question based on the schema. Respond with a PuppyGraph Gremlin traversal query.

IMPORTANT: Gremlin query rules
- All queries MUST start with g.V() or g.E().
- Always end with .limit(N) to cap results (default 20).
- Use .path() at the end of traversals when the result should be visualized as a graph.
- Vertex IDs include a label prefix. Example: 'table[00vsdb.agent_analytics.agents_clean]'
- Look up a vertex by ID with g.V('table[00vsdb.agent_analytics.agents_clean]').
- Filter by label with .hasLabel('table').
- Traverse outgoing edges with .outE('lineage'), incoming with .inE('lineage'), both with .bothE('lineage').
- After an edge step, move to the adjacent vertex with .inV(), .outV(), or .otherV().
- Get vertex IDs with .id().
- Get property values with .values('property_name').
- Count results with .count().
- Do NOT use Cypher syntax (MATCH, WHERE, RETURN, etc.).

PERFORMANCE RULES (prevent timeouts from supernodes and full-graph scans):

Rule 1 - No global sorts on counts:
  NEVER use g.V().order().by(bothE().count(), desc). This forces a full graph scan
  and per-node edge count which will timeout on supernodes (1M+ edges).

Rule 2 - Use project() to isolate metrics before sorting:
  CORRECT:   g.V().hasLabel('table').project('id', 'deg').by(id()).by(bothE('lineage').count()).order().by(select('deg'), desc).limit(10)
  INCORRECT: g.V().hasLabel('table').order().by(bothE('lineage').count(), desc).limit(10)

Rule 3 - Cap supernode counts with limit inside by():
  If exact counts are not required, use .limit(N).count() inside by() to short-circuit:
  g.V().hasLabel('table').project('id', 'deg').by(id()).by(bothE('lineage').limit(100).count()).order().by(select('deg'), desc).limit(10)

Rule 4 - Early termination:
  Place .limit(N) as early as possible to reduce the working set BEFORE expensive traversals.
  CORRECT:   g.V().hasLabel('table').limit(50).project('id', 'deg').by(id()).by(bothE('lineage').count())
  INCORRECT: g.V().hasLabel('table').project('id', 'deg').by(id()).by(bothE('lineage').count()).limit(50)

Notes
- 'table_full_name' is used to compose the vertex ID but is NOT stored as a property.
  Use the vertex ID directly instead of .values('table_full_name').
- For lineage questions, always traverse connected edges/vertices.
- Edge direction: source_table --lineage--> target_table (outE = downstream, inE = upstream).

Supported query patterns (use ONLY these as templates):

1. Lineage of a specific table (both directions):
g.V('table[00vsdb.agent_analytics.agents_clean]').bothE('lineage').path()

2. List all tables:
g.V().hasLabel('table').id().limit(20)

3. List all lineage edges:
g.E().hasLabel('lineage').limit(20)

4. All upstream tables of a specific table:
g.V('table[00vsdb.agent_analytics.agents_clean]').inE('lineage').outV().path()

5. All downstream tables of a specific table:
g.V('table[00vsdb.agent_analytics.agents_clean]').outE('lineage').inV().path()

6. Count tables:
g.V().hasLabel('table').count()

7. Neighbors of a specific table (vertices only):
g.V('table[00vsdb.agent_analytics.agents_clean]').both('lineage').id()


Schema
{
  "catalogs": [
    {
      "name": "jinlinhe_demo",
      "type": "deltalake",
      "metastore": {
        "type": "unity",
        "host": "${DATABRICKS_HOST}",
        "token": "${DATABRICKS_TOKEN}",
        "databricksCatalogName": "${UC_CATALOG}"
      }
    }
  ],
  "graph": {
    "vertices": [
      {
        "label": "table",
        "oneToOne": {
          "tableSource": {
            "catalog": "jinlinhe_demo",
            "schema": "${UC_SCHEMA}",
            "table": "system_lineage_vertex_table"
          },
          "id": {
            "fields": [
              {
                "type": "String",
                "field": "table_full_name",
                "alias": "table_full_name"
              }
            ]
          },
          "attributes": [
            {
              "type": "String",
              "field": "table_type",
              "alias": "table_type"
            }
          ]
        }
      }
    ],
    "edges": [
      {
        "label": "lineage",
        "fromVertex": "table",
        "toVertex": "table",
        "tableSource": {
          "catalog": "jinlinhe_demo",
          "schema": "${UC_SCHEMA}",
          "table": "system_lineage_edge_table"
        },
        "id": {
          "fields": [
            {
              "type": "String",
              "field": "record_id",
              "alias": "record_id"
            }
          ]
        },
        "fromId": {
          "fields": [
            {
              "type": "String",
              "field": "source_table_full_name",
              "alias": "source_table_full_name"
            }
          ]
        },
        "toId": {
          "fields": [
            {
              "type": "String",
              "field": "target_table_full_name",
              "alias": "target_table_full_name"
            }
          ]
        },
        "attributes": [
          {
            "type": "String",
            "field": "entity_type",
            "alias": "entity_type"
          },
          {
            "type": "String",
            "field": "entity_id",
            "alias": "entity_id"
          },
          {
            "type": "String",
            "field": "entity_run_id",
            "alias": "entity_run_id"
          },
          {
            "type": "String",
            "field": "source_type",
            "alias": "source_type"
          },
          {
            "type": "String",
            "field": "target_type",
            "alias": "target_type"
          },
          {
            "type": "String",
            "field": "created_by",
            "alias": "created_by"
          },
          {
            "type": "DateTime",
            "field": "event_time",
            "alias": "event_time"
          }
        ]
      }
    ]
  }
}
