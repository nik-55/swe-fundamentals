# 10 MiB = 10*1024*1024
# b"x" hold roughly 1 byte in raw binary format with little overhead

import mmap
import os
import time
import subprocess

a = []
i = 0

pid = os.getpid()
print(f"PID: {pid}", flush=True)


def get_memory_size():
    result = subprocess.run(
        ["grep", "-E", "VmSize|VmRSS", f"/proc/{pid}/status"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def oom_test():
    while True:
        print(i, flush=True)
        print(get_memory_size(), flush=True)
        a.append(b"x" * 10 * 1024 * 1024)
        i += 1
        time.sleep(1)


def empty_large_array():
    print(f"Before: \n{get_memory_size()}", flush=True)
    # Request anonymous memory from kernel without writing anything to it
    a = mmap.mmap(-1, 1024 * 1024 * 1024) # 1 GiB
    print(f"After: \n{get_memory_size()}", flush=True)


if __name__ == "__main__":
    # oom_test()
    empty_large_array()
