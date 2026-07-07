# backend/app/workflows/analysis/agents/complexity_agent.py
from app.workflows.analysis.agents.agent_factory import run_agent


async def complexity_agent(worker_input: dict) -> dict:
    return await run_agent("complexity", worker_input)
