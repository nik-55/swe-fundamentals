import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import time

num_workers = 8


def cpu_work():
    sum(i * i for i in range(10_000_000)) # 10 Million


def io_work():
    time.sleep(1)


async def async_io_work():
    await asyncio.sleep(1)


def cpu_bound_seq():
    start = time.perf_counter()  # value is guaranteed to move strictly forward
    for i in range(num_workers):
        cpu_work()

    elapsed = time.perf_counter() - start
    print(f"CPU Bound (Seq): {elapsed}s")


def cpu_bound_threads():
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(cpu_work) for _ in range(8)]

    for f in futures:
        try:
            f.result()
        except Exception:
            continue

    elapsed = time.perf_counter() - start
    print(f"CPU Bound (Threads): {elapsed}s")


def cpu_bound_process():
    start = time.perf_counter()

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(cpu_work) for _ in range(8)]

    for f in futures:
        try:
            f.result()
        except Exception:
            continue

    elapsed = time.perf_counter() - start
    print(f"CPU Bound (Process): {elapsed}s")


def io_bound_seq():
    start = time.perf_counter()
    for i in range(num_workers):
        io_work()

    elapsed = time.perf_counter() - start
    print(f"IO Bound (Seq): {elapsed}s")


def io_bound_threads():
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(io_work) for _ in range(8)]

    for f in futures:
        try:
            f.result()
        except Exception:
            continue

    elapsed = time.perf_counter() - start
    print(f"IO Bound (Threads): {elapsed}s")


def io_bound_process():
    start = time.perf_counter()

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(io_work) for _ in range(8)]

    for f in futures:
        try:
            f.result()
        except Exception:
            continue

    elapsed = time.perf_counter() - start
    print(f"IO Bound (Process): {elapsed}s")


async def io_bound_async():
    start = time.perf_counter()
    await asyncio.gather(*[async_io_work() for _ in range(num_workers)])
    elapsed = time.perf_counter() - start
    print(f"IO Bound (async): {elapsed}s")


if __name__ == "__main__":
    # cpu_bound_seq()
    # cpu_bound_threads()
    # cpu_bound_process()

    # io_bound_seq()
    # io_bound_threads()
    # io_bound_process()
    asyncio.run(io_bound_async())
