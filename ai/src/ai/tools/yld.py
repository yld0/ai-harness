"""YLD / gateway GraphQL tool wrapper (read-only by default; extend for mutations in later phases)."""

from __future__ import annotations

from typing import Any, ClassVar

from ai.tools._base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext
from ai.tools.graphql import GraphqlClient


class YldGraphqlQuery(Tool):
    name: ClassVar[str] = "yld_graphql"
    description: ClassVar[str] = (
        "Run a read GraphQL document against the YLD supergraph. " "Use for queries only in this phase; mutations go through specific tools such as user_cli."
    )
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "GraphQL query or short operation",
                },
                "variables": {
                    "type": "object",
                    "description": "Optional variables map",
                },
            },
            "required": ["query"],
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query", ""))
        if not query.strip():
            return err_result("invalid_argument", "query is required")
        first = next((line.strip() for line in query.splitlines() if line.strip()), "")
        for banned in ("mutation", "subscription"):
            if first.lower().startswith(banned + " "):
                return err_result(
                    "governance",
                    "Only queries are allowed via yld_graphql; use the user_cli tool for watchlist/alert writes.",
                )
        variables = args.get("variables")
        if variables is not None and not isinstance(variables, dict):
            return err_result("invalid_argument", "variables must be an object")
        client = GraphqlClient()
        if not ctx.bearer_token:
            return err_result("auth", "No bearer token; cannot call GraphQL")
        data = await client.execute(
            query,
            variables=variables if isinstance(variables, dict) else None,
            bearer_token=ctx.bearer_token,
        )
        return ok_result(data)
