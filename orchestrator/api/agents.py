"""
Agent interview proxy endpoint for MiroFish agent chat.

Proxies chat messages from the UI through the orchestrator to the MiroFish
agent interview API. Per UI-08: agent interview capability.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from orchestrator.api.schemas import AgentChatRequest, AgentChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents"])


@router.post(
    "/campaigns/{campaign_id}/agents/{agent_id}/chat",
    response_model=AgentChatResponse,
)
async def chat_agent(
    request: Request,
    campaign_id: str,
    agent_id: str,
    body: AgentChatRequest,
) -> AgentChatResponse:
    """
    Proxy chat message to a MiroFish simulated agent.

    Per UI-08: The frontend sends user messages here, the orchestrator
    forwards them to MiroFish POST /api/agent/{agent_id}/chat, and
    returns the agent's response.
    """
    mirofish = request.app.state.mirofish_client
    result = await mirofish.chat_agent(agent_id, body.message)

    if result is None:
        raise HTTPException(
            status_code=502,
            detail="MiroFish agent chat unavailable",
        )

    return AgentChatResponse(
        agent_id=agent_id,
        response=result.get("response", "No response received"),
    )
