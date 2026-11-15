import asyncio
import httpx
from app.services import telemetry


def test_summary_uses_only_finite_histogram_samples(monkeypatch):
    factory = httpx.AsyncClient

    def serve(request):
        result = (
            [{"values": [[1, "NaN"], [2, "0.8"]]}]
            if request.url.path.endswith("query_range")
            else [{"value": [2, "1.2"]}]
        )
        return httpx.Response(200, json={"data": {"result": result}})

    monkeypatch.setattr(
        telemetry.httpx,
        "AsyncClient",
        lambda **kw: factory(transport=httpx.MockTransport(serve), **kw),
    )
    data = asyncio.run(telemetry.readings("http://metrics"))
    assert data["latency_ms"] == [800]
    assert data["metrics"][-1]["value"] == "800 ms"
