import asyncio
import time

from fastapi import FastAPI
import httpx

app = FastAPI()


def call_apis():
    async def async_api_call(client, end_point):
        await client.get(f"http://localhost:8000/{end_point}")

    async def batch_run(end_point):
        start = time.perf_counter()
        # timeout=None disable the timeout entirely
        async with httpx.AsyncClient(timeout=None) as client:
            await asyncio.gather(
                *[async_api_call(client, end_point) for _ in range(10)]
            )
        print(f"{end_point}: {time.perf_counter()-start}", flush=True)

    for end_point in ["block-async", "nonblock-async", "block-sync"]:
        asyncio.run(batch_run(end_point))


@app.get("/block-async")
async def block_async():
    time.sleep(2)
    return {"status": "ok"}


@app.get("/nonblock-async")
async def nonblock_async():
    await asyncio.sleep(2)
    return {"status": "ok"}


@app.get("/block-sync")
def block_sync():
    time.sleep(2)
    return {"status": "ok"}
