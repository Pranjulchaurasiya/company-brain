import falkordb

def main():
    print("Connecting to FalkorDB on 127.0.0.1:6379...")
    db = falkordb.FalkorDB(host="127.0.0.1", port=6379)
    g = db.select_graph("company_brain_test")
    res = g.query("CREATE (n:TestNode {name: 'FalkorAlive', status: 'OK'}) RETURN n.name, n.status")
    print("FalkorDB Query Success! Result:", res.result_set)
    
    # Query it back
    res2 = g.query("MATCH (n:TestNode) RETURN n.name, n.status")
    print("Read query back:", res2.result_set)
    
    # Cleanup test node
    g.query("MATCH (n:TestNode) DELETE n")
    print("Test cleanup completed successfully!")

if __name__ == "__main__":
    main()
