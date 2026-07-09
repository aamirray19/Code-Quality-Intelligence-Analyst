# backend/app/workflows/analysis/agents/performance_agent.py
from app.workflows.analysis.agents.agent_factory import run_agent


async def performance_agent(worker_input: dict) -> dict:
    return await run_agent("performance", worker_input)
