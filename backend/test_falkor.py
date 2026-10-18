import falkordb
from backend.config import FALKORDB_HOST, FALKORDB_PORT, FALKORDB_GRAPH_NAME

def main():
    print(f"Connecting to FalkorDB on {FALKORDB_HOST}:{FALKORDB_PORT} ({FALKORDB_GRAPH_NAME})...")
    db = falkordb.FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)
    g = db.select_graph(FALKORDB_GRAPH_NAME)
    res = g.query("CREATE (n:TestNode {name: 'FalkorAlive', status: 'OK'}) RETURN n.name, n.status")
    print("FalkorDB Query Success! Result:", res.result_set)
    
    # Query it back
    res2 = g.query("MATCH (n:TestNode {name: 'FalkorAlive'}) RETURN n.name, n.status")
    print("Read query back:", res2.result_set)
    
    # Cleanup test node
    g.query("MATCH (n:TestNode {name: 'FalkorAlive'}) DELETE n")
    print("Test cleanup completed successfully!")

if __name__ == "__main__":
    main()
