import logging
import falkordb
from typing import Dict, Any, List, Optional
from backend.config import FALKORDB_HOST, FALKORDB_PORT, FALKORDB_GRAPH_NAME

logger = logging.getLogger("company_brain.db")

class FalkorDBClient:
    def __init__(self, host: str = FALKORDB_HOST, port: int = FALKORDB_PORT, graph_name: str = FALKORDB_GRAPH_NAME):
        self.host = host
        self.port = port
        self.graph_name = graph_name
        self._db: Optional[falkordb.FalkorDB] = None
        self._graph: Optional[falkordb.Graph] = None

    def connect(self) -> falkordb.Graph:
        if self._graph is None:
            import time
            last_err = None
            for attempt in range(5):
                try:
                    logger.info(f"Connecting to FalkorDB at {self.host}:{self.port}, graph: {self.graph_name} (attempt {attempt+1})")
                    self._db = falkordb.FalkorDB(host=self.host, port=self.port)
                    self._graph = self._db.select_graph(self.graph_name)
                    # Verify responsive
                    self._graph.query("RETURN 1")
                    return self._graph
                except Exception as e:
                    last_err = e
                    self._graph = None
                    self._db = None
                    time.sleep(1.0)
            if last_err:
                raise last_err
        return self._graph

    def get_graph(self) -> falkordb.Graph:
        if self._graph is None:
            return self.connect()
        return self._graph

    def check_health(self) -> Dict[str, Any]:
        try:
            g = self.get_graph()
            res = g.query("RETURN 1 as ping")
            return {
                "status": "HEALTHY",
                "connected": True,
                "host": self.host,
                "port": self.port,
                "graph_name": self.graph_name,
                "ping": res.result_set[0][0] if res.result_set else 1
            }
        except Exception as e:
            logger.error(f"FalkorDB health check failed: {e}")
            return {
                "status": "UNHEALTHY",
                "connected": False,
                "host": self.host,
                "port": self.port,
                "graph_name": self.graph_name,
                "error": str(e)
            }

    def init_schema(self) -> None:
        """Create indices on core labels to optimize lookup and enforce query performance."""
        g = self.get_graph()
        labels = [
            "Employee", "Team", "Skill", "Goal", "Project", "Service", "Task",
            "Document", "Ticket", "ChatMessage", "Decision", "Fact", "Source",
            "Evidence", "AgentMessage", "Session", "Memory", "Deliverable"
        ]
        for label in labels:
            try:
                g.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
            except Exception as e:
                logger.debug(f"Index creation note for {label}.id: {e}")
            try:
                g.query(f"CREATE INDEX FOR (n:{label}) ON (n.workspace_id)")
            except Exception as e:
                logger.debug(f"Index creation note for {label}.workspace_id: {e}")

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[List[Any]]:
        g = self.get_graph()
        try:
            if params:
                res = g.query(cypher, params=params)
            else:
                res = g.query(cypher)
            return res.result_set or []
        except Exception as e:
            logger.error(f"Cypher query error: {e} | Query: {cypher} | Params: {params}")
            raise

    def reset_graph(self) -> None:
        """Delete all nodes and edges in the graph for zero-setup 1-click demo reset."""
        g = self.get_graph()
        try:
            g.query("MATCH (n) DETACH DELETE n")
            logger.info(f"Graph '{self.graph_name}' has been successfully reset.")
        except Exception as e:
            logger.error(f"Failed to reset graph: {e}")
            raise

# Global singleton client
db_client = FalkorDBClient()
