import asyncio
import httpx
from app.services.recovery import verify


def test_ready_database_with_persisting_fault_is_not_verified():
    def check(request):
        if request.url.path == "/ready":
            return httpx.Response(200, json={"status": "ready"})
        return httpx.Response(200, json={"healthy": False})

    async def exercise():
        async with httpx.AsyncClient(
            base_url="http://pay", transport=httpx.MockTransport(check)
        ) as client:
            assert not await verify(client)

    asyncio.run(exercise())


def test_approved_execution_states(monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from uuid import uuid4
    from app.services import recovery
    from app.seed import seed
    from unittest.mock import AsyncMock

    async def exercise():
        generation = str(uuid4())
        for result, healthy, expected in [
            (200, True, "recovered"),
            (200, False, "persisted"),
            (409, True, "failed"),
        ]:
            calls = []

            def responder(request):
                calls.append(request.url.path)
                if request.method == "POST":
                    return httpx.Response(result)
                if request.url.path == "/ready":
                    return httpx.Response(200, json={"status": "ready"})
                return httpx.Response(
                    200, json={"healthy": healthy, "generation": generation}
                )

            monkeypatch.setattr(
                recovery,
                "client",
                lambda: httpx.AsyncClient(
                    base_url="http://pay", transport=httpx.MockTransport(responder)
                ),
            )
            monkeypatch.setenv("PAYFLOW_INTERNAL_URL", "http://pay")
            incident = seed()
            incident.actions = await recovery.proposal(incident.detected_at)
            action = incident.actions[0]
            scope = AsyncMock()
            scope.lock.return_value = incident

            @asynccontextmanager
            async def begin():
                yield scope

            monkeypatch.setattr(recovery, "sessions", SimpleNamespace(begin=begin))
            monkeypatch.setattr(recovery, "DatabaseIncidents", lambda session: session)
            monkeypatch.setattr(recovery.asyncio, "sleep", AsyncMock())
            await recovery.execute(incident.id, action.id, "operator")
            assert not action.action_started_at
            action.status = "Approved"
            await recovery.execute(incident.id, action.id, "operator")
            assert action.outcome == expected
            assert bool(incident.verified_restored_at) == (expected == "recovered")
            assert [c.args[0].execution for c in scope.append.await_args_list] == [
                "Executing",
                expected,
            ]
            await recovery.execute(incident.id, action.id, "operator")
            assert sum(path.endswith("/clear") for path in calls) == 1

    asyncio.run(exercise())
