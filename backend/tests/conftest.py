import os
import pytest
from backend.db.falkordb_client import db_client

TEST_GRAPH_NAME = "company_brain_test"

@pytest.fixture(scope="session", autouse=True)
def isolated_test_graph():
    """Ensure all tests run strictly against an isolated temporary test graph, protecting company_brain."""
    original_graph_name = db_client.graph_name
    db_client.graph_name = TEST_GRAPH_NAME
    db_client._graph = None
    
    # Initialize schema on the isolated test graph
    db_client.connect()
    db_client.init_schema()
    
    yield
    
    # Clean up test graph after session
    try:
        db_client.reset_graph()
    except Exception:
        pass
    db_client.graph_name = original_graph_name
    db_client._graph = None
