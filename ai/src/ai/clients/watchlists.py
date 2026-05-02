"""Typed client for the ``watchlists_*`` GraphQL surface."""

from __future__ import annotations

from typing import Any

from ai.clients.transport import GraphqlClient

GET_WATCHLISTS_QUERY = """
query GetWatchlists($input: WatchlistFilterInput) {
  watchlists_watchlists(input: $input) {
    watchlists {
      id
      userID
      accountID
      name
      description
      visibility
      assets {
        symbol
        displayOrder
        group
      }
      spaceIDs
      alertIDs
      tagIDs
      displayOrder
      createdAt
      updatedAt
    }
    returnedCount
    totalPossibleCount
  }
}
"""

GET_WATCHLISTS_LITE_QUERY = """
query GetWatchlistsLite($input: WatchlistFilterInput) {
  watchlists_watchlists(input: $input) {
    watchlists {
      id
      name
      description
      visibility
      assets {
        symbol
      }
      spaceIDs
      displayOrder
      createdAt
      updatedAt
    }
    returnedCount
    totalPossibleCount
  }
}
"""

ADD_WATCHLIST_MUTATION = """
mutation AddWatchlist($name: String!, $description: String, $assets: [AddWatchlistAsset], $tags: [String]) {
  watchlists_addWatchlist(name: $name, description: $description, assets: $assets, tags: $tags) {
    id
    userID
    accountID
    name
    description
    visibility
    assets {
      symbol
      displayOrder
      group
    }
    spaceIDs
    alertIDs
    tagIDs
    displayOrder
    createdAt
    updatedAt
  }
}
"""

UPDATE_WATCHLIST_MUTATION = """
mutation UpdateWatchlist($id: String!, $name: String, $description: String, $visibility: VisibilityStatus, $displayOrder: Int) {
  watchlists_updateWatchlist(id: $id, name: $name, description: $description, visibility: $visibility, displayOrder: $displayOrder) {
    watchlist {
      id
      userID
      accountID
      name
      description
      visibility
      assets {
        symbol
        displayOrder
        group
      }
      spaceIDs
      alertIDs
      tagIDs
      displayOrder
      createdAt
      updatedAt
    }
  }
}
"""

DELETE_WATCHLIST_MUTATION = """
mutation DeleteWatchlist($id: String!) {
  watchlists_deleteWatchlist(id: $id)
}
"""

CLONE_WATCHLIST_MUTATION = """
mutation CloneWatchlist($id: String!) {
  watchlists_cloneWatchlist(id: $id) {
    id
    userID
    accountID
    name
    description
    visibility
    assets {
      symbol
      displayOrder
      group
    }
    spaceIDs
    alertIDs
    tagIDs
    displayOrder
    createdAt
    updatedAt
  }
}
"""

ADD_SPACE_TO_WATCHLIST_MUTATION = """
mutation AddSpaceToWatchlist($watchlistID: String!, $spaceID: String!) {
  watchlists_addSpaceToWatchlist(watchlistID: $watchlistID, spaceID: $spaceID) {
    watchlist {
      id
      userID
      accountID
      name
      description
      visibility
      assets {
        symbol
        displayOrder
        group
      }
      spaceIDs
      alertIDs
      tagIDs
      displayOrder
      createdAt
      updatedAt
    }
  }
}
"""

REMOVE_SPACE_FROM_WATCHLIST_MUTATION = """
mutation RemoveSpaceFromWatchlist($watchlistID: String!, $spaceID: String!) {
  watchlists_removeSpaceFromWatchlist(watchlistID: $watchlistID, spaceID: $spaceID) {
    watchlist {
      id
      userID
      accountID
      name
      description
      visibility
      assets {
        symbol
        displayOrder
        group
      }
      spaceIDs
      alertIDs
      tagIDs
      displayOrder
      createdAt
      updatedAt
    }
  }
}
"""


class WatchlistsClient:
    """Client for the ``watchlists_*`` GraphQL namespace."""

    def __init__(self, transport: GraphqlClient | None = None) -> None:
        """Initialize the client with an optional GraphQL transport override."""
        self.transport = transport or GraphqlClient()

    async def get_watchlists(
        self,
        *,
        bearer_token: str,
        name: str | None = None,
        limit: int | None = None,
        skip: int | None = None,
        sort_key: str | None = None,
        sort_ascending: bool | None = True,
    ) -> dict[str, Any]:
        """Return watchlists for the authenticated user."""
        variables = self._filter_variables(name, limit, skip, sort_key, sort_ascending)
        return await self.transport.execute(GET_WATCHLISTS_QUERY, variables=variables, bearer_token=bearer_token)

    async def get_watchlists_lite(
        self,
        *,
        bearer_token: str,
        name: str | None = None,
        limit: int | None = None,
        skip: int | None = None,
        sort_key: str | None = None,
        sort_ascending: bool | None = True,
    ) -> dict[str, Any]:
        """Return lite watchlists for the authenticated user."""
        variables = self._filter_variables(name, limit, skip, sort_key, sort_ascending)
        return await self.transport.execute(GET_WATCHLISTS_LITE_QUERY, variables=variables, bearer_token=bearer_token)

    async def add_watchlist(
        self,
        *,
        bearer_token: str,
        name: str,
        description: str | None = None,
        assets: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add a new watchlist for the authenticated user."""
        variables = {
            "name": name,
            "description": description,
            "assets": assets,
            "tags": tags,
        }
        return await self.transport.execute(ADD_WATCHLIST_MUTATION, variables=variables, bearer_token=bearer_token)

    async def update_watchlist(
        self,
        *,
        bearer_token: str,
        watchlist_id: str,
        name: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        display_order: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing watchlist for the authenticated user."""
        variables = {
            "id": watchlist_id,
            "name": name,
            "description": description,
            "visibility": visibility,
            "displayOrder": display_order,
        }
        return await self.transport.execute(UPDATE_WATCHLIST_MUTATION, variables=variables, bearer_token=bearer_token)

    async def delete_watchlist(self, *, bearer_token: str, watchlist_id: str) -> bool:
        """Delete a watchlist for the authenticated user."""
        data = await self.transport.execute(DELETE_WATCHLIST_MUTATION, variables={"id": watchlist_id}, bearer_token=bearer_token)
        return bool(data.get("watchlists_deleteWatchlist", False))

    async def clone_watchlist(self, *, bearer_token: str, watchlist_id: str) -> dict[str, Any]:
        """Clone a watchlist for the authenticated user."""
        return await self.transport.execute(CLONE_WATCHLIST_MUTATION, variables={"id": watchlist_id}, bearer_token=bearer_token)

    async def add_space_to_watchlist(self, *, bearer_token: str, watchlist_id: str, space_id: str) -> dict[str, Any]:
        """Add a space to a watchlist."""
        variables = {
            "watchlistID": watchlist_id,
            "spaceID": space_id,
        }
        return await self.transport.execute(ADD_SPACE_TO_WATCHLIST_MUTATION, variables=variables, bearer_token=bearer_token)

    async def remove_space_from_watchlist(self, *, bearer_token: str, watchlist_id: str, space_id: str) -> dict[str, Any]:
        """Remove a space from a watchlist."""
        variables = {
            "watchlistID": watchlist_id,
            "spaceID": space_id,
        }
        return await self.transport.execute(REMOVE_SPACE_FROM_WATCHLIST_MUTATION, variables=variables, bearer_token=bearer_token)

    @staticmethod
    def _filter_variables(
        name: str | None,
        limit: int | None,
        skip: int | None,
        sort_key: str | None,
        sort_ascending: bool | None,
    ) -> dict[str, Any]:
        """Build watchlist filter variables."""
        input_dict: dict[str, Any] = {}
        if name:
            input_dict["name"] = name

        filter_dict: dict[str, Any] = {}
        if limit is not None:
            filter_dict["limit"] = limit
        if skip is not None:
            filter_dict["skip"] = skip
        if sort_key:
            filter_dict["sort"] = {
                "key": sort_key,
                "ascending": sort_ascending if sort_ascending is not None else True,
            }
        if filter_dict:
            input_dict["filter"] = filter_dict

        return {"input": input_dict if input_dict else None}
