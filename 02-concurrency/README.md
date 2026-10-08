# Concurrency in Python

---

## 1. Concurrency vs Parallelism

### Hardware Foundations of Instruction Execution

A central processing unit (CPU) core contains high-speed internal registers (such as the instruction pointer, stack pointer, and general-purpose registers), an Arithmetic Logic Unit (ALU) that executes operations, and a control unit driven by a hardware clock.

During each clock cycle, a physical core advances machine instructions through execution stages. At the level of a single physical execution unit, a core can only have one instruction in its execution stage at any single cycle. Multiple tasks cannot be executed simultaneously on a single CPU core.

### Concurrency: Overlapping Task Lifecycles

Concurrency is the condition where multiple computational tasks have overlapping execution lifetimes. A task begins, enters an incomplete state, and finishes at a later time, while one or more other tasks begin, make progress, and finish during that same span of time.

Concurrency does not require simultaneous instruction execution at the physical hardware layer. Concurrency exists on a computer with exactly one single-core processor through operating system time-slicing:

1. **The Operating System Scheduler**:
   The Linux kernel tracks runnable tasks using internal structures arranged in run queues.
2. **Hardware Timer Interrupts**:
   The hardware timer emits electrical interrupt signals to the CPU core at regular intervals.
3. **Interrupt Handling and Preemption**:
   When the timer fires, the CPU switches to kernel mode. The kernel checks the running task's consumed time. If its time slice has expired, the scheduler marks the task as preempted and selects another runnable task.
4. **Context Switch**:
   The kernel saves the register state of the current task into memory, loads the saved register values of the next task into the CPU registers, and resumes execution.

Under this mechanism, tasks are concurrent because both are in progress between their start and finish timestamps. However, at any discrete nanosecond, the hardware executes instructions for only one task.

### Parallelism: Simultaneous Physical Execution

Parallelism is the condition where multiple instructions from two or more tasks are physically executed at the exact same instant in time across distinct hardware execution units.

Parallelism requires multiple hardware units:
* Multi-core processors where a single chip contains multiple independent physical cores.

On a machine with multiple cores, Core 0 executes instructions for Task A while Core 1 executes instructions for Task B during the exact same clock cycle. No time-slicing is required for both to make progress.

---

## 2. CPU-Bound vs I/O-Bound Work

Programs spend their time either computing data inside the processor or waiting for data from outside devices.

### CPU-Bound Work
A task is CPU-bound when its execution speed is limited by the speed of the processor.
* **Characteristics**: The task continuously runs instructions such as arithmetic, data parsing, or logic checks. The CPU core stays at 100% usage.
* **Typical Examples**: Mathematical calculations, video/image processing, cryptographic hashing, compression, parsing JSON or XML strings.
* **Scaling Method**: Requires faster CPU clock speeds, optimized algorithms, or dividing work across multiple cores in parallel. Running multiple CPU-bound tasks on a single core does not make them finish faster.

### I/O-Bound Work
A task is I/O-bound when its execution speed is limited by waiting for Input/Output (I/O) operations. I/O refers to communication outside the CPU and RAM, including storage drives, network interfaces, and external peripherals.
* **Characteristics**: The task spends most of its time paused waiting for an external response. CPU usage for that task is near 0% while waiting.
* **Typical Examples**: HTTP requests to web APIs, database queries over a socket, reading or writing files on disk.
* **Scaling Method**: Overlapping waiting times using concurrency. While one task is paused waiting for a response, the CPU can execute code for another task.

### Hardware Clarification: How I/O Avoids CPU Work (Direct Memory Access)

The CPU is involved in I/O operations, but only for a tiny fraction of the total time. The reason the CPU does not spend time reading individual bytes is a hardware mechanism called **Direct Memory Access (DMA)**.

In early computers, the CPU ran a loop fetching one byte from the disk controller into a register and writing it to RAM. Modern computers use DMA:
1. **The Request (CPU active for a few microseconds)**:
   * The program calls `read()`.
   * The operating system checks permissions and identifies the target disk blocks.
   * The CPU instructs the storage controller: "Read these blocks and write them directly into this memory address in RAM."
   * The kernel changes the program's status from running to sleeping.
2. **Waiting and Data Transfer (CPU idle for milliseconds)**:
   * The storage drive reads the flash memory or disk platter.
   * The drive controller streams the bytes directly into RAM using DMA over the motherboard bus.
   * The CPU executes zero instructions during this data transfer and is free to run other tasks or enter an idle power state.
3. **Completion and Wakeup (CPU active for a few microseconds)**:
   * When the controller finishes placing the bytes into RAM, it sends a hardware interrupt to the CPU.
   * The CPU runs the interrupt handler, marks the sleeping program as ready to run, and returns data to the program.

The same sequence applies to network packets. The Network Interface Card (NIC) decodes incoming signals and uses DMA to write packets directly into kernel memory buffers before interrupting the CPU. 

An operation is called I/O-bound because the CPU work (a few microseconds) is negligible compared to the wait time (milliseconds).

---

## 3. Threads in CPython and the Global Interpreter Lock (GIL)

### What a Thread Is in Python

When Python creates a thread using `threading.Thread`, CPython creates an actual operating system thread (a POSIX thread on Linux using `clone()`). The operating system kernel schedules it and can place it on any CPU core.

### What the GIL Is

The Global Interpreter Lock (GIL) is a mutual exclusion lock (a mutex) managed inside CPython. Its rule is: **Only one operating system thread can execute Python bytecode at any given moment**, regardless of how many CPU cores the machine has.

### Why CPython Has the GIL

1. **Reference Counting**: Every Python object has an internal reference counter. When an object is referenced, the counter increments; when a reference goes out of scope, it decrements. At zero, memory is freed immediately.
2. **Preventing Race Conditions**: If two threads ran Python code simultaneously on two cores, both could modify the reference counter of a shared object at the same instant, leading to memory corruption, premature memory deallocation, or memory leaks.
3. **Single-Threaded Speed**: Protecting every individual object with its own lock would introduce substantial CPU overhead and risk deadlocks. CPython uses one lock around the entire interpreter runtime to keep single-threaded execution fast and simple.

### Behavior During CPU-Bound vs I/O-Bound Work

* **CPU-Bound Work**: Threads compete for the GIL. CPython forces the running thread to release the GIL every 5 milliseconds (switch interval). Because only one thread executes bytecode at a time, multi-threaded CPU-bound code does not run faster, and often runs slower due to lock contention overhead.
* **I/O-Bound Work**: CPython explicitly releases the GIL before executing blocking system calls (such as reading a socket, reading a file, or sleeping). While Thread A sleeps in the kernel waiting for I/O, Thread B acquires the GIL and runs Python code. When Thread A's I/O finishes, it waits to re-acquire the GIL before continuing execution.

### Python 3.13 Free-Threaded Build

Starting in Python 3.13, an experimental build of CPython (PEP 703) runs without the GIL. It enables true parallel execution of Python bytecode across multiple cores.

### Low-Level Clarification: How Locks Function at the Hardware and Kernel Level

#### Why the CPU Does Not Run Both Threads
The CPU does not know what Python bytecode is; it executes machine instructions. Thread B does not jump straight to application code. Before running any bytecode, Thread B executes lock-acquisition instructions. When it detects that Thread A holds the GIL, Thread B's instructions call the operating system to put itself to sleep.

#### Hardware Enforcement: Atomic Instructions
If two cores check and write a memory flag (`0` for free, `1` for locked) using standard instructions, both could read `0` at the same instant and both write `1`.

CPUs prevent this using **atomic instructions** (such as `CMPXCHG` on x86):
* The CPU temporarily locks the memory cache line so no other core can read or write that address during the operation.
* The CPU reads the old value and writes the new value in a single, indivisible hardware step. Only one core can succeed.

#### Operating System Sleeping: Futex on Linux
Spinning in a loop to check the lock burns 100% CPU. Linux avoids this using a **futex** (Fast Userspace Mutex):
1. **User-Space Fast Path**: The thread checks the lock in user memory using an atomic instruction. If free, it claims the lock in nanoseconds without entering kernel space.
2. **Kernel Sleep**: If locked, the thread invokes the `futex` system call. The Linux kernel marks the thread as blocked and removes it from the CPU core's schedule.
3. **Release and Wakeup**: When the holding thread finishes, it resets the lock variable to `0` and asks the kernel to wake a waiting thread. The kernel places the waiting thread back on the run queue.

---

## 4. Processes for CPU-Bound Work

To bypass the GIL and execute Python code in parallel across multiple CPU cores, programs use separate processes via `multiprocessing` or `concurrent.futures.ProcessPoolExecutor`.

### Why Processes Achieve Parallelism
* Each process runs its own independent CPython interpreter.
* Each process has its own isolated memory space and its own GIL.
* The operating system schedules Process A on Core 0 and Process B on Core 1 simultaneously, running Python bytecode at 100% capacity with zero lock contention.

### The Costs of Using Processes

1. **Startup Time**:
   * Threads start in microseconds by sharing memory.
   * Processes take tens to hundreds of milliseconds when spawned via `execve`, because the system must initialize a fresh Python interpreter runtime and re-import modules.
2. **Memory Overhead**:
   * Each process requires its own memory heap for objects and bytecode.
   * Although Linux uses Copy-on-Write (COW) on `fork()`, CPython's reference counting constantly modifies memory on read operations, causing the kernel to copy pages into private RAM and breaking memory sharing.
3. **Data Serialization and Communication (IPC)**:
   * Processes cannot directly read objects in another process's memory.
   * Transferring data requires serializing objects to bytes (`pickle`), transmitting them through operating system pipes, and deserializing them (`unpickle`) in the child process.
   * If communication and serialization time exceeds computation time, multi-process programs can run slower than sequential single-threaded execution.

### `multiprocessing` vs `concurrent.futures.ProcessPoolExecutor`

* **`multiprocessing`**: Low-level primitives (`Process`, `Queue`, `Pipe`, `Value`, `Array`, `Manager`) giving full control over process creation, shared memory, and synchronization.
* **`ProcessPoolExecutor`**: High-level task pool built on top of `multiprocessing` that automates worker process management, task scheduling, and result collection.

#### IPC Queue Architecture and the `Future` Lifecycle

In `ProcessPoolExecutor`, the parent process coordinates workers through operating system pipes:
1. **Call Queue**: The parent serializes (`pickle`) the function and arguments, then transmits them through the pipe to workers.
2. **Result Queue**: Workers execute the task and transmit back the serialized return value or raised exception.
3. **Queue Management Threads**: The parent process runs background helper threads to write pending tasks to the Call Queue and read completed results from the Result Queue without blocking the main thread.
4. **`Future` Lifecycle**: Submitted tasks return a `Future` object tracking state (`PENDING` -> `RUNNING` -> `FINISHED` / `CANCELLED`). Calling `future.result()` blocks until completion, while `future.add_done_callback()` triggers callbacks upon finish.

---

## 5. Blocking vs Non-Blocking I/O

Open resources for input and output (sockets, files, pipes) are tracked in Linux by a File Descriptor (FD) integer.

### Blocking I/O
* **Behavior**: When a program calls `read()` on a blocking socket with an empty buffer, the kernel puts the calling thread to sleep.
* **Resumption**: The thread stays frozen until network packets arrive, fill the buffer, and trigger an interrupt.
* **Consequence**: Handling 1,000 connections requires 1,000 threads, which consumes significant stack memory and increases kernel context-switching overhead.

### Non-Blocking I/O
* **Behavior**: Configured via `O_NONBLOCK` (or `sock.setblocking(False)`). When `read()` is called on an empty buffer, the kernel does not put the thread to sleep. It returns immediately with a status code (`EAGAIN` / `EWOULDBLOCK` in C, or `BlockingIOError` in Python).
* **The Busy-Waiting Problem**: Repeatedly calling `read()` on non-blocking sockets in a tight loop burns 100% CPU checking empty buffers.
* **The Solution (I/O Multiplexing)**: The program registers sockets with the kernel and makes a single call asking the kernel to sleep until at least one socket becomes ready.

---

## 6. The Event Loop and I/O Multiplexing

An event loop allows a single thread to manage thousands of connections by combining non-blocking sockets with operating system multiplexing calls:

1. **`epoll()` (Linux)**:
   * Sockets are registered with the kernel once (`epoll_ctl`) and stored in a kernel data structure.
   * When packets arrive, the kernel places the ready socket on a ready list.
   * The program calls `epoll_wait()`. The thread sleeps until an event occurs, and the kernel returns only the active sockets in O(1) time relative to total idle connections.
   *(Equivalent mechanisms: `kqueue` on macOS/BSD, `IOCP` on Windows).*

Python's `selectors` module abstracts these system calls into a cross-platform interface.

### Execution Clarification: Shared State Across Await in Single-Threaded Code

Even within a single thread, asynchronous code can introduce race conditions if shared state is modified across `await` points:

```python
# Function 1
async def read_after_sleep():
    await asyncio.sleep(10)
    print(a)

# Function 2
async def read_after_small_sleep():
    await asyncio.sleep(1)
    a += 1
```

If both are scheduled at `T = 0s` with initial `a = 0`:
1. `read_after_sleep` pauses at its 10-second sleep and yields control to the loop.
2. `read_after_small_sleep` pauses at its 1-second sleep and yields control.
3. At `T = 1s`, the 1-second timer expires. The loop resumes `read_after_small_sleep`, which increments `a` to 1 and finishes.
4. At `T = 10s`, the 10-second timer expires. The loop resumes `read_after_sleep`, which reads the current value of `a` (now 1) and prints 1.

While code between two `await` statements runs uninterrupted on a single thread, execution is not atomic across `await` boundaries.

---

## 7. Coroutines, Await, and Blocking Calls

### Coroutines and `await`
* A standard function runs from entry to return, destroying its stack frame on exit.
* A coroutine (`async def`) returns a coroutine object that preserves its state on the heap and can pause and resume.
* The `await` keyword checks if the target operation is ready. If not, it pauses the coroutine, registers it with the event loop, and yields control so other coroutines can run.

### Preemptive vs Cooperative Multitasking
* **Preemptive (Threads)**: The operating system kernel forcefully pauses threads at arbitrary moments via hardware timer interrupts.
* **Cooperative (Coroutines)**: The operating system is unaware of coroutines. A coroutine only yields control when it explicitly reaches an `await`.

### Why Blocking Calls Freeze the Application
If a coroutine calls a synchronous blocking function (such as `time.sleep()`, synchronous `requests.get()`, or a heavy CPU loop):
* The operating system puts the single thread running the event loop to sleep.
* The event loop cannot check `epoll` or run timers.
* Every coroutine in the entire application freezes for the duration of that call.

### Execution Clarification: Invoking Async Functions (Node.js vs Python)

* **Node.js**: Calling an `async` function immediately begins executing the function body synchronously on the main thread until it hits the first `await`. At that point, it pauses, returns a pending `Promise` object to the caller, and the caller's subsequent synchronous code continues running.
* **Python**: Calling an `async def` function executes zero code inside the body immediately. It only instantiates a coroutine object in memory. Calling it without `await` produces a `RuntimeWarning`. To run it in the background without immediately awaiting its result, it must be scheduled on the event loop using `asyncio.create_task()`.

### Threading Clarification: How `asyncio.to_thread` and Thread-Safe Futures Work

To execute blocking code without freezing the event loop, Python provides `asyncio.to_thread()`:
1. **Thread Pool Reuse**: `asyncio.to_thread()` submits the function to a default `ThreadPoolExecutor` rather than creating and destroying a new operating system thread for each call.
2. **Independent Execution**: A worker thread runs the blocking call synchronously. If that thread blocks in the kernel, the main event loop thread continues running other coroutines.
3. **Thread-Safe Futures**: The worker thread writes its result into a `Future` object in memory:
   * A `Future` holds state (`PENDING`, `FINISHED`), a value, and callbacks.
   * Because both the worker thread (writing) and the main thread (reading) access the same memory, the `Future` uses an internal mutex to ensure that setting the value, updating the state, and notifying the event loop via `loop.call_soon_threadsafe()` occur safely without memory corruption.
   * Once marked complete, the event loop resumes the coroutine awaiting the `Future`.


---

## 8. asyncio as Runtime and Asynchronous HTTP Clients

### asyncio Is a Runtime, Not an HTTP Client

The Python standard library module `asyncio` provides the core infrastructure for asynchronous programming:
* The event loop (monitoring file descriptors using operating system calls like `epoll`).
* Scheduling mechanisms for timers and coroutines (`Task`, `Future`).
* Low-level network transport primitives (opening raw TCP streams via `asyncio.open_connection()`).

`asyncio` does not parse application-layer protocols like HTTP. It does not parse headers, manage cookies, or format HTTP/2 binary frames. Higher-level libraries implement the HTTP protocol on top of `asyncio`.

### Why requests Fails in Asynchronous Code

The standard `requests` library is synchronous:
* It is built on top of standard blocking sockets via `urllib3`.
* When `requests.get()` runs, it calls `socket.recv()` in blocking mode.
* The operating system kernel puts the single thread running the Python process to sleep until the remote server finishes responding.
* While that thread is asleep, the event loop cannot run, freezing all other concurrent tasks.

### aiohttp vs httpx

* **`aiohttp`**: Built specifically for `asyncio`. It only works inside an event loop with `async with aiohttp.ClientSession()` and focuses primarily on HTTP/1.1.
* **`httpx`**: Supports both asynchronous execution (`httpx.AsyncClient`) and synchronous execution (`httpx.Client`), and includes built-in support for HTTP/2.

### Architecture Clarification: Kernel (TCP) vs User Space (HTTP)

Network communication is strictly divided between the operating system kernel and user space:

1. **Kernel Space (TCP Layer)**:
   * Handles the TCP three-way handshake (`SYN`, `SYN-ACK`, `ACK`).
   * Manages packet sequence numbers, retransmission of lost packets, and flow control.
   * Tracks connection lifecycles (`ESTABLISHED`, `FIN_WAIT`, `TIME_WAIT`).
   * To the kernel, a connection is simply an uninterpreted stream of raw bytes.
2. **User Space (HTTP Layer)**:
   * Libraries like `httpx` or `requests` parse HTTP request/response headers, status codes, cookies, and body encodings.
   * The library builds the HTTP payload in user-space RAM and sends those bytes to the kernel via `write()` or `send()`.

### Protocol Clarification: HTTP/1.1 vs HTTP/2 and What "h2" Means

* **HTTP/1.1**: Plain-text protocol. Each TCP connection can only handle one request and response at a time. If Request 1 is slow, Request 2 must wait behind it (Head-of-Line blocking).
* **HTTP/2**: Binary protocol using frames with 9-byte headers. Allows multiple requests to be multiplexed concurrently over a single TCP connection.
* **The Meaning of "h2"**:
  * In networking standards, `h2` is the official protocol token negotiated during the TLS handshake for HTTP/2 over TLS. It is displayed in browser DevTools and server logs.
  * In the Python ecosystem, `h2` is the name of the standard Python package (`pip install h2`) that implements the HTTP/2 frame parsing and stream state machine used by `httpx`.

### Resource Management Clarification: Keep-Alive vs Multiplexing and Session Reuse

* **Keep-Alive (HTTP/1.1)**: Keeps a TCP socket open between requests to avoid repeated handshakes, but requests must still run sequentially one after another.
* **Multiplexing (HTTP/2)**: Keeps the socket open and allows multiple independent request and response streams to travel simultaneously down that single socket.
* **Reusing Client Sessions**:
  * Creating a new client instance for every request forces a fresh TCP handshake and TLS handshake every time.
  * Creating a shared client instance (`client = httpx.AsyncClient(http2=True)`) allows the client to maintain an internal connection pool, reusing open sockets across requests.

### Web Application Clarification: How Browsers and Backends Handle Multiplexing

* **Web Browsers**: Browsers have HTTP/2 multiplexing built into their native C++ networking engines. When JavaScript triggers multiple `fetch()` calls via `Promise.all()`, the browser automatically transmits them concurrently over a single TCP connection if the backend supports HTTP/2. No custom multiplexing library is needed in JavaScript.
* **Response Demultiplexing**: Each HTTP/2 frame contains a 31-bit Stream Identifier. The browser's networking engine matches incoming frames to their respective Stream IDs and resolves the corresponding JavaScript `Promise`.
* **Backend Serving**: Python ASGI applications (FastAPI) are typically placed behind a reverse proxy (like Nginx with `listen 443 ssl http2;`), or served directly using an ASGI server supporting HTTP/2 (such as Hypercorn).

### Runtime Clarification: HTTP/2 in Node.js (nghttp2 and Built-in node:http2)

* Node.js compiles the native C library **`nghttp2`** directly into the Node binary.
* Node exposes this through the built-in module `node:http2`, allowing developers to create HTTP/2 client sessions and servers without installing third-party npm packages.
* Node's global `fetch()` implementation (powered by Undici) defaults to HTTP/1.1, so using HTTP/2 in Node.js requires using `node:http2` or libraries configured for it.

---

## 9. Race Conditions, Locks, Deadlock, and Condition Variables

### Critical Sections and Race Conditions

A **critical section** is a code block accessing a shared mutable resource that must not be run concurrently by multiple threads.

A **race condition** occurs when execution correctness depends on thread timing:
* An operation like `counter += 1` consists of three distinct steps: read value from RAM, modify value in register, write value back to RAM.
* If a thread is preempted between reading and writing, another thread can read the stale value, resulting in lost updates.

### Mutexes (threading.Lock)

A mutex enforces mutual exclusion so only one thread can hold the lock at a time. In Python, `threading.Lock()` wrapped in a `with lock:` context manager ensures the lock is safely released even if exceptions occur.

### Deadlock and Strict Lock Ordering

A deadlock is a permanent freeze where two threads each wait for a lock held by the other (Thread 1 holds Lock A waiting for B; Thread 2 holds Lock B waiting for A).
* **Prevention**: Establish a strict, global lock acquisition order across the codebase (e.g., always acquire Lock A before Lock B).

### Condition Variables: The Problem Normal Locks Cannot Solve

A normal lock cannot efficiently handle waiting for state to change:
* **Waiting while holding the lock**: Freezes the system because the thread that produces the data cannot acquire the lock to add it.
* **Releasing the lock and polling in a loop**: Wastes CPU cycles repeatedly acquiring and checking empty state, or introduces latency.

A **Condition Variable** (`threading.Condition`) provides a lock combined with a signaling mechanism:
* **`cv.wait()`**: Atomically releases the lock, puts the thread to sleep in the kernel (consuming 0% CPU), and re-acquires the lock upon waking.
* **`cv.notify()`**: Signals the operating system to wake up one sleeping thread.
* **The `while` Loop**: Code must use `while condition: cv.wait()` instead of `if` to protect against spurious wakeups or multiple workers competing for a newly added item.

### Kernel Clarification: How the Operating System Manages Condition Variables

Condition variables exist across operating systems (POSIX `pthread_cond_t` in C/C++, Java, Rust, Go). Python's `threading.Condition` relies directly on the Linux kernel via the `futex` system call.

The kernel manages two main lists:
1. **The Active List (Run Queue)**: Threads runnable on CPU cores.
2. **The Sleeping Lists (Wait Queues)**: Threads paused and ignored by CPU cores.

* **During `wait()`**: The thread asks the kernel to unlock the lock and move its `task_struct` off the Active List and onto the condition variable's Sleeping List. The scheduler switches the CPU core to other work.
* **During `notify()`**: The signaling thread asks the kernel to move one thread from the condition variable's Sleeping List back onto the Active List, allowing it to re-acquire the lock and resume execution.

---

## 10. Thread Pools and Process Pools

### The Problem with Creating Threads or Processes on Demand

Creating execution contexts per task causes serious bottlenecks:
* **Overhead**: Allocating thread stacks and kernel structures (`clone`), or starting new Python interpreter runtimes (`execve`), consumes excessive CPU time for short-lived tasks.
* **Resource Exhaustion**: Creating thousands of threads exhausts stack memory and scheduler capacity; creating thousands of processes exhausts physical RAM, triggering the Linux OOM killer.

### How Pools Work

A pool creates a fixed, bounded number of reusable workers that pull work from a shared task queue:
1. Tasks are submitted to an internal thread-safe or process-safe queue.
2. Workers run a continuous loop: pull task from queue, execute task, store result in a `Future` object, and return to the queue for the next task.
3. If tasks surge, excess tasks wait in the queue without overwhelming system resources.

### ThreadPoolExecutor vs ProcessPoolExecutor

Python provides standardized pools in `concurrent.futures`:

* **`ThreadPoolExecutor`**:
  * Manages reusable operating system threads.
  * Shared process memory; near-zero communication overhead.
  * Bound by the Global Interpreter Lock (GIL) for CPU-bound code.
  * Ideal for I/O-bound tasks.
* **`ProcessPoolExecutor`**:
  * Manages reusable operating system processes, each with its own Python runtime and GIL.
  * Bypasses the GIL, achieving true multi-core parallelism.
  * Higher memory footprint; task arguments and return values must be serialized (`pickled`) through operating system pipes.
  * Ideal for CPU-bound computations.

### How to Size Pools Properly

* **Process Pools (CPU-Bound)**: Set `max_workers` equal to the number of physical CPU cores (`os.cpu_count()`). Running more CPU-bound processes than physical cores adds context-switching overhead without increasing throughput.
* **Thread Pools (I/O-Bound)**: Set `max_workers` significantly higher than core count (e.g., 10 to 50+, with Python defaulting to `min(32, os.cpu_count() + 4)`). Because threads sleep in the kernel during I/O waits, many threads can wait concurrently without saturating the CPU.


---

## 11. How Common Servers Run Code (Gunicorn, Uvicorn, FastAPI, Celery)

### Gunicorn and Uvicorn: Multi-Process Execution

Because the GIL prevents a single Python process from running bytecode in parallel across multiple CPU cores, production Python web servers use multiple processes:

* **Gunicorn**: Follows a pre-fork model. A master process creates a listening socket and forks worker processes. The master monitors worker health and handles process restarts; workers execute HTTP requests.
* **Uvicorn**: An ASGI server that runs an `asyncio` event loop on a single core, handling thousands of concurrent I/O connections via `epoll`.
* **Gunicorn + Uvicorn**: Gunicorn acts as the process manager for multiple Uvicorn workers (`gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker`). This combines multi-core process parallelism with event loop I/O concurrency.

### Server Clarification: How Multiple Workers Listen on the Same Port

In Gunicorn, the master process does not intercept or reverse-proxy HTTP traffic. Multiple workers share the port through operating system socket inheritance:

1. **Master Creates the Listening Socket**: The master process calls `socket()`, `bind()`, and `listen()`, producing a listening File Descriptor (such as `FD 3`).
2. **Workers Inherit via `fork()`**: When Gunicorn forks worker processes, Linux child processes inherit the parent's file descriptor table. All workers hold `FD 3` pointing to the exact same listening socket in kernel space.
3. **The Kernel Accepts and Routes**: When a client completes the TCP handshake, the Linux kernel selects **one worker** waiting on `FD 3` (using `EPOLLEXCLUSIVE`).
4. **`accept()` Generates a Private Socket**: The chosen worker calls `accept(FD 3)`. The kernel creates a **brand-new socket file descriptor** (such as `FD 4`) private to that worker. All subsequent HTTP data flows exclusively through `FD 4`.

### Framework Clarification: Why Uvicorn and AnyIO Exist Alongside asyncio

* **Uvicorn vs `asyncio`**: `asyncio` is a general-purpose asynchronous engine (event loop, coroutines, timers) with no knowledge of HTTP, headers, cookies, or ASGI. Uvicorn runs on top of `asyncio`, parses incoming HTTP bytes using fast C parsers (`httptools`), and routes requests to the application. Uvicorn can also use `uvloop`, a C-based drop-in replacement for the `asyncio` loop built on `libuv`.

### FastAPI Execution: `async def` vs Plain `def`

FastAPI executes routes differently based on how they are declared:

* **`async def` Endpoints**: Run directly on Uvicorn's main **event loop thread**. If an endpoint calls a blocking synchronous library (`time.sleep` or synchronous database calls), the entire event loop freezes for all clients assigned to that worker.
* **Plain `def` Endpoints**: FastAPI automatically offloads plain `def` endpoints to a background **thread pool** (`ThreadPoolExecutor` managed by AnyIO). Blocking calls only pause that worker thread, keeping the event loop responsive.

### Celery: Background Task Worker Pools

Celery executes background tasks pulled from message brokers (RabbitMQ/Redis):
* **Default Pool (`prefork`)**: Forks a pool of OS worker processes matching the CPU core count. Because background jobs are often CPU-intensive (data parsing, image resizing), processes bypass the GIL. Process isolation also ensures that memory leaks or segmentation faults do not crash the entire worker system.
* **Alternative Pools**: `--pool=threads` (uses OS threads, ideal for low-memory I/O-bound jobs).

---

## 12. The Database as Concurrency Control

### Why Application Locks Fail Across Multiple Servers

A Python lock (`threading.Lock` or `asyncio.Lock`) exists exclusively inside the memory space of a single process on a single server. In production architectures with multiple worker processes or multiple Docker containers behind a load balancer, processes share no memory. Concurrency control must be enforced by the centralized database where shared state lives.

### The Lost Update Problem (Read-Modify-Write Races)

When multiple application servers read data, compute modifications in Python, and write back to the database, concurrent updates overwrite each other:
1. Server A reads balance ($100).
2. Server B reads balance ($100).
3. Server A deducts $20 and writes balance = $80.
4. Server B deducts $30 and writes balance = $70.

A total of $50 was withdrawn, but the balance was set to $70 because Server B wrote changes based on a stale read.

### Database Concurrency Mechanisms

#### 1. Unique Constraints
Prevents duplicate entities from concurrent inserts (e.g., duplicate votes or duplicate user registrations):
* Enforced via a unique B-tree index in storage.
* The database engine acquires an internal storage lock on the index leaf page during insertion.
* When two transactions attempt to insert the same key concurrently, one succeeds while the other is rejected with an integrity violation (PostgreSQL error code `23505`, raising `IntegrityError` in Python).

#### 2. Pessimistic Row Locking (`SELECT ... FOR UPDATE`)
Used when business logic must read a row, validate conditions in Python, and write back:
```sql
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;
-- (Application validates balance and business logic)
UPDATE accounts SET balance = balance - 20 WHERE id = 1;
COMMIT;
```
* **Mechanics**: PostgreSQL writes an exclusive lock into the row's tuple header.
* **Blocking**: Concurrent transactions attempting to read that row with `FOR UPDATE` or modify it are put to sleep by the database engine until the holding transaction runs `COMMIT` or `ROLLBACK`.
* **Fresh Reads**: When awakened, the waiting transaction reads the updated data rather than stale values.

#### 3. Atomic Database Updates
For simple modifications (such as decrements or counters), logic can be executed directly within the SQL statement:
```sql
UPDATE accounts 
SET balance = balance - 20 
WHERE id = 1 AND balance >= 20;
```
* The database engine acquires an internal row-level write lock and evaluates the `WHERE` condition on storage atomically.
* If two processes execute this statement simultaneously, the second transaction evaluates the updated balance and safely updates 0 rows if funds are insufficient, bypassing application-level locks.
