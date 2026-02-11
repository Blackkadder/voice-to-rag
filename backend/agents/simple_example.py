"""
Simple Example: Upload Schema and Query PuppyGraph

This is a simplified version that just:
1. Uploads schema.json to PuppyGraph
2. Queries the graph using Gremlin

Usage:
    python -m backend.agents.simple_example
    python -m backend.agents.simple_example --schema schema_lineage.json
    python -m backend.agents.simple_example --schema schema_lineage.json --force
"""

import os
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"✓ Loaded .env from: {env_path}\n")

from backend.agents.simple_client import PuppyGraphClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main(schema_name: str = "schema.json", force: bool = False):
    """
    Main example
    
    Args:
        schema_name: Name of schema file (default: "schema.json")
        force: Force upload even if schema exists (default: False)
    """
    print("="*80)
    print("PuppyGraph Simple Example")
    print("="*80)
    print(f"Schema: {schema_name}")
    print(f"Force upload: {force}")
    print("="*80)
    
    # Initialize client
    client = PuppyGraphClient(
        host=os.getenv("PUPPYGRAPH_HOST", "localhost"),
        gremlin_port=int(os.getenv("PUPPYGRAPH_PORT", "8182")),
        http_port=int(os.getenv("PUPPYGRAPH_HTTP_PORT", "8081")),
        username=os.getenv("PUPPYGRAPH_USERNAME"),
        password=os.getenv("PUPPYGRAPH_PASSWORD")
    )
    
    # Step 1: Upload schema
    force_msg = " (FORCE)" if force else ""
    print(f"\n1. Uploading schema to PuppyGraph{force_msg}...")
    schema_path = Path(__file__).parent / schema_name
    
    if not schema_path.exists():
        print(f"   ✗ Schema file not found: {schema_path}")
        return
    
    try:
        response = client.upload_schema(str(schema_path), force=force)
        if response.get("status") == "skipped":
            print(f"   ⊙ Schema already exists, skipped upload")
            print(f"   Tip: Use --force to override existing schema")
        else:
            print(f"   ✓ Schema uploaded: {response}")
    except Exception as e:
        print(f"   ✗ Failed to upload schema: {e}")
        print("   Note: Make sure PuppyGraph HTTP API is running")
        # Continue anyway - schema might already be loaded
    
    # Step 2: Connect to Gremlin server
    print("\n2. Connecting to PuppyGraph Gremlin server...")
    try:
        client.connect()
    except Exception as e:
        print(f"   ✗ Failed to connect: {e}")
        return
    
    # Step 3: Query the graph
    print("\n3. Querying the graph...")
    
    try:
        # Count vertices
        print("\n   a) Counting vertices:")
        vertex_count = client.count_vertices()
        print(f"      Total vertices: {vertex_count}")
        
        # Count by label
        for label in ["table"]:
            try:
                count = client.count_vertices(label)
                print(f"      {label}: {count}")
            except:
                pass
        
        # Count edges
        print("\n   b) Counting edges:")
        edge_count = client.count_edges()
        print(f"      Total edges: {edge_count}")
        
        for label in ["lineage"]:
            try:
                count = client.count_edges(label)
                print(f"      {label}: {count}")
            except:
                pass
        
        # Get some vertices
        print("\n   c) Sample vertices:")
        vertices = client.get_vertices(limit=5)
        for i, v in enumerate(vertices[:3], 1):
            print(f"      {i}. {v}")
        
        # Custom Gremlin query
        print("\n   d) Custom Gremlin query:")
        print("      Finding all tables...")
        results = client.query("g.V().hasLabel('table').valueMap()")
        for table in results[:3]:
            print(f"      - {table}")
        
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
    
    finally:
        client.disconnect()
    
    print("\n" + "="*80)
    print("Done!")
    print("="*80)


def example_advanced_queries():
    """More advanced query examples"""
    client = PuppyGraphClient(
        host=os.getenv("PUPPYGRAPH_HOST", "localhost"),
        gremlin_port=int(os.getenv("PUPPYGRAPH_PORT", "8182"))
    )
    
    with client:
        # Find person by name
        print("\n1. Find person by name:")
        results = client.find_vertex_by_property("name", "marko", "person")
        print(f"   Found: {results}")
        
        # Find neighbors
        if results:
            vertex_id = results[0].id
            print(f"\n2. Find neighbors of {vertex_id}:")
            neighbors = client.find_neighbors(vertex_id, direction="out")
            print(f"   Neighbors: {neighbors}")
        
        # Find paths
        print("\n3. Find paths between vertices:")
        paths = client.query("""
            g.V().hasLabel('person').limit(2).as('start', 'end')
             .select('start').both().both().where(eq('end'))
             .path()
        """)
        print(f"   Paths: {paths}")
        
        # Complex query: Who created what?
        print("\n4. Who created what?")
        results = client.query("""
            g.V().hasLabel('person')
             .as('person')
             .out('created')
             .as('software')
             .select('person', 'software')
             .by('name')
        """)
        for result in results:
            print(f"   {result}")


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Upload schema to PuppyGraph and query the graph"
    )
    parser.add_argument(
        "--schema",
        type=str,
        default="schema.json",
        help="Schema file name (default: schema.json)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force upload even if schema exists"
    )
    
    args = parser.parse_args()
    
    # Run main with parsed arguments
    main(schema_name=args.schema, force=args.force)
    
    # Uncomment to run advanced examples
    # print("\n" + "="*80)
    # print("Advanced Query Examples")
    # print("="*80)
    # example_advanced_queries()
