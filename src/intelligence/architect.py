# file: src/intelligence/architect.py
from typing import List, Dict, Any
import json
import asyncio
from ..schemas.scenario import Scenario, ScenarioEvent

class Architect:
    """Uses a local/remote LLM to generate system orchestrations."""

    def __init__(self, provider: str = "ollama", model_name: str = "mistral"):
        self.provider = provider
        self.model_name = model_name

    async def generate_scenario(self, prompt: str, system_context: str) -> Scenario:
        """
        Ask the LLM to generate a JSON scenario based on the prompt and current system state.
        For this MVP, we simulate the LLM response.
        """
        # In a real impl, we'd use LiteLLM or LangChain to call the model
        # response = await litellm.acompletion(model=self.model_name, messages=[...])

        # Simulated logic: if prompt contains 'sync', sync ferros and neurometal
        if "sync" in prompt.lower() or "coordinate" in prompt.lower():
            events = [
                ScenarioEvent(timestamp=1.0, system="ferros", action="start"),
                ScenarioEvent(timestamp=3.0, system="neurometal", action="start"),
                ScenarioEvent(timestamp=5.0, system="ferros", action="tune", payload={"intensity": 0.8}),
                ScenarioEvent(timestamp=6.0, system="neurometal", action="tune", payload={"gain": 0.7})
            ]
            return Scenario(name="AI Generated Coordination", timeline=events)

        # Default fallback
        return Scenario(name="AI Default Scenario", timeline=[
            ScenarioEvent(timestamp=2.0, system="hello", action="start")
        ])

    async def retrieve_memory(self, query: str) -> List[str]:
        """Query ChromaDB for relevant past system logs."""
        try:
            import chromadb
            client = chromadb.PersistentClient(path="memory/chroma")
            collection = client.get_collection("system_logs")
            results = collection.query(query_texts=[query], n_results=5)
            return results["documents"][0] if results["documents"] else []
        except:
            return []
