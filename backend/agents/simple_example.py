"""
Simple Example: Upload Schema and Query PuppyGraph

This is a simplified version that just:
1. Uploads schema.json to PuppyGraph
2. Queries the graph using Gremlin
"""

import os
import logging
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


def main():
    """Main example"""
    print("="*80)
    print("PuppyGraph Simple Example")
    print("="*80)
    
    # Initialize client
    client = PuppyGraphClient(
        host=os.getenv("PUPPYGRAPH_HOST", "localhost"),
        gremlin_port=int(os.getenv("PUPPYGRAPH_PORT", "8182")),
        http_port=int(os.getenv("PUPPYGRAPH_HTTP_PORT", "8081")),
        username=os.getenv("PUPPYGRAPH_USERNAME"),
        password=os.getenv("PUPPYGRAPH_PASSWORD")
    )
    
    # Step 1: Upload schema (skip if already exists)
    print("\n1. Uploading schema to PuppyGraph...")
    schema_path = Path(__file__).parent / "schema.json"
    
    try:
        response = client.upload_schema(str(schema_path))
        if response.get("status") == "skipped":
            print(f"   ⊙ Schema already exists, skipped upload")
        else:
            print(f"   ✓ Schema uploaded: {response}")
    except Exception as e:
        print(f"   ✗ Failed to upload schema: {e}")
        print("   Note: Make sure PuppyGraph HTTP API is running")
        print("   Tip: Use force=True to override existing schema")
        # Continue anyway - schema might already be loaded
    
    # Option: Force re-upload if needed
    # response = client.upload_schema(str(schema_path), force=True)
    
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
        for label in ["person", "software"]:
            try:
                count = client.count_vertices(label)
                print(f"      {label}: {count}")
            except:
                pass
        
        # Count edges
        print("\n   b) Counting edges:")
        edge_count = client.count_edges()
        print(f"      Total edges: {edge_count}")
        
        for label in ["knowns", "created"]:
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
        print("      Finding all persons...")
        results = client.query("g.V().hasLabel('person').valueMap()")
        for person in results[:3]:
            print(f"      - {person}")
        
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
    main()
    
    # Uncomment to run advanced examples
    # print("\n" + "="*80)
    # print("Advanced Query Examples")
    # print("="*80)
    # example_advanced_queries()
