"""
Simplified PuppyGraph Client

Upload schema.json to PuppyGraph and query using Gremlin.
"""

from typing import Dict, List, Optional, Any
import logging
import json
import requests

try:
    from gremlin_python.driver import client, serializer
    GREMLIN_AVAILABLE = True
except ImportError:
    GREMLIN_AVAILABLE = False

logger = logging.getLogger(__name__)


class PuppyGraphClient:
    """
    Simple PuppyGraph client for schema upload and Gremlin queries.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        gremlin_port: int = 8182,
        http_port: int = 8081,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize PuppyGraph client.
        
        Args:
            host: PuppyGraph host
            gremlin_port: Gremlin server port (default: 8182)
            http_port: HTTP API port (default: 8081)
            username: Optional username
            password: Optional password
        """
        self.host = host
        self.gremlin_port = gremlin_port
        self.http_port = http_port
        self.username = username
        self.password = password
        
        self._gremlin_client = None
        self._connected = False
        
        logger.info(f"Initialized PuppyGraph client: {host}")
    
    @property
    def gremlin_url(self) -> str:
        """Gremlin WebSocket URL"""
        return f"ws://{self.host}:{self.gremlin_port}/gremlin"
    
    @property
    def http_url(self) -> str:
        """HTTP API base URL"""
        return f"http://{self.host}:{self.http_port}"
    
    def check_schema_exists(self) -> bool:
        """
        Check if schema is already uploaded to PuppyGraph via HTTP API.
        
        Returns:
            True if schema exists, False otherwise
        """
        try:
            # Try to GET the schema from PuppyGraph
            url = f"{self.http_url}/schema"
            
            # Prepare auth if needed
            auth = None
            if self.username and self.password:
                auth = (self.username, self.password)
            
            response = requests.get(
                url,
                auth=auth,
                timeout=10
            )
            
            # If we get a 200 response, schema exists
            if response.status_code == 200:
                logger.info("✓ Schema already exists")
                return True
            else:
                logger.debug(f"Schema check returned {response.status_code}")
                return False
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Schema check failed (expected if not uploaded): {e}")
            return False
    
    def upload_schema(self, schema_path: str, force: bool = False) -> Dict[str, Any]:
        """
        Upload schema.json to PuppyGraph via HTTP API.
        
        Args:
            schema_path: Path to schema.json file
            force: If True, upload even if schema already exists
            
        Returns:
            Response from PuppyGraph API
        """
        # Check if schema already exists
        if not force and self.check_schema_exists():
            logger.info("⊙ Schema already uploaded, skipping upload")
            return {"status": "skipped", "message": "Schema already exists"}
        
        logger.info(f"Uploading schema from: {schema_path}")
        
        # Load schema file
        with open(schema_path, 'r') as f:
            schema_content = f.read()
        
        # Resolve environment variables in schema
        schema_content = self._resolve_env_vars(schema_content)
        
        # Upload via API (matching PuppyGraph curl format)
        url = f"{self.http_url}/schema"
        
        # Prepare auth (HTTP Basic Auth)
        auth = None
        if self.username and self.password:
            auth = (self.username, self.password)
        
        try:
            response = requests.post(
                url,
                data=schema_content,  # Send as raw JSON string (like --data-binary)
                headers={"Content-Type": "application/json"},
                auth=auth,  # HTTP Basic Auth (like --user)
                timeout=30
            )
            response.raise_for_status()
            
            logger.info("✓ Schema uploaded successfully")
            return response.json() if response.content else {"status": "success"}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to upload schema: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def _resolve_env_vars(self, content: str) -> str:
        """Replace ${ENV_VAR} with actual environment variable values"""
        import os
        import re
        
        def replace_var(match):
            var_name = match.group(1)
            value = os.getenv(var_name)
            if value is None:
                logger.warning(f"Environment variable {var_name} not set")
                return match.group(0)
            return value
        
        return re.sub(r'\$\{([^}]+)\}', replace_var, content)
    
    def connect(self) -> None:
        """Connect to PuppyGraph Gremlin server"""
        if not GREMLIN_AVAILABLE:
            raise ImportError("gremlinpython required. Install: pip install gremlinpython")
        
        try:
            self._gremlin_client = client.Client(
                self.gremlin_url,
                'g',
                username=self.username,
                password=self.password,
                message_serializer=serializer.GraphSONSerializersV3d0()
            )
            
            # Test connection
            self._gremlin_client.submit("g.V().limit(1)").all().result()
            self._connected = True
            
            logger.info("✓ Connected to PuppyGraph Gremlin server")
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise
    
    def query(self, gremlin_query: str, bindings: Optional[Dict[str, Any]] = None) -> List[Any]:
        """
        Execute a Gremlin query.
        
        Args:
            gremlin_query: Gremlin query string
            bindings: Optional parameter bindings
            
        Returns:
            Query results as list
        """
        if not self._connected:
            self.connect()
        
        try:
            result_set = self._gremlin_client.submit(gremlin_query, bindings or {})
            results = result_set.all().result()
            
            logger.debug(f"Query returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            logger.debug(f"Query: {gremlin_query}")
            raise
    
    def get_vertices(self, limit: int = 100, label: Optional[str] = None) -> List[Any]:
        """Get vertices from graph"""
        if label:
            query = f"g.V().hasLabel('{label}').limit({limit})"
        else:
            query = f"g.V().limit({limit})"
        return self.query(query)
    
    def get_edges(self, limit: int = 100, label: Optional[str] = None) -> List[Any]:
        """Get edges from graph"""
        if label:
            query = f"g.E().hasLabel('{label}').limit({limit})"
        else:
            query = f"g.E().limit({limit})"
        return self.query(query)
    
    def count_vertices(self, label: Optional[str] = None) -> int:
        """Count vertices in graph"""
        if label:
            query = f"g.V().hasLabel('{label}').count()"
        else:
            query = "g.V().count()"
        return self.query(query)[0]
    
    def count_edges(self, label: Optional[str] = None) -> int:
        """Count edges in graph"""
        if label:
            query = f"g.E().hasLabel('{label}').count()"
        else:
            query = "g.E().count()"
        return self.query(query)[0]
    
    def find_vertex_by_property(
        self,
        property_key: str,
        property_value: Any,
        label: Optional[str] = None
    ) -> List[Any]:
        """Find vertices by property value"""
        if label:
            query = f"g.V().hasLabel('{label}').has('{property_key}', '{property_value}')"
        else:
            query = f"g.V().has('{property_key}', '{property_value}')"
        return self.query(query)
    
    def find_neighbors(
        self,
        vertex_id: Any,
        direction: str = "both",
        edge_label: Optional[str] = None
    ) -> List[Any]:
        """Find neighboring vertices"""
        traversal = {
            "in": "in_" if not edge_label else f"in_('{edge_label}')",
            "out": "out" if not edge_label else f"out('{edge_label}')",
            "both": "both" if not edge_label else f"both('{edge_label}')"
        }
        
        query = f"g.V('{vertex_id}').{traversal[direction]}()"
        return self.query(query)
    
    def find_paths(
        self,
        from_id: Any,
        to_id: Any,
        max_depth: int = 3
    ) -> List[Any]:
        """Find paths between two vertices"""
        query = f"""
        g.V('{from_id}')
         .repeat(__.both().simplePath())
         .until(__.hasId('{to_id}').or().loops().is(gte({max_depth})))
         .hasId('{to_id}')
         .path()
        """
        return self.query(query)
    
    def disconnect(self) -> None:
        """Close connection to PuppyGraph"""
        if self._gremlin_client:
            try:
                self._gremlin_client.close()
                self._connected = False
                logger.info("Disconnected from PuppyGraph")
            except Exception as e:
                logger.warning(f"Error disconnecting: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
