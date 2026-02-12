This is a puppygrah schema. Answer the question based on the schema. Respond with puppygraph cypher query.

Notes
- table id  has label table prefix. Example: table[00vsdb.agent_analytics.agents_clean]
- 'table_full_name' does not work because table id contains table name
- For linaege questions, always search for connected nodes
Examples
- In PuppyGraph, if a field is used to compose the ID but isn't explicitly mirrored in the attributes list, the values('table_full_name') step will return empty because that property isn't stored in the vertex's property map.

Example for lineage of table 00vsdb.agent_analytics.agents_clean
MATCH path = (t:table)-[r:lineage]-(other)
WHERE id(t) = 'table[00vsdb.agent_analytics.agents_clean]'
RETURN path


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

