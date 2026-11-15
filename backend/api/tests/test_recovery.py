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
