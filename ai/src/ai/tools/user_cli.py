"""Watchlist and alert GraphQL operations (mutates → WorkspaceWrite)."""

from __future__ import annotations

from typing import Any, ClassVar

from ai.tools._base import Tool, ToolResult, err_result, ok_result
from ai.tools.context import ToolContext
from ai.tools.graphql import GraphqlClient
from ai.tools.permissions import PermissionMode

_MUTATION_DISPATCH: dict[str, str] = {
    "alerts_add_alert": "mutation M($i:AddAlertInput!){ alerts_addAlert(input:$i){ __typename } }",
    "alerts_update_alert": "mutation M($u:UpdateAlertInput!){ alerts_updateAlert(update:$u){ __typename } }",
    "alerts_delete_alert": "mutation M($id:String!){ alerts_deleteAlert(id:$id) }",
    "alerts_add_default_alerts": "mutation { alerts_addDefaultAlerts }",
    "alerts_sync_watchlist_alerts": "mutation { alerts_syncWatchlistAlerts }",
    "watchlists_add_watchlist": "mutation M($n:String!,$d:String,$a:[AddWatchlistAsset],$t:[String]){ watchlists_addWatchlist(name:$n,description:$d,assets:$a,tags:$t){ id name } }",
    "watchlists_update_watchlist": "mutation M($id:String!,$n:String){ watchlists_updateWatchlist(id:$id,name:$n){ id } }",
    "watchlists_delete_watchlist": "mutation M($id:String!){ watchlists_deleteWatchlist(id:$id) }",
    "watchlists_add_asset_to_watchlist": "mutation M($w:String!,$s:String!){ watchlists_addAssetToWatchlist(watchlistID:$w,symbol:$s){ __typename } }",
    "watchlists_remove_asset_from_watchlist": "mutation M($w:String!,$s:String!){ watchlists_removeAssetFromWatchlist(watchlistID:$w,symbol:$s){ __typename } }",
}

_QUERY_GQL: dict[str, str] = {
    "alerts_list": "query Q($i:AlertsFilterInput){ alerts_alerts(input:$i){ alerts { id title } } }",
    "watchlists_list": "query Q($i:WatchlistFilterInput){ watchlists_watchlists(input:$i){ watchlists { id name } } }",
}


class UserCliTool(Tool):
    name: ClassVar[str] = "user_cli"
    description: ClassVar[str] = "Call gateway GraphQL for alerts and watchlists. " "Use operation names: alerts_*, watchlists_* as listed in the schema."
    required_permission: ClassVar[PermissionMode] = PermissionMode.WorkspaceWrite
    file_component_risk: ClassVar[bool] = False

    @property
    def parameters_json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "E.g. watchlists_list, alerts_list, watchlists_add_watchlist",
                },
                "variables": {"type": "object"},
            },
            "required": ["operation"],
        }

    async def _execute(self, ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        op = str(args.get("operation", ""))
        if not op:
            return err_result("invalid_argument", "operation is required")
        variables = args.get("variables")
        if variables is not None and not isinstance(variables, dict):
            return err_result("invalid_argument", "variables must be an object when provided")
        if not ctx.bearer_token:
            return err_result("auth", "No bearer token; cannot call user_cli")
        if op in _QUERY_GQL:
            doc = _QUERY_GQL[op]
        elif op in _MUTATION_DISPATCH:
            doc = _MUTATION_DISPATCH[op]
        else:
            return err_result("unknown_operation", f"Unknown operation {op!r}")
        client = GraphqlClient()
        data = await client.execute(
            doc,
            variables=variables,
            bearer_token=ctx.bearer_token,
        )
        return ok_result(data)
