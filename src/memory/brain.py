# ==============================================================================
# File Location: dart-agent/src/memory/brain.py
# File Name: brain.py
# Description:
# - ChromaDB-backed long-term memory storing post-mortems for recall.
# - Provides store and recall utilities for incident context.
# Inputs:
# - IncidentContext objects (for storage) and query strings for recall.
# Outputs:
# - Persisted embeddings/metadata; lists of similar incidents on recall.
# ==============================================================================

import chromadb
from src.utils.types import IncidentContext
from src.utils.config import config # <--- New Import

class AgentMemory:
    def __init__(self):
        # Initialize persistent ChromaDB client using Config
        self.client = chromadb.PersistentClient(path=config.memory_db_path)
        
        # Get or create the collection for post-mortems
        # We use the default embedding function (all-MiniLM-L6-v2) built into Chroma
        self.collection = self.client.get_or_create_collection(
            name="incident_post_mortems",
            metadata={"hnsw:space": "cosine"}
        )
        print(f"🧠 Memory System Online. Collection: {self.collection.name} loaded.")

    def store_incident(self, context: IncidentContext):
        """
        Saves a resolved incident into vector memory.
        We embed the 'root_cause_hypothesis' and 'message' so agents can find it later.
        """
        if not context.root_cause_hypothesis:
            print("⚠️ Cannot memorize incident: No root cause found.")
            return

        # Create a rich text description for embedding
        document_text = (
            f"Error Code: {context.initial_alert.error_code}. "
            f"Message: {context.initial_alert.message}. "
            f"Root Cause: {context.root_cause_hypothesis}. "
            f"Fix: {context.proposed_remediation_plan}"
        )

        # Store metadata for precise retrieval
        metadata = {
            "incident_id": context.incident_id,
            "incident_type": context.initial_alert.error_code,
            "severity": context.initial_alert.severity.value,
            "source": context.initial_alert.source_system,
            "timestamp": str(context.initial_alert.timestamp),
            "remediation_type": "SQL" if "ALTER" in str(context.proposed_remediation_plan) else "MANUAL"
        }

        self.collection.add(
            documents=[document_text],
            metadatas=[metadata],
            ids=[context.incident_id]
        )
        print(f"💾 Incident {context.incident_id} memorized.")

    def recall_similar_incidents(self, query: str, n_results: int = 2):
        """
        Searches memory for similar past failures.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results

# Global Singleton
brain = AgentMemory()
