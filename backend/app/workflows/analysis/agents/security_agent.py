# backend/app/workflows/analysis/agents/security_agent.py
from app.workflows.analysis.agents.agent_factory import run_agent


async def security_agent(worker_input: dict) -> dict:
    return await run_agent("security", worker_input)
