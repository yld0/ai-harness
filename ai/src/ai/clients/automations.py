"""Typed client for the ``automations_*`` GraphQL surface."""

from __future__ import annotations

from typing import Any

from ai.clients.transport import GraphqlClient

LIST_AUTOMATIONS_QUERY = """
query ListAutomations($limit: Int, $skip: Int, $status: AutomationStatus) {
  automations_automations(limit: $limit, skip: $skip, status: $status) {
    automations {
      id
      userID
      name
      description
      status
      schedule {
        type
        expression
        intervalMinutes
        runAt
      }
      timezone
      route
      target {
        type
        ref
      }
      input
      lastRunAt
      nextRunAt
      lastError
      createdAt
      updatedAt
    }
    returnedCount
    totalPossibleCount
  }
}
"""

GET_AUTOMATION_QUERY = """
query GetAutomation($id: String!) {
  automations_automation(id: $id) {
    id
    userID
    name
    description
    status
    schedule {
      type
      expression
      intervalMinutes
      runAt
    }
    timezone
    route
    target {
      type
      ref
    }
    input
    lastRunAt
    nextRunAt
    lastError
    createdAt
    updatedAt
  }
}
"""

CREATE_AUTOMATION_MUTATION = """
mutation CreateAutomation($input: AutomationsCreateAutomationInput!) {
  automations_createAutomation(input: $input) {
    id
    name
    status
    route
    nextRunAt
  }
}
"""

UPDATE_AUTOMATION_MUTATION = """
mutation UpdateAutomation($id: String!, $input: AutomationsUpdateAutomationInput!) {
  automations_updateAutomation(id: $id, input: $input) {
    id
    name
    status
  }
}
"""

PAUSE_AUTOMATION_MUTATION = """
mutation PauseAutomation($id: String!) {
  automations_pauseAutomation(id: $id) {
    id
    status
  }
}
"""

RESUME_AUTOMATION_MUTATION = """
mutation ResumeAutomation($id: String!) {
  automations_resumeAutomation(id: $id) {
    id
    status
  }
}
"""

DELETE_AUTOMATION_MUTATION = """
mutation DeleteAutomation($id: String!) {
  automations_deleteAutomation(id: $id)
}
"""

RUN_NOW_MUTATION = """
mutation RunNow($id: String!) {
  automations_runNow(id: $id) {
    id
    automationID
    status
    triggeredBy
    startedAt
  }
}
"""


class AutomationsClient:
    """Client for the ``automations_*`` GraphQL namespace."""

    def __init__(self, transport: GraphqlClient | None = None) -> None:
        """Initialize the client with an optional GraphQL transport override."""
        self.transport = transport or GraphqlClient()

    async def list_automations(
        self,
        *,
        bearer_token: str,
        limit: int = 50,
        skip: int = 0,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Return automations for the authenticated user."""
        variables: dict[str, Any] = {"limit": limit, "skip": skip}
        if status is not None:
            variables["status"] = status
        return await self.transport.execute(
            LIST_AUTOMATIONS_QUERY, variables=variables, bearer_token=bearer_token,
        )

    async def get_automation(self, *, bearer_token: str, automation_id: str) -> dict[str, Any]:
        """Return a single automation by ID."""
        return await self.transport.execute(
            GET_AUTOMATION_QUERY, variables={"id": automation_id}, bearer_token=bearer_token,
        )

    async def create_automation(
        self,
        *,
        bearer_token: str,
        name: str,
        route: str,
        schedule: dict[str, Any],
        description: str | None = None,
        timezone: str = "UTC",
        target: dict[str, Any] | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new automation schedule."""
        automation_input: dict[str, Any] = {
            "name": name,
            "route": route,
            "schedule": schedule,
            "timezone": timezone,
        }
        if description is not None:
            automation_input["description"] = description
        if target is not None:
            automation_input["target"] = target
        if input_data is not None:
            automation_input["input"] = input_data
        return await self.transport.execute(
            CREATE_AUTOMATION_MUTATION, variables={"input": automation_input}, bearer_token=bearer_token,
        )

    async def update_automation(
        self,
        *,
        bearer_token: str,
        automation_id: str,
        name: str | None = None,
        description: str | None = None,
        schedule: dict[str, Any] | None = None,
        timezone: str | None = None,
        route: str | None = None,
        target: dict[str, Any] | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update an existing automation."""
        update_input: dict[str, Any] = {}
        if name is not None:
            update_input["name"] = name
        if description is not None:
            update_input["description"] = description
        if schedule is not None:
            update_input["schedule"] = schedule
        if timezone is not None:
            update_input["timezone"] = timezone
        if route is not None:
            update_input["route"] = route
        if target is not None:
            update_input["target"] = target
        if input_data is not None:
            update_input["input"] = input_data
        return await self.transport.execute(
            UPDATE_AUTOMATION_MUTATION,
            variables={"id": automation_id, "input": update_input},
            bearer_token=bearer_token,
        )

    async def pause_automation(self, *, bearer_token: str, automation_id: str) -> dict[str, Any]:
        """Pause an active automation."""
        return await self.transport.execute(
            PAUSE_AUTOMATION_MUTATION, variables={"id": automation_id}, bearer_token=bearer_token,
        )

    async def resume_automation(self, *, bearer_token: str, automation_id: str) -> dict[str, Any]:
        """Resume a paused automation."""
        return await self.transport.execute(
            RESUME_AUTOMATION_MUTATION, variables={"id": automation_id}, bearer_token=bearer_token,
        )

    async def delete_automation(self, *, bearer_token: str, automation_id: str) -> bool:
        """Delete an automation."""
        data = await self.transport.execute(
            DELETE_AUTOMATION_MUTATION, variables={"id": automation_id}, bearer_token=bearer_token,
        )
        return bool(data.get("automations_deleteAutomation", False))

    async def run_now(self, *, bearer_token: str, automation_id: str) -> dict[str, Any]:
        """Trigger an immediate run of an automation."""
        return await self.transport.execute(
            RUN_NOW_MUTATION, variables={"id": automation_id}, bearer_token=bearer_token,
        )


async def find_automation_by_route(
    bearer_token: str,
    route: str,
    *,
    client: GraphqlClient | None = None,
) -> dict[str, Any] | None:
    """Find the first automation matching a given route name, or None."""
    data = await AutomationsClient(transport=client).list_automations(
        bearer_token=bearer_token, status="ACTIVE",
    )
    for auto in (data.get("automations_automations") or {}).get("automations") or []:
        if isinstance(auto, dict) and auto.get("route") == route:
            return auto

    data = await AutomationsClient(transport=client).list_automations(
        bearer_token=bearer_token, status="PAUSED",
    )
    for auto in (data.get("automations_automations") or {}).get("automations") or []:
        if isinstance(auto, dict) and auto.get("route") == route:
            return auto

    return None
