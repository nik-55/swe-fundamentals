from concurrent.futures import ThreadPoolExecutor
import time


def io_task():
    time.sleep(0.1)  # I/O Task


def test_pool(pool_size):
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=pool_size) as executor:
        futures = [executor.submit(io_task) for _ in range(200)]

        for f in futures:
            f.result()

    print(f"{pool_size}: {time.perf_counter()-start}s", flush=True)


def main():
    for pool_size in [1, 10, 50, 200]:
        test_pool(pool_size)


if __name__ == "__main__":
    main()
