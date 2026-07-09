# backend/app/workflows/analysis/agents/duplication_agent.py
from app.workflows.analysis.agents.agent_factory import run_agent


async def duplication_agent(worker_input: dict) -> dict:
    return await run_agent("duplication", worker_input)
