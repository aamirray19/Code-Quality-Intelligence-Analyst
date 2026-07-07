# backend/app/workflows/analysis/agents/reliability_agent.py
from app.workflows.analysis.agents.agent_factory import run_agent


async def reliability_agent(worker_input: dict) -> dict:
    return await run_agent("reliability", worker_input)
