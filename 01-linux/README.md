# Linux Processes, Memory, and Containers

---

## 1. Processes and Memory Architecture

### What Is a Process
A process is a running program managed by the Linux kernel. Every process has:

* **Process ID (PID)**: A positive number (`1, 2, 3, ...`) that identifies the process. Inside the kernel, Linux tracks each process using a C structure called `task_struct`.
* **Private Virtual Memory**: Its own private address space containing the program code, global variables, stack, and heap. By default, one process cannot read or write memory belonging to another process.
* **File Descriptor Table**: An internal array of numbers (`0, 1, 2, ...`) pointing to open files, pipes, and network connections.

### Stack vs Heap
The stack and the heap are two different ways a program organizes memory during execution. The Linux kernel does not manage stacks or heaps; to the kernel, all process memory is made of 4 KB blocks called pages. The program's runtime code decides how to use them:

* **The Stack (Function Memory)**:
  * Used for function calls: function arguments, local variables, and return addresses.
  * Functions call other functions and return in reverse order. Because of this, allocating or freeing stack memory takes a single CPU operation: moving the stack pointer register up or down.
* **The Heap (Dynamic Memory)**:
  * Used for data whose size is unknown ahead of time or data that must stay in memory after a function finishes (such as dynamic arrays or objects).
  * Data on the heap is created and deleted in any order. Programs use a memory allocator (such as `malloc` in C or Python's memory allocator) to find free space and reuse memory.
* **The Kernel's Role**:
  * The kernel does not check what data structures reside on the stack or heap. It gives the process initial memory pages, sets the starting stack pointer register, and provides system calls (`mmap`) when the process requests more memory pages.
* **How Python Uses Memory**:
  * In compiled languages like C, local variables live on the CPU stack. In Python, all objects (`int`, `str`, `list`, `dict`) and function execution frames live on the heap.
  * The CPU hardware stack is used only by the compiled C code of the Python interpreter executable itself.

### Kernel Primitives for Memory and Execution
Programs running in user space cannot touch hardware directly. They use a small set of kernel primitives to obtain memory and start execution:

* **System Call (`syscall`)**: The official request mechanism a user-space program uses to ask the kernel to perform operations (such as allocating memory, reading a disk file, or starting a thread).
* **`mmap` (Memory Map)**: A system call that asks the kernel to assign a new block of virtual memory pages to the process. Runtimes use `mmap` to request memory for the heap or for thread stacks.
* **`clone`**: The Linux system call that creates a new execution context (`task_struct`). Depending on the flags passed to it, `clone` creates either an isolated process or a thread sharing memory.
* **`pthread` (POSIX Threads)**: A standard C library wrapper. Application code and language runtimes rarely invoke raw system calls like `clone` directly. When Python imports the `threading` module, Python uses `pthread`, which calls `mmap` to allocate a stack and calls `clone` to start the thread.

---

## 2. Threads and CPU Scheduling

### How a CPU Core Runs Instructions
A physical CPU core runs a continuous four-step loop:

1. Read the address of the next machine instruction from the Program Counter register.
2. Fetch that instruction from memory or CPU cache.
3. Execute the instruction using CPU registers.
4. Advance the Program Counter to the next instruction.

### Switching Between Tasks (Context Switching)
A computer usually has hundreds of tasks running on only a few CPU cores. Linux shares CPU time across tasks:

* **Context Switch**: The kernel pauses the running task, copies its current CPU register values into RAM, and loads the saved register values of the next task onto the CPU core.
* **How Linux Tracks Threads and Processes**:
  * Linux does not use separate data structures for threads. Both processes and threads are instances of `task_struct`.
  * The Linux scheduler shares CPU time across these tasks. **A thread is the smallest unit of execution that Linux schedules on a CPU core.**

### Creating Processes vs Threads (`clone`)
Linux creates both processes and threads using the same system call: `clone()`.

* **New Process**: `clone()` is called without memory-sharing flags. The kernel gives the new process its own memory map. Modifying memory in one process does not change memory in the other.
* **New Thread**: `clone()` is called with flags to share memory (`CLONE_VM`) and share open files (`CLONE_FILES`). The new thread shares the exact same memory pages and file descriptors as the parent process.

### Identifying Tasks: TID vs PID vs PGID
Linux structures execution streams into three distinct tiers:

* **TID (Thread ID)**: The unique number the kernel gives to each individual schedulable thread (`task_struct`). In kernel source code, this field is literally named `pid`.
* **PID (Process ID)**: To user-space programs, this identifies the process. Inside the kernel, this is the `task_struct->tgid` (**Thread Group ID**) field.
* **PGID (Process Group ID)**: A number that groups related processes working together in a terminal pipeline.

#### The Kernel Naming Inversion (`task_struct->pid` vs `task_struct->tgid`)
The POSIX standard specifies that if an application starts multiple threads, all threads must appear to the outside world as a single process with a single PID:

* When the main thread of a process starts, the kernel sets its `pid` and its `tgid` to the same number (`pid == tgid`).
* When that process creates worker threads using `clone(CLONE_VM | CLONE_FILES, ...)`, the kernel assigns each new worker thread a new unique `pid` (its TID), while setting its `tgid` to the parent's `tgid`.
* When user-space code calls `getpid()` (or Python calls `os.getpid()`), the kernel returns the `tgid`.
* When code calls `gettid()` (or Python calls `threading.get_native_id()`), the kernel returns the `pid` (TID).

#### The Execution Hierarchy
```text
[ Process Group: PGID ]  --> Groups related processes running a pipeline
       |
       +--> [ Process: PID / TGID ]  --> Groups threads sharing the same memory
                 |
                 +--> [ Thread: TID ]  --> The single execution unit on a CPU core
```

#### How Process Groups Work in Pipelines
When you run a command like `cat access.log | grep "404" | wc -l`:

* The shell creates three separate processes using `fork()`, each with its own isolated virtual memory space and PID.
* The shell assigns all three processes the same Process Group ID using the `setpgid()` system call, typically using the PID of the first command (`cat`) as the group leader.
* When you press `Ctrl+C`, the kernel terminal driver does not target a single process. It addresses the signal to the entire foreground process group using negative PID notation (`kill(-PGID, SIGINT)`). The kernel delivers `SIGINT` to every task in that PGID, terminating all three pipeline stages simultaneously.

#### Sessions and Controlling Terminals
Above process groups sits the **Session (`SID`)**:

* When a user logs in via SSH or opens a terminal window, the shell initializes a new session via the `setsid()` system call.
* The session connects its process groups to a single controlling terminal (`session->tty`).
* A background daemon disconnects from the terminal by calling `setsid()` to become the leader of a new session with no controlling terminal attached (`session->tty = NULL`), causing `ps aux` to display `?` in the `TTY` column.

### Thread Stacks and Guard Pages
* **Each Thread Gets Its Own Stack**: When a program starts a new thread, the threading library allocates a block of memory for that thread's stack via `mmap()` and passes that memory address to `clone()`. The kernel sets the thread's stack pointer register (`RSP`) to that address.
* **Stack Overflow Protection**: Unlike the main thread stack, secondary thread stacks have fixed sizes and do not grow automatically. The threading library places an unmapped "guard page" with no read or write permissions at the end of the stack. If a thread runs out of stack space and touches this guard page, the CPU raises an exception and Linux stops the program with a segmentation fault (`SIGSEGV`).

### Why Shared Memory Causes Race Conditions
Because threads share the same memory addresses, an operation like `count += 1` is not a single atomic step. The CPU executes it in three separate steps:

1. **Read**: Copy the value of `count` from RAM into a CPU register.
2. **Modify**: Increment the value inside that register.
3. **Write**: Store the updated value from the register back into RAM.

If the kernel switches execution to another thread between step 1 and step 3, both threads read the same initial value and write back the same incremented number, causing lost updates.

---

## 3. Virtual Memory, Paging, and Memory Accounting

### How Virtual Memory Works
Programs do not access physical RAM addresses directly. Every program works with virtual memory addresses:

* **Pages and Frames**: Linux splits memory into 4 KB blocks. Virtual memory is split into 4 KB **pages**, and physical RAM is split into 4 KB **frames**.
* **Page Tables**: The kernel maintains a lookup table (page table) for each process that maps each 4 KB virtual page to a physical 4 KB RAM frame.
* **Hardware Translation**: On every memory read or write, the CPU hardware (the Memory Management Unit, or MMU) translates the virtual address into a physical RAM address using the active page table.
* **Memory Protection**: User programs run in unprivileged CPU mode (User Mode / Ring 3). If a program tries to access an unmapped address or access kernel memory, the CPU blocks the operation and Linux stops the program with a segmentation fault (`SIGSEGV`).

### VSZ vs RSS
When checking memory usage in tools like `ps` or `top`, processes report two different memory numbers:

* **VSZ (Virtual Size)**: The total amount of virtual address space the process has reserved. Claiming virtual address space via `mmap` is cheap because Linux does not assign physical RAM frames until bytes are actually written. For example, runtimes like Node.js reserve several gigabytes of virtual address space on startup for memory management, producing a high VSZ despite using little physical RAM.
* **RSS (Resident Set Size)**: The actual amount of physical RAM currently holding the process's data.
* **Out-of-Memory Impact**: When the Linux Out-of-Memory (OOM) killer selects a process to terminate, it counts real physical RAM usage (**RSS**) plus swap, never virtual address space (VSZ).

### The Page Cache and Memory Inspection (`free -h`)
* **Page Cache**: Linux uses otherwise unused physical RAM to cache disk blocks. When running programs require more RAM for heap or stack memory, Linux immediately drops clean page cache pages to free up physical memory.
* **Dirty Pages**: When a program writes data to a file, Linux writes the data to the RAM page cache first. Background kernel threads flush these modified ("dirty") pages to disk later, or immediately if the program calls `fsync()`.
* **Reading `free -h`**:
  * `used`: RAM currently in use by processes and the kernel (total minus `free` minus `buff/cache`).
  * `buff/cache`: Disk files and filesystem buffers currently held in RAM.
  * `available`: The estimated amount of RAM available for starting new applications without swapping (`free` memory plus page cache that can be dropped).
  * `shared`: Memory shared between multiple processes simultaneously, primarily RAM-backed filesystems (`tmpfs` such as `/dev/shm`, `/run`, and `/tmp`).
* **Why Total RAM Looks Lower Than Sold**:
  * Memory manufacturers measure RAM in decimal gigabytes (`1 GB = 1,000,000,000 bytes`). Linux measures memory in binary gibibytes (`1 GiB = 1,073,741,824 bytes`).
  * A 16 GB memory stick is about 14.9 GiB. Hardware firmware (UEFI/BIOS) and integrated graphics chips reserve additional memory before Linux boots, leaving roughly 14 GiB visible to the operating system.
* **`/tmp` in RAM**:
  * On distributions such as Fedora and Arch (including this machine), `/tmp` is mounted as a RAM filesystem (`tmpfs`, verified via `df -T /tmp`). Files written to `/tmp` take up RAM and are discarded upon reboot.

---

## 4. The OOM (Out Of Memory) Killer

### When the OOM Killer Activates
* **Memory Watermarks**: Linux defines three free-memory thresholds: `high`, `low`, and `min`.
* When free memory drops below the `min` threshold and the kernel cannot reclaim enough pages from the page cache, the kernel invokes the OOM killer **before** free physical RAM reaches zero.
* **Emergency Kernel Reserve (`vm.min_free_kbytes`)**: A dedicated pool of physical RAM reserved exclusively for internal kernel operations and hardware interrupts. If this reserve runs out, kernel memory allocations fail and the kernel logs warnings. It does not crash the machine by default.

### How the Kernel Stops the Process
To eliminate memory overhead during an out-of-memory emergency, terminating a process does not allocate new memory: the kernel flips the pre-allocated `SIGKILL` bit directly inside the chosen victim's `task_struct`.

### How Linux Chooses a Process to Kill
* The kernel calculates a score (`/proc/<pid>/oom_score`, 0 to 1000) based on the process's RSS plus swap and page table memory, as a share of total RAM plus swap.
* The score can be adjusted via `/proc/<pid>/oom_score_adj` (-1000 means "never kill", +1000 means "kill first"). Databases like PostgreSQL often lower this score to avoid termination.
* **Scopes**:
  * **System-wide**: When host RAM and swap are exhausted.
  * **Cgroup Limit**: When a container exceeds its allocated `memory.max` limit, triggering the OOM killer exclusively within that container's cgroup.

---

## 5. Process Lifecycle, System Calls, and Signals

### System Calls (Syscalls)
The only interface for user-space programs to interact with the OS kernel:

1. User code places arguments in registers and executes the `syscall` assembly instruction.
2. The CPU traps from User Mode (Ring 3) to Kernel Mode (Ring 0).
3. The kernel validates permissions, executes the request, writes results to registers, and returns via `sysret`.
* The shell is an ordinary user-space program that uses syscalls; programs like Python or Nginx call syscalls directly without needing a shell.
* Syscalls can be monitored using `strace -e trace=file,network`.

### The `fork` and `execve` Execution Pattern
When running commands like `python script.py > output.log`:

1. **`fork()`**: The shell clones itself into a child process (inheriting identical memory maps and file descriptor tables via Copy-On-Write).
2. **File Descriptor Redirection**: The child process opens `output.log` and uses `dup2()` to replace its standard output (FD 1) with the file descriptor of `output.log`.
3. **`execve()`**: The child replaces its address space with the `/usr/bin/python3` binary. The previous shell code is discarded, but open file descriptors persist across `execve`.
4. **`waitpid()`**: The parent shell pauses until the child process terminates and returns its exit code.

### Signals and the Zombie State
* **Signals**:
  * `SIGTERM` (Signal 15): Graceful termination request. Catchable by application code.
  * `SIGKILL` (Signal 9): Immediate termination executed directly by the kernel. Uncatchable.
  * Exit code rule: A process killed by signal N exits with status **128 + N** (137 for `SIGKILL`, 143 for `SIGTERM`).
* **Zombie State (`Z`)**:
  * When a process terminates, its RAM is freed immediately, but its `task_struct` remains in the kernel process table as a zombie until its parent reads its status via `waitpid()`.
  * **Shell Variable Isolation**: The shell captures the exit code into `$?` and the last background PID into `$!`. These variables reside strictly in that shell's private memory. In a new terminal, `$?` evaluates to `0` and `$!` is empty because each shell runs in an isolated address space.
  * **Parent-Only Reaping**: The Linux kernel permits only the direct parent process to call `waitpid()` and reap the zombie. Once the parent reads the exit code, the kernel deletes the `task_struct` entry entirely. An unrelated terminal or process cannot inspect the exit code of an already-reaped process.

---

## 6. File Descriptors, TTYs, and Terminal Mechanics

### File Descriptors (FDs)
* Non-negative integers referencing entries in a process's kernel file table: `0` (stdin), `1` (stdout), `2` (stderr).
* Inspected via `/proc/<pid>/fd/`.

#### Descriptor Types in `/proc/<pid>/fd/`
A process file descriptor table can reference diverse kernel objects:
* **Standard Streams**: `0 -> /dev/pts/1`, `1` and `2` pointing to terminal devices, log files, or `/dev/null`.
* **Network Sockets (`socket:[...]`)**: Active TCP or Unix domain connections communicating with APIs or local services.
* **Filesystem Watchers (`anon_inode:inotify`)**: Handles used by file-system watching libraries to receive kernel notifications when disk files change.
* **Event Loop Multiplexing (`anon_inode:[eventpoll]`)**: An `epoll` handle. Runtimes use this to monitor hundreds of sockets, pipes, and watchers in a single thread without CPU polling.
* **Inter-Process Pipes (`pipe:[...]`)**: Communication channels between processes or threads, distinguishing the read end (`lr-x`) from the write end (`l-wx`).
* **Lock Files (`.lock`)**: File descriptors held open on disk to enforce single-instance application execution.

#### Descriptor Limits (`EMFILE`)
The Linux kernel limits the maximum number of file descriptors a single process can hold open simultaneously (`ulimit -n`, typically 1024 by default). If a process exhausts this limit, subsequent calls to `open()`, `socket()`, or `accept()` fail with error 24: `EMFILE: Too many open files`.

#### Buffering Mechanics
* `stdout` buffering is performed in user space by the C library (and Python), not by the kernel. On an interactive terminal, output is line-buffered (flushed at each newline). When redirected to a file or pipe, it is block-buffered (held in 4 KB or 8 KB chunks) to minimize system calls.
* `stderr` is unbuffered so error tracebacks write immediately to disk or screen before an unexpected process termination.
* **Where GUI Streams Go**: Graphical applications (such as web browsers) have no terminal window. When launched from a desktop icon, desktop environments redirect `stdout` and `stderr` to `systemd-journald` (`journalctl --user`) or discard them to `/dev/null`. When launched from a terminal, they remain attached to that terminal's pseudo-terminal device.

### Devices vs Processes
* **Devices Never Receive PIDs**: Process IDs (PIDs) belong strictly to schedulable execution tasks (`task_struct`). Devices in Linux are exposed as character or block device files under `/dev/` and identified by **Major and Minor device numbers**.
* **Two Separate Terminal Connections**:
  1. **File Descriptors**: Descriptors 0, 1, and 2 pointing to the device node (`/dev/pts/1`) for reading input and writing output.
  2. **Controlling Terminal Pointer (`session->tty`)**: An internal kernel session pointer in `task_struct`. Even if a program redirects FDs 0 and 1 to disk files (`python script.py < in.txt > out.txt`), this session link remains active.

### The TTY / PTY Subsystem
* The Linux kernel has no concept of graphical desktop windows; windows are rendered in user space by display servers (Wayland or X11).
* The kernel DOES contain the **TTY subsystem** (`drivers/tty/`):
  * **Pseudo-Terminals (PTY)**: Composed of a controller (master) held by terminal emulators or `sshd`, and a device file (slave, e.g., `/dev/pts/1`) connected to process standard I/O.
  * **Controlling Terminal Link (`session->tty`)**: Maintained at the kernel session level independently of file descriptors.
  * **Processes Without a Terminal**: Background daemons call `setsid()` to detach from the session (`session->tty == NULL`), displaying `?` in the `TTY` column of `ps aux`.

### Why the Kernel Treats TTYs Specially
The kernel treats TTY devices differently from regular files or pipes for three concrete reasons:
1. **Emergency Human Intervention**: If a program enters an infinite loop or deadlocks, it stops executing `read()` calls. If a terminal were a regular file or pipe, typing `Ctrl+C` would sit unread in an input buffer. The kernel intercepts `Ctrl+C` at the driver level and delivers `SIGINT` regardless of whether the program is responsive.
2. **Line Discipline (`N_TTY`)**: The kernel handles basic keyboard input rules (echoing characters back to the screen, deleting bytes on Backspace, buffering input until Enter is pressed) so CLI programs do not each have to write their own line-editing logic.
3. **Automatic Cleanup on Disconnect (`SIGHUP`)**: When an SSH session drops or a terminal emulator closes, the kernel detects the disconnected device and automatically delivers `SIGHUP` to all child processes in that session, preventing abandoned background processes.

### Delivery of Terminal Signals and Job Control
* When a key combination is pressed, the terminal emulator (or `sshd`) writes the corresponding byte to the PTY controller, and the kernel's **TTY Line Discipline (`N_TTY`)** intercepts it:
  * Byte `0x03` (`Ctrl+C`) generates `SIGINT` (2).
  * Byte `0x1A` (`Ctrl+Z`) generates `SIGTSTP` (20, terminal stop).
* **Kernel Foreground Enforcement**:
  * The kernel tracks the active foreground process group via the `foreground_pgrp` field on the TTY structure.
  * The shell sets this group using the `tcsetpgrp(fd, pgid)` system call.
  * Signals are delivered directly to that foreground process group.
  * If a **background** process attempts to read from `stdin`, the kernel blocks the process by delivering `SIGTTIN`.
* **Job Suspension (`SIGTSTP`) Mechanics**:
  * Pressing `Ctrl+Z` delivers `SIGTSTP` to the foreground process group.
  * The process transitions into the **`Stopped`** state (`T` in `ps`).
  * The process remains resident in RAM, but the kernel scheduler allocates zero CPU time to it.
  * Resuming execution requires the `SIGCONT` signal, sent when running the shell's `fg` (foreground) or `bg` (background) commands.

---

## 7. Containers, Namespaces, Cgroups, and Mounts

### Container Architecture
A container is not a virtual machine. There is no hypervisor and no secondary kernel. A container is a standard Linux host process isolated via three mechanisms:

1. **Namespaces (Visibility)**: PID (isolated process tree), NET (isolated network interfaces), MNT (isolated mount points), IPC, USER.
2. **Cgroups (Resource Limits)**: Restrict total CPU shares, memory ceilings (`memory.max`), and I/O rates.
3. **OverlayFS (Filesystem)**: Merges read-only image layers with an ephemeral read-write upper container layer via copy-on-write.

### Root Filesystem and System Call Execution
* **Image Rootfs (`pivot_root`)**: A container image is a `.tar` archive containing a standard directory tree (`/bin`, `/usr`, `/lib`, `/etc`). When Docker starts a container, it unpacks these layers under `/var/lib/docker/` and executes the `pivot_root` system call, locking the process into that directory tree so it cannot see the host's `/`.
* **Execution Without an Internal Kernel**: The command binaries inside the container (`/bin/ls`, `/usr/bin/python3`) are native ELF (Executable and Linkable Format: standard binary file format used by Linux) executables. They issue standard Linux system calls. The **host Linux kernel** executes every system call directly because all Linux distributions share the same standard Linux system call ABI.

### Container Lifecycle and Multi-Process Execution
* Containers can run multiple processes (e.g., Gunicorn or Nginx with workers).
* Child processes stay within the container's PID namespace and cgroup.
* Cgroup resource limits apply to the **combined sum of all processes** in that container.
* The container entrypoint is **PID 1** inside its PID namespace. If PID 1 terminates, the kernel terminates all other processes in that namespace.
* **`docker exec`**: Spawns a new host process and uses the `setns()` system call to attach it to the target container's existing namespaces.

### Process Inspection Syntax (BSD vs POSIX)
When inspecting processes on the host or inside a container, `ps` supports two distinct syntax conventions:

* **BSD Style (No Dash, e.g., `ps aux`)**:
  * `a`: Shows processes from all users, not just the current user.
  * `u`: Activates user-oriented columns (`USER`, `%CPU`, `%MEM`, `VSZ`, `RSS`, `STAT`).
  * `x`: Includes processes running without a controlling terminal (`TTY = ?`), such as background daemons and services.
* **POSIX Style (With Dash, e.g., `ps -ef`, `ps -a`)**:
  * `-e`: Selects all processes on the system.
  * `-f`: Generates full-format listing (`UID`, `PID`, `PPID`, `C`, `STIME`, `TTY`, `TIME`, `CMD`).
  * `-a`: Displays processes attached to terminals across users, excluding session leaders.

---

## 8. User Namespaces and Filesystem Mount Permissions

### Numeric Identity vs Usernames
* The Linux kernel evaluates permissions strictly through numeric **UIDs and GIDs**, not text strings.
* Usernames exist only as lookup tables in `/etc/passwd`.
* In the Debian-based official Postgres container images, the `postgres` user is hardcoded to numeric **UID 999** in the Dockerfile. Other image variants use a different UID.
* In standard Docker (user namespaces disabled), container processes run with their raw numeric UID directly on the host kernel.

### Host User Collisions with Container UIDs
When user namespaces are disabled (standard Docker behavior), the container process runs with its raw numeric UID directly on the host kernel. If that numeric UID matches an existing user account on the host (for example, UID 999 belonging to a host account `alice` or a system service):

* **Process Listings (`ps aux`)**: The host `ps` command consults the host `/etc/passwd`. It matches UID 999 to `alice`, displaying `alice` in the `USER` column for the container process on the host.
* **File Permissions on Host Mounts**: If host user `alice` owns private host files set to mode `0600` (readable only by UID 999), and those files or folders are mounted into the container, the container process running as UID 999 has kernel permission to read and modify those files.
* **Signal Delivery**: The Linux kernel permits processes with the same UID to send signals to one another. A local host user with UID 999 can send signals (`kill`) to the container process.

### Path Resolution Inside Mount Namespaces
* When a host directory is bind-mounted (`-v /home/pdev/data:/var/lib/postgresql/data`):
  * The kernel links the directory inode directly to the mount point in the container's mount namespace.
  * Path resolution inside the container evaluates paths starting from the container root:
    `/` -> `/var` -> `/var/lib` -> `/var/lib/postgresql` -> mounted directory inode.
  * **Host parent directories (such as `/home` or `/home/pdev`) do not exist in the container's mount namespace and are never traversed during path resolution.**

### Bind Mount Permission Denied: Root Cause and Resolution
* **The Cause**: The permission error is governed strictly by the **inode permissions of the mounted directory itself**.
  * If `/home/pdev/data` is created on the host owned by UID 1000 with mode `0755` (`drwxr-xr-x`), an unprivileged container process running as UID 999 cannot write inside it (`EACCES`).
* **The Postgres Solution**:
  * By default, the Postgres container starts its entrypoint as **`root` (UID 0)**.
  * The official entrypoint (`docker-entrypoint.sh`) executes: `find "$PGDATA" \! -user postgres -exec chown postgres '{}' +`
  * Because it runs as root, it changes the ownership of the mounted directory inode to UID 999 on disk.
  * The entrypoint then drops privileges via `exec gosu postgres ...` to run the database engine as UID 999.

### Why Named Volumes Avoid Permission Mismatches
* Named volumes are managed by the Docker daemon under `/var/lib/docker/volumes/<vol>/_data`.
* When an empty named volume is initialized, Docker automatically copies the directory permissions and ownership (**`999:999`**) defined in the image layer directly into the volume on disk.
* Because the volume directory inode is pre-configured with matching ownership before container execution, no permission mismatch occurs.

---

## 9. Non-Root Containers, Privileges, and Capabilities

### Running Containers as Non-Root Users
By default, Dockerfile instructions and the resulting container process execute as **`root` (UID 0)**. Running applications as root exposes the host kernel if a container breakout vulnerability occurs.

#### Standard Dockerfile Non-Root Pattern
```dockerfile
FROM python:3.12-slim

# 1. Create a non-root group and user with fixed numeric IDs
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /usr/sbin/nologin appuser

WORKDIR /app

# 2. Copy application source with non-root ownership
COPY --chown=appuser:appuser . /app

# 3. Set the active runtime user
USER appuser

# 4. Entrypoint and commands execute under UID 10001
CMD ["python", "main.py"]
```

### Executing into a Non-Root Container from the Host
Even if a container runs under an unprivileged user (e.g., UID 10001), the host administrator can execute commands as root: `docker exec -u 0 -it <container_name> bash`

* **Mechanism**: The command is initiated by the host Docker daemon (which runs with root authority on the host).
* Docker spawns a brand-new process on the host with `UID 0` and joins it to the target container's namespaces via `setns()`. The unprivileged process inside the container has no mechanism to block this.

### How sudo and Root Privileges Work
In the Linux kernel, **no user other than UID 0 possesses native root privileges**.

* A regular account (e.g., `pdev` with `UID 1000`) cannot execute privileged system calls directly.
* **How `sudo` Works**:
  1. The binary `/usr/bin/sudo` has the **setuid bit** enabled (`-rwsr-xr-x 1 root root /usr/bin/sudo`).
  2. When executed, the kernel sets the process's **Effective UID (EUID)** to `0`.
  3. `sudo` consults `/etc/sudoers` to verify permissions, and upon successful authentication, executes the requested command with UID 0.
* **Linux Capabilities (`man 7 capabilities`)**:
  * Modern kernels decompose root authority into ~40 discrete capabilities (e.g., `CAP_NET_BIND_SERVICE` to bind ports below 1024, `CAP_CHOWN` to alter file ownership).
  * Processes can be assigned specific capabilities without full UID 0 access. Docker uses capabilities to restrict containerized root processes by default.

---

## 10. Storage Architecture: Block Devices, Partitions, Filesystems, and Mounts

### Block Devices
* **Hardware Reality**: Storage media (SSDs, NVMe drives, HDDs, virtual disks) do not store files or directories. They expose an array of fixed-size storage sectors (typically 4,096 bytes) accessed by sector number (`read_block(N)`, `write_block(N)`).
* **Virtual Disks**: Software-emulated block devices presenting files (such as `.img` or `.vmdk` files, or network-attached AWS EBS volumes) to the kernel as standard block devices.
* **Device Names in `/dev`**:
  * `/dev/sda`, `/dev/sdb`: SATA/SCSI SSDs and HDDs.
  * `/dev/nvme0n1`: M.2 NVMe SSDs communicating over PCIe buses.
  * `/dev/xvda`: Virtual disks on cloud hypervisors (AWS EC2).
  * `/dev/nvme1n1`: The second NVMe drive (on this machine, an Intel Optane 3D XPoint caching module).

### Partitions as an On-Disk Standard
A partition is defined by a table written at the start of the drive in a standard format (**GPT / GUID Partition Table** or legacy MBR). GPT uses the first 34 sectors. The drive itself does not know about partitions; the firmware and the OS read this table.

* **Why Partitions Exist**:
  1. **Hardware Boot Requirements**: Motherboard UEFI firmware only reads FAT32 filesystems, requiring a dedicated boot partition (`/dev/nvme0n1p1` mounted at `/boot/efi`).
  2. **Filesystem Independence**: Allows different filesystems (`FAT32`, `ext4`, `NTFS`) to coexist on the same physical drive.
  3. **Failure Isolation**: Runaway log files on `/var/log` cannot exhaust storage on the root partition (`/`) if they occupy separate partitions.
  4. **Preservation**: The operating system on `/` can be wiped and reinstalled without affecting user files on a separate `/home` partition.

### Filesystems (`ext4`, `xfs`)
A filesystem formats raw block devices into structured files and folders:

* **Formatting (`mkfs`)**: Commands like `mkfs.ext4 /dev/nvme0n1p2` write empty superblock metadata, block allocation bitmaps, and Inode tables onto the partition.
* **Inodes**: Metadata structures storing file attributes (UID, permissions, size, timestamps) and direct/indirect pointers to physical data block addresses.
* **Directories**: In Linux, a directory is a file containing an index table mapping text strings to Inode numbers:
  ```text
  "main.py"    --> Inode #4102
  "config.json" --> Inode #4105
  ```

### Mounts and `/etc/fstab`
* Linux organizes all storage under a single tree rooted at **`/`**.
* **What Mounting Means at the VFS Level**:
  * In Linux, filesystems do not have separate drive letters (like `C:` or `D:`).
  * Mounting binds the root inode of a formatted filesystem on a block device to an existing directory (the mount point).
  * When a directory is mounted, the kernel's Virtual Filesystem (VFS) layer intercepts all path lookups entering that directory and redirects them to the mounted storage device.
  * **Hiding Effect**: If the mount point directory already contains files before mounting, those files are not deleted. They become hidden and inaccessible while the filesystem is mounted. When unmounted (`umount`), the original files reappear.
* **The Root Mount (`/`) at Boot**:
  * When the Linux kernel first boots, it runs in RAM with an empty VFS directory tree.
  * The bootloader tells the kernel where the root filesystem lives (e.g., `root=UUID=...` on the kernel command line).
  * The kernel mounts that partition as `/`. This initial mount makes `/bin`, `/lib`, and `/etc` accessible so the kernel can execute `/sbin/init` (systemd).
* **Subfolder Mount Inheritance vs Separate Partitions**:
  * By default, directories like `/home`, `/var`, `/tmp`, and `/usr` are regular folders inside the root partition (`/dev/nvme0n1p2`). Running `df -h /home/pdev` shows that `/home/pdev` resides on the filesystem mounted at `/`.
  * If `/home` is given its own partition (e.g., `/dev/nvme0n1p3`), it is mounted over `/home`. If the operating system on `/` is wiped and reinstalled, the user data on the separate `/home` partition remains untouched.
* **`/etc/fstab` (Filesystem Table)**:
  * A configuration file read during boot by systemd to automatically mount partitions.
  * Partitions are identified by persistent UUIDs rather than device paths (since `/dev/sda` can change order across reboots):
    ```text
    # <device UUID>                           <mount point>  <type>  <options>  <dump> <pass>
    UUID=51720e64-dc2c-4225-91ea-78212a291798 /              ext4    defaults   0      1
    UUID=8a213e44-11fa-4921-99ee-123456789abc /home          ext4    defaults   0      2
    ```
* **RAM-Backed Filesystems (`tmpfs`)**:
  * Not all mounts connect to physical storage drives. A `tmpfs` mount creates a filesystem stored entirely in volatile RAM (and swap).
  * Memory is allocated dynamically: an empty `tmpfs` uses virtually zero RAM, growing only as files are written to it, up to a configured maximum (by default, 50% of physical RAM).
  * Used for `/run` (runtime sockets and PIDs), `/dev/shm` (shared memory), and `/tmp`. Because data is stored in RAM, all files vanish when the computer reboots or powers off.
* **Loop Devices (`-o loop`)**:
  * The Linux VFS can only mount block devices, not regular files.
  * When mounting a disk image file (such as `fallocate -l 200M /tmp/disk.img` formatted with `mkfs.ext4`), passing `-o loop` tells `mount` to attach the file to a virtual loop block device (`/dev/loop0`). The kernel mounts that virtual block device as if it were a physical drive.

### Full Disk Failures (`ENOSPC`)
When a filesystem runs out of storage, the kernel returns **`ENOSPC: No space left on device`** (Errno 28):

1. **Data Block Exhaustion**: All storage blocks are occupied by file data.
2. **Inode Exhaustion**: Even with gigabytes of free disk space, creating millions of tiny files can exhaust the fixed allocation of Inodes (`df -i`).
3. **Database Impact**: If a write to a data file fails, PostgreSQL fails that transaction. If a write to the Write-Ahead Log (WAL) fails, the server shuts down to prevent corruption.
4. **Failure Scope**:
   * If a secondary mount (`/mnt/data`) runs out of space, only the application writing to that mount fails.
   * If the root filesystem (`/`) runs out of space, services that write to `/` (such as logging to `/var/log`) fail.

---

## 11. systemd, Logging, and Resource Throttling

### systemd as PID 1 and Init System
The Linux kernel launches one initial user-space program from `/sbin/init`: `systemd`.

* **Universal Init Standard**: Runs as **PID 1** across all modern mainstream Linux distributions (Ubuntu, Debian, Fedora, Arch, RHEL, CentOS, SUSE).
* **Root Ancestor**: Acts as the parent or ancestor of every user-space process on the operating system.
* **Orphan Adoption and Reaping**: When a parent process terminates without waiting on its children, the kernel re-parents those orphaned children to PID 1. `systemd` runs a continuous event loop calling `waitpid()` to reap dead child processes immediately, preventing zombie (`<defunct>`) accumulation on the host.

### What Is a Daemon
A daemon is a background process that runs continuously to handle system requests, without direct interactive user control.

* **Naming Convention**: In Unix and Linux, daemon program names traditionally end with the letter `d` (such as `systemd`, `sshd`, `dockerd`, `crond`, `systemd-journald`).
* **Terminal Detachment Mechanics**:
  * An interactive command runs attached to a terminal session (`session->tty`).
  * A daemon detaches from the terminal by calling the `setsid()` system call. This makes the daemon the leader of a new session with no controlling terminal (`session->tty = NULL`).
  * Because it has no controlling terminal, `ps aux` displays `?` in the `TTY` column.
  * A daemon redirects or closes standard input (`stdin`, FD 0), standard output (`stdout`, FD 1), and standard error (`stderr`, FD 2) so its execution is never tied to a terminal window or SSH session.

### Targets
* **Target Units**: Synchronization milestones that group multiple services together for a specific operating mode:
  * `rescue.target`: Single-user maintenance state with no network and minimal services; drops into a raw root shell for recovery.
  * `multi-user.target`: Standard multi-user operating state with networking and background daemons active, but without a desktop graphical interface (the standard state for servers).
  * `graphical.target`: Extends `multi-user.target` by starting the display manager and graphical desktop environment (Wayland/X11).
* **Boot Integration**: In a service unit file, the directive `WantedBy=multi-user.target` in the `[Install]` section specifies that this service belongs to the multi-user milestone. Enabling the service creates a symlink inside `/etc/systemd/system/multi-user.target.wants/`, so the service automatically launches whenever `multi-user.target` is reached at boot.

### Service Unit Files (`.service`)
System services are defined in declarative unit files placed in `/etc/systemd/system/` (administrator configurations) or `/usr/lib/systemd/system/` (system package defaults):

```ini
[Unit]
Description=Background Worker
After=network.target

[Service]
Type=simple
User=pdev
ExecStart=/usr/bin/python3 /app/worker.py
Restart=on-failure
RestartSec=5s
MemoryMax=1G
CPUQuota=50%

[Install]
WantedBy=multi-user.target
```

#### Service Supervision and Failure Recovery
* **Process Supervision**: Unlike running a program in a shell (which terminates if the terminal disconnects), `systemd` monitors the service's PID and all child processes within a dedicated cgroup.
* **Automatic Restarts**:
  * `Restart=on-failure`: If the process crashes, exits with a non-zero exit code, or is killed by an unhandled signal (such as an out-of-memory `SIGKILL`), `systemd` detects the termination and automatically restarts it.
  * `RestartSec=5s`: Enforces a 5-second delay before restarting to prevent rapid, runaway CPU loops if the process fails repeatedly.
  * `Restart=always`: Re-executes the service regardless of whether it exited cleanly (`exit 0`) or crashed.

### Service Management CLI (`systemctl`)
`systemctl` is the primary command-line tool used to manage `systemd` units:

* `systemctl start <name>`: Starts a stopped service immediately.
* `systemctl stop <name>`: Stops a running service by sending `SIGTERM` to every process in its cgroup, waiting up to `TimeoutStopSec` (default 90 seconds), and delivering `SIGKILL` if processes do not exit voluntarily.
* `systemctl restart <name>`: Stops and re-executes the service.
* `systemctl status <name>`: Displays the active state, uptime, main PID, memory consumption, cgroup slice hierarchy, and the latest journal log lines.
* `systemctl enable <name>`: Creates symlinks in the target's `.wants/` directory so the service starts automatically during boot.
* `systemctl disable <name>`: Deletes the boot symlinks so the service does not start on boot.
* `systemctl daemon-reload`: Tells `systemd` to scan `/etc/systemd/system/` and re-read all unit files into memory after you create or edit configuration files.

### Unified Logging with `journald` and `journalctl`
`systemd-journald` is the central logging service in modern Linux.

#### Three Core Log Sources
`systemd-journald` collects log streams from three distinct sources into a single unified index:
1. **Application Standard Streams (FD 1 & FD 2)**: Captures `stdout` and `stderr` from all services managed by `systemd` automatically. Applications do not need dedicated file-logging libraries; writing to standard output is automatically ingested.
2. **Kernel Ring Buffer (`/dev/kmsg`)**: Listens to the kernel message buffer, capturing hardware errors, driver events, network interface state changes, and kernel OOM killer actions (`dmesg` stream).
3. **System Logs**: Ingests traditional syslog messages submitted via `/dev/log` or structured logs submitted via the native journal API (`sd_journal_print`).

#### Binary Indexed Storage
* Logs are stored as structured binary files in `/run/log/journal/` (volatile RAM, cleared on reboot) or `/var/log/journal/` (persistent disk).
* Because records are indexed by timestamp, service unit, PID, UID, and priority, queries do not require parsing large text files sequentially.

#### Querying Logs with `journalctl`
* `journalctl -u <unit>`: Filters logs strictly for the specified service unit (e.g., `journalctl -u worker.service`).
* `journalctl -u <unit> -f`: Follows log output in real time as new lines arrive (similar to `tail -f`).
* `journalctl -k`: Queries kernel log messages (`dmesg` stream).
* `journalctl -b`: Shows logs strictly from the current boot cycle. `journalctl -b -1` shows logs from the previous boot.
* `journalctl -p err`: Shows only log messages with priority level error or higher.
* `journalctl --since "1 hour ago"`: Filters logs within a specific time window.

### Resource Limits and Cgroups: systemd and Docker
Linux uses two complementary mechanisms for process control:
* **Namespaces**: Control **visibility** (what a process can see: process table, network interfaces, mounts).
* **Cgroups (Control Groups)**: Control **resource consumption** (what a process can use: CPU time, RAM, PIDs, disk I/O).

#### The Unified Cgroup Hierarchy (`/sys/fs/cgroup/`)
Both `systemd` and Docker interact directly with the Linux kernel cgroup filesystem mounted at `/sys/fs/cgroup/`:

* **systemd Slices**: `systemd` creates a cgroup slice for every service (e.g., `/sys/fs/cgroup/system.slice/worker.service`) and writes configuration directives directly to cgroup controller files:
  * `MemoryMax=1G` writes `1073741824` into `memory.max`. If the process exceeds this limit, the kernel invokes the OOM killer exclusively within that service's cgroup.
  * `CPUQuota=50%` writes `50000 100000` into `cpu.max`.
* **Docker's systemd Cgroup Driver**: On modern Linux installations, Docker uses the `systemd` cgroup driver by default. When Docker starts a container, it requests `systemd` to create the container's cgroup slice, ensuring a single unified resource hierarchy across both host services and containers.

### CPU Limits and Completely Fair Scheduler (CFS) Throttling
CPU limits in cgroups do not alter processor clock speeds (GHz). They are enforced via time allocation in microseconds (us):

* **Period**: The tracking window (defaults to 100,000 us = 100 ms).
* **Quota**: Total CPU runtime allowed during that window.
* **Files**: On this machine, both values are in one file, `cpu.max`. For example, `50000 100000` means a quota of 50,000 us per 100,000 us period. `cpu.cfs_period_us` and `cpu.cfs_quota_us` are the file names in the older cgroup version.
* **Mechanics**:
  * A limit of `0.5 CPUs` (`CPUQuota=50%` or Docker `--cpus=0.5`) sets the quota to 50,000 us.
  * Once the process consumes 50 ms of CPU time within the 100 ms window, the kernel scheduler **throttles** (pauses) the process until the next window starts.
  * A limit of `2.0 CPUs` (`CPUQuota=200%`) allocates a quota of 200,000 us, permitting two threads to execute simultaneously across two separate cores for the entire 100 ms window.
