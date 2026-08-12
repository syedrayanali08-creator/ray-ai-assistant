"""The memory endpoints: user control, auth, and validation (docs/05, docs/12)."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ray.domain.enums import MemoryCategory, MemorySource
from ray.memory.embeddings import HashingEmbedder
from ray.services import memory_service

GAME = "The user is building a Processing game called Starfall Sprint"


async def _seed(session: AsyncSession, user_id: uuid.UUID, content: str = GAME) -> uuid.UUID:
    memory = await memory_service.create(
        session,
        user_id,
        content=content,
        category=MemoryCategory.PROJECT,
        importance=4,
        why="Stated in conversation.",
        embedding=(await HashingEmbedder().embed([content]))[0],
    )
    await session.commit()
    return memory.id


async def test_memory_endpoints_require_a_token(client: AsyncClient) -> None:
    for method, url in (
        ("GET", "/memory"),
        ("GET", "/memory/search?q=x"),
        ("GET", "/memory/stats"),
        ("POST", "/memory"),
    ):
        response = await client.request(method, url, json={"content": "x"})
        assert response.status_code == 401


async def test_create_read_edit_delete_round_trip(
    auth_client: AsyncClient, user_id: uuid.UUID
) -> None:
    created = await auth_client.post(
        "/memory",
        json={"content": GAME, "category": "project", "importance": 4},
    )
    assert created.status_code == 201
    memory = created.json()
    # Provenance is visible: a user-written memory says so.
    assert memory["source"] == MemorySource.USER.value
    assert memory["why"] == "Added by the user."

    listed = await auth_client.get("/memory")
    assert [m["id"] for m in listed.json()] == [memory["id"]]

    edited = await auth_client.patch(
        f"/memory/{memory['id']}", json={"content": f"{GAME} (2D)", "importance": 5}
    )
    assert edited.status_code == 200
    assert edited.json()["importance"] == 5

    deleted = await auth_client.delete(f"/memory/{memory['id']}")
    assert deleted.status_code == 204
    assert (await auth_client.get("/memory")).json() == []


async def test_editing_content_re_embeds_so_search_follows_the_edit(
    auth_client: AsyncClient, user_id: uuid.UUID
) -> None:
    """A stale vector would keep matching the text the user just corrected."""
    created = await auth_client.post(
        "/memory", json={"content": "The user is learning French", "category": "learning"}
    )
    memory_id = created.json()["id"]
    await auth_client.patch(
        f"/memory/{memory_id}", json={"content": "The user is learning Japanese"}
    )

    japanese = (await auth_client.get("/memory/search", params={"q": "Japanese study"})).json()
    assert [item["memory"]["id"] for item in japanese] == [memory_id]

    # The debug search reports everything it ranked, so the edit shows up as the
    # similarity collapsing rather than as the row disappearing.
    french = (await auth_client.get("/memory/search", params={"q": "French study"})).json()
    assert french[0]["similarity"] < japanese[0]["similarity"] / 2


async def test_search_returns_the_scores_behind_the_ranking(
    auth_client: AsyncClient, session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _seed(session, user_id)
    response = await auth_client.get("/memory/search", params={"q": "Processing game"})
    assert response.status_code == 200
    item = response.json()[0]
    assert 0.0 < item["similarity"] <= 1.0
    assert item["score"] > 0.0
    assert item["memory"]["why"] == "Stated in conversation."


async def test_listing_filters_by_category_and_substring(
    auth_client: AsyncClient, session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _seed(session, user_id)
    assert len((await auth_client.get("/memory", params={"category": "project"})).json()) == 1
    assert (await auth_client.get("/memory", params={"category": "goal"})).json() == []
    assert len((await auth_client.get("/memory", params={"q": "Starfall"})).json()) == 1
    assert (await auth_client.get("/memory", params={"q": "kayaking"})).json() == []


async def test_disabling_a_category_hides_it_from_retrieval_but_keeps_the_row(
    auth_client: AsyncClient, session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _seed(session, user_id)
    response = await auth_client.put(
        "/memory/categories", json={"disabled_categories": ["project"]}
    )
    assert response.json()["disabled_categories"] == ["project"]

    assert (await auth_client.get("/memory/search", params={"q": "Processing game"})).json() == []
    # Still listed and still editable — disabled is not deleted.
    assert len((await auth_client.get("/memory")).json()) == 1
    assert (await auth_client.get("/memory/stats")).json()["disabled_categories"] == ["project"]


async def test_stats_summarise_the_store(
    auth_client: AsyncClient, session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _seed(session, user_id)
    stats = (await auth_client.get("/memory/stats")).json()
    assert stats["total"] == 1
    assert stats["by_category"] == {"project": 1}
    assert stats["unembedded"] == 0


async def test_review_queue_is_empty_for_a_healthy_store(auth_client: AsyncClient) -> None:
    assert (await auth_client.get("/memory/review")).json() == []


async def test_unknown_memory_is_a_404_not_a_500(auth_client: AsyncClient) -> None:
    missing = uuid.uuid4()
    assert (await auth_client.patch(f"/memory/{missing}", json={"why": "x"})).status_code == 404
    assert (await auth_client.delete(f"/memory/{missing}")).status_code == 404


async def test_malformed_payloads_are_rejected(auth_client: AsyncClient) -> None:
    assert (await auth_client.post("/memory", json={"content": ""})).status_code == 422
    assert (
        await auth_client.post("/memory", json={"content": "x", "importance": 9})
    ).status_code == 422
    assert (
        await auth_client.post("/memory", json={"content": "x", "category": "nonsense"})
    ).status_code == 422
    assert (await auth_client.get("/memory/search", params={"q": ""})).status_code == 422
    assert (
        await auth_client.put("/memory/categories", json={"disabled_categories": ["nope"]})
    ).status_code == 422


async def test_one_users_memory_cannot_be_touched_by_another(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    from ray.db.models import User

    other = User(name="Other", email="other@example.com", preferences={}, settings={})
    session.add(other)
    await session.commit()
    memory_id = await _seed(session, other.id)

    # Ownership is enforced in the query, so someone else's row simply does not exist.
    assert (await auth_client.get("/memory")).json() == []
    assert (await auth_client.delete(f"/memory/{memory_id}")).status_code == 404
