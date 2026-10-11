# Networking

---

## 1. What a Network Is

### One Computer on Its Own
A program on a computer can read and write that computer's memory and disk, and nothing else. Its processor has no physical path to the memory or disk of any other computer.

### The Problem
Two computers, A and B, sit on a desk. A has a file, and a program on B needs it. Before networks, a person copied the file onto a USB stick or floppy disk, walked it over to B, and plugged it in. That needs a person every time, it is slow, and B cannot ask A for something on its own.

### The Definition
A network is two or more computers joined by a physical connection, plus a set of rules both computers follow, so that a program on A can send bytes and a program on B can receive them, with no person carrying anything.

Once bytes can travel between computers, a program on B can ask A for a file, use a printer attached to A, or ask A to do work and send back the result.

---

## 2. The Cable and What Travels Through It

### The Cable
The physical connection is a cable with copper wires inside. One end plugs into a socket on A, the other into a socket on B.

Behind each socket is a small piece of hardware inside the computer. Its job is to take bytes from the computer's memory and turn them into electrical signals on the wire, and on the receiving side, turn the signals back into bytes in memory.

### What Travels Through It
What travels through the wire is voltage (electrical pressure that can be raised or lowered). A byte is 8 bits, each bit is a 0 or a 1. In the simplest version:

* The sender sets the wire to high voltage for a 1 and low voltage for a 0, holding each level for a fixed short time (for example one billionth of a second).
* The receiver measures the voltage once per time slot and writes down a 1 or a 0.
* Both sides must agree on the time slot in advance. If they do not, the receiver measures at the wrong moments and reads wrong bits.

Real cables use more complicated signal patterns than plain high and low, but the idea is the same: the sender changes the wire's state, the receiver measures it.

### The Problem This Creates
The only thing that crosses from A to B is a long sequence of 0s and 1s. The wire always carries some voltage, even when A has nothing to send. So how does B know where a message starts and where it ends?

---

## 3. Where a Message Starts and Ends

### The Start
The two computers agree on a fixed starting pattern in advance. Before every message, A sends the same bits, for example `10101010` seven times followed by `10101011`.

* B watches the wire all the time. Until it sees this pattern, it ignores whatever voltage is on the wire.
* The alternating `1010...` part also lets B line up its measuring moments with A's timing, because their clocks are never exactly equal.
* The final `11` marks where the pattern ends. The next bit is the first bit of the real message.

### The End
A stops sending, and the wire goes quiet. B notices there are no more changes and knows the message is over. A also leaves a short required gap before the next message, so two messages never run together.

### Frame
The block of bits between the start pattern and the quiet gap is called a **frame**. A frame is one message as it travels on the wire, with a clear start and a clear end.

---

## 4. Detecting Damaged Frames

### The Problem
The wire is a physical object. Electrical noise from nearby cables or motors can change the voltage, so a 1 sent by A can be measured as a 0 by B.

### The Fix
A adds a few extra bytes to the end of every frame, calculated from the rest of the frame's contents. B runs the same calculation on what it received and compares.

Simple version: the message is three bytes, 5, 10 and 20. A adds them, gets 35, and puts 35 at the end. B adds the three bytes itself and compares with 35. If noise changed 10 into 11, B gets 36, the results do not match, and B knows the frame is damaged.

### CRC
Plain addition has a weakness: if noise adds 1 to one byte and subtracts 1 from another, the sum stays the same and the damage is not seen. Real hardware uses a more careful calculation called **CRC** (cyclic redundancy check). It works on the bits, and it is designed so that common kinds of damage almost never produce the same result. On a cable, the CRC is 4 bytes at the end of every frame.

### What B Does With a Damaged Frame
B throws it away. It does not tell A and does not ask for it again. At this level a damaged frame is simply gone. Getting it resent is handled by a different part of the system (section 8).

---

## 5. Both Sides Sending at Once

### The Problem
If there is only one wire and A and B change its voltage at the same time, the two signals mix. B measures a voltage that is neither A's bits nor its own, and both frames are destroyed. This is called a **collision**.

### Old Fix: Take Turns
Early cables used rules each computer followed:

1. Listen to the wire before sending. Only send if it is quiet.
2. While sending, keep measuring the wire. If the voltage does not match what you are sending, someone else is sending too, so stop.
3. Wait a random amount of time, then try again. Each side picks its own random wait, so one of them usually starts first next time.

When only one side can send at a time, it is called **half duplex**.

### Modern Fix: Separate Wires
A normal cable has 8 copper wires inside, arranged in 4 pairs. In the simplest case, one pair carries signals only from A to B, and another pair only from B to A. Both can send at the same moment and the signals never mix. This is called **full duplex**. Faster cables use all four pairs in both directions at once, with electronics that subtract their own outgoing signal from what they measure. The result is the same: no collisions on a direct modern cable.

---

## 6. From the Hardware to the Program

This part happens inside B and uses the kernel, system calls and file descriptors from area 1.

1. **The hardware writes the frame into memory.** At startup, the kernel reserves an area of RAM for incoming frames and gives its location to the hardware. When a frame arrives and passes the CRC check, the hardware writes the bytes directly into that RAM, without the processor copying them one at a time. This is called **DMA** (direct memory access).
2. **The hardware tells the processor.** It sends an electrical signal called an **interrupt**. The processor pauses what it is doing and runs a specific kernel function. That function belongs to the **driver**, the part of the kernel written for this exact model of hardware. The driver knows where the new frame sits in RAM and how long it is.
3. **The kernel finds the receiving program.** A program that wants incoming bytes asks the kernel for them. The kernel creates an object called a **socket** and gives the program a file descriptor pointing to it, the same way `open()` gives a file descriptor for a file. Each socket has its own receive buffer in kernel memory. The kernel copies the frame's bytes into that buffer.
4. **The program reads the bytes.** The program calls `read()` or `recv()` on its file descriptor. That is a system call, so the kernel copies the bytes from the socket's receive buffer into the program's memory. If the buffer is empty, the program blocks (waits) until a frame arrives, the same blocking measured in area 2.

The full path:

```text
wire -> hardware -> RAM (DMA) -> interrupt -> driver -> socket receive buffer -> recv() -> program memory
```

Sending is the same path in reverse: the program calls `send()`, the kernel copies the bytes into its own memory, the driver tells the hardware where they are, and the hardware turns them into voltage on the wire.

---

## 7. Which Program Gets the Frame

### The Problem
B usually runs more than one program that wants to receive bytes, for example a file-sharing program and a chat program. When a frame arrives, the kernel must know which program's socket it belongs to.

### Read, Look Up, Decide
Every machine that handles frames does the same three things:

1. Read a few bytes from the frame's header.
2. Look up those bytes in a table.
3. Make one decision: send the frame out a particular wire, hand it to a particular program, rewrite it, or drop it.

For each new concept below, the useful questions are: which bytes does it read, what table does it use, what decision does it make, and why does that table need to exist.

### Ports
The sender writes a number into the frame that says which program on B the frame is for. This number is a **port**. It is 2 bytes, so it can be 0 to 65535.

* **Header**: a fixed set of bytes at the start of a frame that describes the frame, placed before the message. The frame now looks like this:

  ```text
  [start pattern][receiver port: 2 bytes][sender port: 2 bytes][message bytes][CRC: 4 bytes]
  ```

  The sender's port is there so B can reply to the right program on A.

* **The table**: when a program on B starts, it creates a socket and calls `bind()`, a system call that says "give me every frame marked with port 7000". The kernel adds a row `7000 -> this socket`. The chat program binds to 7001 and gets its own row. Two programs cannot bind the same port, because then the kernel could not choose between them.
* **The decision**: when a frame arrives, the kernel reads the receiver port, finds it in the table, and copies the message into that socket's receive buffer. If no row matches, nobody asked for that port, and the kernel drops the frame.

A knows which port to use by agreement in advance. The program's author documents "we listen on 7000". That is why web servers use port 80 by convention.

Simplification: in real systems, the port numbers do not sit right after the start pattern. They are inside other headers built in later sections. The table idea is the same.

### Several Conversations to the Same Port
A program on A can open 5 conversations at once to the same program on B. Each conversation uses a different port on A's side. When A's program calls `connect()`, A's kernel picks an unused port on A automatically. These automatically picked ports are called **ephemeral ports** (temporary ports).

```text
A:50001 -> B:7000
A:50002 -> B:7000
A:50003 -> B:7000
A:50004 -> B:7000
A:50005 -> B:7000
```

So B's kernel does not look up a frame by B's port alone. It looks up the pair (sender port, receiver port):

* A frame starting a new conversation (section 11) to port 7000 goes to the listening socket, the one B's program called `listen()` on.
* Every other frame goes to the record matching both ports. For example `50003 -> 7000` goes to conversation 3's socket.

B's program gets one file descriptor per conversation, plus the listening one.

Once there are more than two computers, the pair becomes four values: sender computer, sender port, receiver computer, receiver port.

---

## 8. Lost Frames

### The Problem
Noise damages a frame, and B throws it away (section 4). A's program has no idea and assumes the bytes arrived.

### Acknowledgment
When B receives a frame that passes the CRC check, B sends back a small frame meaning "got it". This is an **acknowledgment**, usually shortened to **ack**.

### Timer and Resend
A keeps a copy of every frame it sends and starts a timer, for example 200 milliseconds.

* If the ack arrives before the timer runs out, A deletes the copy.
* If the timer runs out first, A assumes the frame was lost, sends the copy again, and restarts the timer.

The time limit is called a **timeout**. Sending the copy again is called a **retransmission**.

### Sequence Numbers
The ack itself can be destroyed by noise:

1. A sends a frame. B receives it and passes the message to its program.
2. B's ack is lost on the way back.
3. A's timer runs out, so A sends the same frame again.
4. B receives it a second time and passes the same message to its program again. The program now has the data twice.

The fix: A writes a number into each frame's header, 1, 2, 3, and so on. This is a **sequence number**. B remembers the last number it delivered. If frame 2 arrives again, B knows it is a resend. It does not pass the message to the program again, but it does send the ack again, because A clearly never got the first one. The ack carries the number too ("got 2"), so A knows which frame it refers to.

```text
[start pattern][receiver port][sender port][sequence number][message bytes][CRC]
```

In real systems this job belongs to a set of rules called **TCP** (Transmission Control Protocol). TCP numbers bytes, not whole frames. The mechanism is the same three pieces: ack, timeout with resend, and sequence numbers.

---

## 9. Sending Without Waiting

### The Problem
With the rules above, A sends frame 1 and sits idle until the ack comes back before sending frame 2. A 10 MB file means thousands of waits.

### Window
A picks a limit, for example 4: the most frames A may have sent but not yet had acknowledged. This limit is the **window**.

1. A sends frames 1, 2, 3, 4 back to back, keeping a copy and a timer for each.
2. The ack for 1 arrives. A deletes copy 1. Only 3 frames are now unacknowledged, so A may send frame 5.
3. The ack for 2 arrives, so A sends 6. And so on.

The range of frames A may have in flight moves forward by one with each ack, so this is called a **sliding window**.

### Why It Is Faster
Say a 1500-byte frame takes 0.012 milliseconds to put on the wire, and the round trip (frame goes out, ack comes back) takes 1 millisecond. Waiting for every ack means about 0.012 ms sending and about 1 ms idle, so the wire is used about 1% of the time. With a large enough window, A keeps sending while earlier acks are still on their way, and the wire stays busy.

### One Frame in the Middle Is Lost
Frames 1 to 4 are sent, and 2 is damaged and thrown away.

* B receives 1, 3 and 4. It passes 1 to the program. It holds 3 and 4 in its buffer and does not pass them on, because the program must receive bytes in order.
* Each ack B sends says "I have everything up to and including 1". This is a **cumulative ack**: one number that covers everything before it.
* A's timer for frame 2 runs out, A resends 2. Once 2 arrives, B passes 2, 3 and 4 to the program in order and acks "everything up to 4".

Sequence numbers now do two jobs: detect duplicates, and put frames back in order.

### Why Not Ack 3 and 4 Separately
In this design, 3 and 4 never get their own acks. B cannot say "up to 4" while 2 is missing, so it repeats "up to 1". B could ack 3 and 4 individually, and real systems support that as an extra option called **selective ack**. The cumulative ack is the base design for two reasons:

1. **A lost ack does not matter.** If "up to 3" is destroyed and then "up to 4" arrives, the single number 4 tells A that 1 to 4 all arrived. With individual acks, losing the ack for 3 makes A resend frame 3 even though B already has it.
2. **Repeated acks tell A something is missing.** If A receives "up to 1" several times in a row, frames after 1 are arriving but 2 is not. After 3 repeated acks with the same number, TCP resends the missing frame right away instead of waiting for its timer. This is called **fast retransmit**.

The cumulative ack gives A one number with one meaning: everything before this point is safe, delete those copies.

---

## 10. A Slow Receiver

### The Problem
B's socket receive buffer has a fixed size, for example 64 KB. If B's program calls `recv()` slowly and A keeps sending, the buffer fills. The kernel on B has nowhere to put new frames, so it drops them. A gets no acks, resends, and the resent frames are dropped too. The wire is busy but nothing useful gets through.

### The Fix
Every ack B sends carries a second number: how many bytes of free space are left in its receive buffer right now.

```text
ack: "I have everything up to 40, and I have 8000 bytes of free space"
```

That number is the **receive window**. A follows one rule: data sent but not yet acknowledged must never be larger than the free space B last reported. So A's window is not a fixed number like 4. B sets it, and it changes with every ack.

* B's program reads quickly: the buffer stays mostly empty, B reports a lot of space, A sends at full speed.
* B's program reads slowly: the space shrinks, B reports less, A sends less.
* The buffer is full: B reports 0 and A stops. A sends a tiny frame every so often to ask "is there space now?". Once B's program reads some data, B answers with the new free space and A continues.

This is called **flow control**: the receiver controls how fast the sender sends.

### What A's Program Sees
A's kernel also has a send buffer for each socket, holding bytes that are not acknowledged yet. When B reports 0, A's kernel cannot send, so its send buffer fills. Once it is full, the next `send()` in A's program blocks until space frees up. A slow `recv()` on B makes `send()` on A wait.

---

## 11. Starting a Conversation

### What Each Side Needs First
* Data flows in both directions, so each side has its own sequence numbers. A numbers what A sends, B numbers what B sends. Each side must learn the other's starting number.
* Starting numbers are picked at random, not 0. If A and B talked a minute ago on the same ports, a delayed resend from the old conversation could arrive late and fall inside the new conversation's numbers. A random start makes that very unlikely.
* A must know that a program on B is actually waiting on that port.

### Flags
A **flag** is a single bit in the header that marks what kind of frame this is.

* **SYN** (synchronize): "here is my starting number".
* **ACK**: "the ack number in this header is valid".

### The Three Frames
1. A -> B: SYN. "I want to start. My starting number is 1000."
2. B -> A: SYN + ACK. "I got your 1000, I expect 1001 next. My starting number is 5000."
3. A -> B: ACK. "I got your 5000, I expect 5001 next."

Each side must announce its number (2 frames) and get an ack for it (2 frames), which makes 4. B puts its ack and its own announcement in the same frame, so 4 becomes 3. Without frame 3, B would not know whether A received B's starting number. This is the **three-way handshake**.

### What the Programs Do
The kernels do the handshake, not the programs.

* B's program calls `bind()` on port 7000, then `listen()`, which tells the kernel to accept handshakes on that port. Then it calls `accept()`, which blocks.
* A's program calls `connect()` to B's port 7000. A's kernel sends the SYN, and `connect()` blocks until the SYN + ACK arrives.
* When frame 3 reaches B, `accept()` returns a new file descriptor for this conversation.

If no program on B listens on 7000, B's kernel replies with a frame carrying the **RST** (reset) flag, and `connect()` on A fails with `Connection refused`.

### What a Connection Actually Is
After the handshake, nothing on the wire has changed. The "connection" is a record in each kernel's memory: the ports, both sequence numbers, the latest receive window, and the send and receive buffers. Each kernel has its own copy, and the handshake makes the two copies start out in agreement.

---

## 12. Ending a Conversation

### Each Direction Closes Separately
A new flag, **FIN** (finish), means "I have no more data to send". It closes only the sender's direction.

"A is done" means only that A is done sending. A can still receive. After A's FIN:

* B can keep sending data to A for as long as it wants. A's kernel receives and acks it as usual.
* A cannot send more data on this connection. To send more, it must open a new connection with a new handshake.

### The Frames
1. A -> B: FIN. The FIN takes a sequence number like data, so it arrives after all of A's data and is resent if lost.
2. B -> A: ACK for the FIN.
3. On B, the program's next `recv()` returns 0 bytes. That is how a program learns the other side is finished, the same way `read()` on a file returns 0 at the end of the file. B's program sends any remaining data, then closes, and B's kernel sends its own FIN.
4. A -> B: ACK for B's FIN.

If B has nothing left to send, it can put its ACK and FIN in one frame, which makes three.

### Example: Request and Reply
1. A sends "give me file X", then FIN. The FIN means "my request is complete".
2. B's `recv()` returns 0, so B knows it has the whole request.
3. B sends the file, possibly many megabytes, while A's direction is already closed.
4. B closes and sends FIN. A's `recv()` returns 0, so A knows it has the whole file.

### shutdown() vs close()
* `shutdown(fd, SHUT_WR)` sends FIN and closes only A's sending direction. A's program can still call `recv()` and read B's data. The example above uses this.
* `close(fd)` also sends FIN, but A's program gives up the file descriptor completely and cannot read anything anymore. If B sends data after that, A's kernel has no program to deliver it to, and it answers with RST.

The FIN on the wire looks the same in both cases.

### CLOSE_WAIT and TIME_WAIT
Each kernel's record has a field that says which stage the conversation is at. CLOSE_WAIT and TIME_WAIT are two values of that field.

```text
step  frame             A's record      B's record
1     A -> B  FIN       (waiting)
2     B -> A  ACK                       CLOSE_WAIT
3     B -> A  FIN                       (waiting)
4     A -> B  ACK       TIME_WAIT       deleted
      60 seconds later  deleted
```

* **CLOSE_WAIT (on B)**: A's direction is closed, B's is still open. B's kernel is waiting for B's program to close. The kernel cannot send B's FIN on its own, because B's program might still have data to send. If the program never closes, the record stays in CLOSE_WAIT forever. Programs that forget to close sockets pile up these records and use up file descriptors. This is a common bug in real servers.
* **TIME_WAIT (on A)**: both sides are finished, but A keeps the record for 60 seconds (on Linux) before deleting it. Only the side that sent the first FIN does this.

### Why TIME_WAIT Exists
**Reason 1: the last ACK can be lost.** If frame 4 is destroyed, B's timer runs out and B resends its FIN. If A had already deleted its record, A's kernel would not recognize the frame and would answer with RST, so B would see an error even though all data arrived. Because A still has the record, it sends the ACK again.

**Reason 2: old frames must disappear.** A concrete case:

1. Conversation 1 runs between A's port 50000 and B's port 7000. A sends frame 3000, but it gets delayed somewhere. A's timer runs out, A resends it, the copy arrives, and conversation 1 finishes normally.
2. Conversation 2 starts right away on the same ports, 50000 and 7000, with a new random starting number 2500.
3. The delayed old copy of frame 3000 finally arrives. The ports match conversation 2, and 3000 is close to what B expects, so B accepts it. B's program receives bytes from the old conversation mixed into the new one.

While A's record is in TIME_WAIT, A will not start a new conversation on the same port pair, so the delayed copy arrives while there is no matching conversation and is thrown away.

On a single cable between two computers, a frame is almost never delayed that long. It becomes a real problem once there are machines in between that hold frames in queues (sections 14 and 17).

TIME_WAIT is a time-based safeguard. It relies on one assumption: a frame cannot stay in transit longer than some maximum time. TIME_WAIT is set to twice that maximum, rounded on Linux to 60 seconds. The rule that enforces the maximum is in section 18.

### If an Old Frame Does Get Mixed In
* **Its sequence number is outside the range B expects**: B treats it as invalid and throws it away. Nothing goes wrong.
* **Its sequence number is inside the range B expects**: B accepts it. The CRC passes because the frame is not damaged, only from the wrong conversation. The ports match and the number looks valid. B's program receives wrong bytes with no error anywhere.

Linux adds one more check by default: a timestamp in each frame's header, taken from the sender's clock, which only goes up. B remembers the latest timestamp on the connection and drops frames with an older one.

### Why Applications Are Still Reliable
Yes, a frame that passes every check gets delivered to the program. It almost never happens, for two reasons.

**1. Every condition has to be true at once.** The old frame has to:

* be delayed more than 60 seconds. Machines in between normally hold a frame for milliseconds, and frames that pass through too many routers are dropped (section 18).
* arrive while a new conversation uses the exact same port pair. A's kernel picks ports from about 28,000 options and will not reuse a pair in TIME_WAIT.
* carry a sequence number inside the small range B accepts. Sequence numbers run from 0 to about 4.3 billion. If B accepts the next 64 KB, a random old number lands in that range about 1 time in 65,000.
* pass the timestamp check.

**2. Programs that need correct data add their own checks.**

* **TLS** (the encryption used by HTTPS) adds a cryptographic check to every block of data, using a secret key created fresh for each connection. An old frame from a different connection was protected with a different key, so the check fails, and the connection ends with an error instead of delivering wrong bytes.
* **Downloads and package installs** compare a hash of the whole file (for example SHA-256) with a known value and reject the file if they differ.
* **Databases** store their own checksums on pages and log records.

These checks also catch damage TCP misses for another reason. The CRC protects a frame only while it is on the wire. A machine in between with faulty memory can damage the bytes after checking them, and TCP's own checksum is only 16 bits and fairly weak. The general rule: lower layers make errors rare, and a program that cannot accept any errors checks the data itself, end to end.

### Cost of TIME_WAIT
Each record in TIME_WAIT keeps its port pair in use for 60 seconds. Linux picks ephemeral ports from roughly 32768 to 60999, about 28,000 of them. A program that opens and closes thousands of short connections to the same server can use them all up, and then `connect()` fails. This is one reason programs reuse connections instead of opening a new one per request.

---

## 13. Three Computers

### How to Wire Them
* **A cable between every pair** (A-B, A-C, B-C). Each computer needs one socket per other computer. With 50 computers, each needs 49 sockets, and there are 1,225 cables. This does not scale.
* **A box in the middle.** Each computer has one socket and one cable, and every cable goes to a central box with many sockets. The simplest box copies whatever comes in on one socket out of every other socket. These boxes are called **hubs**.

### The Problem
A sends a frame meant for B. The hub copies it to both B and C, so C's hardware receives the same bits as B's. Ports do not help: they pick a program inside a computer. Nothing yet says which computer the frame is for.

### MAC Address
When the hardware behind the socket is manufactured, the factory stores a unique 6-byte number in it, written like `3c:52:82:1a:4f:e0`.

* The first 3 bytes identify the manufacturer. A standards body assigns them so no two manufacturers share them.
* The manufacturer picks the last 3 bytes so none of its products repeat.

This number is the **MAC address** (media access control address). It identifies a piece of hardware, not a program and not a person.

```text
[start pattern][to: 6 bytes][from: 6 bytes][ports][sequence number][message][CRC]
```

When a frame arrives, the hardware reads the 6 bytes after the start pattern and compares them with its own MAC address. If they match, the frame goes to RAM and the kernel as before. If not, the hardware throws it away right there, without interrupting the processor. C still receives the bits of A's frame, but drops it after reading 6 bytes. The "from" address tells B where to send its reply.

### What Is Still Wrong With the Hub
The hub still sends every frame out of every socket. That wastes cable time on computers that will drop the frame, and all computers share one signal path through the hub, so collisions come back.

---

## 14. The Switch

### The Table
A **switch** learns where each computer is by reading the "from" address of every frame that comes in. It keeps a table in its memory: `MAC address -> socket number`. At power on, the table is empty.

A is on socket 1, B on socket 2, C on socket 3.

1. **A sends a frame to B.** The switch reads "from": A's MAC on socket 1, and adds `A -> 1`. It reads "to": B's MAC. No row for B yet, so it copies the frame out of every socket except the one it came in on (2 and 3). This is called **flooding**. C receives the frame and drops it.
2. **B replies to A.** The switch reads "from": B's MAC on socket 2, and adds `B -> 2`. It reads "to": A's MAC, finds `A -> 1`, and sends the frame out of socket 1 only. C never sees it.
3. From now on, frames between A and B go only between sockets 1 and 2. Once C sends anything, the switch adds `C -> 3`.

```text
MAC address          socket
A's MAC              1
B's MAC              2
C's MAC              3
```

Read, look up, decide: the switch reads the 6-byte "to" address, looks it up in the MAC -> socket table, and picks the socket to send out of.

Each row is deleted after about 5 minutes with no frames from that address. If a computer moves to another socket, the old row expires, and the switch learns the new socket from its next frame.

### Why Collisions Go Away
Each socket on the switch has its own path, and every cable is full duplex. A -> B and C -> A can happen at the same moment without mixing.

### One Frame at a Time on Each Cable
If A and C both send to B at the same moment, the switch cannot put both frames on B's cable at once. At any instant a wire has one voltage, so it can carry one bit from one frame. Mixing them would be a collision again.

The switch holds one frame in its memory and sends it right after the other. That holding area is a **queue**.

This is also true of the 5 conversations in section 7. They were all open at the same time, but their frames took turns on the cable:

```text
time ->
[conv 1 frame][conv 3 frame][conv 2 frame][conv 1 frame][conv 5 frame]...
```

A 1500-byte frame takes about 0.012 milliseconds on a 1 Gbit/s cable, so the turns are short enough that all conversations seem to move forward together. This is the concurrency vs parallelism difference from area 2: the conversations are concurrent (all in progress), but on one wire in one direction they are never parallel (sent at the same instant).

### When the Queue Fills
If A and C each send at the full cable speed of 1 Gbit/s, together they try to put 2 Gbit/s into B's cable, which carries 1 Gbit/s. Half the frames must wait, the queue fills, and once it is full, the switch drops new frames. TCP's acks and resends recover them. TCP also has a separate mechanism that detects this and slows the senders down. It is different from flow control, which only protects B's buffer. Not covered yet.

---

## 15. Finding a MAC Address

### The Problem
The frame needs B's MAC address in its "to" field. A's program only knows it wants "computer B". It does not know a 6-byte number stored in B's hardware at the factory, and that number changes whenever B's hardware is replaced.

### IP Address
Whoever sets up the network gives each computer a number and stores it in that computer's kernel settings:

```text
A: 192.168.1.1
B: 192.168.1.2
C: 192.168.1.3
```

This is an **IP address** (Internet Protocol address): 4 bytes, written as four numbers from 0 to 255. It is chosen by people, so it stays the same when B's hardware is replaced. A's program says "connect to 192.168.1.2, port 7000". The bigger reason IP addresses exist is in section 16.

### ARP
A's kernel keeps a table `IP address -> MAC address`. At first B is not in it, so A asks:

1. A sends a frame with "to" set to `ff:ff:ff:ff:ff:ff`, a special MAC address meaning "everyone". All hardware accepts it, and the switch always floods it. This is a **broadcast**. The message says: "Who has 192.168.1.2? Reply to 192.168.1.1 at MAC `aa:aa:...`."
2. C sees the IP is not its own and ignores it.
3. B sees its own IP. B saves A's IP and MAC in its own table, since it needs them to reply, then sends a normal frame to A's MAC only: "192.168.1.2 is at MAC `bb:bb:...`."
4. A adds `192.168.1.2 -> bb:bb:...` to its table and can now fill in the "to" field of its real frame.

```text
IP address      MAC address
192.168.1.2     bb:bb:bb:bb:bb:bb
```

Rows expire after a few minutes without use, and A asks again when needed, so replaced hardware is picked up automatically. The table can be seen with `ip neigh`.

This set of rules is **ARP** (Address Resolution Protocol). A **protocol** is a set of rules two computers agree on: the format of each message and what to do when one arrives. TCP and ARP are both protocols.

---

## 16. Computers in Another Building

### The Problem
A second switch in another building has its own computers, D, E and F. Broadcasting "who has this IP?" to every computer in every building, and eventually the whole world, is not possible.

### Why Not Just Connect the Two Switches
Switches connected to each other learn MAC addresses and flood broadcasts across both. That works for a few hundred computers. But every switch would need a row for every computer, and every ARP broadcast would reach every computer. At world scale, neither is possible. The groups must be kept separate, with something between them that forwards frames but not broadcasts.

### Group the IP Addresses
```text
Building 1: A 192.168.1.1, B 192.168.1.2, C 192.168.1.3
Building 2: D 192.168.2.4, E 192.168.2.5, F 192.168.2.6
```

A group of computers that can reach each other through switches alone, and that all receive each other's broadcasts, is a **local network**. Each local network gets its own address **prefix** (the shared first part of the address).

### The Router
A **router** is a computer with two sockets: one cabled to building 1's switch, one to building 2's switch. Each socket has its own MAC address and its own IP address, for example `192.168.1.254` on the building 1 side.

### A's Decision
A's kernel settings say two things: "my local network is everything starting with 192.168.1", and "for anything else, send to 192.168.1.254". That router address is the **default gateway**.

* **To B (192.168.1.2)**: same prefix, so ARP for B's MAC and send directly.
* **To D (192.168.2.4)**: different prefix, so send it to the router.

### Two Addresses With Two Jobs
For the frame to D, A puts the router's MAC in "to MAC", because the router is the next machine that should pick it up, and D's IP in "to IP", because D is the final destination.

```text
[start][to MAC][from MAC][from IP][to IP][ports][sequence number][message][CRC]
```

* MAC addresses say which machine on this cable takes the frame next. A MAC address only has meaning inside one local network.
* IP addresses say where the frame should end up. An IP address has meaning everywhere.

### What the Router Does
1. Its building 1 socket receives the frame. "To MAC" matches its own, so it accepts it.
2. It reads "to IP" (192.168.2.4) and looks it up in its table:

   ```text
   prefix          send out of
   192.168.1.x     socket 1
   192.168.2.x     socket 2
   ```

3. 192.168.2.x matches socket 2. Using ARP on building 2, the router finds D's MAC.
4. It builds a new frame: "from MAC" is its own socket 2 MAC, "to MAC" is D's MAC. The IP part, ports and message are unchanged. A new CRC is calculated, and the frame goes out of socket 2.

D's kernel sees its own IP in "to IP" and delivers the message to the program on the right port.

### Why the Router Finds D's MAC and Not the Switch
The router is a member of building 2's local network itself: its socket 2 is cabled to building 2's switch, like D's socket. It is inside two local networks at once, one per socket. From socket 2, D's MAC is a local address, the same way B's MAC is local to A.

A switch only reads MAC addresses. It reads "to MAC", looks it up in its MAC -> socket table, and sends the frame out. It never reads IP addresses and never does ARP. If the frame reaching building 2's switch did not already have D's MAC in "to MAC", the switch would have nothing to look up.

The rule: whoever sends a frame onto a cable writes the "to MAC" for the next machine on that local network.

* In building 1, A is the sender and writes the router's MAC.
* In building 2, the router is the sender and writes D's MAC.
* The switches only move the frame to the socket that matches "to MAC".

### The Router's Two Tables
* **Routing table** (prefix -> socket): answers "which socket does this frame go out of?". One row per local network.
* **ARP table** (IP -> MAC): answers "what MAC goes in 'to MAC' for the last step?". It holds only computers on local networks the router is cabled to, and only ones that exchanged frames recently. Rows expire after a few minutes.

In the two-building setup, the router can end up with a MAC address for every computer in both buildings, because it is cabled into both.

The routing table is why IP addresses exist. Building 2 could have 200 computers, and the routing table still needs one row for all of them. This matters for routers that are not cabled to D's building (section 17): they need only the prefix row and never store D's MAC. Only the last router, the one cabled to D's local network, needs D's MAC.

---

## 17. Networks Not Cabled to the Router

### The Setup
Building 3 has computers starting with `192.168.3`, for example G at 192.168.3.7. Building 3's switch is cabled to a second router, R2. R2 is cabled to the first router, R1, by its own short cable. That cable is a tiny local network of two machines with its own addresses: R1's end is `10.0.0.1`, R2's end is `10.0.0.2`.

```text
building 1 --- R1 --- R2 --- building 3
               |
          building 2
```

### A New Kind of Row
```text
prefix          send to                 out of
192.168.1.x     directly                socket 1
192.168.2.x     directly                socket 2
192.168.3.x     next router 10.0.0.2    socket 3
```

* **Directly**: the destination is on a local network cabled to this socket, so the router uses ARP to find the destination computer's MAC.
* **Next router**: the destination is further away, so the router uses ARP to find the next router's MAC.

### A Frame From A to G
1. A: the prefix is not 192.168.1, so A sends to its default gateway. "To MAC" = R1's MAC, "to IP" = G.
2. R1 reads "to IP", finds the 192.168.3.x row, sees "next router 10.0.0.2", finds R2's MAC with ARP on socket 3, and writes R2's MAC into "to MAC". "To IP" is still G.
3. R2 reads "to IP". In R2's table, 192.168.3.x is "directly" on one of its sockets, so it finds G's MAC with ARP and sends the frame to G.

Each router also writes its own MAC into "from MAC", using the MAC of the socket it sends out of:

```text
step         from MAC              to MAC     from IP   to IP
A -> R1      A                     R1 (s1)    A         G
R1 -> R2     R1 (socket 3)         R2         A         G
R2 -> G      R2 (building 3 side)  G          A         G
```

The MAC pair is rewritten at every step. Both IP addresses stay the same the whole way. When G receives the frame, "from MAC" is R2's, but "from IP" is still A's, so G knows the frame came from A and where to reply.

Each router only decides the next step. None of them knows the whole path.

### The Default Route
A router cannot list every network in the world. Its table can have one row that matches any address, usually written `0.0.0.0/0`. This is the **default route**: "if no other row matches, send it to this next router".

A's default gateway is just this row in A's own routing table. A computer runs the same lookup as a router, but its table usually has two rows:

```text
192.168.1.x       directly
everything else   next router 192.168.1.254
```

It can be seen with `ip route`.

When several rows match, the most specific one wins. A frame for 192.168.3.7 matches both `192.168.3.x` and "everything else", so the `192.168.3.x` row is used.

### How the Rows Get There
On small networks, a person types them in. On large networks, routers send each other messages like "I can reach 192.168.3.x, send it through me", and each router builds its table from them automatically. The internet does this between companies with a protocol called BGP (Border Gateway Protocol). Not covered here.

---

## 18. Loops and the Hop Counter

### Why a Loop Happens
Each router only follows its own table. It does not remember frames it has already seen, and it does not know the full path. It reads "to IP", finds the matching row, and sends the frame where the row says.

Say someone made a mistake typing R2's table. It should have:

```text
192.168.3.x     directly, socket 2
```

But it has:

```text
192.168.3.x     next router R1
```

R1's table is correct:

```text
192.168.3.x     next router R2
```

Follow one frame for G (192.168.3.7):

1. R1 receives it. Its row says "send to R2".
2. R2 receives it. Its wrong row says "send to R1".
3. R1 receives the same frame again. It does not know it has seen it before. Its row still says "send to R2".
4. R2 sends it back to R1 again.

Nothing in either table changes, so this repeats forever. Every pass uses time on the cable between them. Each new frame for building 3 joins the loop and never leaves. The cable and the routers' queues fill, and frames for every other destination start getting dropped too.

### The Fix: TTL
The frame carries a small number in the IP part of its header. Every router subtracts 1 before forwarding, and a router that gets it to 0 throws the frame away. Starting at 3:

```text
A sends the frame            number = 3
R1 subtracts 1, forwards     number = 2
R2 subtracts 1, forwards     number = 1
R1 subtracts 1, gets 0       throws the frame away
```

The field is called **TTL** (time to live). The original design meant seconds. In practice every router subtracts 1, so it counts router steps, called **hops**.

TTL does not fix the wrong table row. It only makes sure a looping frame eventually disappears. A person or the automatic messages between routers still have to fix the row.

### Why Frames Hop at All
There is no single cable from a laptop to a server in another country. The world is made of many local networks joined by routers, and the frame must cross many routers in a row:

```text
your laptop -> your home router -> your internet provider's routers -> ... -> the server's router -> server
```

Each router moves the frame one step closer, like R1 and R2 did for A -> G.

### 64 Is a Limit, Not a Target
Linux starts TTL at 64. A normal frame does not hop 64 times. It passes through however many routers are on the path, and the leftover count does not matter. A frame to a server in another country might pass about 15 routers and arrive with 64 - 15 = 49 left. Only a looping frame counts all the way to 0. 64 is comfortably more than any real path needs, and small enough that a looping frame disappears quickly.

TTL is also the rule behind the TIME_WAIT assumption in section 12: a frame can only be forwarded a limited number of times, and each router holds it briefly, so it cannot stay in transit forever.

### ICMP
When a router throws a frame away because its TTL reached 0, it sends a short message back to the original sender: "I threw away your frame because its count ran out". Without it, the sender would only know that no reply came, not why. **ICMP** (Internet Control Message Protocol) is the name for the format of short status and error messages like this one. `ping` also uses ICMP.

---

## 19. How the Header Parts Fit Together

### Same Fields, Grouped
Nothing here is new. The frame carries the same fields built in earlier sections, grouped by who reads them.

### Building a Frame for `hi`
A's program sends the two letters `hi` to B. The kernel on A builds the frame one step at a time.

1. The program gives the kernel `hi`.
2. The TCP code puts the port and sequence fields in front:

   ```text
   [from port 50001, to port 7000, seq 1001] hi
   ```

3. The IP code puts the IP fields in front of that:

   ```text
   [from IP 192.168.1.1, to IP 192.168.1.2, TTL 64] [from port 50001, to port 7000, seq 1001] hi
   ```

4. The hardware puts the MAC fields in front and the CRC at the end:

   ```text
   [to MAC bb.., from MAC aa..] [from IP .., to IP .., TTL 64] [from port .., to port .., seq ..] hi [CRC]
   ```

The last line is the frame that goes on the cable. Each group is added by a different piece of the kernel. B's kernel reads it from left to right and removes one group at a time: first the MAC group, then the IP group, then the TCP group, until only `hi` is left for the program.

Putting one group inside another like this is called **encapsulation**. Each group is called a **layer**.

### "What Is Inside" Fields
When B's kernel removes the MAC group, the next bytes are just bytes. The kernel cannot tell what they are by looking at them. They might be an IP group, or an ARP question, which has a different layout. So each group carries one small field that says what the next group is.

* In the MAC group, a field called **type**:

  ```text
  0x0800  -> an IP group comes next
  0x0806  -> an ARP message comes next
  ```

* In the IP group, a field called **protocol**:

  ```text
  6   -> a TCP group comes next
  17  -> a UDP group comes next
  ```

**UDP** (User Datagram Protocol) is a simpler protocol than TCP. It has ports like TCP, but no handshake, no acks, no sequence numbers and no resends.

The frame for `hi` with these fields:

```text
[to MAC bb.., from MAC aa.., type 0x0800] [from IP .., to IP .., TTL 64, protocol 6] [from port .., to port .., seq ..] hi [CRC]
```

How B reads it:

1. Reads the MAC group. Type is `0x0800`, so it passes the rest to the IP code.
2. The IP code reads the IP group. Protocol is `6`, so it passes the rest to the TCP code.
3. The TCP code reads the ports, finds the socket, and puts `hi` in its receive buffer.

If the type had been `0x0806`, step 1 would have passed the rest to the ARP code, and there would be no IP or TCP group at all.

### Who Reads Which Group
* A switch reads only the MAC group.
* A router removes the MAC group, reads the IP group, subtracts 1 from TTL, and adds a new MAC group. It never reads the TCP group.
* Only the two end computers read the TCP group.

---

## 20. Telling Conversations Apart

### The Problem
Section 7 looked up conversations by a pair of ports. With more computers, A and C each pick their own temporary port, and nothing stops them from picking the same number:

```text
A: 50001 -> B: 7000
C: 50001 -> B: 7000
```

A frame arrives at B with ports `50001 -> 7000`. By ports alone, B cannot tell whether it belongs to A's conversation or C's.

### Four Values
B's kernel looks up each frame by four values: from IP, from port, to IP, to port. All four come from the frame itself, from the IP group and the TCP group.

```text
from IP        from port   to IP          to port   socket
192.168.1.1    50001       192.168.1.2    7000      conversation with A
192.168.1.3    50001       192.168.1.2    7000      conversation with C
```

The ports match, but "from IP" differs, so these are two different conversations. Each row is one connection. Two connections can share up to three of the four values.

### Two Earlier Points, Updated
* TIME_WAIT (section 12) blocks reuse of the same four values, not just the same two ports.
* The limit of about 28,000 ephemeral ports applies per destination. A can have up to 28,000 connections to B's port 7000, and another 28,000 to some other server, because the "to" values differ.

Each line in `ss -tan` output is one of these rows: local address and port, then remote address and port.

---

## 21. How Big a Frame Can Be

### The Limit
On a normal cable network, everything after the MAC group in one frame (IP group, TCP group and program bytes) can be at most 1500 bytes. This limit is the **MTU** (maximum transmission unit).

Why there is a limit:

* The hardware and switches reserve fixed-size memory slots for incoming frames, so they need to know the largest size in advance.
* While one frame is on the cable, every other frame for that cable waits in the queue. A 10 MB frame would block everyone else for its whole length.
* If noise damages one bit, the CRC fails and the whole frame is thrown away. Losing and resending 1500 bytes costs much less than losing 10 MB.

### A 10 MB send()
The TCP code cuts the bytes into pieces that fit:

```text
1500 bytes allowed
- 20 bytes IP group
- 20 bytes TCP group
= 1460 bytes of program data per frame
```

That 1460 is the **MSS** (maximum segment size). Each side tells the other its MSS inside the SYN during the handshake. 10 MB / 1460 is about 7,200 frames.

### What the Sequence Number Counts
TCP numbers bytes, not frames (section 8). With a starting number of 1001:

```text
frame 1: seq 1001, carries bytes 1001 to 2460
frame 2: seq 2461, carries bytes 2461 to 3920
frame 3: seq 3921, ...
```

The sequence number is the number of the first byte in the frame. An ack says "the next byte I expect is 3921", meaning everything before 3921 arrived.

### What the Programs See
* **A**: `send()` copies the bytes into A's send buffer. If 10 MB does not fit, it either blocks until there is space, or returns early saying how many bytes it took, and the program must call it again with the rest. Python's `sendall()` repeats the call itself.
* **B**: B's program does not see 7,200 frames. It sees one long stream of bytes. One `recv(4096)` returns up to 4096 bytes from whatever has arrived, which may be part of one frame or pieces of several. Where A's `send()` calls started and ended is not kept.

So if A sends two separate messages, B can receive them joined in one `recv()` and cannot tell where the first one ends. Each program protocol must mark its own message boundaries. This is roadmap experiment 2, "No message boundaries".

---

## 22. Full Queues in the Middle

### The Problem
The receive window (section 10) only protects B's buffer. It does not protect the queues on switches and routers in between. When A and C both send at full speed into B's cable (section 14), B's buffer can have plenty of space while the switch's queue in front of B's cable is full and dropping frames. Nothing in the middle sends A a message about it.

### What A Can See
A cannot see the switch's queue. It sees only the result: frames get dropped, so acks stop coming or the same ack repeats. TCP treats a lost frame as a sign that something on the path is overloaded. A full queue somewhere on the path is called **congestion**.

### A Second Limit
A keeps its own estimate of how much data the path can carry at once, called the **congestion window**. Data sent but not yet acknowledged must stay under both limits, B's receive window and A's congestion window, whichever is smaller.

### How A Adjusts It
1. **Start small.** A new connection starts at about 10 frames (Linux's default).
2. **Grow quickly while nothing is lost.** For every frame acked, A raises the window by one frame. In practice it doubles every round trip: 10, 20, 40, 80. This phase is called **slow start**, even though it grows fast. The name comes from starting at 10 frames rather than at full speed.
3. **Cut back on loss.** When a frame is lost, A shrinks the window, by about half in the classic version, or to about 70% in Linux's default.
4. **Grow slowly after that.** A raises the window gradually and backs off again at the next loss.

A keeps raising its speed until it fills a queue somewhere, backs off, then raises it again. When A and C both send into B's cable, each loses frames and backs off, and over time each ends up with roughly half the cable. This whole mechanism is **congestion control**.

### A Practical Result
Every new connection starts at 10 frames and works its way up. A short connection sending a few hundred KB may finish before reaching full speed. This is one more reason programs reuse one connection for many requests.

---

## 23. Why Both Switches and Routers

### The Home Box
The box at home called a "router" is several devices in one case:

* **A router**: one socket (often labeled WAN) connects to the internet provider. The router part moves frames between the home local network and the provider's network, using IP addresses.
* **A switch**: the group of sockets usually labeled LAN, often 4. Computers plugged into those talk to each other through the switch part, using MAC addresses, without the router part reading IP at all.
* **Other services**: handing out IP addresses automatically (section 26), and NAT (not covered yet).

Separate switches are common in offices and data centers. A data center rack usually has a 48-socket switch at the top connecting all servers in that rack, with a few cables from it to routers.

### Two Different Jobs
* **A switch** joins computers inside one local network. It reads only 6 bytes and looks them up in a table it fills in by itself, so it needs no setup and is cheap per socket.
* **A router** joins different local networks. It reads the IP group, uses prefixes, subtracts from TTL, rewrites the MAC group, and does not forward broadcasts. It needs configuration and does more work per frame.

A home needs one small local network, so both jobs fit in one box. A large building has many local networks, so it uses many switches and a few routers between them.

---

## 24. Switches Cabled in a Circle

### Why a Circle
As a backup. If switch 1 connects to switch 2 through one cable and that cable breaks, the two halves cannot reach each other. An extra cable that forms a circle gives a second path.

```text
   switch 1
   /      \
switch 2 -- switch 3
```

### What Goes Wrong
A, on switch 1, sends an ARP broadcast. A switch always floods a broadcast out of every socket except the one it came in on.

1. Switch 1 sends it to switch 2 and switch 3.
2. Switch 2 floods it to switch 3. Switch 3 floods it to switch 2.
3. Each floods its copy back to switch 1, which floods those again.

Copies go around in both directions forever. A router would stop this with TTL, but the MAC group has no counter, and switches do not read the IP group. Each new broadcast adds more copies. Within seconds the cables are full and normal frames cannot get through. Switch MAC tables also break, because a switch sees A's MAC arriving from different sockets one moment to the next. This is a **broadcast storm**.

### The Fix
Switches send each other small messages and agree on one switch as the center, the one with the lowest ID number. Each switch keeps active only its shortest path toward the center and turns off forwarding on any extra socket that would close a circle:

```text
   switch 1  (center)
   /      \
switch 2 xx switch 3     (xx = turned off)
```

Now there is exactly one path between any two switches, so a frame cannot come back around. The cable between switch 2 and switch 3 stays plugged in but carries no traffic. If the cable between switch 1 and switch 2 breaks, the switches notice the missing messages and turn the extra socket back on, so switch 2 is reached through switch 3.

This protocol is **STP** (Spanning Tree Protocol). "Tree" means a layout with no circles.

---

## 25. Why MAC Is Needed When IP Exists

A switch could map IP addresses to sockets instead of MAC addresses. There are three reasons it does not.

**1. The frame needs a "next machine" field separate from the final destination.** For A sending to G (section 17), "to IP" is G's IP the whole way. On building 1's switch, the frame must go to R1, not G, and G is not even on that switch. A switch looking only at "to IP" would look for G and find no socket. So the frame needs one field for "the next machine on this cable" and a separate one for "the final destination". The MAC address is the first. Without it, another field would be needed for the same job.

**2. A computer must send frames before it has an IP address.** A newly plugged-in laptop often has no IP yet, and gets one by sending a frame that asks for one (section 26). It needs an address that already exists, and the MAC address is stored in the hardware at the factory. ARP is the same kind of case: an ARP message has no IP group at all and travels with MAC addresses only.

**3. The cable layer was designed to carry more than IP.** When this frame format was created in the 1970s and 80s, several competing protocols ran on the same cables, and IP was only one of them. That is what the type field (section 19) is for. Switches and hardware deliver frames using only the MAC group, whatever is inside. The hardware can throw away frames for other computers by comparing 6 bytes at a fixed position, without understanding any protocol.

The IP address says where the frame should end up. The MAC address says which machine on this cable takes it next.

---

## 26. Getting an IP Address Automatically

### The Problem
So far a person typed each computer's settings. A computer needs three:

```text
my IP address        192.168.1.23
my local network     everything starting with 192.168.1
default gateway      192.168.1.254
```

Typing them is slow and mistakes are easy. If two computers get the same IP, frames for that IP reach whichever one answered ARP last. A laptop moving between places would need new settings each time.

### Where the Settings Live
A computer's settings are stored in its own kernel. A person can set them in two ways:

* With commands that change the kernel's tables directly. These are lost on reboot.

  ```bash
  sudo ip addr add 192.168.1.5/24 dev eth0
  sudo ip route add default via 192.168.1.254
  ```

  The first gives the cable socket `eth0` the address 192.168.1.5 and the local network prefix. The second adds the "everything else -> 192.168.1.254" row to the routing table, which is the default gateway.

* In a settings screen or file that a program reads at startup and turns into the same commands. On a Linux desktop like Ubuntu: Settings -> Network -> IPv4, switch "Automatic (DHCP)" to "Manual", and type the address, prefix and gateway.

Either way, the result ends up in the kernel. `ip addr` shows the address, and `ip route` shows the default gateway row.

### The Fix: Ask Everyone
It is the same trick as ARP: ask everyone, and the one who knows answers. One machine on the local network chooses settings for the others. At home, that is the home router box. It keeps a list of addresses already handed out, so it never gives the same one twice. This machine is a **DHCP server** (Dynamic Host Configuration Protocol).

The laptop does not know anyone's address yet, not even the router's. But it knows its own MAC address, because it is stored in the hardware.

1. **Laptop -> everyone** (a broadcast, like ARP): "My MAC is `aa:aa:...`. I need settings."
2. **Router -> that MAC**: "Use 192.168.1.23. Your local network is 192.168.1. Your gateway is 192.168.1.254."

The laptop's kernel stores the three settings, and from then on works like A in the earlier sections.

The real protocol uses four messages, not two. The extra two are the laptop saying "I am taking this one" and the router saying "confirmed". They exist because a network can have more than one DHCP server, and the laptop must say whose offer it took. The messages use UDP (section 19).

### The Lease
The address is loaned for a set time, for example 24 hours. This is the **lease**. Halfway through, the laptop asks the server to extend it. If the laptop leaves and stops asking, the lease runs out and the address can go to another computer.

### When the Messages Happen
* Right when the laptop connects. When the cable is plugged in, the hardware detects a signal from the other end, and a program on the laptop (NetworkManager on most Linux desktops) sends message 1. All four messages usually finish in well under a second.
* At boot, if the cable is already plugged in.
* Halfway through the lease, when renewing. The laptop already knows the server and its own address, so it skips the first two messages and sends only "I would like to keep 192.168.1.23" directly to the server, which confirms.

When reconnecting to a network used before, the laptop often asks for its previous address, and the server usually gives it back if no one else has it.

### Where the DHCP Server Sits
* It must be on the same local network. The laptop's first message is a broadcast, and routers do not forward broadcasts. A DHCP server in building 2 would never hear a laptop in building 1.
* Its own IP is typed in by hand, since it cannot ask anyone. At home, the DHCP server is the home router box, so its address is the same as the default gateway, for example 192.168.1.254. Addresses typed in by hand are **static addresses**. Machines that others need to find at a known address (routers, DHCP servers, printers, servers) usually get static addresses.

### Why IP Inside a Local Network
With only one local network and nothing else, MAC addresses alone could deliver every frame. IP is needed because of routers: it is the address that still means something after the frame leaves the switch.

Programs always use IP addresses, whether the destination is on the same switch or in another country. A program calls `sock.connect(("192.168.1.2", 7000))` and never sees or handles a MAC address. The kernel does the rest:

1. It looks up 192.168.1.2 in the routing table. It matches "192.168.1.x, directly", so this machine is on the same local network.
2. It looks up 192.168.1.2 in the ARP table, or sends an ARP broadcast if it is not there, and gets that machine's MAC.
3. It puts that MAC in "to MAC" and sends the frame through the switch straight to that machine.

If the IP were outside the local network, step 1 would match the "everything else" row, and step 2 would look up the default gateway's MAC instead.

---

## 27. What /24 Means

### Prefix Length
An IP address is 4 bytes, which is 32 bits. `192.168.1.23` is just those 4 bytes written as numbers.

`/24` means "the first 24 bits are the local network part". 24 bits is exactly the first 3 bytes. So `192.168.1.0/24` means every address whose first 3 bytes are `192.168.1`, the exact form of "everything starting with 192.168.1". The last byte identifies each computer, and one byte holds 256 values:

```text
192.168.1.0/24  covers  192.168.1.0  to  192.168.1.255   (256 addresses)
```

Two are reserved: `.0` is the name of the local network itself, and `.255` means "every computer on this local network" at the IP level. So 254 are usable.

### Other Sizes
A smaller number after the slash means fewer fixed bits and more addresses:

```text
/24   first 3 bytes fixed    256 addresses
/16   first 2 bytes fixed    65,536 addresses
/8    first 1 byte fixed     about 16.7 million addresses
```

The number does not have to fall on a byte boundary. `192.168.1.0/26` fixes the first 26 bits, leaving 6 bits for computers, and 6 bits hold 64 values. So it covers `192.168.1.0` to `192.168.1.63`. This is how one block of addresses is split into smaller local networks.

### How the Kernel Uses It
To check whether an address matches a row, the kernel compares only the first N bits and ignores the rest. A laptop's routing table, as `ip route` prints it:

```text
default via 192.168.1.254 dev eth0
192.168.1.0/24 dev eth0
```

* The second line is the "directly" row: any address whose first 24 bits match is on the local network.
* `default` is the "everything else" row. As a prefix it is `0.0.0.0/0`. Zero bits have to match, so every address matches it. When several rows match, the one with the larger number after the slash wins, because it is more specific.

### Subnet Mask
A **subnet mask** is another way of writing the same information as `/24`. It is a 4-byte number, written like an IP address, where every bit in the network part is 1 and every bit in the computer part is 0. For `/24`:

```text
11111111.11111111.11111111.00000000
   255  .   255  .   255  .    0
```

So `255.255.255.0` and `/24` mean the same thing. The `/24` form counts the 1s instead of writing them out. Both are in use.

The kernel combines an address with the mask bit by bit. Where the mask has a 1, the address's bit is kept. Where it has a 0, the bit becomes 0. What remains is the local network part:

```text
192.168.1.23   with mask 255.255.255.0   ->  192.168.1.0
192.168.2.4    with mask 255.255.255.0   ->  192.168.2.0
```

The first matches the local network (`192.168.1.0`), so it is local. The second does not, so it goes to the default gateway.

"Subnet" is short for subnetwork: one local network, especially one made by splitting a larger block of addresses, like the `/26` split above.

---

## 28. Two Computers Without a Cable

### The Setup
Two laptops, A and B, in one room. No cable, no other devices nearby, no encryption. A's program sends `hi` to B's program, as in section 19.

### What Replaces the Cable
On the cable, A's hardware raised and lowered the voltage on a copper wire, and B measured it at the other end of the same wire.

Each laptop has a **wireless chip**: a piece of hardware like the one behind the cable socket, connected to a short piece of metal called an **antenna**.

* **Sending**: the chip pushes an electric current back and forth along A's antenna, very fast. A current that keeps changing direction produces a **radio wave**: changing electric and magnetic force that spreads out from the antenna in every direction at the speed of light. It does not need air.
* **Receiving**: when the wave reaches B's antenna, it creates a very small current in that metal, swinging back and forth at the same rate. B's chip measures that small current.

```text
cable:     A's chip -> voltage on copper -> B's chip
wireless:  A's chip -> current in A's antenna -> wave through the room -> small current in B's antenna -> B's chip
```

---

## 29. Frequency and Channels

### Frequency
How many times per second the current swings back and forth is the **frequency**. Laptop wireless chips use about 2.4 billion or 5 billion swings per second, written **2.4 GHz** and **5 GHz** (gigahertz, billions per second).

An FM radio set to 98.3 measures only waves swinging 98.3 million times per second and ignores waves at other frequencies. A wireless chip works the same way: it can be set to measure one frequency, and waves at other frequencies do not disturb that measurement.

### Channels
The frequencies a chip can use are divided into numbered slots called **channels**:

```text
2.4 GHz group:   channel 1 = 2.412   channel 6 = 2.437   channel 11 = 2.462   (billion per second)
5 GHz group:     channel 36 = 5.180  channel 40 = 5.200  channel 44 = 5.220
```

A and B must use the same channel to hear each other. "Agreed frequency" means exactly that: both chips are set to the same channel. Choosing the same channel replaces plugging in a cable. In the sections below, both use channel 36.

In a real building, many devices use the same few channels, and everyone close enough to hear each other on one channel shares it. That is why wireless in a crowded building is slower. Not covered yet. The sections below stay with A and B only.

---

## 30. Putting Bits on the Wave

### Time Slot
On the cable (section 2), A held the wire at high or low voltage for a fixed short time, then set the next value. B measured once during each of those short times. That fixed short time is a **time slot**: the stretch of time during which A sends one value and B measures one value.

```text
time slot:   |  1st  |  2nd  |  3rd  |  4th  |
cable:         high    low     low     high
bits:          1       0       0       1
```

Wireless uses time slots the same way. During one time slot, A keeps its wave the same. In the next slot, it can change it.

### Level
On the cable, A had two choices per time slot: high voltage or low voltage. Each of those choices is a **level**.

On wireless, the wave's swings can be big or small. In each time slot, A makes the swings one agreed size. Each agreed size is a level. With two levels:

```text
small swings  ->  0
big swings    ->  1
```

### More Than Two Levels
If A and B agree on four sizes instead of two, one time slot carries 2 bits:

```text
size 1 (smallest)   ->  00
size 2              ->  01
size 3              ->  10
size 4 (biggest)    ->  11
```

* 2 levels: 1 bit per time slot.
* 4 levels: 2 bits per time slot.

The number of time slots per second stays the same, so 4 levels carry twice as many bits per second.

Real chips change both the size of the swings and the timing of the swings, so they have more combinations than this. The slowest setting uses 2 combinations (1 bit per time slot). The fastest on modern chips uses 1024 combinations (10 bits per time slot).

---

## 31. Weak Signal and Noise

### Signal
The **signal** is A's wave as it arrives at B's antenna, seen by B's chip as a small current swinging back and forth. **Signal strength** is how big those swings are. It depends on distance and walls, and A cannot change it:

* The wave gets weaker the further it travels.
* Walls absorb part of it.

### Noise
B's measurement is never perfectly exact. There is always some tiny random electrical activity on every frequency, from electronics and the environment. This is **noise**. It adds a small random amount to what B measures, and its size does not depend on how far away A is.

### Why Far Away Needs Fewer Levels
The numbers below are made-up units for how big the swings are when they reach B. They are only there to compare sizes. Noise adds or subtracts up to 2 units.

**B is far, so A's levels arrive small.** With 4 levels (2 bits per time slot):

```text
level arrives as:   0    3    6    9
means:              00   01   10   11
```

A sends the level that arrives as 6 (bits `10`). Noise adds 2, so B measures 8. 8 is closer to 9 than to 6, so B reads `11`. Wrong bits.

With 2 levels (1 bit per time slot):

```text
level arrives as:   0    9
means:              0    1
```

A sends the level that arrives as 9. Noise subtracts 2, so B measures 7. 7 is still much closer to 9 than to 0, so B reads `1`. Correct.

With fewer levels, the levels are further apart, so noise cannot push one level close to another.

**B is close, so the same levels arrive 10 times bigger.**

```text
4 levels arrive as:   0    30   60   90
```

Noise is still at most 2 units. 60 plus 2 is 62, which is still clearly 60. So 4 levels or more read correctly, and A can put more bits in each time slot.

```text
close:   strong signal -> more levels -> more bits per time slot -> more bits per second
far:     weak signal   -> fewer levels -> fewer bits per time slot -> fewer bits per second
```

Fewer bits per time slot does not make the signal stronger. It makes a weak signal readable. That is why wireless gets slower in a far room. A cable does not have this problem, because its signal strength stays the same.

---

## 32. Telling B the Speed of Each Frame

### The Cable: Agreed Once
On a cable, the speed is agreed once, when the cable is plugged in. Before any frames are sent, the two pieces of hardware exchange short signals listing the speeds each supports, for example 100 Mbit/s and 1 Gbit/s, and both pick the highest one they have in common. This is **auto-negotiation**. After that, every frame uses that speed for as long as the cable stays plugged in. The start pattern (section 3) only marks the start and lines up timing.

### Wireless: Chosen Per Frame
The signal strength changes all the time: someone walks between the laptops, a door closes, a laptop is carried to another room. A speed that worked a second ago may now produce wrong bits. So A's chip picks the number of levels again for each frame, based on how well its recent frames got through.

B cannot know in advance which setting A picked. If B measured with the wrong setting, it would read wrong bits. So every wireless frame starts with two parts, both sent at the slowest setting, which both chips know in advance:

```text
[start pattern][short header: speed + length][rest of the frame at that speed]
 ^--- both sent at the slowest setting ---^
```

* **Start pattern**: same job as on the cable. It marks the start and lets B line up its measuring moments with A's.
* **Short header**: "the rest of this frame uses this many bits per time slot" and "the rest is this many bytes long".

B's chip reads the short header, switches its measuring to that setting for the rest of the frame, and from the length knows when the frame will end.

---

## 33. Busy and Quiet

### The Problem
Waves are always present on every channel, at least as noise. So "is the other laptop sending right now?" cannot mean "is there any wave at all?".

### What the Chip Measures
B's chip keeps measuring how strong the wave is on channel 36:

```text
A is sending a frame       strong wave       -> busy
nobody is sending          only noise        -> quiet
```

* **Quiet**: nothing stronger than noise. It does not mean zero waves.
* **Busy**: the strength is above a fixed limit built into the chip, or the chip recognizes the start pattern of a frame, even a weak one.

With only A and B, "busy" means "the other laptop is sending right now". This is the same as on the cable, where some voltage was always on the wire and B ignored it until it saw the start pattern.

---

## 34. Finding Each Other

### The Problem
With a cable, a person plugged A into B, and that decided who is connected. In the air there is no plug. B does not know that A exists or which channel A uses.

### A Announces Itself
About 10 times per second (every 102.4 milliseconds), A's chip sends a short frame called a **beacon**, whether or not anyone is listening:

```text
to MAC:      ff:ff:ff:ff:ff:ff     (everyone, like the ARP broadcast)
from MAC:    aa:aa:aa:aa:aa:aa     (A's wireless chip)
name:        "a-laptop"            (typed by a person in A's settings)
channel:     36
```

A wireless chip has a 6-byte MAC address stored at the factory, the same as cable hardware (section 13).

The name is the **SSID** (service set identifier). It is the name that appears in a laptop's list of wireless networks.

### B Looks for Announcements
B does not know A's channel, so it tries them one at a time: set the chip to channel 1, listen for about a tenth of a second, note any beacons, then channel 6, and so on through every channel. This is **scanning**. B ends up with a list:

```text
name        MAC                  channel
a-laptop    aa:aa:aa:aa:aa:aa    36
```

That list is what is shown when you click the wireless icon. To save time, B can also send a short "is anyone here?" frame on each channel and listen for replies instead of waiting for beacons.

### B Joins
A person on B picks "a-laptop". B's chip switches to channel 36 and sends a frame to A's MAC: "I want to join". A replies "accepted". This is the wireless version of plugging in the cable. From then on, A and B send frames to each other's MAC addresses on channel 36.

---

## 35. The Wireless Frame

A's kernel builds the TCP group and the IP group exactly as on the cable (section 19). Only the outer group, built by the wireless chip, is different:

```text
cable:     [start pattern][to MAC][from MAC][type 0x0800]                                   [IP group][TCP group] hi [CRC]
wireless:  [start pattern][short header][kind][to MAC][from MAC][hw seq][type 0x0800]      [IP group][TCP group] hi [CRC]
```

* **start pattern** and **short header**: section 32.
* **kind**: data, ack, beacon, or join request. On the cable every frame carried data, so this field was not needed.
* **to MAC / from MAC**: same as on the cable.
* **hw seq**: a hardware-level sequence number (section 39).
* **type 0x0800**: same as on the cable, an IP group comes next.
* **CRC**: the same 4-byte damage check.

The real wireless frame also has a third MAC field. It is used only once a box in the middle is involved. Not covered here.

---

## 36. Why They Must Take Turns

### One Channel, Two Laptops
The cable had separate wire pairs for each direction, so A and B could send at the same moment (full duplex, section 5). The air has one channel 36, shared by both. If A and B send at the same moment on the same channel, the two waves add together, and each receives a mix that is neither frame. This is a **collision** again. So only one can send at a time: half duplex.

### Why a Collision Cannot Be Detected
On the old shared cable (section 5), a computer kept measuring the wire while sending and stopped when it noticed a collision. Wireless cannot do that:

* While A is sending, its own wave at its own antenna is millions of times stronger than B's wave arriving from across the room. A cannot measure B underneath it.
* Most chips use the antenna for either sending or receiving, not both at the same time.

So A has no way to notice a collision while sending. The rules must avoid collisions before they happen, and A learns that a frame arrived only when B replies.

---

## 37. The Sending Rules

These times are for 5 GHz channels. A **microsecond** is one millionth of a second.

1. **Listen.** A's chip measures channel 36. If it is busy, A waits until it is quiet.
2. **Fixed wait.** A waits until the channel has been quiet for 34 microseconds.
3. **Random wait.** A picks a random number from 0 to 15 and counts down that many slots of 9 microseconds each. It counts only while the channel stays quiet. If B starts sending, A pauses the countdown and continues later from where it stopped (section 38).
4. **Send.** When the countdown reaches 0, A sends the whole frame. It cannot detect a collision, so it does not stop partway.
5. **B checks.** B's chip checks the CRC. If it fails, B drops the frame and does nothing else.
6. **B acks.** If the CRC passes, B's chip waits 16 microseconds and sends a short frame with kind = ack and to MAC = A.
7. **No ack.** If no ack arrives shortly after A's frame ends, A assumes the frame was damaged. It doubles the random range (0 to 31, then 0 to 63, and so on) and goes back to step 1. After a fixed number of tries (often 7), it gives up on that frame.

These rules are called **CSMA/CA** (carrier sense multiple access with collision avoidance). "Carrier sense" means listening to the channel before sending.

### Why B Waits Exactly 16 Microseconds
16 microseconds is about the shortest time B's chip needs to do three things after A's frame ends:

1. Finish receiving the last bits.
2. Check the CRC.
3. Switch the antenna from receiving to sending.

The number is fixed in the standard, so both chips know it in advance. It has no other meaning.

---

## 38. The Waits in Order

### Example
A has two frames to send. B has one frame of its own to send to A. A's first frame has just ended.

```text
time (microseconds)       what happens
0                         A's frame 1 ends, channel quiet
16                        B's chip sends the ack for frame 1
                          (B's own frame must wait 34 + random, so it cannot go first)
ack ends                  channel quiet
then 34                   A (frame 2) and B (its own frame) both finish the fixed wait
                          A picked 3 random slots, B picked 11
then 27 (3 slots)         A's count reaches 0, A sends frame 2
                          B has counted 3 slots, sees the channel busy, pauses with 8 left
frame 2 ends              B does nothing while frame 2 is on the air
then 16                   B's chip sends the ack for frame 2
ack ends                  channel quiet
then 34                   fixed wait done
then 72 (8 slots)         B's count reaches 0, B sends its own frame
then 16 after it ends     A's chip sends the ack for B's frame
```

### Why Each Wait Exists
* **The ack waits 16, new data waits at least 34.** The ack always goes before any new data frame, so A learns right away that its frame arrived. If the waits were equal, B's own data frame could start first, A would see no ack, and A would resend a frame B already has.
* **Random wait.** A and B both finish the fixed 34 at the same moment. Without a random part, they would start at the same moment and collide every time. With 3 and 11, A goes first, and B sees the channel busy and holds off.
* **B continues from 8 instead of picking a new number.** B already waited through 3 slots. If A has a third frame, A must pick a new number from 0 to 15, for example 12. B has only 8 left, so B goes first. Keeping the leftover count means the one that has waited longer gets its turn sooner, and neither laptop keeps the channel all the time.
* **B does not count while A's frame is on the air.** B continues counting only after A's frame has ended, the ack has been sent, and the channel has been quiet for the fixed 34 again.
* **Doubling the range after a failure.** If A and B still collide, picking from 0 to 31 makes it less likely they pick the same number again.

---

## 39. The Hardware Ack and hw seq

### Why the Chip Sends the Ack
16 microseconds is not enough for an interrupt, the driver and the kernel's code to run. The wireless chip has its own small processor running its own small program, separate from the main processor and the kernel. So the chip builds and sends the ack by itself.

```text
                  hardware ack (wireless)         TCP ack (kernel)
built by          B's wireless chip               B's kernel TCP code
covers            one frame, just received        bytes, by sequence number
travels           only from B's antenna to A's    to the other program's computer
sent after        16 microseconds                 usually within milliseconds
```

The hardware ack only means "the frame reached my antenna undamaged". TCP still runs above it unchanged, because the frame can still be lost afterwards, for example when B's kernel drops it because the socket's receive buffer is full (section 10).

On the cable, a damaged frame was dropped silently and TCP noticed later (section 8). Wireless adds a per-frame ack because collisions and noise are much more common in the air.

### Why hw seq
B's ack itself can be damaged. Then A gets no ack, resends, and B receives the same frame twice. B's chip sees the same hw seq number as the last frame from A and drops the copy. It still sends an ack again, because A clearly did not get the first one. This is the same problem and fix as section 8, handled again at the chip level, so the kernel rarely sees duplicates.

---

## 40. The Full Path for `hi`

```text
1.  A's program calls send("hi").
2.  A's kernel adds the TCP group and the IP group (same as the cable).
3.  A's driver hands the bytes to the wireless chip.
4.  A's chip adds the wireless group (kind = data, to MAC = B, from MAC = A, hw seq) and the CRC.
5.  A's chip listens on channel 36, waits 34 microseconds of quiet, then its random slots.
6.  A's chip sends the start pattern and short header at the slowest setting, then the rest
    of the frame at the setting it picked, as changes in the wave on channel 36.
7.  B's antenna picks up the wave. B's chip reads the short header, switches to that setting,
    reads the rest of the bits, and checks the CRC.
8.  16 microseconds after the frame ends, B's chip sends an ack to A.
9.  A's chip gets the ack and moves on to its next frame.
10. B's chip copies the frame into RAM (DMA) and interrupts the processor.
11. B's driver and kernel remove the wireless group, the IP group and the TCP group.
12. B's kernel puts "hi" into the socket's receive buffer. TCP sends its own ack later.
13. B's program calls recv() and gets "hi".
```

Steps 1 to 3 and 10 to 13 are the same as on the cable (section 6). Steps 4 to 9 are the wireless part. The program cannot tell whether a cable or the air carried its bytes.

---

## 41. Cable and Wireless Side by Side

```text
                       cable                               wireless
carries bits           voltage on copper                   radio wave on a channel
finding each other     a person plugs in the cable         beacon, scanning, join
speed                  agreed once at plug-in              chosen per frame, stated in the short header
speed vs distance      fixed                               slower when far or behind walls
both send at once      yes (separate wire pairs)           no (one channel, take turns)
noticing a collision   no collisions on modern cables      cannot detect, so avoid it
per-frame "got it"     no                                  yes, from B's chip after 16 microseconds
duplicate check        only TCP's                          hw seq, plus TCP's
```

---

## 42. Others Nearby Can Receive Every Frame

### The Problem
The wave goes in every direction. Any device nearby set to channel 36 receives every bit A and B send. On a cable, someone would have to physically plug into the wire.

### Encryption
The bits cannot be kept from a nearby receiver, but A and B can change the bytes so they are useless without a secret number only A and B know. Tiny version, with the secret number 7:

```text
A's program sends     h    i
as byte values        104  105
A adds 7              111  112     <- what goes through the air
B subtracts 7         104  105  ->  h  i
```

Turning bytes into unreadable bytes with a secret is **encryption**. The secret is the **key**. Turning them back is **decryption**. A one-byte key has only 256 possible values, so a nearby laptop could try all of them. Real wireless chips use a method called **AES** with a 16-byte key, which has far too many possible values to try, and mixes the bytes so patterns in the original do not show.

The MAC group stays readable, because B's chip must read "to MAC" before doing anything else. A nearby laptop can still see which two devices are talking, when, and how much, but not what they say. The wireless security setting shown as "WPA2" or "WPA3" in a laptop's settings is the set of rules that does this. With no password set (an "open" network), the bytes go through the air unencrypted.

### Wireless Encryption vs TLS
On a cable there is normally no encryption at the cable level. Without TLS, raw bytes travel on the copper. (An optional cable-level encryption, MACsec, exists, but is mostly used in data centers and large companies.)

```text
                      who encrypts           protects
wireless (WPA2/3)     the wireless chip      only the air between two antennas
TLS                   the programs           the whole path, program to program
```

Wireless encryption ends at the receiving antenna. If the frame continues over a cable, it travels raw there. TLS is encrypted by A's program and decrypted only by the program on the final computer, across every cable, air step and router in between. The two are used together.

---

## 43. Three Laptops on One Channel

### The Setup
A third laptop, C, is in the same room as A and B, also on channel 36. C joins the same way B did (section 34): it scans, hears the beacon on channel 36, sends "I want to join", and gets "accepted".

### The Air Already Does the Hub's Job
On the cable, one wire has only two ends, so three computers needed a hub (section 13). The hub copied every frame to every socket, and each computer kept only frames whose "to MAC" was its own.

In the air, A's wave spreads in every direction. Every frame A sends reaches both B's antenna and C's antenna. No box is needed for that.

```text
        A  ---- wave ---->  B
         \
          ---- wave ---->  C
```

A sends `hi` to B, with "to MAC" = B:

```text
                            B's chip                                C's chip
hears the start pattern     yes                                     yes
receives the whole frame    yes                                     yes
CRC correct                 yes                                     yes
"to MAC" is mine?           yes                                     no
result                      keeps it, acks after 16 microseconds    drops it, no ack
```

C receives every frame, the same as a computer behind a hub, and keeps only its own.

### What Changes: Busy Is Busy for Everyone
With two laptops, "busy" meant "the other laptop is sending to me". Now, while A sends to B, the channel is busy for C too. C has to wait even though the frame is not for C. All three laptops share the time on one channel.

---

## 44. Why Nobody Can Start in the Ack Gap

### The Problem
C sees A's frame end, then a 16 microsecond gap, then B's ack. Why can C not start sending inside that gap?

### The Two Waits
B waits 16 microseconds before its ack. C must see 34 microseconds of quiet in a row before it may even start its random countdown (section 37). 16 is less than 34, so B's ack always starts before C's wait can finish.

Say A's frame takes 200 microseconds and an ack takes about 44:

```text
time (microseconds)   air                     B                              C
0 to 200              busy, A's frame         receiving                      waiting, channel busy
200                   A's frame ends          checks CRC, switches antenna   starts counting quiet, needs 34
200 to 216            quiet                   preparing the ack              has counted 16 of 34
216                   busy, B's ack starts    sending the ack                count broken at 16, must start again from 0
216 to 260            busy, B's ack           sending the ack                waiting, channel busy
260                   ack ends                done                           starts counting quiet again from 0
260 to 294            quiet                                                  counts 34 of quiet
294 onward            quiet                                                  counts its random slots, then sends
```

C's 34 must be quiet in a row. B's ack breaks it at 16, so C can never reach 34 inside the gap.

### If C Were Allowed to Send After 16
C's frame and B's ack would start at the same moment. Both waves arrive at A's antenna together and mix, and A can read neither:

* A gets no ack, so it resends `hi`. B drops the copy using hw seq (section 39), but the resend wasted channel time.
* C's frame also mixed at its receiver, so C gets no ack either and must resend.

The 16 vs 34 difference does one job: the time right after a frame belongs to that frame's ack, and no one else can start then.

---

## 45. Why Not Put Each Pair on Its Own Channel

A laptop's wireless chip measures one channel at a time (section 29). If A and B used 36 and C used 40, C's chip would measure only 40 and never receive anything A or B send. For A to reach C, one of them would have to switch channels, and while a chip is set to the other channel, it misses every frame sent on its own.

So laptops that all need to reach each other stay on one channel and take turns.

---

## 46. Two Senders Pick the Same Random Number

### The Setup
After an ack ends, both A and C have a frame to send. Both count 34 microseconds of quiet, and both happen to pick 5 random slots.

```text
time after quiet starts   A                          C
0 to 34                   counts quiet               counts quiet
34 to 79                  counts 5 slots x 9         counts 5 slots x 9
79                        count reaches 0, sends     count reaches 0, sends
```

Both waves are on the channel at once. At each receiver they mix, and the CRC fails.

### The Whole Frame Is Wasted
Neither A nor C can notice the collision while sending (section 36). Each one's own wave is millions of times stronger at its own antenna. So both send their whole frame. On the old shared cable, a collision was noticed partway through and the sender stopped early. In the air, the full frame time is lost.

### Recovery
Both wait for an ack, get none, and follow the existing rule (section 37, step 7):

1. Double the range to 0 to 31 and pick again. For example, A picks 12 and C picks 25.
2. A reaches 0 first and sends.
3. C sees the channel busy with 13 slots left and pauses. It continues after A's frame, the ack, and 34 microseconds of quiet.

### How Often It Happens
```text
range     choices   chance both pick the same
0 to 15   16        1 in 16, about 6%
0 to 31   32        1 in 32, about 3%
0 to 63   64        1 in 64, about 1.5%
```

With two laptops this rarely mattered, because B was usually only sending acks. With three, two senders often want the channel at the same time, so this happens more.

---

## 47. Laptops That Cannot Hear Each Other

### The Setup
A and C are at opposite ends of a long house, with B in the middle:

```text
A ------ 15 m ------ B ------ 15 m ------ C
         A's wave reaches B         C's wave reaches B
A's wave is too weak at C, and C's wave is too weak at A
```

At C's antenna, A's wave is weaker than the busy limit (section 33), so to C it is the same as noise.

### What Goes Wrong
A's frame takes 200 microseconds:

```text
time (microseconds)   A                         C measures       C                                       at B
0                     starts sending to B       only noise       not sending                             A's wave
50                    still sending             quiet            wants to send to B, counts 34 of quiet  A's wave
84                    still sending             quiet            picks 3 random slots, counts 27         A's wave
111                   still sending             quiet            sends to B                              A's and C's waves mix
200                   frame ends, waits for ack                  still sending                           CRC fails for both
```

B cannot read either frame and sends no ack. A and C both double their range and try again.

### Why the Random Wait Does Not Help Here
When all three hear each other, A and C collide only if both reach 0 in the same 9 microsecond slot. Otherwise the later one sees the channel busy and pauses.

Here C never hears A, so C's countdown never pauses. They collide whenever C starts at any moment during A's 200 microsecond frame. 200 microseconds is about 22 slots. With a range of 0 to 15, almost any number C picks lands inside A's frame. Doubling the range helps slowly, and every failed try wastes a whole frame.

### Name
A **node** is any device that sends and receives on the network, here a laptop. This is the **hidden node problem**: C is hidden from A and A is hidden from C, but both reach B.

The cable did not have this. Through a hub, every computer received every frame, so "busy" was the same for everyone.

---

## 48. RTS and CTS

### The Idea
B is the only one that hears both A and C. So B announces how long the channel will be busy. A first asks B for permission with a short frame. B answers with a short frame that both A and C receive, and that answer carries a time. C treats the channel as busy for that time, even though C hears only noise.

### Two New Kinds of Frame
The "kind" field (section 35) gets two more values:

```text
kind                       sent by    means                         size
RTS (request to send)      A -> B     "I want to send you a frame"  20 bytes
CTS (clear to send)        B -> A     "go ahead"                    14 bytes
```

### One New Field: Duration
Right after "kind", every frame carries a **duration**: a number of microseconds. It says how long the channel stays busy after this frame ends, until the whole exchange is finished.

```text
[start pattern][short header][kind][duration][to MAC][from MAC][hw seq]...
```

### The New Busy Rule
When a chip receives a frame that is not for it, it reads the duration and starts a timer. Until the timer runs out, the chip treats the channel as busy, no matter what its antenna measures. A chip now has two ways to decide busy:

1. It measures a wave (section 33).
2. Its timer is still running.

### Timeline
A has a 200 microsecond data frame for B. At the slowest setting, an RTS takes about 52 microseconds, and a CTS and an ack about 44 each.

```text
time (microseconds)   air                          A                  B               C
before 0              quiet                        34 + random slots
0 to 52               A's RTS, duration 336        sends RTS          receives it     hears nothing
52 to 68              gap                                             waits 16
68 to 112             B's CTS, duration 276        receives it        sends CTS       receives CTS, sets timer to 112 + 276 = 388
112 to 128            gap                          waits 16                           timer running: busy
128 to 328            A's data                     sends hi           receives it     hears nothing, timer says busy
328 to 344            gap                                             waits 16        timer says busy
344 to 388            B's ack                      receives it        sends ack       timer says busy
388                   quiet                        done                               timer ends, starts counting 34 of quiet
```

Where the durations come from:

```text
RTS duration = 16 + CTS 44 + 16 + data 200 + 16 + ack 44 = 336
CTS duration = 16 + data 200 + 16 + ack 44             = 276
```

### What Can Still Go Wrong
C cannot hear A's RTS, so C may still send during it, and the RTS collides. But the RTS is 52 microseconds, not 200. A gets no CTS, doubles its range and tries again. The time lost is one short RTS instead of one full data frame.

### Cost
Every frame now needs an RTS, a CTS and two 16 microsecond gaps first: 52 + 16 + 44 + 16 = 128 microseconds extra. For a small frame that is more than the frame itself. So chips use RTS and CTS only for frames above a set size, and the size is a setting in the chip.

---

## 49. The Access Point

### The Problem
RTS and CTS stop A and C from talking over each other. But if A wants to send `hi` to C, A's wave never reaches C at all.

Laptops do not forward frames for each other. Your laptop does not pass along someone else's frames.

### The Box in the Middle
The fix is a small box placed in the middle of the space, whose only job is to be the center of the wireless network. It is an **access point**.

* It sends the beacons (section 34). Every laptop joins the access point, not another laptop.
* Every frame goes laptop -> access point -> laptop. A never sends straight to C, even when A and C are side by side.

### What It Fixes
* **Reach**: the access point sits in the middle, so A and C can exchange frames even when they cannot hear each other.
* **Hidden laptops**: A and C may still not hear each other, so they can still both send to the access point at the same time. But every laptop hears the access point, so when the access point sends a CTS, all of them receive it and set their timers. RTS and CTS now work for everyone.

### What It Costs
Each frame crosses the channel twice: once to the access point and once from it, even for two laptops side by side.

---

## 50. Why the Air Needs a Third MAC

### The Access Point Is Like a Switch
The access point does the same job as the switch (section 14): it moves frames between devices inside one local network, and it does not touch the IP group or the TCP group.

### Why the Switch Needs Only Two MACs
On a cable, A's wire goes only to the switch. The switch receives A's frame because it sits at the other end of the wire. Nothing in the frame needs to name the switch. The frame names only the final destination ("to MAC" = C), and the switch reads that to pick a socket. Two MAC fields are enough: to and from.

### Why the Air Needs Three
A's wave reaches every chip in range, including C if C is close. So the frame must say which chip should take it now and send the hardware ack. That is the access point, not C. Only one chip may ack: if two chips acked after 16 microseconds, their acks would collide. So two different machines must be named: the access point now, and C at the end.

The MAC fields in a wireless frame:

```text
receiver      the chip that should take this wave now and send the hardware ack
transmitter   the chip sending this wave now
third MAC     the other end: final destination on the way in, original sender on the way out
```

A sends `hi` to C:

```text
                      receiver        transmitter     third MAC
A -> access point     access point    A               C (final destination)
access point -> C     C               access point    A (original sender)
```

If C is close and hears the first frame, C's chip sees receiver = access point, not itself, and drops it. C keeps only the second frame.

A wire goes to one place. A wave reaches everyone in range. That is why the air needs the third MAC and the cable does not.

---

## 51. A Frame Through the Access Point

### What the Access Point Keeps
A list of the laptops that joined it. A laptop is added when the access point sends "accepted":

```text
joined laptops
aa:aa:aa:aa:aa:aa   (A)
cc:cc:cc:cc:cc:cc   (C)
```

This is like the switch's table, but it is filled at join time instead of by watching frames.

### Step by Step
A sends `hi` to C. A knows C's MAC from ARP, the same as on the cable, and knows the access point's MAC from its beacon. Data frames are 200 microseconds, acks 44:

```text
time (microseconds)   who sends        what
before 0                               A waits 34 of quiet + random slots
0 to 200              A                frame 1: receiver = access point, transmitter = A, third = C
200 to 216                             access point checks CRC: correct, receiver = me
216 to 260            access point     hardware ack to A. A knows the access point has it.
                                       access point reads third = C, finds C in its joined list, builds frame 2
260 to 348                             access point waits 34 of quiet + random slots (6 x 9 = 54)
348 to 548            access point     frame 2: receiver = C, transmitter = access point, third = A
548 to 564                             C checks CRC: correct, receiver = me
564 to 608            C                hardware ack to the access point
```

After that, C's chip hands `hi` to C's kernel, and everything from there is the same as on the cable (section 6).

### Notes
* The access point waits its own 34 and random slots before frame 2, because on the channel it is just one more sender. A or C might also be counting down.
* There are two hardware acks. The one A gets means "the access point has it", not "C has it". The TCP ack from C's kernel travels back C -> access point -> A the same way.
* One `hi` uses about 608 microseconds of channel time this way. Sent directly, it would be about 260.

---

## 52. Nobody Gives Out Turns

No device tells the others when to send.

A system that gives out turns would work like this: the access point sends "A, you may send now", A sends, then "C, you may send now", C sends, and nobody sends until named.

Wireless does not work that way. Each chip, including the access point's, decides by itself using only what it measures and its own random number:

* Is the channel busy, or is my timer running? Wait.
* Has it been quiet for 34 microseconds? Count my random slots.
* Did my count reach 0? Send.

Every chip follows the same rules, so collisions are rare. When one happens, the missing ack leads to a retry.

---

## 53. Two Wireless Networks in One Room

### The Setup
A second access point with its own laptops is in the same room. The two networks are meant to be independent.

### Different Channels
Network 1 uses channel 36, network 2 uses channel 44. A chip measures only its own channel, so neither network ever receives the other's waves. They are fully independent.

Many access points scan the channels when they start and pick one with little activity to get this case. Others use whatever channel is set in their settings.

### Same Channel
Both networks share channel 36. The existing rules keep working across both, because they depend only on waves:

* **Busy is busy.** When network 1 sends, network 2's chips measure the wave and wait. A chip does not care which network a wave came from.
* **Collisions** between the two networks are handled the same way: no ack, double the range, retry.
* **Frames from the other network are dropped.** Network 2's chips receive network 1's frames, see that the receiver is not them, and drop them.
* **Timers apply.** A chip starts its timer from any frame not for it, so network 2 also waits during network 1's CTS times.

The two networks stay independent in what they read: neither keeps or uses the other's frames. They are not independent in time. Only one wave can be on a channel at once, so each network gets less channel time and both are slower.

### Name
People call this a "congested channel", but it is different from the congestion in section 22. That one is a full router queue, handled by TCP's congestion control. This one is networks sharing channel time. Its exact name is **co-channel interference**: "co-channel" means "on the same channel".

Different channels only help while there are enough of them. The 2.4 GHz group has only three channels that do not overlap (1, 6 and 11). The 5 GHz group has more. In a building with many networks, some must share a channel.

---

## 54. From the Air to the Cable

### The Setup
The access point also has a cable socket. Computer D is plugged into it with a cable.

```text
A ~~~ air ~~~ [access point] ---- cable ---- D
```

The access point knows where devices are in two ways:

```text
side           how it learns a MAC
air            from joining: "I want to join" / "accepted"
cable socket   from the "from MAC" of frames arriving, the same as a switch
```

### A Sends `hi` to D
A knows D's MAC from ARP. A does not know or care that D is on a cable. To A, D is just another MAC.

Frame 1, in the air:

```text
[receiver: access point][transmitter: A][third: D][type 0x0800][IP group: A -> D][TCP group] hi [CRC]
```

The access point acks after 16 microseconds as usual. It reads third = D. D is not in its joined list, but it learned D on the cable socket, so it rebuilds the frame as a cable frame.

Frame 2, on the cable:

```text
[to MAC: D][from MAC: A][type 0x0800][IP group: unchanged][TCP group: unchanged] hi [new CRC]
```

What the access point changed:

* **Removed** the fields that matter only in the air: kind, duration, hw seq, and the receiver/transmitter split.
* **Kept** the two MACs that matter at the ends: to = D, from = A.
* **Copied** the type, IP group, TCP group and data unchanged.
* **Calculated a new CRC**, because the bytes are different.

### D Replies
The opposite direction. A cable frame arrives with to = A and from = D. A is in the joined list, so the access point sends it into the air with receiver = A, transmitter = access point, third = D.

### Name
A device that joins two kinds of network at the MAC level, rebuilding the MAC part of frames but never touching the IP group, is a **bridge**. The access point is a bridge between the air and the cable.

---

## 55. The Home Box, With Wireless

The home box in section 23 had a router and a switch inside. Most home boxes also have an access point inside, connected to the switch:

```text
                     [ home box ]
 internet line ---- router
                      |
 cable sockets 1-4 -- switch ---- access point ~~~ air ~~~ laptops
```

* **Router**: joins the home local network to the internet provider's line, through its own separate socket.
* **Switch**: joins the cable sockets, the router and the access point inside the box. It is there so several computers can be plugged in by cable.
* **Access point**: joins the laptops in the air to that switch.

So a laptop in the air and a computer on cable socket 2 are on the same local network. A frame between them goes laptop -> access point -> switch -> socket 2, and no router reads it.

---

## 56. Local Networks Joined Over Wireless

### Same Router, Same Rules
A router reads only the IP group (section 19), so it does not care whether a local network is wireless or cable. A wireless local network reaches the router through the access point's cable socket, and the access point rebuilds every frame as a cable frame (section 54).

### Two Buildings With Wireless
Section 16 again, but the computers in each building use wireless. Each building has an access point plugged into its switch. R sits between the two switches as before.

```text
building 1                                                          building 2
A, B, C ~~~ air ~~~ [AP1] -- switch 1 --(s1) R (s2)-- switch 2 -- [AP2] ~~~ air ~~~ D, E, F
192.168.1.x                                                         192.168.2.x
```

* AP1 and AP2 are the two access points.
* R's socket 1 is `192.168.1.254`, with MAC R(s1). R's socket 2 is `192.168.2.254`, with MAC R(s2).
* A is `192.168.1.1`. D is `192.168.2.4`.

### A Sends `hi` to D
A makes the same decision as in section 16: D's prefix is not 192.168.1, so the frame goes to the default gateway `192.168.1.254`. A finds R(s1) with ARP. The ARP broadcast goes through AP1 to everyone in building 1, including R's socket 1. R does not forward broadcasts, so building 2 never sees it.

```text
step                       where           next machine      sender on this step   third MAC   IP group
1. A -> AP1                air, bldg 1     receiver = AP1    transmitter = A       R(s1)       A -> D, TTL 64
2. AP1 -> switch 1 -> R    cable, bldg 1   to = R(s1)        from = A              none        A -> D, TTL 64
3. R -> switch 2 -> AP2    cable, bldg 2   to = D            from = R(s2)          none        A -> D, TTL 63
4. AP2 -> D                air, bldg 2     receiver = D      transmitter = AP2     R(s2)       A -> D, TTL 63
```

What each machine does:

* **AP1**: acks A after 16 microseconds and rebuilds the air frame as a cable frame (section 54).
* **Switch 1**: reads to = R(s1) and sends the frame out of the socket R is on.
* **R**: exactly what it did in section 16. It reads D's IP, matches 192.168.2.x to socket 2, lowers TTL to 63, finds D's MAC with ARP on building 2's side, and writes a new MAC group: to = D, from = R(s2).
* **Switch 2**: reads to = D. It learned that D's frames come in through the socket AP2 is on, so it sends the frame there.
* **AP2**: D is in its joined list, so it rebuilds the frame as an air frame. D's chip acks AP2 after 16 microseconds.

### Things to Notice
* **In step 4, the third MAC is R(s2), not A.** A MAC address only has meaning inside one local network (section 16). In building 2, the frame came from the router, so the original sender on that local network is R(s2). A's IP is still in the IP group, so D knows the frame came from A.
* **Both buildings can use channel 36.** The buildings are far apart and walls weaken the wave, so building 1's waves reach building 2 only as noise. They do not share channel time.
* **R never learns that A or D is wireless.** Only steps 1 and 4 are in the air, and the access points turn them into ordinary cable frames.

---

## 57. Houses in Different Cities

### The Problem
Your house is one local network: laptops, a switch and an access point. A friend's house in another city is another local network. In section 16, one router joined two buildings because both buildings were cabled to it. Between two houses in different cities there is no cable, and you cannot lay one across a city yourself.

### Who Lays the Cables
Companies lay cables under streets and between cities, and put routers where the cables meet. Each house gets one cable from the company's nearest router. The house pays the company every month. This company is an **internet provider**. The word "internet" is explained at the end of this section.

### Where the Cable Plugs In
Into the home box (sections 23 and 55). The box has one socket separate from the others, and the company's cable goes there. Inside the box, that socket belongs to the router part.

* That socket is usually labeled **WAN** (wide area network): the network on the far side of the socket, the company's cables, which cover a large area.
* The other sockets are labeled **LAN** (local area network): they connect to your own local network.

```text
laptops ~~~ [access point] -- switch -- (LAN side) router (WAN side) ---- company's router
             your home local network                       one cable, like R1-R2 in section 17
```

The home router's routing table:

```text
192.168.1.x       directly (your home)
everything else   next router = the company's router
```

### Why the Router Needs Its Own Socket
A router needs one socket for each local network it joins. In section 16, R had socket 1 cabled to building 1 and socket 2 cabled to building 2. It reads "to IP" and decides which socket the frame goes out of. With one socket, it would have nothing to choose between.

The home router joins two local networks:

```text
socket 1 (inside the box, to the switch)   ->  your home local network
WAN socket                                 ->  the one cable to the company's router
```

The LAN sockets are not router sockets. They are switch sockets, all in the home local network.

If the company's cable went into a switch socket instead, the company's router would become part of the home local network. The laptops' ARP broadcasts would go out to the company, and frames between the house and the company would never pass through the home router at all. A router only does its job (reading the IP group, picking a side, not forwarding broadcasts) for frames that come in on one of its sockets and go out of another.

### What the Internet Is
Every house and every office does this. The company's routers are cabled to other companies' routers, across cities and countries. The **internet** is all of these local networks (homes, offices, and the computers that run websites) joined by routers that many companies own. No single company owns all of it.

Nothing new happens to a frame there. It is sections 16 to 18 repeated across many routers: each router reads "to IP", picks a row, writes new MACs, and lowers TTL by 1.

---

## 58. Two Houses With the Same Addresses

### The Problem
S is a computer somewhere else that runs a website.

```text
house 1:  laptop A 192.168.1.23 -- [home box H1] --\
                                                    [company router P] -- ... -- S 198.51.100.7
house 2:  laptop X 192.168.1.23 -- [home box H2] --/
```

Home boxes come from the factory set up the same way, so a laptop in house 2 can have the same address as A.

1. A sends `hi` to S. The IP group is from `192.168.1.23` to `198.51.100.7`.
2. Every router reads only "to IP", so the frame reaches S. Nothing has gone wrong yet.
3. S replies. The IP group is from `198.51.100.7` to `192.168.1.23`.
4. P would need these rows:

   ```text
   192.168.1.x   ->  house 1 cable
   192.168.1.x   ->  house 2 cable
   ```

   The same prefix points two ways, so P cannot choose. The reply cannot be delivered.

### Why Houses Reuse Addresses
An IP address is 4 bytes, which is 32 bits, so there are about 4.3 billion possible addresses. The world has more phones, laptops and servers than that, so not every device can have its own.

So three ranges were set aside for use only inside a local network. Any house or office may reuse them, and routers between companies have no rows for them:

```text
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
```

Every other address belongs to exactly one machine in the world. Organizations that track who has which range hand ranges out to companies, so no two companies get the same one.

* **Private address**: an address from the three reused ranges. It means something only inside one local network.
* **Public address**: an address that belongs to one machine in the world, so routers anywhere can have a row that leads to it.

`198.51.100.7` is not in any of the three ranges, so S's address is public.

### What Each House Gets
The internet provider owns ranges of public addresses. When the home box is connected, it asks over the WAN cable for an address, and the company's router gives it one from those ranges. Sometimes the company gives the address on paper and a person types it in. The address is set on the WAN socket only:

```text
H1's WAN socket   203.0.113.10
H2's WAN socket   203.0.113.20
```

Now P's rows are unique:

```text
203.0.113.10   ->  house 1 cable
203.0.113.20   ->  house 2 cable
```

A frame sent to `203.0.113.10` reaches house 1's box and no other.

Routers in other companies know to send `203.0.113.x` toward this provider because the provider tells them, with messages like "I can reach 203.0.113.x, send it through me" (the automatic messages at the end of section 17). So every frame for the house first reaches the provider's routers, and the last of them, the one cabled to the house, passes it to the box.

### Picking an Address Yourself
You can type any number into the box, but it will not work. An address only works if routers have rows that lead to your cable. Those rows are in the company's routers, and only the company changes them. If you type `203.0.113.99` and the company never gave it to you, P has no row sending it to your cable, so replies never reach you. If that address belongs to someone else, the replies go to them.

### Addresses Used in These Examples
The organizations that track address ranges keep three small ranges back and never give them to any company:

```text
192.0.2.0/24
198.51.100.0/24
203.0.113.0/24
```

They exist for people who write books, manuals and tutorials. If a writer used a real address, readers who copied the example would send frames to a real machine that belongs to someone else. No machine owns these addresses, and routers have no rows for them. The examples here use them for S and the home boxes for the same reason: they look like real public addresses but do not point at anyone's real machine.

### The Next Problem
A's frame left with "from IP" = `192.168.1.23`, so S still replies to that address, not to `203.0.113.10`. And A, B and C are all inside house 1 behind that one public address.

---

## 59. NAT

### Going Out
A (`192.168.1.23`, port 50001) sends to S (`198.51.100.7`, port 80). When the frame reaches the home box:

1. The box picks an unused port of its own, for example 40001.
2. It writes a row in a table.
3. It replaces "from IP" with its public address and "from port" with 40001. Then the router part sends the frame out of the WAN socket as usual (new MACs, TTL lowered by 1).

```text
before:  from 192.168.1.23 : 50001   to 198.51.100.7 : 80
after:   from 203.0.113.10 : 40001   to 198.51.100.7 : 80
```

S only ever sees `203.0.113.10 : 40001`. It never sees `192.168.1.23`.

### Coming Back
S replies to `203.0.113.10 : 40001`. Routers outside have rows for that address, so the reply reaches the home box. The box reads "to port" = 40001, finds the row, and changes the frame back:

```text
before:  to 203.0.113.10 : 40001
after:   to 192.168.1.23 : 50001
```

Then it sends the frame into the house to A.

### Two Laptops With the Same Port
B (`192.168.1.24`) opens a conversation with S at the same moment. As in section 7, each kernel picks its own port, and B also picks 50001 by chance. The box gives B a different outside port:

```text
inside IP : port        outside port    other end
192.168.1.23 : 50001    40001           198.51.100.7 : 80     (A)
192.168.1.24 : 50001    40002           198.51.100.7 : 80     (B)
```

S sees two conversations, `203.0.113.10 : 40001` and `203.0.113.10 : 40002`. The four values differ by port (section 20), so S keeps them apart.

If the box changed only the IP, both replies would come back to `203.0.113.10 : 50001`, and the box could not tell A's reply from B's. The outside port is the only thing that tells them apart, which is why the port changes as well as the IP.

### Name
Changing addresses and ports at the box is **NAT** (network address translation). It is the one exception to the rule in section 19 that a router never reads the TCP group: NAT reads and changes the ports. The box deletes each row a short time after the conversation ends.

### Why the Two-Building Example Did Not Need It
NAT is needed only because several devices share one public address, so the box has to use ports to tell them apart. In section 16, every computer had its own address, and the router had rows for all of them, so nothing had to be rewritten. If every laptop in a house had its own public address, NAT would not be needed either.

---

## 60. Frames Nobody Inside Asked For

### No Row, Dropped
A frame arrives at the WAN socket for a port that has no row, for example `203.0.113.10 : 40050`. It does not belong to any conversation started from inside, so the box has no inside address to change it to. The box drops it.

```text
arrives:  to 203.0.113.10 : 40050
table:    no row for 40050
result:   dropped
```

* Laptops inside can start conversations with anyone outside, because a row is created on the way out and the reply finds it.
* Nobody outside can start a conversation with a laptop inside. Their first frame, the SYN (section 11), has no row, so it is dropped.

A computer outside cannot reach a program listening on a laptop inside unless the laptop spoke first.

### Port Forwarding
A runs a program listening on port 7000, and a friend in another city wants to connect to it. The friend's SYN arrives at `203.0.113.10 : 7000`, there is no row, and it is dropped.

The fix is to type a row into the box's settings by hand:

```text
outside port    inside IP : port
7000            192.168.1.23 : 7000      (typed by a person, never deleted automatically)
```

Now the friend connects to `203.0.113.10 : 7000`. The box finds the row, changes "to IP" to `192.168.1.23`, and sends the frame to A. Replies go back out through the same row.

A row typed by hand like this is **port forwarding**. It is the only way a frame that nobody inside asked for gets through the box.

### After a Conversation Closes
While a row exists, S can send a frame that reaches the laptop, even after the conversation is over. If S sends a frame with exactly the same addresses and ports right after the conversation closes, the box still has the row, so it forwards the frame and it reaches the laptop. Three things limit this:

1. **Only S can use the row.** The row records the other end, `198.51.100.7 : 80`. Most home boxes, including the ones that run Linux, forward a frame through the row only if its "from IP : port" is exactly that. A different computer sending to `203.0.113.10 : 40001` does not match and is dropped. Not every box checks this. Some forward anything that arrives on 40001.
2. **The row does not last long.** The box sees the FIN frames go through (section 12), so it knows the conversation ended. It deletes the row a short time later, for example about 2 minutes on Linux-based boxes. After that, even S is dropped.
3. **The laptop's kernel rejects it.** A's kernel looks up the four values (section 20). Port 50001 was a temporary port that A's kernel picked for `connect()`. No program called `listen()` on it, and the conversation is closed. So the kernel answers with RST (section 11), and no program sees the frame.

### Who Can Reach Whom
A laptop can start a conversation with any machine whose address routers can reach and where a program is listening.

* **A server in a data center**: yes. Servers are set up so that an address reachable from outside leads to them, and a program listens on a known port, such as 80.
* **A friend's laptop in another city**: only if the friend's box has a port forwarding row for that port. On your side nothing is needed: your box creates a NAT row by itself on the way out.
* **A friend's laptop in the same house**: no port forwarding needed. Frames between two laptops in one house go laptop -> access point -> switch -> laptop (section 55). They never pass through the router part, so NAT never sees them. You connect directly to the friend's private address, for example `192.168.1.24 : 7000`.

```text
friend in another city:   you -> your box (NAT row made automatically) -> ... -> friend's box (needs port forwarding) -> friend
friend in your house:     you -> access point / switch -> friend      (no router, no NAT)
```

The other direction always works: any computer you start a conversation with can reply, because your box creates the row on the way out.

---

## 61. One Laptop in Two Networks

### Two Wireless Chips
A laptop with two wireless chips can join two access points at once. Each chip has its own MAC, and each network gives the laptop an address on that chip. The laptop is then in two local networks at once, the same position as R in section 16, with one socket in each building. A laptop with a cable plugged in and wireless connected at the same time is the same case.

### Different Ranges: No Conflict
```text
chip 1 joined home Wi-Fi      laptop is 192.168.0.23
chip 2 joined office Wi-Fi    laptop is 192.168.1.40
```

The laptop's routing table gets one row per network:

```text
192.168.0.x       directly, out of chip 1
192.168.1.x       directly, out of chip 2
everything else   next router 192.168.0.1 out of chip 1, priority 600
everything else   next router 192.168.1.1 out of chip 2, priority 601
```

The two "everything else" rows match the same addresses, so each row carries a priority number, and the lower number wins. All outside traffic goes out through chip 1, and chip 2 is used only for 192.168.1.x. This priority number is the **metric**.

### Same Range: Conflict
If both networks use 192.168.0.x:

```text
192.168.0.x   directly, out of chip 1
192.168.0.x   directly, out of chip 2
```

Two rows match the same prefix. The metric decides, so the kernel always uses one of them. If both networks have a printer at `192.168.0.50`, the laptop can reach only the one on the network the winning row points to. The other is unreachable by address. Both boxes may even be `192.168.0.1`. Nothing breaks completely, but everything addressed in that range goes to only one of the two networks.

### Not a Router by Default
Being in both networks does not make the laptop pass frames from one network to the other. Linux has that switched off by default.

### How the Metric Is Chosen
On a Linux desktop, the program that manages connections (NetworkManager on Ubuntu) sets the metric from the type of connection:

```text
cable       100
Wi-Fi       600
VPN          50    (a later topic)
```

When a cable and Wi-Fi are both connected, the cable wins, because a cable is usually faster and steadier. With two Wi-Fi chips, both start at 600, and NetworkManager gives the second one a slightly higher number, such as 601, so the rows never tie. Which chip gets the lower number depends on the order they connected. The exact rule was not checked.

The number can be set by hand for any connection, in Ubuntu's settings for that network or with `nmcli connection modify <name> ipv4.route-metric 50`. A lower number makes that connection the one used for "everything else".

---

## 62. Names Instead of Numbers

### The Problem
A's program has to put S's address into `connect()`. People remember words, not `198.51.100.7`. The address can also change: if S's owner moves S to another data center, S gets a new address from a different company, and everyone who wrote down the old number now has a wrong one. So people want to type a name like `www.bluepizza.com` and have the computer find the current address.

### A File on Every Computer
The simplest fix: each computer keeps a text file with one line per name.

```text
198.51.100.7    www.bluepizza.com
192.168.1.24    friend-laptop
```

Before connecting, the program's networking code reads this file, finds the name, and uses the address next to it. On Linux this file still exists, at `/etc/hosts`.

When the whole network was a few hundred computers, in the 1970s and early 80s, it worked exactly like this. One organization kept a single master file, and every computer downloaded a copy regularly.

### Why It Stops Working
* **Size**: there are hundreds of millions of names. A file every computer downloads would be huge, and almost all of its lines would never be used.
* **Changes**: names get new addresses all the time. Every computer would need a fresh copy constantly, and an old copy gives a wrong address.
* **One editor**: every new name or change would have to go through that one organization.

---

## 63. Asking a Name Server

### One Computer Answers
Instead of every computer holding every name, a computer asks for only the one name it needs. Whoever answers is just another computer with an address that can be reached, running a program that answers name questions.

Say one computer, N at `198.51.100.53`, holds the whole name list, and a program on it listens on port 53. Port 53 is agreed in advance for this, the same way 80 is agreed for web servers (section 7). N's address is one of A's settings, the same way the default gateway is.

```text
question:  [MAC group][IP: A -> 198.51.100.53][UDP: from port 50123 to port 53]  "what is the address of www.bluepizza.com?"
answer:    [MAC group][IP: 198.51.100.53 -> A][UDP: from port 53 to port 50123]  "www.bluepizza.com is 198.51.100.7"
```

Then A's program calls `connect(("198.51.100.7", 80))` as before.

A computer that answers name questions is a **name server**.

### Why UDP and Not TCP
The question and the answer each fit in one small frame. TCP would need the three-frame handshake (section 11) before the question and FIN frames after it, all to carry two small frames. With UDP (section 19), A sends the question and waits. If no answer comes within a short time, for example 1 second, A asks again.

### Why One Name Server Is Not Enough
* **Load**: every computer in the world asks it, every time it opens a conversation. That is billions of questions a day for one machine.
* **One editor**: whoever owns `www.bluepizza.com` has to ask the one organization that runs N to change its line.
* **One point of failure**: if N is switched off or its cable breaks, no name works anywhere.

These are the same problems the single file had, moved onto one computer.

---

## 64. Splitting the Names

### Read From Right to Left
The list is split by the parts of the name. The parts are separated by dots and read from right to left. Each level of name servers knows only who handles the next part.

### The Setup
* A pizza shop owns the name `bluepizza.com`.
* Its website runs on a computer at `198.51.100.7`, named `www.bluepizza.com`.
* The shop does not run its own name server. It rents one from a company called DNSHost. That server is `ns1.dnshost.net`, at `203.0.113.53`.
* One of the com servers is at `192.0.2.10`. "com-server-1" below is a made-up label for it.

### What Each Server Holds
```text
root server:
  com                  ->  ask com-server-1        (address 192.0.2.10)

com server (192.0.2.10):
  bluepizza.com        ->  ask ns1.dnshost.net     (address 203.0.113.53)

ns1.dnshost.net (203.0.113.53):
  www.bluepizza.com    ->  198.51.100.7
```

* **Root servers** know who handles each last part: `com`, `org`, `in`, and so on.
* **com servers** know who handles each name ending in `.com`.
* **bluepizza.com's name server** knows the actual addresses of the names under `bluepizza.com`.

### Looking Up `www.bluepizza.com`
Each step is one UDP question and answer to port 53:

1. Ask a root server about `www.bluepizza.com`. Answer: "I do not have it. For `com`, ask `192.0.2.10`."
2. Ask `192.0.2.10`. Answer: "I do not have it. For `bluepizza.com`, ask `ns1.dnshost.net` at `203.0.113.53`."
3. Ask `203.0.113.53`. Answer: "`www.bluepizza.com` is `198.51.100.7`."

### How the Root Servers Are Found
There are 13 root server addresses. They are a fixed list built into name server programs. The list almost never changes, so a copy of it is enough. It is the old file idea again, but for 13 lines instead of millions.

### What This Fixes
* **Load**: root servers answer only about the last part, com servers only about names ending in `.com`. The actual lines for `www.bluepizza.com` sit only on bluepizza.com's name server.
* **One editor**: the pizza shop edits its own lines on `ns1.dnshost.net` directly. Nobody else is involved. When the shop first buys the name `bluepizza.com` from a company that sells names, that company adds the `bluepizza.com -> ask ns1.dnshost.net` line to the com servers.
* **One point of failure**: each level has several servers, so one being off does not stop names from working.

### Names
A name together with everything under it, like `bluepizza.com`, is a **domain**. This whole split system of name servers is **DNS** (Domain Name System).

---

## 65. The Resolver and Its Memory

### The Problem
Every new connection would need three questions before the first SYN, and every computer in the world would keep asking the root and com servers the same things.

### One Computer Does the Asking
The laptop does not hold the 13 root addresses, and it does not ask three times. The laptop has one name server address in its settings, the same way it has the default gateway. That name server might be:

* the home box, which passes the question on to the next one
* a name server run by the internet provider
* a large shared one, such as Google's at `8.8.8.8` or Cloudflare's at `1.1.1.1`

The laptop sends it one question, "what is the address of `www.bluepizza.com`?", and waits for one answer. That name server holds the list of 13 root addresses, asks root, then com, then bluepizza.com's name server, and sends the final answer back to the laptop.

A name server that does this asking for other computers is a **resolver**.

### The Resolver Remembers Answers
The resolver keeps every answer it receives in memory, not only the final one:

```text
com                  ->  ask 192.0.2.10
bluepizza.com        ->  ask 203.0.113.53
www.bluepizza.com    ->  198.51.100.7
```

```text
later question                         what the resolver does                       questions sent
another laptop: www.bluepizza.com      answers from memory                          0
someone: mail.bluepizza.com            skips root and com, asks 203.0.113.53        1
someone: other.com                     skips root, asks the com server              2
```

A resolver used by thousands of laptops rarely asks the root servers, because the `com` line is almost always already in memory. The laptop and the browser also keep their own short-term copies, so repeated connections often send no question at all.

### How Long It Remembers
Each answer carries a number of seconds set by the owner of the name, for example 300. The resolver keeps the answer that long, then deletes it and asks again next time. This number is also called **TTL** (time to live). It is a different field from the TTL in the IP group (section 18), which counts router hops. Only the name is the same.

The owner picks it:

* **Long TTL, for example 1 day**: few questions, but after the owner changes the address, resolvers keep giving the old one until their copy expires.
* **Short TTL, for example 60 seconds**: an address change reaches everyone within a minute, but resolvers ask more often.

### Where the Resolver Is Set
By default nothing is set by hand. When the laptop joins the home network, the box gives it its settings automatically: its address, the default gateway, and a resolver address. Usually the resolver address is the box itself, for example `192.168.1.254`, and the box passes questions on to the internet provider's resolver.

To change it, there are two places:

```text
where                                       what is set                                     affects
laptop (Ubuntu: Settings -> Network ->      which resolver this laptop asks                 only this laptop
IPv4 -> DNS, turn off Automatic,
type for example 1.1.1.1)
home box (its settings page)                which resolver the box passes questions to,     every device using the
                                            or which resolver address it gives devices      automatic setting
```

If both are set, the laptop's own setting wins for that laptop.

`192.168.1.254` is only the number these notes use (section 16). Real boxes use whatever their maker set at the factory, commonly `192.168.0.1`, `192.168.1.1`, `192.168.1.254` or `10.0.0.1`, and it can be changed in the box's settings. The only rule is that the box's address must be inside its own home network's range: a home network of 192.168.0.x needs a box address like `192.168.0.1`, not one from 192.168.1.x.

---

## 66. Kinds of Records

### Record
One line in a name server's list is a **record**. Each record has four parts: name, type, value and TTL. Each type says what the value means.

### Type A (Address)
The value is an IP address. This is the line used in every step so far:

```text
name                 type     value            TTL (seconds)
www.bluepizza.com    A        198.51.100.7     300
```

### Type NS (Name Server)
The value is the name of the name server to ask for a domain. The "ask this server" lines on the root and com servers are NS records.

On the com servers:

```text
name             type    value                TTL
bluepizza.com    NS      ns1.dnshost.net      86400
bluepizza.com    NS      ns2.dnshost.net      86400
```

This means: "for any name ending in `bluepizza.com`, ask `ns1.dnshost.net` or `ns2.dnshost.net`". Two lines are there so that if one server is off, the other works.

The value is a name, but the resolver needs an IP address to send its question to. So the com servers also send the name server's address in the same answer:

```text
ns1.dnshost.net    A    203.0.113.53
```

The root servers do the same one level up: an NS record for `com`, plus the address of each com server.

### Type CNAME (Canonical Name)
"Canonical name" means "the real name". The value is another name, not an address. It says: "this name is another name for that one, look that one up instead".

Say the pizza shop does not run its website computer itself. It rents space from a hosting company, `hostco.net`, which moves its customers between machines and changes their addresses. With an A record, the shop would have to edit its record every time hostco changed the address. Instead the shop writes:

```text
name                 type     value                     TTL
www.bluepizza.com    CNAME    bluepizza.hostco.net      3600
```

hostco keeps the A record for `bluepizza.hostco.net` up to date on its own name servers. The shop never edits anything, and its name always leads to the current address.

The resolver follows it:

1. A laptop asks for `www.bluepizza.com`.
2. The resolver gets `CNAME bluepizza.hostco.net`. That is not an address yet.
3. It looks up `bluepizza.hostco.net` and gets an A record with the address.
4. It answers the laptop with that address, and keeps both records in memory, each for its own TTL.

### The Three Types Side by Side
```text
type     value                  meaning
A        an IP address          this is the address
CNAME    another name           look up that name instead
NS       a name server's name   ask that server about this domain
```

### How Many Steps
Each step is one handoff, where one name server says "ask this other server". Three steps is the common case for a name like `www.bluepizza.com` when nothing is in memory, but the count can differ:

* **More handoffs, more steps.** A university might give its computer science department its own name server for names ending in `cs.someuni.edu`. Looking up `www.cs.someuni.edu` then takes four steps: root, edu servers, the university's server, the department's server.
* **A CNAME starts another lookup.** The resolver has to look up the new name from the start, which can add up to three more steps, fewer if parts of it are in memory.
* **A missing name server address.** If an NS answer gives only a server's name without its address, the resolver first has to look up that name, which adds more steps.

### The Next Problem
A's program now has `198.51.100.7` and connects to port 80. The handshake finishes, and a connection is open. What bytes should A's program send so that the program on S knows which page is wanted, and what bytes come back?

---

## 67. What a Protocol Is

### Rules Already Used
Before that question can be answered, the rules under the bytes have to be built properly, starting from what a protocol is. The TCP and UDP parts earlier in these notes were loose, so this part builds them again from the start: protocol, ports, lost frames, UDP, then TCP. Several protocols have already been used without the name.

When A sends a wireless frame to B, both chips agreed in advance on:

* **The order of the fields**: kind, duration, receiver MAC, transmitter MAC, third MAC, ..., CRC.
* **The size of each field**: a MAC is 6 bytes.
* **What each side does**: wait for 34 microseconds of quiet plus a random wait before sending. The receiver acks after 16 microseconds.

If B's chip expected the receiver MAC 2 bytes later than where A put it, B would read the wrong 6 bytes as the address and drop every frame. The bytes mean something only because both sides follow the same written rules.

### The Definition
A **protocol** is a written set of rules: which bytes go where, what each one means, and what each side does in reply.

* The wireless sending rules are one protocol.
* ARP is another: the question "who has 192.168.1.254?" and its answer have a fixed layout.
* The IP group is another: from IP, to IP and TTL, each in a fixed place.

### The Next Problem
The IP group gets a frame to the right computer. That computer runs many programs at once, for example a browser, a music player and a chat program. Which program should get the bytes?

---

## 68. Which Program Gets the Bytes

### Why Not the Process ID
The kernel receives every frame first. The frame needs a number that tells the kernel which program the bytes are for.

The process ID cannot be that number. The kernel gives a program a new process ID every time it starts, so it changes on every run. The sending computer also cannot see the receiving computer's process IDs.

### Ports
A fixed number is agreed instead. When a program starts, it asks the kernel: "give me every frame that arrives for number 7000". The kernel writes that in a table. This number is a **port**. It is 2 bytes, so it can be 0 to 65535.

Laptop B (`192.168.1.24`) runs two programs. B's kernel has this table:

```text
port    program
7000    chat program
6600    music program
```

A's chat program sends "hi" to B's chat program. A's kernel adds a small group of bytes after the IP group:

```text
[MAC group][IP group: to 192.168.1.24][from port 50001, to port 7000]["hi"]
```

1. The frame reaches B, as in section 16.
2. B's kernel reads "to port" = 7000, finds the chat program in its table, and gives it "hi".
3. If no row has that port, no program asked for it, so no program gets the bytes. What the kernel sends back in that case is in sections 70 (UDP) and 74 (TCP).

### Why the Frame Also Carries "From Port"
B's chat program has to reply to the right program on A. A's kernel gave A's chat program port 50001 when it started sending. The program did not choose that number. The kernel picked an unused one. The reply goes back as:

```text
[IP group: to A][from port 7000, to port 50001]["hello"]
```

### How A Knows 7000
A has to know B's port before sending anything, so programs agree on fixed numbers in advance. Web servers use 80, and name servers use 53 (section 63). The sender's own port can be any unused number, because the reply carries it back.

### The Next Problem
Frames can be lost. A sends "hi", and nothing arrives at B. With only these ports, does anyone notice?

---

## 69. Where Frames Get Dropped

### Three Places
**1. In the air, after too many tries.** A sends a frame to the access point. If it collides with another frame or is damaged by noise, the access point's CRC check fails, so it sends no ack. A's chip waits and sends again (section 39). It does not try forever. After a fixed number of tries, often about 7 (not checked for a specific chip), A's chip gives up and throws the frame away. This happens when the air is very busy or the signal is weak, for example two rooms away from the access point.

**2. On a cable, damaged bytes.** A cable has no ack at all. The receiving chip checks the CRC. If bits were flipped by electrical noise or a bad plug, the CRC does not match, and it drops the frame without telling anyone (section 4). On a good cable this is rare.

**3. In a router or switch, no room to wait.** This is the most common cause, on cable and in the air.

```text
socket 1 in:  1 Gbit/s ---\
                           router ---> socket 3 out: 1 Gbit/s
socket 2 in:  1 Gbit/s ---/
```

Frames come in twice as fast as they can go out. The router keeps the extra frames in memory, in a line where each frame waits its turn. That memory is limited. When the line is full, each new frame that arrives is dropped. An access point does the same when frames from the cable come in faster than it can send them through the air.

### Why the Wireless Ack Does Not Help
```text
A ~~air~~ access point -- switch -- router -- ... -- B
  ack here               no acks on any of these
```

A's chip gets its ack as soon as the access point receives the frame. If a router farther along drops it because its line is full, A's chip has already moved on, and that router tells nobody.

### The Program Is Not Told Either
When A's program calls `send("hi")`, the kernel copies the bytes into its own memory and `send` returns. It never waits for the frame to reach B.

```text
program: send("hi")  -> returns                (time 0)
kernel:  builds the frame, gives it to the chip
chip:    try 1 ... try 7, no ack, gives up     (later)
         adds 1 to a counter of failed frames in the driver; the program is never told
```

Usually the copy is immediate, so the program goes to its next line right away. The exception: the kernel keeps a limited amount of memory for each program's outgoing bytes. If that memory is full, because the program sends faster than the chip can put frames out, `send` waits until there is room. Even then it is waiting for room in the kernel's memory, not for B.

### The Drop Comes First
"The sender slows down when acks stop coming" is a TCP rule (section 73). It does not prevent drops. It reacts to them:

```text
1. a router's line is full
2. the router drops a frame             <- the drop happens first
3. that frame's ack never comes back
4. the sender's kernel sees the missing ack and slows down
```

The router sends no "slow down" message. It only drops frames, so the drop is the signal. Many computers send through the same router, and none of them knows about the others, so the line can fill up before any of them slows down. UDP has nothing like this rule: the kernel sends as fast as the program gives it bytes.

---

## 70. UDP

### Nobody Notices the Loss
With only ports, a lost frame stays lost, and nobody finds out:

* The hardware ack covers only one trip through the air.
* The router that drops the frame tells nobody.
* B cannot miss a frame it never heard about.

So A's program believes "hi" was sent, and B's program never gets it.

### The Rules
The small group from section 68 is a real protocol with exactly this behaviour. Its group is always 8 bytes and sits between the IP group and the data:

```text
[MAC group][IP group, protocol 17][ UDP group, 8 bytes ]["hi"][CRC]
                                    from port   2 bytes
                                    to port     2 bytes
                                    length      2 bytes   (this group plus the data, in bytes)
                                    checksum    2 bytes   (a number computed from the bytes, like the CRC)
```

The sender's kernel:

1. Writes the program's port in "from port" and the destination port in "to port".
2. Writes the length of the UDP group plus the data. For "hi": 8 + 2 = 10.
3. Computes the checksum from the bytes and writes it.

The receiver's kernel:

1. Computes the checksum again. If it differs, some bytes were damaged, so it drops the frame.
2. Reads "to port" and finds the program that asked for that port.
3. Gives the data to that program. If no program asked for that port, it drops the frame and sends back an ICMP "port unreachable" message (section 78). Linux limits how many of these it sends per second.

That is the whole protocol. Only the two kernels at the ends read the UDP group. Routers and access points read only the MAC and IP groups and pass the UDP group along unchanged. The rules do not include waiting for a reply, resending, or numbering frames.

A program picks UDP when it starts. It tells the kernel "I will send with UDP", and from then on the kernel adds this 8-byte group to everything that program sends.

**UDP** = User Datagram Protocol. A **datagram** is one piece of data sent in one frame, on its own, unconnected to any other.

### The Bytes for "hi"
Written in hex (base 16, two hex digits per byte):

```text
field        value     bytes on the wire
from port    50001     C3 51
to port      7000      1B 58
length       10        00 0A        <- 10 in hex is 0A
checksum     computed  for example 4F 2E
data         "hi"      68 69        <- 'h' is 68, 'i' is 69
```

Counting them: 2 + 2 + 2 + 2 + 2 = 10 bytes. The length counts the UDP group itself as well as the data.

### Two Bytes, One Number
`C3 51` is one number, not two. The first byte counts how many 256s there are, and the second counts the ones:

```text
C3 51  =  195 × 256 +  81  =  50001
1B 58  =   27 × 256 +  88  =  7000
00 0A  =    0 × 256 +  10  =  10
FF FF  =  255 × 256 + 255  =  65535   <- the largest; this is why ports stop at 65535
```

It works the same way as decimal digits. In "42", the 4 counts tens and the 2 counts ones. Each byte holds 0 to 255, so the first byte counts 256s instead of tens.

The byte that counts 256s goes first. Every network protocol uses this order, so it is called **network byte order**. A laptop's processor stores numbers in memory with the ones byte first, so the kernel swaps the two bytes when it writes a port into a frame.

### Why the Length Field
A cable frame has a minimum size of 64 bytes. A frame carrying only "hi" is shorter, so the sender's chip adds zero bytes before the CRC. B's kernel then receives "hi" followed by zeros. The length tells it the data is 10 − 8 = 2 bytes, so the zeros are ignored.

The IP group has its own length field, which does the same job for the whole IP part, so the UDP length is partly a second copy. It is kept because UDP's rules were written so that the UDP group can be checked on its own.

### When UDP Is Enough
* **Name lookups**: the question fits in one frame. If no answer comes within about 1 second, the program asks again. The program does the noticing itself.
* **Voice calls**: each frame carries about 20 milliseconds of sound. If one is lost, resending it would make it arrive too late to play. Skipping it causes a short click, which is better.

### The Next Problem
A sends a 1 MB photo to B. One frame carries at most about 1500 bytes of data, so the photo needs about 700 frames. With UDP, some can be lost and nobody notices. How would B know which pieces are missing, and how would A know to send them again?

---

## 71. Numbering the Bytes

To keep the numbers simple, say each frame carries 1000 bytes of the photo (the real figure is 1460, section 77). A 1,000,000-byte photo then needs 1000 frames.

### Rule 1: A Writes a Number in Every Frame
The number is the position of the frame's first byte within the photo:

```text
frame 1:  number 0       bytes 0 to 999
frame 2:  number 1000    bytes 1000 to 1999
frame 3:  number 2000    bytes 2000 to 2999
...
```

The position tells B exactly where those bytes go, so B can see which positions are still empty. This number is the **sequence number**.

### Rule 2: B Replies With the Next Position It Wants
"Ack 1000" means "I have every byte before 1000, that is 0 to 999. Send 1000 next." This number is the **ack number**.

### Rule 3: A Keeps a Copy Until It Is Acked
A keeps a copy of every frame until an ack covers it. If no ack covers that frame within a set time, for example 200 milliseconds, A sends the copy again.

### One Frame Lost
```text
A sends          B has                  B replies
0      ->        0-999                  ack 1000
1000   -> lost
2000   ->        0-999, 2000-2999       ack 1000   (still missing 1000-1999)
... 200 ms pass, no ack covers frame 1000 ...
1000   ->        0-2999                 ack 3000
```

B holds 2000–2999 in memory and does not give it to its program until 1000–1999 arrives. So the program always gets the bytes in order, with no gaps.

### How This Differs From the Hardware Ack
This ack is sent by B's kernel, and it travels back across every router to A's kernel. A drop anywhere along the way means no ack, so A finds out and resends. The hardware ack only covers one trip through the air.

These are the first rules of **TCP** (Transmission Control Protocol). TCP has its own group in the frame, in the same place as the UDP group.

### The Next Problem
A is in one city and B in another. A frame takes 25 ms to get there, and the ack takes 25 ms to come back. If A waits for each ack before sending the next frame, how long do 1000 frames take?

---

## 72. Sending Without Waiting

### The Cost of Waiting
Every frame costs one full trip there and back: 25 + 25 = 50 ms. 1000 frames × 50 ms = 50 seconds for a 1 MB photo. Most of that time, the cable sits idle while A waits.

### Rule 4: Many Frames Before Any Ack
Say A may have at most 10 unacked frames out at once:

```text
time 0 ms:   A sends 0, 1000, 2000 ... 9000         (10 frames, then stops)
time 50 ms:  ack 1000 arrives  -> A sends 10000      (10 out again)
             ack 2000 arrives  -> A sends 11000
             ...
```

Each ack frees one place, and A fills it right away. Each 50 ms trip now moves 10 frames instead of 1: 100 trips × 50 ms = 5 seconds. With 100 frames allowed, 0.5 seconds. Rule 3 still applies: A keeps a copy of every unacked frame and resends any whose ack does not come in time.

### Rule 5: Every Ack Says How Much Room Is Left
B's kernel holds received bytes until B's program reads them. If B's program reads slowly, that memory fills up. If A keeps sending, B has nowhere to put the bytes and has to drop them. So every ack from B also says how much room B has left:

```text
ack 5000, room 8000 bytes   -> A may have at most 8000 unacked bytes out
ack 6000, room 0 bytes      -> A stops sending until B reports room again
```

The number of unacked bytes A is allowed to have out is the **window**. The "room" number B sends in every ack is the **window field** in the TCP group.

### The Next Problem
B has plenty of room and says "room 1,000,000 bytes". A sends 1000 frames at once. But on the way there is a router whose line holds only 200 frames (section 69). B's room number says nothing about that router. How can A find out how much the path between them can take?

---

## 73. What the Path Can Take

### A Tests the Path
A cannot ask the router. Routers do not answer questions about their lines. The only thing A can see is whether acks come back. So A starts small, sends more each time everything is acked, and backs off when something is lost.

### Rule 6: A Keeps a Second Limit of Its Own
A sends no more than whichever is smaller: its own limit, or B's room.

```text
start:                  10 frames     (Linux starts at 10)
all acked in one trip:  double it
a frame was lost:       cut it in half, then add 1 frame per trip
```

With the router line from before, which holds about 200 frames:

```text
trip    A's limit    what happens
1       10           all acked
2       20           all acked
3       40           all acked
4       80           all acked
5       160          all acked
6       320          router line overflows, some frames dropped
7       160          cut in half, resend the lost ones
8       161          +1
9       162          +1
...                  slowly rises until the line overflows again, then halves again
```

So A's limit stays close to what the path can take. When the path is busy, it goes down. When the path is quiet, it goes back up.

### Many Senders
Ten computers might send through the same router. Each one sees its own drops and lowers its own limit. None of them knows about the others, but together they bring the line back under 200.

### Names
A router line that is full, so frames get dropped, is **congestion**. A's own limit is the **congestion window**.

Linux uses a variant called CUBIC. It cuts to about 70% instead of half, and grows back faster than +1 per trip. Its formula is not covered here.

### The Next Problem
Until now, A just started sending frame 0. But B runs many programs and many conversations at once. How does B's kernel know that a new conversation is starting, and where its numbers begin?

---

## 74. Starting a Connection

### What B Needs First
Before any data, B's kernel has to set aside memory for the new conversation: the next byte it expects, its room, and space to hold frames that arrive out of order. It also has to know where A's numbers begin.

### Why Not Always Start at 0
Say A and B had a conversation a minute ago with the same ports. A frame from it could still be sitting in a router line and arrive late. If the new conversation also started at 0, B would take those old bytes as new ones. So each side picks a random starting number. The sequence field is 4 bytes, so the number can be 0 to about 4.3 billion, and an old frame almost never fits the new range.

### Why Both Sides Pick One
Data goes both ways. B will reply on the same conversation, so B's bytes need their own numbers, and A has to ack them.

### Rule 7: Three Frames Before Any Data
The TCP group has single-bit fields called flags (section 76). **SYN** (synchronize) means "this is my starting number". **ACK** means "read the ack number in this frame".

```text
1. A -> B:  SYN,       seq 4000                "my numbers start at 4000"
2. B -> A:  SYN + ACK, seq 9000, ack 4001      "got yours; mine start at 9000"
3. A -> B:  ACK,       ack 9001                "got yours"
```

Frame 3 is needed because B has to know that A received B's starting number. Each frame also carries its sender's room (rule 5). This exchange is the **handshake**.

### Which Things Take a Number
Each side keeps a counter. The seq field in each frame shows the counter's value at the moment the frame is sent. It is a counter, not an index from 0: each thing that takes a number gets the next one.

```text
frame   what A sends     seq field shows   counter after
1       SYN              4000              4001   (SYN takes 1 number)
3       plain ACK        4001              4001   (ACK takes no number)
4       "hi"             4001              4003   (h = 4001, i = 4002)
```

The rule: a number is given only to things that must be acked and resent if lost. Only three things are like that:

* **Data bytes**: one number each.
* **SYN**: without it there is no connection, so it takes a number for the other side to ack.
* **FIN** (section 75): the same reason.

A plain ACK is never acked itself. If acks needed acks, the ack of the ack would need an ack, forever. If a plain ACK is lost, the next ACK carries a newer number that covers everything before it.

Section 71 counted the photo from 0 to keep it simple. With the random start, photo byte 0 is actually number 4001, and photo byte k is 4001 + k.

### What B's Kernel Checks on the SYN
Some program on B must already have told the kernel "accept new conversations on port 7000". If no program did, B's kernel replies with a frame carrying the **RST** (reset) flag, meaning "nothing here". UDP answers the same case with ICMP "port unreachable".

### Four Values
After the handshake, B's kernel keeps the conversation under four values:

```text
A's IP : A's port      B's IP : B's port
192.168.1.23 : 50001   192.168.1.24 : 7000    -> next byte expected, room, held frames
192.168.1.25 : 50001   192.168.1.24 : 7000    -> a different conversation
```

Two senders can use the same port, as long as at least one of the four values differs. A conversation set up like this is a **connection**.

### The Next Problem
A has sent the whole photo, and every byte has been acked. B's kernel is still holding memory for this connection. How do both sides agree that it is over, so they can free it?

---

## 75. Ending a Connection

### Each Direction Ends Separately
When A is done sending, B may still have bytes to send back. So each side ends its own direction.

### Rule 8: FIN
A frame with the **FIN** (finish) flag means "I have no more bytes to send". Like SYN, the FIN takes one number, so it is acked and resent exactly like data.

A sent the 1,000,000-byte photo as bytes 4001 to 1,004,000. B sent back "ok", as bytes 9001 to 9002.

```text
1. A -> B:  FIN, seq 1004001      A's program called close(); "I'm done sending"
2. B -> A:  ACK 1004002           "got your FIN"
            ... B could still send bytes here ...
3. B -> A:  FIN, seq 9003         B's program called close(); "I'm done too"
4. A -> B:  ACK 9004              "got your FIN"
```

If B has nothing more to send, B's kernel often combines frames 2 and 3 into one frame (FIN + ACK), so the close takes three frames.

### How B's Program Learns That A Is Done
B's program gets the bytes by asking its kernel over and over, in a loop:

```text
loop:
    data = read()      # whatever bytes have arrived
    if data is empty:  # 0 bytes
        stop
    save data
```

Each `read()` returns the bytes that have arrived so far. If nothing has arrived yet, it waits until something does. So `read()` normally never returns 0 bytes: it either returns some bytes or it waits.

After the FIN arrives and B's program has read every byte before it, the kernel knows no more bytes will ever come. So the next `read()` returns 0 bytes immediately. The program never sees the FIN frame itself. That empty result is the only way B's program learns that A is done.

### TIME_WAIT
Frame 4 can be lost. Then B, which gets no ack for its FIN, sends the FIN again (rule 3). If A had already deleted the connection, it would not recognize that FIN. So the side that sent the first FIN keeps the four values for a while after frame 4: 60 seconds on Linux. During that time, late frames from this connection arrive while the four values are still taken, so they cannot be mistaken for part of a new connection. This waiting state is **TIME_WAIT**.

### The Faster Ending: RST
```text
normal:  FIN -> ACK -> FIN -> ACK, then 60 s wait
RST:     one frame, no ack, no wait
```

When a kernel sends or receives RST, it deletes the connection at once. Any bytes still in its memory, either not yet sent or not yet read by the program, are thrown away. The program on the other side gets an error ("connection reset") instead of the empty read.

When it is sent:

* **A frame arrives for a connection that does not exist**, for example the late frame from S in section 60.
* **A program closes the connection while bytes it has not read are still in its kernel.** Linux then sends RST instead of FIN, so the other side knows not everything was taken.

A program that exits abruptly does not always cause RST. When a program exits, the kernel closes its connections for it, and if there are no unread bytes, it sends a normal FIN.

---

## 76. The TCP Group

### The Rules of TCP
```text
rule    what it says                                                       what it fixes
ports   "to port" picks the program; "from port" is where replies go        which program (same as UDP)
1       every byte has a number; seq = the number of the frame's first byte which pieces are missing
2       the receiver acks the next number it wants; it holds out-of-order   order, no gaps
        bytes and gives its program only bytes in order
3       keep a copy until acked; resend if no ack comes in time             lost frames
4       many unacked frames may be out at once                              waiting on every ack
5       every frame carries how much more its sender has room for           the receiver's memory
6       congestion window: start at 10, double while all acked, cut on      router lines
        loss, grow slowly; send no more than the smaller of this and room
7       SYN, SYN + ACK, ACK, with a random start on each side;              starting
        RST if no program accepts that port
8       FIN for each direction, acked; the first-FIN side waits 60 s;       ending
        RST ends at once
check   checksum; if it does not match, the frame is dropped, so no ack     damaged bytes
        comes and rule 3 resends it
```

### The Layout
It sits where the UDP group was: after the IP group, before the data. It is at least 20 bytes. Each row below is 4 bytes:

```text
byte    0          1          2          3
      +----------+----------+----------+----------+
  0   |      from port      |       to port       |
  4   |               sequence number             |
  8   |                 ack number                |
 12   | len | rsv |  flags  |       window        |
 16   |      checksum       |   urgent pointer    |
 20   |      options (0 to 40 bytes, if any)      |
      +-------------------------------------------+
```

### The Fields
```text
field            size       what it holds                                                     rule
from port        2 bytes    sender's port                                                     ports
to port          2 bytes    receiver's port                                                   ports
sequence number  4 bytes    the number of this frame's first data byte; on a SYN or FIN,      1, 7, 8
                            the number that the SYN or FIN itself takes
ack number       4 bytes    the next number expected from the other side                      2
len              4 bits     length of the TCP group itself, in 4-byte units                   -
rsv              4 bits     reserved, always 0                                                -
flags            8 bits     eight yes/no bits                                                 7, 8
window           2 bytes    room: how many more bytes the sender of this frame can accept     5
checksum         2 bytes    damage check over the TCP group, the data, and the from and to IP check
urgent pointer   2 bytes    almost never used, 0                                              -
options          0-40 bytes extra settings, mostly sent in SYN frames                         -
```

### len
It counts only the TCP group, not the data. 5 means 5 × 4 = 20 bytes, with no options. 6 means 24 bytes, for example 20 plus one 4-byte option. 15 is the maximum, which means 60 bytes. Options make the group's size vary, so the receiver needs len to find where the data starts.

TCP has no field for the data's length. The receiver works it out from the IP group, which records the length of everything after the MAC group: IP total length − IP group − TCP group. UDP is the other way around. Its group is always 8 bytes, so it needs no group length, and its length field counts the group plus the data.

### Flags
A flag is one bit: 1 means yes, 0 means no. It is not text. The flags field is 1 byte, which is 8 bits, so it holds 8 yes/no answers, one per bit:

```text
bit:      CWR ECE URG ACK PSH RST SYN FIN
SYN:       0   0   0   0   0   0   1   0      = 02
SYN+ACK:   0   0   0   1   0   0   1   0      = 12
```

* **SYN**: "my numbers start here" (rule 7).
* **ACK**: read the ack number. Set on every frame after the first SYN.
* **FIN**: "I have no more bytes to send" (rule 8).
* **RST**: "end this connection now" or "nothing here".
* **PSH** (push): give the data to the program now. Linux sets it on the last frame of each send call.
* **URG**: the urgent pointer is valid. Almost never used.
* **ECE, CWR**: used when a router marks a frame to signal congestion instead of dropping it. This is the one exception to "routers only drop". It needs both ends and the routers to support it, and Linux does not ask for it on its own outgoing connections.

### "Read Only If ACK Is Set"
The 4 bytes for the ack number are in every TCP group. In A's very first SYN, A has received nothing from B, so there is nothing to ack. Those 4 bytes are 0, and the ACK bit is 0, which tells B "ignore these 4 bytes". In every frame after that, the ACK bit is 1, which means "these 4 bytes contain a real ack number, read them".

### Options
An option is written as 1 byte for its kind, 1 byte for its total length, then the value.

* **MSS**: "send me at most this many data bytes per frame" (section 77). Kind 2, length 4, value 2 bytes.
* **Window scale**: the window field is 2 bytes, so it holds at most 65535. With a 50 ms round trip, A could then send only 65535 bytes every 50 ms, about 1.3 MB per second, even on a much faster cable. With this option in its SYN, a side says "multiply every window number I send by 128" (or another power of 2). After that, a window field of 8000 means 8000 × 128 = 1,024,000 bytes.

A real Linux SYN carries a few more options. They are not covered here.

### Checksum vs CRC
They are two different checks in two places:

```text
[MAC group][IP group][TCP group (checksum inside)][data][CRC]
 ^ chip                ^ A's kernel                       ^ chip
```

* **CRC**: the chip adds the MAC group at the front and the CRC at the end. The CRC covers one trip, from one chip to the next. A router checks it, removes the MAC group and CRC, changes the TTL, then writes a new MAC group and computes a new CRC.
* **Checksum**: written once by A's kernel, inside the TCP or UDP group, and checked only by B's kernel.

Both are needed because inside a router, the frame sits in memory with no CRC protecting it. If a memory fault or a software bug damages a byte there, the router computes the new CRC over the damaged bytes, and every chip after that sees a matching CRC. Only the checksum, made at A and checked at B, catches it.

### What Is Not a Field
The congestion window (rule 6) is not in the group. It exists only in the sender's kernel memory, and the other side never sees it. The same goes for the copies kept for resending, and for the timers.

---

## 77. How Big a Frame Can Be

### MTU
The **MTU** (maximum transmission unit) is the most bytes a frame can carry after the MAC group: IP group + TCP or UDP group + data, together. It is a size limit from the network's rules, not a speed.

* **Cable**: the rules set it to 1500.
* **Wireless**: the air rules allow up to 2304 bytes. But the access point turns air frames into cable frames (section 54), and those can be at most 1500, so wireless networks use 1500 too.

The kernel stores one MTU number for each chip, which is 1500 by default. Nothing measures it.

### 1500 Is a Default, Not a Law
1500 counts only the part after the MAC group. The whole cable frame is longer:

```text
MAC group           14 bytes
IP + TCP + data     up to 1500 bytes   <- the MTU
CRC                  4 bytes
total               up to 1518 bytes
```

* **Larger**: in data centers, chips and switches are often set to an MTU of 9000. That only works if every chip and switch on that local network is set to accept it. A switch set to 1500 drops the larger frames. Frames over 1500 like this are **jumbo frames**.
* **Smaller**: some internet providers add 8 bytes of their own to every frame on the cable to the house, so the MTU on that cable is 1492.

Every machine on one local network has to use the same value.

### MSS
The **MSS** (maximum segment size) is the most data bytes per frame. The kernel computes it from the MTU:

```text
1500 (MTU) - 20 (IP group) - 20 (TCP group) = 1460 (MSS)
```

When the handshake starts, each side writes its own MSS into an option in its SYN. Both sides then use the smaller of the two.

### A Smaller MTU on the Path
The lower MTU is usually not on your own local network. It is on a cable further along, for example the provider's cable at 1492:

```text
laptop --1500-- [home box] --1492-- company router -- ... -- S
```

The laptop sends a 1500-byte frame, and the box cannot put it on the 1492 cable. Two things handle this automatically, which is why nobody normally sets an MTU by hand.

**Fix 1: the box rewrites the MSS in the SYN.** The home box knows its own provider cable is 1492. When the laptop's SYN passes through, the box changes the MSS option inside it from 1460 to 1452 (1492 − 40), and it does the same to S's SYN coming back. From then on, both sides send frames that fit.

**Fix 2: the router reports "too big".** This is for a smaller cable further away that the box does not know about. Linux sets a "do not split" bit in the IP group of TCP frames. A router that gets a frame too big for its next cable then:

1. drops it
2. sends an ICMP message (section 78) back to the sender: "too big, the most I can take is 1492"

The sender's kernel stores 1492 for that destination, makes smaller frames, and resends the lost data (rule 3). Finding the smallest MTU on the way like this is **path MTU discovery**.

If the "do not split" bit is not set, the IP rules let the router split the frame into smaller pieces instead, and the receiver's kernel joins them back together. Linux avoids this for TCP, because if one piece is lost, the whole frame is lost.

---

## 78. ICMP

### What It Is
**ICMP** (Internet Control Message Protocol) is the protocol routers and kernels use to send short messages about delivery problems back to the sender of a frame. Section 18 used it once: when TTL reaches 0, the router drops the frame and sends an ICMP message back.

### Where It Sits
ICMP has its own group in the same place as the TCP or UDP group, right after the IP group (protocol number 1):

```text
[MAC group][IP group, protocol 1][ICMP group][CRC]
```

It has no ports. The message is for the sender's kernel, not for a program.

### Its Fields
```text
type        1 byte    what kind of message
code        1 byte    more detail within that type
checksum    2 bytes   damage check
extra       4 bytes   depends on the type
copy        the IP group and the first 8 bytes after it, from the frame that caused the problem
```

The copy is how the sender's kernel knows which connection the message is about: those first 8 bytes after the IP group contain the from port and to port.

### Messages Met So Far
```text
type  code   meaning                    when
11    0      TTL reached 0              section 18
3     4      too big, cannot split      path MTU (section 77); "extra" holds the allowed size, e.g. 1492
3     3      no program on that port    a UDP frame for a port nobody asked for (section 70)
8     0      echo request               sent by the `ping` program
0     0      echo reply                 the other kernel's answer to ping
```

`ping` checks whether a machine is reachable without any program listening on a port: the other computer's kernel itself answers type 8 with type 0.

---

## 79. A Full TCP Conversation, Every Field

### The Setup
Two buildings on cable, as in section 16:

```text
A  192.168.1.1   MAC aa:aa:aa:aa:aa:aa   port 50001
R  socket 1: 192.168.1.254  MAC 11:11:11:11:11:11
   socket 2: 192.168.2.254  MAC 22:22:22:22:22:22
D  192.168.2.4   MAC dd:dd:dd:dd:dd:dd   port 7000 (a program on D is listening)

A --cable-- switch 1 --cable-- R --cable-- switch 2 --cable-- D
```

A sends "hi", D answers "ok", then both close. A's ARP table already has R's MAC, and R's ARP table already has D's MAC. The starting numbers are A = 4000 and D = 9000.

### Frame 1: SYN, A -> D, on the Cable in Building 1
Every byte, in the order it goes on the cable. Byte values are in hex.

Start pattern (section 3):

```text
field           value                                bytes
start pattern   10101010 seven times, then 10101011  AA AA AA AA AA AA AA AB
```

MAC group, 14 bytes:

```text
field      value         bytes               meaning
to MAC     R socket 1    11 11 11 11 11 11   next machine on this cable
from MAC   A             AA AA AA AA AA AA   who put it on this cable
type       0x0800        08 00               an IP group comes next (section 19)
```

IP group, 20 bytes:

```text
field                 size     value               bytes         meaning
version               4 bits   4                   4_            version of the IP rules; 4 = the 4-byte addresses
header length         4 bits   5                   _5            IP group length in 4-byte units: 5 × 4 = 20 bytes
service               1 byte   0                   00            priority marks; 0 = normal
total length          2 bytes  44                  00 2C         IP group + TCP group + data: 20 + 24 + 0
identification        2 bytes  7238                1C 46         a number for this frame, used only if a router splits it
flags + split position 2 bytes "do not split" = 1  40 00         the bit from section 77; position is used only when split
TTL                   1 byte   64                  40            hop counter (section 18)
protocol              1 byte   6                   06            a TCP group comes next
header checksum       2 bytes  computed            xx xx         damage check on these 20 IP bytes only
from IP               4 bytes  192.168.1.1         C0 A8 01 01   the original sender
to IP                 4 bytes  192.168.2.4         C0 A8 02 04   the final destination
```

TCP group, 24 bytes (20 + one 4-byte option):

```text
field            size     value                          bytes
from port        2 bytes  50001                          C3 51
to port          2 bytes  7000                           1B 58
sequence number  4 bytes  4000                           00 00 0F A0
ack number       4 bytes  0 (ignored, ACK bit is 0)      00 00 00 00
len + rsv        1 byte   len 6 (6 × 4 = 24), rsv 0      60
flags            1 byte   SYN only: 00000010             02
window           2 bytes  64240                          FA F0
checksum         2 bytes  computed                       xx xx
urgent pointer   2 bytes  0                              00 00
option: MSS      4 bytes  kind 2, length 4, value 1460   02 04 05 B4
```

A real Linux SYN carries a few more options. Only MSS is shown here.

Data: none.

Padding and CRC:

```text
field     value      bytes          meaning
padding   zeros      00 00          14 + 20 + 24 + 4 = 62; the minimum is 64, so 2 zero bytes are added.
                                    D ignores them because the IP total length says 44
CRC       computed   xx xx xx xx    damage check for this one cable trip
```

Then the cable goes quiet.

### Frame 1 Again, After R
R checks the CRC, removes the MAC group and CRC, reads "to IP", picks socket 2, lowers the TTL, and builds a new frame. Every field from both hops:

```text
field                    hop 1 (building 1)          hop 2 (building 2)
to MAC                   11:11:11:11:11:11 (R s1)    dd:dd:dd:dd:dd:dd (D)            <- changed
from MAC                 aa:aa:aa:aa:aa:aa (A)       22:22:22:22:22:22 (R s2)         <- changed
type                     0x0800                      0x0800
version, header length   4, 5                        4, 5
service                  0                           0
total length             44                          44
identification           7238                        7238
flags + split position   do not split, 0             do not split, 0
TTL                      64                          63                               <- changed
protocol                 6                           6
header checksum          computed                    computed again (TTL changed)     <- changed
from IP                  192.168.1.1                 192.168.1.1
to IP                    192.168.2.4                 192.168.2.4
whole TCP group          as above                    unchanged, R never reads it
padding                  2 zero bytes                2 zero bytes
CRC                      computed                    computed again                   <- changed
```

Every frame below crosses R the same way: the MAC pair, the TTL, the IP header checksum and the CRC change. Nothing else does.

### All 9 Frames
These fields are the same in every frame: type 0x0800, version 4, header length 5, service 0, "do not split" = 1, protocol 6, urgent pointer 0. The identification gets a new number on each frame from the same sender. The checksums and CRC are computed for each frame.

```text
#  direction  from IP -> to IP               IP total  seq    ack    len  flags     window  data
1  A -> D     192.168.1.1 -> 192.168.2.4     44        4000   0      6    SYN       64240   none (MSS option)
2  D -> A     192.168.2.4 -> 192.168.1.1     44        9000   4001   6    SYN, ACK  64240   none (MSS option)
3  A -> D     192.168.1.1 -> 192.168.2.4     40        4001   9001   5    ACK       64240   none
4  A -> D     192.168.1.1 -> 192.168.2.4     42        4001   9001   5    ACK, PSH  64240   68 69 ("hi")
5  D -> A     192.168.2.4 -> 192.168.1.1     42        9001   4003   5    ACK, PSH  64240   6F 6B ("ok")
6  A -> D     192.168.1.1 -> 192.168.2.4     40        4003   9003   5    ACK       64240   none
7  A -> D     192.168.1.1 -> 192.168.2.4     40        4003   9003   5    FIN, ACK  64240   none
8  D -> A     192.168.2.4 -> 192.168.1.1     40        9003   4004   5    FIN, ACK  64240   none
9  A -> D     192.168.1.1 -> 192.168.2.4     40        4004   9004   5    ACK       64240   none
```

MACs on each hop:

```text
direction   hop 1                  hop 2
A -> D      to R s1, from A        to D, from R s2
D -> A      to R s2, from D        to A, from R s1
```

### How to Read the Numbers
* **len is 6, then 5.** Frames 1 and 2 have the 20 standard bytes plus the 4-byte MSS option: 24 ÷ 4 = 6. Frames 3 to 9 have no options: 20 ÷ 4 = 5. MSS is sent only in SYN frames, because both sides only need to agree on it once.
* **Frames 3 and 4 both have seq 4001.** The SYN took 4000, so A's counter is at 4001. Frame 3 is a plain ACK and takes no number, so the counter stays at 4001 (section 74). Frame 4 is sent next and also shows 4001. Its "hi" is 2 bytes, so "h" = 4001 and "i" = 4002.
* **Frame 5 has ack 4003.** D received 4001 and 4002 and wants 4003 next. D sent "ok" in the same frame as this ack instead of sending a separate ack frame.
* **Frames 6 and 7 both have seq 4003.** Frame 6 is an ACK only. Frame 7's FIN takes 4003, so D acks it with 4004 in frame 8.
* **Frame 8** is D's FIN combined with its ack of A's FIN. D's FIN takes 9003, so A acks 9004.
* **IP total length**: 20 (IP) + 20 or 24 (TCP) + data bytes. 42 = 20 + 20 + 2.
* **After frame 9**, A keeps the four values (192.168.1.1, 50001, 192.168.2.4, 7000) for 60 seconds in TIME_WAIT.

---

## 80. Layers

### The Problem
A frame now has four groups: the MAC group, the IP group, the TCP or UDP group, and the data. Each was added to solve a different problem. Why are they kept as separate groups instead of one big set of rules?

### Who Reads Which Group
```text
group               problem it solves                            read by
voltage / waves     sending bits at all                          every chip
MAC group + CRC     which machine on this cable or in this air   every chip, switches, access points
IP group            which computer anywhere, across routers      routers, the two end kernels
TCP or UDP group    which program; for TCP: loss, order, speed   the two end kernels only
data                what the bytes mean                          the two programs only
```

A switch reads 6 bytes and nothing else. A router reads the IP group and never looks at the TCP group. If everything were one set of rules, every switch and router would have to understand all of it.

### Each Group Can Be Replaced on Its Own
* **Cable vs air.** The MAC group in the air is different: kind, duration, three MACs. But the IP and TCP groups inside are byte for byte the same. The access point swaps only the MAC group (section 54). TCP never knows that part of the path was wireless.
* **TCP vs UDP.** Routers forward both the same way, because they only read the IP group. Only the protocol field (6 or 17) changes.
* **A new kind of program.** A chat program, a game and a web browser each put their own data in. No switch, router or kernel has to change.

Inside the kernel it works the same way. The TCP code hands its group to the IP code, the IP code hands it to the chip's driver, and none of them reads the others' fields.

### Names and Numbers
Each group is a **layer** (section 19). They are usually numbered, and the numbers appear in names like "L4 load balancer":

```text
number  name           what is in the frame            examples
1       physical       voltage on the cable, waves     cable signals, Wi-Fi channel 36
2       data link      MAC group + CRC                 cable frame, wireless frame, ARP
3       network        IP group                        IP, ICMP
4       transport      TCP or UDP group                TCP, UDP
7       application    the program's data              DNS questions, HTTP
```

"L4" means "reads up to the TCP or UDP group". "L7" means "also reads the program's data".

### Why the Numbers Skip 5 and 6
In the late 1970s and 1980s, two groups designed network rules at about the same time:

* **OSI** (Open Systems Interconnection): an international standards organization (ISO) designed a full set of protocols with 7 layers.
* **TCP/IP**: researchers on a US government network designed IP, TCP and UDP, with fewer layers.

TCP/IP was already running on real machines, and anyone could use it without paying, so it is what spread. The OSI protocols themselves are almost unused today. But OSI's 7-layer numbering was kept as a common way to talk about layers. So "L2", "L3", "L4" and "L7" are OSI numbers, while the actual groups in a frame are TCP/IP's.

The two skipped layers:

* **5, session**: starting, pausing and resuming a conversation.
* **6, presentation**: the format of the data, for example text encoding or encryption.

TCP/IP has no separate group for either. Programs handle them inside their own data, so on a real frame they are part of layer 7. People often describe TCP/IP itself as 5 layers numbered 1 to 5, but in conversation, the OSI numbers 1, 2, 3, 4 and 7 are what is used.

### Two That Do Not Fit Neatly
**ARP.** An ARP frame has no IP group at all:

```text
[to MAC, from MAC, type 0x0806][ARP question: "who has 192.168.1.254?"][CRC]
```

Its job is to find a MAC on one local network, and it never passes through a router. So it is placed at layer 2.

**ICMP.** By position, the ICMP group sits where TCP or UDP would, so it looks like layer 4:

```text
[MAC group][IP group, protocol 1][ICMP group: type, code, ...][CRC]
```

But its job is to report IP delivery problems, and it has no ports. So it is counted as part of layer 3, with IP.

---

## 81. IP as a Protocol

An **IP address** is one field in the IP group. **IP** (Internet Protocol) is the whole set of rules: the layout of the 20 bytes (section 79), and what each machine does with them.

The sender's kernel:

1. Fills in "from IP" with its own address and "to IP" with the destination.
2. Sets TTL to 64 and the protocol number (6 for TCP, 17 for UDP, 1 for ICMP).
3. Looks up "to IP" in its routing table to choose: send directly, or send to the default gateway.

Each router:

1. Checks the header checksum. If it does not match, it drops the frame.
2. Lowers TTL by 1. If TTL reaches 0, it drops the frame and sends ICMP "TTL reached 0" back.
3. Looks up "to IP" in its routing table and picks a socket.
4. If the frame is too big for that socket and "do not split" is set, it drops the frame and sends ICMP "too big" back.
5. Computes a new header checksum, because TTL changed, and sends the frame out.

The receiver's kernel:

1. Checks that "to IP" is its own address.
2. Reads the protocol number and passes the rest to the TCP, UDP or ICMP code.

What IP does not do: it does not ack, resend, keep order or slow down. A router that cannot deliver a frame drops it. That is why TCP exists on top of it.

The version field says 4 because this is IP version 4, with 4-byte addresses. There is also a version 6 with longer addresses. It is not covered here.

---

## 82. Where One Message Ends

### The Problem
A's program calls `send("hi")` and then `send("there")`. TCP numbers bytes, not sends. D's kernel puts arriving bytes into one buffer, in order, with nothing between them. Say D's program is busy for a moment, and both frames arrive in the meantime:

```text
D's buffer:  h i t h e r e
read(1024) returns "hithere"   (all 7 bytes, the most it can give)
```

It can also go the other way. If "there" arrived split across two frames, one `read()` might return "the" and the next "re".

So the two programs have to agree on their own rule for marking where a message ends. That rule goes in the data, at layer 7.

### Three Common Ways
**1. Write the length first.** Before each message, A writes its length in 2 bytes:

```text
00 02 h i 00 05 t h e r e
```

D reads 2 bytes and gets 2, then reads until it has exactly 2 more bytes: "hi". Then it reads 2 bytes and gets 5, then 5 more: "there". D keeps calling `read()` until each count is reached, so a split arrival does not matter.

**2. End each message with a special byte**, for example the newline byte, 0A:

```text
h i 0A t h e r e 0A
```

D reads until it sees 0A. A message cannot contain 0A itself unless both sides add an extra rule for it.

**3. One message per connection.** A sends "hi" and then FIN. D reads until `read()` returns 0 bytes. This is the simplest, but every message costs a handshake and a close.

### Application Protocol
A program's own rules, covering how messages are marked and what the bytes in them mean, are an **application protocol**: the layer 7 part. DNS is one. Its question and answer have a fixed layout inside the UDP data.

---

## 83. A DNS Message, Byte by Byte

A DNS question and its answer each fit in one UDP datagram. The whole DNS message is the data after the UDP group:

```text
[to MAC, from MAC, type 0x0800]
[IP group: from 192.168.1.23, to 192.168.1.254, protocol 17, TTL 64, ...]
[UDP group: from port 50123, to port 53, length, checksum]
[DNS message: header 12 bytes, question 23 bytes]
[CRC]
```

The DNS message has its own 12-byte header, inside the data. It is a different thing from the MAC, IP and UDP groups.

### The Question From A to the Resolver
```text
header (12 bytes)
  ID              3A 7F    a random number; the answer carries the same one
  flags           01 00    "this is a question; please do the asking for me"
  questions       00 01    1 question follows
  answers         00 00    0
  name servers    00 00    0
  extra records   00 00    0

question
  name     03 77 77 77                       3, "www"
           09 62 6C 75 65 70 69 7A 7A 61     9, "bluepizza"
           03 63 6F 6D                       3, "com"
           00                                0 = end of name
  type     00 01    A (1 = A, 2 = NS, 5 = CNAME)
  class    00 01    always 1 in practice
```

The name is not stored with dots. Each part is written as one length byte followed by its letters, and a 0 byte ends the name. That is method 1 from section 82, used inside the name.

### The Answer From the Resolver to A
```text
header
  ID              3A 7F    same as the question, so A knows which question this answers
  flags           81 80    "this is an answer; I did the asking; no error"
  questions       00 01
  answers         00 01    1 answer record follows
  name servers    00 00
  extra records   00 00

question     (copied back unchanged, the same 23 bytes as above)

answer record
  name     C0 0C           "the same name as at byte 12 of this message"
  type     00 01           A
  class    00 01
  TTL      00 00 01 2C     300 seconds
  length   00 04           the value is 4 bytes
  value    C6 33 64 07     198.51.100.7
```

* **ID.** A could have several questions out at once, and UDP does not track which datagram answers which (section 84). The ID is how A matches each answer to its question.
* **C0 0C.** Instead of writing `www.bluepizza.com` again, these 2 bytes point back to byte 12 of this message, where the name starts in the question. This saves space.
* **The four counts** say how many records of each kind follow. "Name servers" and "extra records" are where an NS record and its address go in the com server's answer, the "address sent alongside" from section 66.
* **Where the message ends.** One datagram is one whole DNS message, and UDP's length field marks its end. UDP never joins two datagrams the way TCP joins bytes, so DNS needs no extra boundary rule over UDP.

### Each Resolver Question Is a New Message
Nothing is appended to the laptop's message. The laptop's message ends at the resolver. The resolver then writes its own new questions, each in a new UDP datagram, from its own IP and port, with its own new ID:

```text
1. laptop   -> resolver       ID 3A7F   "www.bluepizza.com?"  (please do the asking)
2. resolver -> root           ID 91C2   "www.bluepizza.com?"  (just tell me what you know)
   root     -> resolver       ID 91C2   NS for com + com server's address
3. resolver -> 192.0.2.10     ID 4E08   "www.bluepizza.com?"
   com      -> resolver       ID 4E08   NS for bluepizza.com + 203.0.113.53
4. resolver -> 203.0.113.53   ID B713   "www.bluepizza.com?"
   ns1      -> resolver       ID B713   A 198.51.100.7
5. resolver -> laptop         ID 3A7F   A 198.51.100.7
```

In steps 2 to 4, the "please do the asking" flag is off. Root and com only answer with what they hold. In step 5, the resolver writes a fresh answer message for the laptop, using the laptop's original ID, 3A7F.

---

## 84. UDP Has No Connection

### What the Kernel Keeps
UDP has ports, and the kernel keeps one table: which port belongs to which program. What it does not keep is a record for each conversation.

```text
UDP: one row per program's port
  port 50123  ->  DNS program on A
  (any datagram arriving for 50123, from anyone, goes to this program)

TCP: one row per conversation
  192.168.1.1 : 50001  <->  192.168.2.4 : 7000
     next seq to send, next byte expected, window,
     copies of unacked bytes, timers, state (e.g. TIME_WAIT)
```

When A sends a UDP question, A's kernel writes no row saying "I sent something to 192.168.1.254 port 53, expect a reply". It builds the frame, sends it, and keeps nothing about it. That is what "UDP has no connection" means.

### How the Reply Still Comes Back
1. A's program sends from port 50123 to the resolver's port 53. The frame carries "from port 50123".
2. The resolver's program reads the question. Its kernel also gives it A's IP and port, taken from the frame.
3. The resolver's program sends a new datagram from port 53 to `192.168.1.23 : 50123`.
4. A's kernel reads "to port" 50123, finds the row `50123 -> DNS program`, and gives it the data.

To UDP, the reply is just another datagram that happens to go to port 50123. If A's program sends two questions from the same port, both answers come back to that port, possibly in either order. The idea of "question and answer" belongs to the programs, following DNS's rules, and the ID is how A's program matches them.

### connect() on UDP
`connect()` is the function a program calls to give its kernel the other end's address. With TCP, it starts the handshake. With UDP, it sends nothing at all. It only adds the other end's IP and port to the kernel's row:

```text
before connect():
  port 50123  ->  DNS program        (accepts datagrams from anyone)

after connect(("192.168.1.254", 53)):
  port 50123, only from 192.168.1.254 : 53  ->  DNS program
```

After that:

1. **Receiving**: a datagram for port 50123 from any other IP or port is not given to the program.
2. **Sending**: the program can call `send()` without writing the address each time.

This is called a "connected UDP socket", but it is not a connection like TCP's:

```text
                          TCP connection             UDP after connect()
frames sent to set up     handshake, 3 frames        none
other side knows          yes, both kernels agree    no, only A's kernel has the row
what the row holds        seq numbers, window,       the other end's IP and port, nothing else
                          copies, timers
lost datagram             resent                     still lost
order                     guaranteed                 not guaranteed
```

### Fake DNS Answers
Without `connect()`, any datagram for the program's port, from any IP, reaches the program. Someone on another computer cannot see A's question, but they can write any "from IP" into a frame they send, so they can pretend to be the resolver. Two things stop a fake answer from being used.

**1. The program checks.** A program that sends a DNS question remembers the ID and where it sent it. It throws away any answer that comes from a different IP or port than the one it asked, or that has a different ID. With `connect()`, the kernel does the first check. The ID check stays in the program, because the kernel never reads the DNS data. Most DNS code on Linux uses `connect()`.

**2. Guessing is hard.** To be accepted, the faker has to guess:

```text
ID              1 of 65,536
A's port        1 of about 28,000 (picked at random by the kernel)
together        about 1 in 1.8 billion
```

The fake also has to arrive before the real answer, because once the program accepts an answer, it stops listening for that question.

If a resolver does accept a fake answer, it keeps it in memory for the TTL the faker wrote. During that time, every laptop that asks this resolver for `www.bluepizza.com` gets the faker's address. This attack is **DNS cache poisoning**, and it is the reason the ID and the port are random instead of counting up.

---

## 85. Request and Response Belong to the Programs

### TCP Does Not Have Them Either
TCP gives the two programs two streams of bytes, one in each direction, delivered in order and with no gaps. What those bytes mean, and whether one message is a "request" and the next is a "response", is decided by the programs' own rules at layer 7.

* **TCP's acks are not responses.** The kernels write them, only to say "bytes up to here arrived". The program never sees them.
* **Either side can send at any time.** In a chat program, both sides send whenever a person types. Nothing forces question, answer, question, answer.
* **TCP's record is about delivering bytes.** It holds sequence numbers, window and copies, not "which question is this the answer to".

So the difference between UDP and TCP is not request and response. TCP has a connection and guarantees every byte arrives in order. UDP sends separate datagrams and guarantees nothing. Request and response are something a layer 7 protocol adds, like DNS does with its ID.

### Sending in One Direction Only
A program can send over TCP and never read anything back. For example, a program can send its log lines to a log server all day, and the log server never writes a byte back. TCP has no issue with that. The receiving kernel still sends acks, so frames flow back, but they carry no data.

Two things still reach a program that never reads:

* **If the other program stops reading**, its room drops to 0, the sending kernel stops, and eventually `send()` waits (rule 5).
* **If the connection breaks**, for example the other side sent RST, the next `send()` returns an error.

---

## 86. HTTP: Asking for a Page

### The Situation
The browser on A has a TCP connection open to `198.51.100.7` port 80 (section 66). It wants the page `/menu`. A page is just bytes the server stores, for example in a file.

### What the Request Has to Say
1. **What to do**: get a page. The browser writes the word `GET`.
2. **Which page**: its name, `/menu`. A name like this is a **path**.
3. **Which version of the rules**: `HTTP/1.1`, so the server reads the rest correctly.
4. **Which website**: `Host: www.bluepizza.com`. The reason is below.
5. **Where the request ends**: method 2 from section 82. Each line ends with the two bytes `0D 0A` (written `\r\n`), and an empty line ends the request.

```text
GET /menu HTTP/1.1\r\n             20 bytes
Host: www.bluepizza.com\r\n        25 bytes
\r\n                                2 bytes   <- empty line: request is over
```

### Why the Host Line
One computer can run several websites, all on port 80. The browser connects to port 80 for every website, by agreement, and the person only types a name, never a port. So one web server program listens on port 80 and holds the pages of several websites, in separate folders:

```text
DNS:
  www.bluepizza.com    A    198.51.100.7
  www.greencafe.com    A    198.51.100.7     <- same computer

web server program on port 80:
  folder /sites/bluepizza/   has  menu
  folder /sites/greencafe/   has  menu
```

This is common when a hosting company rents one computer to many small shops, like hostco in section 66. Both websites have a page called `/menu`. The TCP connection only carries the IP, so with only `GET /menu` the program could not tell which folder to use. The browser writes the name it looked up with DNS, `Host: www.bluepizza.com`, and the program picks the bluepizza folder.

### What a Line Is
HTTP/1.1 requests are text. Every letter is one byte, for example `G` = 47 and `E` = 45. A **line** is a run of these bytes ended by the two bytes `0D 0A`. The first line, byte by byte:

```text
G  E  T     /  m  e  n  u     H  T  T  P  /  1  .  1  \r \n
47 45 54 20 2F 6D 65 6E 75 20 48 54 54 50 2F 31 2E 31 0D 0A
```

20 is the space. HTTP's rules say what each line holds:

* **Line 1**: the action, the path and the version, separated by spaces.
* **Each line after that**: one extra piece of information, written `Name: value`.

`0D` and `0A` are control bytes, not letters. They come from old terminals, where one moved the print position back to the left and the other moved it down a line. HTTP's rules use the pair to mark the end of a line.

### Where the Request Ends
TCP gives the server one stream of bytes (section 82), possibly arriving in several pieces. The server has to know when the browser has finished its request, so it can start answering. After the last `Name: value` line, the browser sends one more `0D 0A` with nothing before it: an empty line. The server keeps reading until it sees four bytes in a row, `0D 0A 0D 0A`:

```text
...  c  o  m  \r \n \r \n
...  63 6F 6D 0D 0A 0D 0A
              ^ end of the Host line
                    ^ empty line = request is over
```

### What the Reply Has to Say
1. **Did it work**: a number and a short word. `200 OK` means "found, here it is". `404 Not Found` means "no page with that path".
2. **What kind of bytes the page is**: `Content-Type`. It does the same job as the type field in the MAC group and the protocol field in the IP group: it says what comes next.
3. **Where the page ends**: the page can contain any bytes, including `0D 0A 0D 0A`, so an empty line cannot mark its end. Method 1 from section 82 is used instead: the server writes the length first, `Content-Length`.
4. **The page itself.**

Say the page is this 26-byte text:

```text
Margherita 8\n      13 bytes
Pepperoni 10\n      13 bytes
```

The reply:

```text
HTTP/1.1 200 OK\r\n
Content-Type: text/plain\r\n
Content-Length: 26\r\n
\r\n
Margherita 8\nPepperoni 10\n
```

The browser reads lines until the empty line, finds `Content-Length: 26`, and then reads exactly 26 more bytes.

Some `Content-Type` values:

```text
text/plain      plain text, like the menu
text/html       a web page the browser draws
image/jpeg      a photo
```

In HTTP/1.1, the first line and the headers are always text. The body can be any bytes: text, a photo, a video, a zip file. Because of `Content-Length`, the body is never searched for `0D 0A`, so any byte value is allowed.

### Names
* The first line of a request, `GET /menu HTTP/1.1`, is the **request line**. `GET` is the **method**.
* The first line of a reply, `HTTP/1.1 200 OK`, is the **status line**. `200` is the **status code**.
* Each `Name: value` line is a **header**.
* The bytes after the empty line are the **body**.
* These rules are **HTTP** (Hypertext Transfer Protocol). "Hypertext" means text with links to other pages.

All of it is layer 7: plain bytes in the TCP data. Routers and TCP never look at any of it.

### Why the Connection Is Not Closed After the Request
The browser could mark the end of its request with FIN (method 3). FIN closes only the browser's sending direction, so the reply would still come back:

```text
browser -> server:  "GET /menu ..."  then FIN     browser can't send anymore
server  -> browser: "HTTP/1.1 200 OK ... body"    browser still receives this
server  -> browser: FIN
```

HTTP/1.1 uses the empty line instead because of reuse. After a FIN, the browser can't send another request on that connection. A page usually needs many requests, so each one would need a new handshake and would start again at a congestion window of 10 frames (rule 6). Keeping the connection open avoids both. After the reply, the browser sends its next request on the same connection.

### When the Connection Does Close
The server program never sees a FIN frame itself. Its kernel handles it, and the program only notices `read()` returning 0 bytes (section 75).

1. **After a request**: the browser sends no FIN. The server knows the request is over from the empty line.
2. **Later**: when the tab is closed, or the connection sits unused for a while, the browser's kernel sends FIN. The server program, waiting in `read()` for the next request, gets 0 bytes and closes its side too.

The server can also close first. Many servers close a connection that has been unused for some seconds, and then the browser's `read()` gets the 0 bytes.

If the connection is lost before the reply, the reply has nowhere to go. The server only replies on the connection the request came in on. It can't open a new connection to the browser, because the browser sits behind a home box with NAT and there is no row for a connection started from outside (section 60). So the browser opens a new connection and sends the request again.

---

## 87. Sending Data to the Server

### The Problem
The browser wants to send an order for one Margherita to the server. Where in these bytes does the order go?

### POST
The order is bytes, so it goes in the body of the request, the same place the page went in the reply. Three things change from the GET request.

**1. A different method.** `GET` means "give me this page", and it must not change anything on the server. Browsers repeat GETs freely, for example on reload, so an order sent with GET would be placed twice. Sending data that the server should act on uses the method `POST`.

**2. A path for the part of the server that takes orders**: `/order`.

**3. A body, with `Content-Type` and `Content-Length`.** The server needs `Content-Length` to know where the order ends, because it comes after the empty line. A common format for small data is `name=value` pairs joined by `&`:

```text
item=margherita&count=1        23 bytes
```

The `Content-Type` name for this format is `application/x-www-form-urlencoded`. It is long, but it is only a label.

The request:

```text
POST /order HTTP/1.1\r\n
Host: www.bluepizza.com\r\n
Content-Type: application/x-www-form-urlencoded\r\n
Content-Length: 23\r\n
\r\n
item=margherita&count=1
```

The server reads lines until the empty line, finds `Content-Length: 23`, and reads exactly 23 more bytes. A GET has no body, so it has no `Content-Length`, and the server takes the body length as 0.

The reply:

```text
HTTP/1.1 200 OK\r\n
Content-Type: text/plain\r\n
Content-Length: 18\r\n
\r\n
order 57 received\n
```

Requests and replies have the same shape: a first line, headers, an empty line, then an optional body.

### Query Parameters
Extra values can also go in the path, after a `?`, in the same `name=value&name=value` format:

```text
GET /menu?size=large&veg=yes HTTP/1.1\r\n
Host: www.bluepizza.com\r\n
\r\n
```

The server program splits the path at the `?`. The part before it, `/menu`, picks the page. The part after it, `size=large&veg=yes`, is the **query**, and each pair is a **query parameter**.

* **Query**: with GET, to say which version of a page is wanted, for example search words or a filter. It changes nothing on the server, so it is safe to repeat.
* **Body**: with POST, for data the server acts on, and for anything large. Servers limit the length of the request line, often to about 8 KB, while a body can be megabytes.

A value cannot contain a space, `&` or `=` directly, because those would break the splitting. They are written as `%` followed by the byte in hex. A space is `%20`, so `search=blue pizza` is sent as `search=blue%20pizza`.

`application/x-www-form-urlencoded` describes the body. The query uses the same format and the same `%` rule, but has no `Content-Type` header: `Content-Type` only ever describes the body. The server knows by HTTP's rules that whatever follows `?` in the path is in this format.

---

## 88. Many Files on One Page

### The Problem
The `/menu` page is now a real web page that shows 10 photos. The browser needs 11 files. On one HTTP/1.1 connection, the browser sends a request and has to read the whole reply before the next reply can start. If one photo is large, everything behind it waits.

### Sending the Next Request Early: Pipelining
The browser sends all 11 requests back to back on the one connection. This saves waiting, but the replies still have to come back in the same order as the requests. A reply has no field saying which request it answers, so the browser matches them only by order. If photo 2 is 5 MB, photos 3 to 10 sit behind it on the server, even if they are tiny. This is **pipelining**.

It is real. It is part of the HTTP/1.1 rules, from the original 1999 rules to the current RFC 9112, the document that holds the HTTP/1.1 rules. Browsers implemented it and then removed it: Chrome around 2013 to 2014, and Firefox, which had it behind a setting that was off by default, around 2017 (exact versions not checked). Two reasons: the waiting behind a big reply, and some servers and machines in between handled it wrongly, sending replies mixed up or not at all, and a browser could not tell in advance which ones would. Some programs that are not browsers, such as command-line HTTP tools, can still use it.

### Several Connections
Browsers open up to 6 TCP connections to the same website name at once, and send one request at a time on each:

```text
connection 1:  page      -> photo 6
connection 2:  photo 1   -> photo 7
connection 3:  photo 2 (5 MB) .........................
connection 4:  photo 3   -> photo 8
connection 5:  photo 4   -> photo 9
connection 6:  photo 5   -> photo 10
```

The big photo blocks only its own connection. The limits:

* **Each connection costs a handshake** before its first request. With a 50 ms round trip, that is 50 ms each.
* **Each connection starts at a congestion window of 10 frames** (rule 6) and grows on its own. Six connections each learn the path separately and compete with each other at the router lines.
* **The server keeps 6 records and buffers** per browser instead of 1.
* **It is still capped at 6.** A page with 100 files waits in line anyway.

The root cause in both cases: a reply has no label, so a connection can only carry one reply at a time, start to finish.

### Why HTTP/1.1 Websites Are Still Fast
* **6 connections already handle a normal page well.** With a short round trip, for example 10 ms, a few extra handshakes cost little. A better method helps most when the round trip is long and the page has many files.
* **The browser keeps copies.** A reply can carry a header saying how long the browser may keep the file, for example a day. On the next visit, the browser uses its stored copy and sends no request.
* **Websites send fewer, bigger files.** For example, many small code files are joined into one before being put on the server.
* **Files are spread over several names**, like `img1.bluepizza.com` and `img2.bluepizza.com`. The limit of 6 applies to each name, so two names give 12 connections.
* **Often the browser is not talking HTTP/1.1 at all.** Many websites have a server from another company placed in front of theirs. That server speaks HTTP/2 (section 89) to the browser and HTTP/1.1 to the website's own server. That is a later topic (proxies).

### The Next Problem
Suppose each reply were cut into small pieces, and every piece carried a label saying which request it belongs to. What would that make possible on a single connection?

---

## 89. HTTP/2

### Labeled Pieces
With a label on every piece, one connection can carry all 11 replies at once, mixed together, and the browser sorts the pieces back out by label.

Each request and each reply is cut into pieces. Every piece starts with a 9-byte binary header:

```text
length      3 bytes   how many bytes follow this 9-byte header
type        1 byte    0 = DATA (body bytes), 1 = HEADERS (the headers)
flags       1 byte    one bit means "this is the last piece of this request or reply"
stream ID   4 bytes   the label: which request this piece belongs to
```

HTTP/2 calls these pieces **frames**. That is a different thing from the cable frames in sections 3 to 55. An HTTP/2 frame is a few bytes inside the TCP data.

### The Label
One request and its reply share one number. One request plus its reply is a **stream**.

The browser numbers its streams 1, 3, 5, 7 and so on, odd numbers only. The server can also start a stream of its own, without a request, and it uses even numbers. That way, if both start a stream at the same moment, they cannot pick the same number. Stream 0 is kept for messages about the whole connection, such as a settings message sent at the start.

### On One Connection
```text
browser -> server:
  HEADERS stream 1   GET /menu
  HEADERS stream 3   GET /photo1.jpg
  HEADERS stream 5   GET /photo2.jpg     (5 MB)
  ... all 11 requests, back to back

server -> browser:
  HEADERS stream 1   200, text/html
  DATA    stream 1   page bytes, last piece
  HEADERS stream 5   200, image/jpeg
  DATA    stream 5   16 KB of photo 2
  HEADERS stream 3   200, image/jpeg
  DATA    stream 3   all of photo 1, last piece
  DATA    stream 5   16 KB of photo 2
  DATA    stream 5   ...
```

The server sends pieces from any stream in any order. Small photos finish while the big one is still going.

### Pieces Are Sent Whole
The stream ID appears only once, in the 9-byte header at the start of a piece. The bytes after it carry no label. The reader counts `length` bytes and puts all of them into that stream. So a piece from another stream cannot be put inside it:

```text
correct:
[hdr: stream 5, length 16384][16384 bytes of photo 2][hdr: stream 3, length 900][900 bytes of photo 1]

if stream 3's piece were put inside stream 5's piece:
[hdr: stream 5, length 16384][8000 bytes of photo 2][hdr: stream 3 ...][900 bytes][8384 bytes of photo 2]
                              ^ the reader counts 16384 bytes from here, all as photo 2
```

In the second line, the reader would take stream 3's header and its 900 bytes as part of photo 2, then read the leftover photo 2 bytes as if they were the next header, and everything after that would be garbage. Mixing happens only between whole pieces.

### Why 16,384 Bytes
A DATA piece carries at most 16,384 bytes (2^14) by default, so a 5 MB photo becomes about 320 pieces. The receiver can allow larger pieces, up to about 16 MB, with the settings message on stream 0. The limit is kept small because a piece, once started, must be sent whole before another stream's piece can go in. Small pieces mean a small reply never waits behind more than 16 KB of a big one. They also mean the receiver needs only 16 KB of memory to hold one piece while reading it.

### Pieces and Cable Frames
A 16,384-byte piece plus its 9-byte header is spread over about 12 cable frames, at 1460 data bytes each. TCP does not know pieces exist; it only numbers bytes. The receiving program reads the byte stream like this: read 9 bytes, get the length, read that many bytes, repeat. That is method 1 from section 82.

```text
one HTTP/2 piece:  [9-byte header][16,384 bytes]
on the cables:     frame 1460 B | frame 1460 B | ... | frame ~333 B     (about 12 frames)
```

### What This Fixes From Section 88
* One handshake instead of six.
* One congestion window that grows once and is shared by all requests.
* No cap of 6. A hundred streams can be open at once.
* One record on the server instead of six.

Two more changes:

* **The headers are binary, not text.** A header sent once, like `Host: www.bluepizza.com`, is later referred to by a small number instead of being written out again.
* **Browsers use HTTP/2 only on encrypted connections.** The two sides agree to use it during the encryption setup, which is a later topic.

### How a Server Program Sees It
The "one request" a server's code sees is a stream, not a connection. A library sorts the pieces before the code runs. In Node:

```text
kernel        one TCP connection: one stream of bytes
                 |
Node's http2  reads 9-byte header -> length, type, stream ID
library       reads that many bytes, adds them to that stream's table:
                 stream 1: headers "GET /menu"            complete
                 stream 3: headers "GET /photo1.jpg"      complete
                 stream 5: headers "POST /order", body... still arriving
                 |
              for each stream whose headers have arrived:
                 builds req and res objects, calls the handler
                 |
your code     app.get("/menu", (req, res) => ...)   called once per stream
```

Going back out is the reverse. When the handler calls `res.write(...)` or `res.end(...)`, the library cuts the bytes into DATA pieces labeled with that stream's ID and mixes them onto the same connection with pieces from other handlers.

So a handler is called once per request either way:

* **HTTP/1.1**: once per request, read in order from one of up to 6 connections.
* **HTTP/2**: once per stream, sorted out of one shared connection.

Node's usual `http` module, which Express is built on, speaks only HTTP/1.1. HTTP/2 needs Node's separate `http2` module, which provides the same kind of `req` and `res` objects. How well Express works on top of it is not checked. Often a Node server stays on HTTP/1.1, and a server placed in front of it speaks HTTP/2 to browsers.

### The Next Problem
All 11 streams travel inside one TCP connection. Say one cable frame carrying a piece of photo 2 is lost. TCP gives the program bytes only in order, with no gaps. What happens to the pieces of photo 1 that arrived right after the lost frame?

---

## 90. One Lost Frame Stops Every Stream

### What Happens
Photo 1's pieces wait, even though they have nothing to do with photo 2.

```text
cable frames, in TCP byte order:
  frame 20   bytes of a photo 2 piece (stream 5)     lost
  frame 21   bytes of a photo 1 piece (stream 3)     arrives
  frame 22   last bytes of photo 1 (stream 3)        arrives
```

1. The browser's kernel receives frames 21 and 22. It holds them, because frame 20's bytes come first and are missing (rule 2).
2. The browser's `read()` returns nothing past frame 19. Photo 1 is complete in kernel memory, but the browser cannot get to it.
3. The server's kernel gets no ack for frame 20 and resends it, at least one round trip later and often 200 ms or more.
4. Frame 20 arrives. Now `read()` returns 20, 21 and 22 at once, and photo 1 shows.

The HTTP/2 labels cannot help, because they are inside the bytes, and TCP will not hand over any bytes past the gap. TCP does not know about streams. It only knows one line of numbered bytes.

### What It Costs
On a good cable, losses are rare, so this hardly matters. On weak Wi-Fi or a phone network, where for example 2 of every 100 frames are lost, every loss stops all 100 streams. Then HTTP/1.1 with 6 connections can be faster than HTTP/2, because a loss on one connection stops only that one.

### Name
This is the same problem as in section 88: everyone waits behind the first in line. It is called **head-of-line blocking**. HTTP/2 removed it at the HTTP level, but it is still there at the TCP level, underneath.

### The Next Problem
The fix would be for the transport to keep order per stream instead of per connection, so a gap in stream 5 holds back only stream 5. But TCP's rules live in every kernel in the world, and many routers and home boxes in between also expect frames to be exactly TCP or UDP. How could a browser get a new transport without changing every kernel and every box in between?

---

## 91. QUIC and HTTP/3

### Build the Transport Inside the Program, on Top of UDP
The browser cannot change TCP, but it can use UDP. UDP adds only ports and a checksum, and every kernel and every box in between already passes it, for example for DNS. Home boxes also make NAT rows for UDP, by port, the same as for TCP. So the new rules are written as code inside the browser and inside the server program, and their bytes travel as UDP data:

```text
HTTP/2:  [MAC][IP, protocol 6 ][TCP group               ][HTTP/2 pieces][CRC]
HTTP/3:  [MAC][IP, protocol 17][UDP group][QUIC group   ][QUIC pieces  ][CRC]
                                ports only  numbering, acks: done by the program
```

To every router and box, this is just a UDP datagram.

### What the Program Does Itself
All of TCP's rules: numbering, acks, resending, the room window, the congestion window and the handshake. They are the same ideas as sections 71 to 75, but the code lives in the program, not the kernel.

### The Important Difference: Order Per Stream
Each stream counts its own byte positions. A piece is labeled "stream 5, bytes 32768 to 34167" instead of only a connection-wide number.

```text
datagram 20   stream 5, photo 2 bytes     lost
datagram 21   stream 3, photo 1 bytes     arrives -> given to the browser right away
datagram 22   stream 3, photo 1 end       arrives -> photo 1 shows
... datagram 20's bytes are resent; only stream 5 waited
```

### One More Thing It Fixes
A TCP connection is identified by the four values. When a phone moves from Wi-Fi to the mobile network, its IP changes, so every TCP connection breaks and has to start over. QUIC puts its own connection number in every datagram, so the server recognizes the phone at its new address and carries on.

### Costs
* The program does work the kernel used to do, so it uses more processor time.
* Some networks block UDP except port 53. The browser then falls back to TCP and HTTP/2. A server tells the browser it supports HTTP/3 with a header in an earlier HTTP/2 reply, and the browser tries it on the next connection.

### Names
The new transport is **QUIC**. It started as an abbreviation, but now it is just a name. HTTP's rules on top of QUIC are **HTTP/3**. The request and reply meanings, `GET`, `/menu`, `200`, headers and body, are the same in HTTP/1.1, HTTP/2 and HTTP/3. Only how they are cut up and carried changes.

### Who Uses It
All major browsers (Chrome, Firefox, Safari, Edge) support HTTP/3. Google (Search, YouTube), Meta (Facebook, Instagram) and websites served through Cloudflare use it. Surveys from around 2024 to 2025 put it at roughly a third of popular websites (current figure not checked).

To see it: in Chrome's developer tools, Network tab, right-click the column headers and turn on "Protocol". Requests to google.com or youtube.com usually show `h3`, which means HTTP/3. Others show `h2` or `http/1.1`.

### Why the Effort
Google and Meta serve billions of people, many on phones with weak signals where frames are often lost, which is the case from section 90. A small saving per page, multiplied by billions of page loads a day, is large. Google published measurements in 2017 from its switch: search results loaded about 8% faster on desktop and 3.6% faster on phones, and YouTube videos paused to load about 15 to 18% less often.

For a small website on a good connection, the difference between HTTP/1.1, 2 and 3 is small, which is why HTTP/1.1 still works fine for many sites.

### The Next Problem
Every byte so far, including the order `item=margherita&count=1` and every header, travels as readable bytes through the air and through many routers owned by different companies. Anyone on the same Wi-Fi channel can receive the frames (section 42), and any router on the path can read them. How can the browser and the server make the bytes unreadable to everyone except each other?

---

## 92. A Proxy in Front of the Website

Encryption, the question at the end of section 91, is skipped for now. It is a long topic of its own.

### The Problem
bluepizza's website runs on one computer at `198.51.100.7`. At lunch time, 50,000 browsers connect at once, and one computer cannot handle them all. The shop adds three more computers with the same website. But DNS gives browsers one address, and every browser connects to that one address. How can the requests be spread across all four computers?

### A Program in Front
Put one more computer, P, at `198.51.100.7`, and give the four website computers private addresses behind it (section 58). P is the only one browsers ever connect to. It takes each request and passes it to one of the four.

```text
                                        shop's local network 10.0.0.x
browser ---- ... ---- [P] 198.51.100.7 | 10.0.0.1 ---- switch ---- web1 10.0.0.11
                      two sockets, like the home box   |---- web2 10.0.0.12
                                                       |---- web3 10.0.0.13
                                                       |---- web4 10.0.0.14
```

P has two sockets, one toward the internet provider and one in the shop's local network, the same as any router (section 57). The difference is that P runs a program that reads HTTP.

### One Request, Step by Step
1. The browser looks up `www.bluepizza.com`, gets `198.51.100.7`, and does a TCP handshake with P on port 80. It sends:

   ```text
   GET /menu HTTP/1.1\r\n
   Host: www.bluepizza.com\r\n
   \r\n
   ```

2. P's program reads until the empty line, so it has the whole request (section 86).
3. P picks one of the four, say web2. It opens its **own** TCP connection, from `10.0.0.1 : 51000` to `10.0.0.12 : 80`, and sends the same request with one extra header:

   ```text
   GET /menu HTTP/1.1\r\n
   Host: www.bluepizza.com\r\n
   X-Forwarded-For: 203.0.113.10\r\n
   \r\n
   ```

   web2 only sees P's address on its connection. This header tells it which address the browser really came from, for example to keep a log.
4. web2 replies to P. P's program reads the reply and writes the same bytes to the browser on the first connection.

### Two Separate Connections
Each has its own handshake, sequence numbers and windows:

```text
browser (203.0.113.10 : 40001)  <-- connection 1 -->  P (198.51.100.7 : 80)
P (10.0.0.1 : 51000)            <-- connection 2 -->  web2 (10.0.0.12 : 80)
```

### How This Differs From a Router or NAT
```text
                         router / NAT box                 P
reads                    MAC, IP (+ ports for NAT)        the whole HTTP request
TCP connection           passes the browser's frames      ends the browser's connection,
                         through, one by one              opens a new one of its own
can choose by path       no                               yes, e.g. /order -> web4
```

Because P reads the HTTP request and opens its own connection, the two sides do not even need the same HTTP version. P can speak HTTP/2 to the browser and HTTP/1.1 to web2. That is the "server placed in front" from sections 88 and 89.

### Names
A program that receives requests and sends them on for someone else is a **proxy**. One that sits in front of the servers, on the website owner's side, is a **reverse proxy**. The browser does not know it exists. It thinks P is the website. A common program for this is nginx.

How P picks among the four is the load balancer topic, which comes next.

### The Next Problem
Now the other side. A school wants all 500 students' browsers to go through one computer of its own, so it can block some websites and keep copies of popular pages. That computer sits next to the browsers, not next to the website. What changes?

---

## 93. A Proxy Next to the Browsers

### The Setup
The school's computer F sits in the school's local network. Every browser is set to send its requests to F instead of to the websites.

```text
school local network 10.1.0.x
student 10.1.0.23 ---- switch ---- [F] 10.1.0.5, port 3128 ---- school router ---- ... ---- 198.51.100.7
student 10.1.0.24 ----/
```

### How a Browser Knows to Use F
It is a setting. In Ubuntu: Settings -> Network -> Network Proxy, with address `10.1.0.5` and port `3128`. The school can also push this setting to its computers automatically. To stop students from just removing the setting, the school's router drops any frame from a student computer to port 80 unless it is going to F.

### One Request, Step by Step
1. The student types `www.bluepizza.com/menu`. Because the proxy setting is on, the browser does **not** look up the name itself. It connects to F at `10.1.0.5 : 3128` and sends:

   ```text
   GET http://www.bluepizza.com/menu HTTP/1.1\r\n
   Host: www.bluepizza.com\r\n
   \r\n
   ```

   The request line holds the full address, not just `/menu`, because F needs to know which website to go to.

2. F checks its block list. If the name is on it, F replies right away and never contacts the website:

   ```text
   HTTP/1.1 403 Forbidden\r\n
   ...
   ```

3. F checks its stored copies. If it has a copy of this page that the website's reply allowed to be kept and the time limit has not passed (the same kind of time limit the browser uses for its own copies, section 88), F replies from the copy. The website is never contacted.
4. Otherwise, F looks up `www.bluepizza.com` with DNS, opens its **own** TCP connection to `198.51.100.7 : 80`, sends the request with the normal `/menu` path, reads the reply, stores a copy, and sends the reply to the student.

The website only ever sees connections from the school's public address, never from the students.

### Forward vs Reverse
```text
                  forward proxy (F)               reverse proxy (P)
sits next to      the browsers                    the website's servers
set up by         the browsers' owner (school)    the website's owner (shop)
who knows         browsers must be set to use it  browsers do not know it exists
used for          blocking, copies, logging       spreading requests, one public address
```

The mechanics are the same in both: read the HTTP request, open a separate TCP connection, pass the request on, and pass the reply back. The only difference is which side it serves. A proxy on the browsers' side is a **forward proxy**, or just "a proxy" in everyday speech.

With encryption, F can see much less: the website's name, but not the path or the body. That comes with TLS.

### The Next Problem
Back to the shop. P has four computers behind it. How should it pick one for each request, and what should it do if web3 is switched off?

---

## 94. Picking a Server, and Skipping a Broken One

### The Setup
```text
browser ---- ... ---- [P] 198.51.100.7 | 10.0.0.1 ---- switch ---- web1 10.0.0.11
                                                              ---- web2 10.0.0.12
                                                              ---- web3 10.0.0.13
                                                              ---- web4 10.0.0.14
```

P holds a list of the four addresses. For every request it has to pick one.

### Way 1: Take Turns
P keeps a counter. Request 1 goes to web1, request 2 to web2, request 3 to web3, request 4 to web4, request 5 to web1 again, and so on. This is **round robin**.

The weakness: requests do not cost the same. A menu request takes web2 about 5 ms, a photo upload about 2 s. With plain turns, web2 can get three uploads in a row while web1 sits idle.

### Way 2: Pick the Least Busy
P opened every connection to the four servers itself (section 92), so it knows how many are open to each one right now:

```text
web1  2 open
web2  9 open
web3  4 open
web4  3 open
```

The next request goes to web1, the one with the fewest. This is **least connections**.

### What Actually Happens When web3 Is Off
P sends its SYN to `10.0.0.13 : 80`. What P sees depends on what is broken:

```text
what is broken                  what P's kernel sees                            what P's connect() gets
computer switched off           no ARP reply, so no MAC to send to              fails after about 3 s ("no route to host")
computer on, program stopped    web3's kernel sends RST (no listener, sec. 74)  fails right away ("connection refused")
program running but stuck       handshake works, but no reply ever comes        P waits until its own time limit, e.g. 60 s
```

If P does nothing about this, every fourth request fails or waits.

### Checking Each Server Itself
Every 5 seconds, P sends each server a small request of its own:

```text
GET /health HTTP/1.1\r\n
Host: web3\r\n
\r\n
```

The web program is written to answer `HTTP/1.1 200 OK` on `/health` when it is working. Each check waits up to 2 seconds for its answer. If 3 checks in a row get no 200, P marks the server as down and leaves it out of the turns:

```text
time    check                       result
0 s     GET /health to web3         no answer by 2 s  -> fail 1
5 s     GET /health to web3         no answer by 7 s  -> fail 2
10 s    GET /health to web3         no answer by 12 s -> fail 3 -> web3 marked down
```

So P notices about 12 seconds after web3 went off. If any one of those checks gets a 200, the count goes back to 0. P keeps checking a down server, and after 2 good answers in a row puts it back.

Why "in a row": a single check can fail while the server is fine. For example, web3 is busy with three photo uploads for 2.5 seconds, so its answer to `/health` arrives after the 2-second limit. The next check, 5 seconds later, gets a normal 200. Needing 3 failures in a row means only a problem that lasts across all three checks removes a server.

These requests are **health checks**. The 5 s, 2 s, 3 and 2 are example settings the shop chooses.

### The Request That Was Already Going to web3
A request was sent to web3 just before it stopped, and the connection failed. If it was a GET, P can send the same request to web4, because a GET must not change anything (section 87). If it was a POST to `/order`, P cannot know whether web3 already saved the order. Sending it again could place the order twice, so P returns an error to the browser instead.

### Name
Spreading requests over several servers and skipping broken ones is **load balancing**. "Load" is the amount of work each server has. A program or machine that does it is a **load balancer**. P is a reverse proxy that also does load balancing.

### The Next Problem
P reads every HTTP request up to the empty line before it can pick a server, and it holds two TCP connections for every browser. Could a load balancer pick a server using only the IP and TCP groups, without the HTTP part? What would it gain, and what could it no longer do?

---

## 95. A Load Balancer That Reads Less

### Holding vs Looking
Every machine that passes frames on holds the whole frame in its memory. The difference between machines is which bytes they look at to decide, and whether they have to wait for more frames first.

One frame carrying the start of a request, counting from the first byte of the MAC group, with a 20-byte TCP group:

```text
byte position in frame    what is there
0 - 13                    MAC group
26 - 29                   from IP
30 - 33                   to IP
34 - 35                   from port
36 - 37                   to port
54 - ...                  data: "GET /menu HTTP/1.1\r\n..."
```

* **A router (section 16)** stores the whole frame and looks only at bytes 30–33, the to-IP. It sends the whole frame out, data included. The data bytes sit in memory and go out again, but nothing looks at them.
* **P (section 92)** has its kernel take the data bytes out and give them to nginx. nginx collects data until it finds `0D 0A 0D 0A`, and only then picks a server.

### The Idea
Call the new machine Q. It replaces P at `198.51.100.7` and is the router for web1–web4, so their replies to the outside go through Q, the same way a laptop's frames go through the home box (section 23). Q looks only at the IP group and the TCP group: the four values from section 20.

### One Connection, Step by Step
1. The browser `203.0.113.10 : 40001` sends a SYN to `198.51.100.7 : 80`.
2. Q sees a SYN, so this is a new connection. It picks a server (section 94), say web2, and writes a row in its table:

   ```text
   browser IP      browser port    server picked
   203.0.113.10    40001           10.0.0.12  (web2)
   ```

3. Q changes the to-IP in the frame from `198.51.100.7` to `10.0.0.12` and sends it on. The TCP checksum also covers the two IP addresses, so Q recomputes it along with the IP header checksum. Nothing else changes: same ports, same seq, same data.
4. web2's kernel answers with a SYN+ACK from `10.0.0.12 : 80`. Q changes the from-IP back to `198.51.100.7`. If it did not, the browser's kernel would get a frame from `10.0.0.12`, which matches none of its connections, and would answer with RST (section 75).
5. Every later frame from `203.0.113.10 : 40001` matches the row and goes to web2. It has to: web2's kernel holds this connection's seq numbers, and web4 would answer RST.

There is only **one** TCP connection, between the browser and web2. Q does not do the handshake itself. It changes addresses and passes frames along. As the router for web1–web4, it also does a router's usual work: new MACs, TTL lowered by 1.

Q's table has one row per connection. A row is made when a SYN arrives from outside, and removed when the connection ends with FIN or RST, or after no frames have passed for a long time:

```text
browser IP      browser port    server picked
203.0.113.10    40001           10.0.0.12  (web2)
203.0.113.10    40002           10.0.0.14  (web4)
198.18.5.9      61200           10.0.0.11  (web1)
```

### Q Does Not Wait; P Does
Q decides what to do with a frame using only the bytes inside that same frame, so it sends the frame out before the next one arrives. Say a request is split over 3 frames, arriving 1 ms apart:

```text
time    arrives     Q                                    P
0 ms    frame 1     sends frame 1 to web2                keeps the data, sends nothing
1 ms    frame 2     sends frame 2 to web2                keeps the data, sends nothing
2 ms    frame 3     sends frame 3 to web2                finds 0D 0A 0D 0A, picks web2, starts sending
```

Q can send frame 1 at 0 ms because what it needs, the two IPs and two ports, is in frame 1's own bytes. P cannot, because the end of the request is only in frame 3.

### P Builds New Frames, Q Does Not
The browser's frames never leave P. In order:

1. A frame from the browser arrives at P. P's kernel takes its data bytes (`GET /menu ...`) and copies them into a memory area the kernel keeps for this one connection.
2. P's kernel sends an ack to the browser.
3. The memory that held the frame is freed. Only the data bytes remain, in the connection's memory area.
4. nginx calls `read()`. The kernel copies the data bytes from the connection's memory area into nginx's own memory.
5. nginx calls `write()` on its second connection. P's kernel puts those bytes into new frames with new MAC, IP and TCP groups and sends them to web2.

```text
                   frame from browser into P        new frame from P to web2
from IP            203.0.113.10                     10.0.0.1
to IP              198.51.100.7                     10.0.0.12
from port          40001                            51000
to port            80                               80
seq                browser's numbers                P's own numbers, from its own handshake with web2
data               GET /menu ... Host ...           same request, plus the X-Forwarded-For line
```

The HTTP request line and headers are part of the data bytes, so they go on to web2. What P drops is the browser frame's MAC, IP and TCP groups. The number of frames can differ too: three frames in can go out as two, because P's kernel packs the bytes nginx wrote into frames of up to 1460 data bytes (the MSS).

Q never builds a frame. It changes a few bytes in the frame it received and sends that same frame out.

### What Q Gains
* Little work per frame: one table lookup and one address rewrite. It does not read up to an empty line, open a second connection, or copy bytes into a program.
* It works for any program on TCP, not only HTTP, for example a database on port 5432.
* web2 sees the browser's real address as the from-IP, so no `X-Forwarded-For` is needed.

### What Q Can No Longer Do
* It cannot send `/order` to web4, because it never sees the path.
* It picks once per connection, not once per request. If one browser sends 100 requests on one open connection (section 86), all 100 go to web2.
* If web2 stops in the middle, Q cannot resend a GET to another server. It does not know where one request starts and ends.
* It cannot speak HTTP/2 to the browser and HTTP/1.1 to web2, because it is not speaking HTTP at all.

### How Q Differs From a Router
```text
                       router (R, section 16)                  Q
looks at               to-IP only (layer 3)                    both IPs and both ports (layer 4)
the to-IP already      names the final computer;               is Q's own address, 198.51.100.7;
                       R only finds the cable toward it        Q decides which computer gets it
changes IP or ports    never                                   to-IP on the way in, from-IP on the way out
table rows             one per address range                   one per TCP connection
rows made by           a person, or the automatic messages     Q itself, when a SYN arrives
                       (section 17)
```

A frame reaching R already says which computer it is for, so R only moves it closer. A frame reaching Q says `198.51.100.7`, which only means "the shop". Q picks web1, web2, web3 or web4 and writes that address into the frame.

### How Q Differs From NAT in the Home Box
NAT (section 59) also looks at the IP and TCP groups, because it uses ports. The difference is which way connections start, and whether there is a choice:

```text
                       home box (NAT)                         Q
connection starts      from inside (your laptop)              from outside (a browser)
row created when       laptop's first frame goes out          browser's SYN comes in
bytes it changes       from-IP and from-port of outgoing      to-IP of incoming
does it choose?        no: the laptop decided where to go     yes: picks one of web1-web4
no matching row        incoming frame dropped (section 60)    SYN gets a new row and a server
```

So Q is close to NAT running the other way round. The new part is that Q picks which inside computer gets each new connection.

NAT is a step in the router part of the home box, at its WAN side (section 57). It is not a separate chip or socket. Most home boxes are a small computer running Linux, and the NAT table lives in that kernel's memory, next to the router's rows:

```text
laptops ~~~ [access point] -- switch -- (LAN side) router [NAT] (WAN side) ---- company's router
```

```text
going out (laptop -> website)
1. router part reads to-IP 198.51.100.7, decides: out of the WAN socket
2. NAT changes from 192.168.1.23 : 50001 to 203.0.113.10 : 40001, writes the row
3. frame leaves the WAN socket

coming in (website -> laptop)
1. frame arrives at the WAN socket, to 203.0.113.10 : 40001
2. NAT finds row 40001, changes to-IP and to-port to 192.168.1.23 : 50001
3. router part reads the new to-IP 192.168.1.23, decides: LAN side, to the switch
```

Coming in, NAT has to run before the router part. Before the change, the to-IP is the box's own address, and the router part would not know which laptop the frame is for.

### Names
From the layer numbers in section 80:

```text
                     looks at up to         picks a server       TCP connections
L4 load balancer     TCP group (layer 4)    once per connection  one, browser <-> server
L7 load balancer     HTTP part (layer 7)    once per request     two, browser <-> P, P <-> server
```

P is an **L7 load balancer**, and Q is an **L4 load balancer**. NAT also looks at up to layer 4, but people just call it NAT, not "L4 NAT".

nginx is usually set up as L7. The Linux kernel has an L4 balancer called IPVS. On AWS, the "Network Load Balancer" is L4 and the "Application Load Balancer" is L7. Large sites often use both: L4 machines in front, each sending connections to several L7 machines.

---

## 96. What P Does With the Bytes

### What web2 Knows About the Browser
web2's connection is with P, not the browser. When web2's program asks its kernel who the connection is from, the answer is `10.0.0.1`, P, for every request from every customer. The shop's program may need the real address, for example to write it in a log, or to refuse an address that sends 1000 requests a second.

P knows the real address because the browser's connection is with P. So before sending the request on, P adds one header:

```text
GET /menu HTTP/1.1\r\n
Host: www.bluepizza.com\r\n
X-Forwarded-For: 203.0.113.10\r\n     <- added by P
\r\n
```

A browser can write its own `X-Forwarded-For` line with any address it likes. If one is already there, nginx does not replace it. It adds the real address at the end: `X-Forwarded-For: 1.2.3.4, 203.0.113.10`. So web2's program should trust only the last address, the one P wrote.

The "X-" at the start was the old way to mark a header that is not in the official HTTP rules. Q does not need this header, because it changes only the to-IP, and web2 sees the browser's real address as the from-IP.

### How the Reply Gets Back
The browser's connection to P stays open the whole time. nginx holds two connections at once. When web2's reply arrives on the second, nginx writes it into the first:

```text
browser ==conn 1==> P ==conn 2==> web2      request goes right
browser <==conn 1== P <==conn 2== web2      reply comes back the same way
```

The browser only ever talks to P, so the reply reaches it on the connection it sent the request on.

### nginx's Settings File
nginx reads its settings from a text file, `/etc/nginx/nginx.conf`. Each setting is one line with a name and a value, ending in `;`. If a line is missing, nginx uses a default value.

### A Large Request Body
nginx needs only the headers, up to `0D 0A 0D 0A`, to pick web2. For the body it has two ways:

```text
way 1 (default)   keep the whole body first, then send it to web2
way 2             send each part of the body to web2 as soon as it arrives
```

In way 1, nginx does not keep a large body in memory. It keeps the first 16 KB in memory (on a 64-bit machine) and writes the rest to a file on P's disk. Once the last byte has arrived, it reads the file back and sends it to web2.

The setting line:

```text
proxy_request_buffering on;     <- way 1 (used if the line is missing)
proxy_request_buffering off;    <- way 2
```

There is also a size limit line, `client_max_body_size`. If it is missing, nginx refuses any body over 1 MB and replies `413 Request Entity Too Large`. A shop that accepts 5 GB uploads has to raise that limit first.

### Why Way 1 Is the Default
The shop's web program on web2 often can work on only a few requests at a time, and a slow upload would keep one of them busy for a long time.

Say web2 runs 4 copies of the shop's program (4 processes). Each copy handles one request from start to end: it reads the body, does the work, and sends the reply. While it reads a body, it does nothing else. A phone uploads a 50 MB photo at 1 MB per second, so the upload takes 50 s:

```text
way 2 (send as it arrives)            way 1 (nginx keeps it first)
bytes reach web2 at 1 MB/s            nginx receives all 50 MB over 50 s
one copy busy for 50 s                then sends 50 MB over the shop's 1 Gbit/s cable
                                      (about 125 MB/s), so about 0.4 s
4 slow phones -> all 4 copies busy,   one copy busy for 0.4 s
menu requests wait
```

nginx can afford the 50 s wait and web2 cannot, because nginx is written differently. One nginx process works on thousands of connections: it asks the kernel which connections have new bytes, handles those bytes, and goes back to asking. It never sits waiting on one connection, so a slow phone costs it only some disk space.

A second reason, from section 94: if web2 fails partway, nginx still has the full body and can send the same request to another server.

If the web program itself works the way nginx does (Node.js does), the first reason matters less. For very large uploads like 5 GB, writing everything to disk first costs time and disk space, so shops usually use way 2 for that path, or let browsers upload straight to separate storage.

### The Reply Going Back
A **buffer** is a piece of memory where bytes wait before they are sent on.

Say web2 has a 1 MB reply for a phone. web2 can send it to nginx at about 125 MB/s over the shop's cable. The phone can take only 100 KB/s, so it needs 10 s.

```text
setting                 what nginx does                                   web2's program is busy for
proxy_buffering on;     takes bytes from web2 as fast as web2 sends,      about 8 ms
(default)               keeps what the phone has not taken yet in
                        buffers (and a disk file if they do not fit),
                        sends to the phone as soon as it has bytes

proxy_buffering off;    takes bytes from web2 only as fast as the        about 10 s
                        phone takes them, keeps nothing extra
```

The two settings use the same word but do not behave the same way:

```text
proxy_request_buffering on    (phone -> web2)   sends nothing to web2 until the whole body has arrived
proxy_buffering on            (web2 -> phone)   starts sending to the phone as soon as bytes arrive,
                                                and takes bytes from web2 faster than the phone can
```

For the reply, "buffering" does not mean "wait for everything". It means nginx does not make web2 wait for the slow phone. The difference comes from what waiting gains:

* **Request**: having the whole body before contacting web2 means web2 gets it in one fast burst, and nginx can resend it to another server.
* **Reply**: waiting for the whole reply before sending gains nothing. web2 is already free either way, and the phone would only start receiving later.

One side effect matters later (section 101): with `proxy_buffering on`, a small part of a reply, say 30 bytes, can sit in nginx's buffer instead of going to the browser right away.

---

## 97. One Request, One Reply

### It Is HTTP's Rule
TCP only carries bytes in both directions (section 85). HTTP adds the rule: the server must send exactly one response for each request. TCP does not enforce it. If the program on web2 never writes a reply, nothing at the TCP level complains. The program just broke HTTP's rules.

DNS (section 83) and HTTP are both layer 7 protocols. Each one's rules cover only the bytes in the data part: DNS in UDP datagrams, HTTP in a TCP byte stream (or QUIC in HTTP/3).

### Matching a Reply to Its Request
* **HTTP/1.1**: replies on a connection come back in the same order as the requests. The first reply is for the first request, and so on. There is no ID (section 88).
* **HTTP/2**: the reply carries the same stream ID as its request (section 89).

### Time Limits
HTTP's rules give no number. Each program sets its own limit. nginx waits up to 60 s for web2 by default:

```text
web2 refuses the connection (RST)       nginx replies 502 Bad Gateway to the browser
web2 sends nothing for 60 s             nginx replies 504 Gateway Timeout to the browser
```

If a connection closes before any reply arrives, the browser shows an error page. Chrome shows `ERR_EMPTY_RESPONSE`. How long a browser itself waits for a reply before giving up: not checked.

---

## 98. Keeping the Connection Open

### What It Means
When a page first loads, the browser opens a TCP connection with the handshake (SYN, SYN+ACK, ACK). After the first reply, the browser does not send FIN (section 86). Both kernels keep their records for the connection: the four values, the seq numbers and the window. The next request is written into that same open connection, with no new handshake:

```text
0 s     SYN, SYN+ACK, ACK         connection opened once
0 s     GET /order/57/status  ->  reply
5 s     GET /order/57/status  ->  reply      same connection, no handshake
10 s    GET /order/57/status  ->  reply      same connection, no handshake
```

Once the connection is closed, by either side, the next request needs a new connection, and that starts with a new handshake.

### The Connection Header
It is part of HTTP through one header, `Connection`:

```text
Connection: close        "after this reply, this connection will be closed"
Connection: keep-alive   "keep the connection open after this reply"
```

```text
HTTP/1.0 (older)   the connection closes after each reply, unless the request says
                   Connection: keep-alive
HTTP/1.1           the connection stays open after each reply, unless either side says
                   Connection: close
```

So in HTTP/1.1 the header usually appears only when someone wants to close. Keeping it open also needs the reply to mark where it ends, with `Content-Length` or chunks (section 101). Otherwise the only way to mark the end is to close the connection (method 3, section 82).

### Who Calls close()
The kernel never reads HTTP. The program reads the header, and calls `close()` after the reply has been completely written. Then the kernel sends FIN.

**The browser sends it in the request:**

```text
GET /menu HTTP/1.1\r\n
Host: www.bluepizza.com\r\n
Connection: close\r\n
\r\n
```

1. The server program reads the request, including this line.
2. It writes the full reply.
3. It calls `close()`. Its kernel sends FIN after the last reply byte.
4. The browser reads the reply, then `read()` returns 0, and the browser calls `close()` too.

**The server puts it in the reply:**

```text
HTTP/1.1 200 OK\r\n
Content-Length: 26\r\n
Connection: close\r\n
\r\n
Margherita 8\nPepperoni 10\n
```

1. The server program writes this reply, then calls `close()`. Its kernel sends FIN.
2. The browser reads the 26 body bytes.
3. Having seen `Connection: close`, the browser sends no more requests on this connection and calls `close()`. Its next request goes on a new connection.

### How Long It Stays Open
HTTP's rules give no number. Each program sets its own limit for how long a connection may sit with no requests:

```text
nginx      75 s   (default)
Node.js    5 s    (default; it also sends "Keep-Alive: timeout=5" in replies to tell the browser)
Firefox    115 s
Chrome     not checked
```

Whichever side's limit comes first closes the connection with FIN.

### Too Many Open Connections
Each open connection takes memory in the server's kernel and in nginx, even when no requests come. That is the main reason server limits are short. With nginx's 75 s, 10,000 browsers that load one page and go quiet hold 10,000 connections for 75 s, and then all are closed. nginx also has a maximum number of connections it holds at once. Past that, new connections wait or are refused.

### With a Proxy
The header applies only to the one connection it travels on. P holds two connections, so nginx does not pass the browser's `Connection` line on to web2. It decides separately whether its own connection to web2 stays open.

### The Next Problem
A customer orders a pizza. Ten minutes later the kitchen marks order 57 as ready on web2. The shop wants the page to show "order 57 is ready" at that moment. But in HTTP, the server sends a response only after the browser sends a request. How can the server tell the browser about something that happened later?

---

## 99. Asking Again and Again

### The Setup
The order page has a small JavaScript program that the browser runs. After the order is placed, it knows the order number, 57.

### The Simplest Way
Every 5 seconds, the JavaScript sends a request:

```text
GET /order/57/status HTTP/1.1\r\n
Host: www.bluepizza.com\r\n
\r\n
```

web2 checks its records and replies:

```text
HTTP/1.1 200 OK\r\n
Content-Type: text/plain\r\n
Content-Length: 8\r\n
\r\n
cooking\n
```

When the kitchen marks it ready, the next request gets `ready\n`, and the page shows "order 57 is ready". The requests go on the same open connection (section 98), so there is no new handshake each time.

### What It Costs
The pizza takes 10 minutes:

```text
requests sent          600 s / 5 s = 120
replies with news      1
replies "cooking"      119
```

With 1000 customers waiting at once, the shop gets 1000 / 5 = 200 requests per second, almost all answered "cooking".

There is also a delay. If the kitchen marks it ready just after a request was answered, the page finds out up to 5 seconds later. Asking every 1 second cuts the delay to 1 second but makes 5 times as many requests. Asking every 30 seconds makes fewer requests but can be 30 seconds late.

### Name
Sending the same request on a timer to check for news is **polling**.

### The Next Problem
Almost every reply says "cooking". What if web2 did not answer at once when there is no news? It could keep the request and reply only when the order becomes ready. What would that change, and what could go wrong while the request waits?

---

## 100. Holding the Request Until There Is News

### The Change
The browser sends one request:

```text
GET /order/57/wait HTTP/1.1\r\n
Host: www.bluepizza.com\r\n
\r\n
```

web2's program first checks order 57. If it is already ready, it replies right away. If not, it does not reply. It keeps the request in a list in its memory:

```text
waiting for order 57:   connection from P, port 51000
```

Ten minutes later the kitchen marks order 57 ready. The program finds that entry and writes the reply on that connection:

```text
HTTP/1.1 200 OK\r\n
Content-Length: 6\r\n
\r\n
ready\n
```

The page shows "order 57 is ready" within milliseconds, not up to 5 seconds later. One request, one reply, both within HTTP's rules. The reply just comes late.

### What Goes Wrong While It Waits
**1. Time limits along the way.** nginx waits up to 60 s for web2's reply (section 97). After 60 s with nothing, it sends `504 Gateway Timeout` to the browser. So the shop's program replies by itself before that, say after 30 s:

```text
HTTP/1.1 200 OK\r\n
Content-Length: 8\r\n
\r\n
waiting\n
```

and the JavaScript sends a new `/wait` request right away. Over 10 minutes that is about 20 requests instead of 120.

**2. Open connections.** Every waiting customer holds one connection to P and one from P to web2, the whole time. With 1000 customers, that is 1000 + 1000 open connections, all idle. A web program that runs 4 copies, each handling one request at a time, could hold only 4 waiting requests. Long polling needs a program that works like nginx or Node.js, handling many connections at once.

**3. News arriving between requests.** The order might become ready in the few milliseconds after a `waiting` reply and before the next `/wait` arrives. That is fine, because the program checks order 57's state first when the next request comes in, and replies right away.

### In Node.js
Here the kitchen's screen marks an order ready by sending `POST /order/57/ready` to the same program.

```js
const http = require("http");

const status = new Map([["57", "cooking"]]); // order number -> "cooking" or "ready"
const waiting = new Map();                   // order number -> list of { res, timer }

function reply(res, text) {
  res.writeHead(200, {
    "Content-Type": "text/plain",
    "Content-Length": Buffer.byteLength(text),
  });
  res.end(text);
}

function remove(id, entry) {
  const list = waiting.get(id) || [];
  waiting.set(id, list.filter((e) => e !== entry));
}

const server = http.createServer((req, res) => {
  const wait = req.url.match(/^\/order\/(\d+)\/wait$/);
  if (req.method === "GET" && wait) {
    const id = wait[1];
    if (status.get(id) === "ready") return reply(res, "ready\n");

    // no news: keep res, do not reply now
    const entry = { res };
    entry.timer = setTimeout(() => {
      remove(id, entry);
      reply(res, "waiting\n");               // reply by itself after 30 s
    }, 30000);
    waiting.set(id, [...(waiting.get(id) || []), entry]);

    // browser went away: drop the entry and its timer
    res.on("close", () => {
      clearTimeout(entry.timer);
      remove(id, entry);
    });
    return;                                   // handler ends, nothing sent yet
  }

  const ready = req.url.match(/^\/order\/(\d+)\/ready$/);
  if (req.method === "POST" && ready) {
    const id = ready[1];
    status.set(id, "ready");
    for (const entry of waiting.get(id) || []) {
      clearTimeout(entry.timer);
      reply(entry.res, "ready\n");            // the late replies go out now
    }
    waiting.delete(id);
    return reply(res, "ok\n");
  }

  res.writeHead(404);
  res.end();
});

server.listen(80);
```

The function passed to `http.createServer` is the **handler**. It runs once for every request. `res` is the object the handler writes the reply on.

### No Busy Waiting
When the handler reaches `return;` without calling `res.end()`, the connection stays open with no reply sent. Node does not loop and check. It makes one call to the kernel (on Linux, `epoll_wait`) that means "put this process to sleep until any of my connections has new bytes, or until my next timer is due". While asleep, the process uses no CPU. When the kitchen's POST arrives, the kernel wakes Node, Node runs the handler for it, and that handler finds the stored `res` objects and writes the replies.

One limit: `waiting` and `status` live in this one process's memory. This works only when the browser's `/wait` and the kitchen's POST reach the same process. With web1–web4 behind P, they might not. That needs the servers to share the news with each other, which is not covered here.

### Name
Holding a request open until there is news, or until a time limit, is **long polling**. The polling from section 99 is sometimes called short polling, to tell them apart.

### The Next Problem
Each request still gets exactly one reply. Suppose the shop wants several updates in a row: "cooking", "in oven", "out for delivery", then the driver's position every 2 seconds. Each update ends the reply, and the browser has to send a new request. Could web2 keep sending more bytes in one reply, and never end it?

---

## 101. One Reply That Never Ends

### The Idea
web2 sends the reply's status line and headers right away, and does not end the body. Each time there is news, it writes a few more body bytes on the same open connection. The browser reads each part as it arrives.

This leaves one problem. Until now, the browser found the end of the body with `Content-Length`. Here nobody knows the length in advance, because the body has no end.

### Marking the Body Without a Total Length
HTTP/1.1 has another way: the header `Transfer-Encoding: chunked`. The body is then sent in parts called **chunks**. Each chunk is its length, written as hex text, then `\r\n`, then the bytes, then `\r\n`. A chunk of length 0 means the body is finished. This is the length-prefix method from section 82, done by HTTP.

The length line before a chunk and the `\r\n` after it are the **chunk markers**. They are not part of the body.

The browser needs to know where the body ends for two reasons:

* To tell the page's JavaScript "this is the whole body". For example, `await res.text()` after `fetch()` returns only once the browser has found the end of the body.
* To know which bytes come next on the same open connection. Everything after the body's end belongs to the next reply.

### The Format of the Body: text/event-stream
`text/event-stream` is a `Content-Type` value, like `text/plain` and `text/html`. It says the body is written in one particular text format:

* The body is a series of **messages**. A message is one piece of news the server wants the page to get, like `cooking`.
* A line starting with `data: ` holds the message's text.
* An empty line ends a message.
* A line starting with `:` means nothing, and the browser skips it.

"Event" is the word these rules use for one message. "Event stream" means a series of messages arriving over time. The whole body is text and must be UTF-8. Raw binary data, like a photo's bytes, would first have to be turned into text characters, which makes it about a third larger. In practice it is used for short text messages.

### Several Messages, and Text With Line Breaks
One message is everything up to the next empty line, so several messages can go in one write and arrive in the same frame. The browser still calls `onmessage` once for each:

```text
data: a\n\ndata: b\n\ndata: c\n\ndata: d\n\n      -> onmessage("a"), ("b"), ("c"), ("d")
```

A line break ends a `data:` line, so text with line breaks is sent as one `data:` line per line of text. The browser joins them back with `\n`:

```text
text "a\n\nb"   is sent as   data: a\ndata: \ndata: b\n\n   -> onmessage("a\n\nb")
```

Often the server sends JSON from `JSON.stringify`, which writes a line break as the two characters `\` and `n`, so the text has no real line breaks at all.

### The Bytes, in Order
The page opens the stream at 0 s, and the browser sends:

```text
GET /order/57/events HTTP/1.1\r\n
Host: www.bluepizza.com\r\n
Accept: text/event-stream\r\n
\r\n
```

`Accept` is a request header where the browser lists which body formats (`Content-Type` values) it wants in the reply.

web2 replies at once with the headers and the current state, and does not end the body:

```text
HTTP/1.1 200 OK\r\n
Content-Type: text/event-stream\r\n
Transfer-Encoding: chunked\r\n
\r\n
F\r\ndata: cooking\n\n\r\n             <- 0 s: 0xF = 15 bytes, message "cooking"
```

`data: ` is 6 bytes, `cooking` is 7, and two `\n` are 2: 6 + 7 + 2 = 15 = hex F. Later bytes on the same reply:

```text
8\r\n: ping\n\n\r\n                    <- 30 s, skipped by the browser
8\r\n: ping\n\n\r\n                    <- 60 s, skipped
F\r\ndata: in oven\n\n\r\n             <- 4 min, message "in oven"
...
18\r\ndata: out for delivery\n\n\r\n   <- 9 min, 0x18 = 24 bytes, message "out for delivery"
```

### One Write as Bytes
`data: a\n\n` is 9 bytes. Four of them are 36 bytes, hex 24. One write of all four is one chunk:

```text
32 34 0D 0A                      "24\r\n"   chunk marker: 0x24 = 36 bytes follow
64 61 74 61 3A 20 61 0A 0A       "data: a\n\n"
64 61 74 61 3A 20 62 0A 0A       "data: b\n\n"
64 61 74 61 3A 20 63 0A 0A       "data: c\n\n"
64 61 74 61 3A 20 64 0A 0A       "data: d\n\n"
0D 0A                            "\r\n"     chunk marker: end of this chunk
```

42 bytes of TCP data: 4 + 36 + 2. The browser removes the first 4 and the last 2, then finds `0A 0A` four times, so it calls `onmessage` four times.

### Who Does the Parsing
The browser, as the bytes arrive, not the page's JavaScript. `EventSource` is code built into the browser by its makers. The page's JavaScript calls `new EventSource(...)` once, and from then on the browser's code runs by itself:

```text
0 s       page JS calls new EventSource("/order/57/events")   <- page JS runs once
0 s       browser sends the GET request, reads the reply's headers
4 min     bytes arrive: F\r\ndata: in oven\n\n\r\n
          browser removes chunk markers -> data: in oven\n\n
          browser finds the empty line -> one complete message
          browser removes "data: ", calls page JS onmessage("in oven")   <- page JS runs again
9 min     next bytes arrive, same steps
```

If a message arrives split across two frames, the browser keeps the first part and calls `onmessage` only when the empty line has arrived. If the page used `fetch()` instead of `EventSource`, it would get the body bytes `data: in oven\n\n` and would have to split them itself.

### Server (Node.js)
```js
const http = require("http");

const status = new Map([["57", "cooking"]]); // order number -> current text
const listeners = new Map();                 // order number -> list of open replies (res)

function send(res, text) {
  // one data line per line of text, then the empty line that ends the message
  res.write(text.split("\n").map((line) => `data: ${line}`).join("\n") + "\n\n");
}

http.createServer((req, res) => {
  const events = req.url.match(/^\/order\/(\d+)\/events$/);
  if (req.method === "GET" && events) {
    const id = events[1];
    res.writeHead(200, { "Content-Type": "text/event-stream" });
    send(res, status.get(id));               // current state first
    listeners.set(id, [...(listeners.get(id) || []), res]);

    const ping = setInterval(() => res.write(": ping\n\n"), 30000);
    res.on("close", () => {                  // browser went away
      clearInterval(ping);
      listeners.set(id, listeners.get(id).filter((r) => r !== res));
    });
    return;                                  // res.end() is not called here
  }

  const update = req.url.match(/^\/order\/(\d+)\/status$/);
  if (req.method === "POST" && update) {     // the kitchen sends "in oven", ...
    let body = "";
    req.on("data", (part) => (body += part));
    req.on("end", () => {
      const id = update[1];
      status.set(id, body);
      for (const r of listeners.get(id) || []) send(r, body);
      res.end("ok\n");
    });
    return;
  }

  res.writeHead(404);
  res.end();
}).listen(80);
```

The handler does not write `Transfer-Encoding: chunked`. Node adds it by itself: when the handler gives no `Content-Length`, Node puts that header in, and wraps every `res.write()` in a chunk. The handler never sees the chunk markers.

### Browser (the Page's JavaScript)
```js
const events = new EventSource("/order/57/events");

events.onmessage = (e) => {
  document.getElementById("status").textContent = e.data;  // "cooking", "in oven", ...
  if (e.data === "delivered") events.close();              // stop, no more requests
};
```

### nginx in Between
Two of nginx's defaults get in the way:

* **Its buffer** (section 96): with `proxy_buffering on`, a 15-byte message can sit in nginx's buffer instead of going to the browser.
* **Its 60 s limit** (section 97): if web2 sends nothing for 60 s, nginx ends the reply.

Both are set in nginx's settings file, only for the stream paths:

```text
location ~ /events$ {               # these settings apply only to paths ending in /events
    proxy_pass http://shop_servers; # send these requests to the list web1-web4 (named elsewhere in the file)
    proxy_buffering off;            # send web2's bytes to the browser as soon as they arrive
    proxy_read_timeout 3600s;       # allow up to 1 hour with no bytes from web2, instead of 60 s
}
```

The other way is for web2's program to decide per reply, without changing nginx's file. It adds the header `X-Accel-Buffering: no` to the reply. nginx reads it, sends this reply's bytes on as they arrive, and removes the line, so the browser never sees it. Node knows nothing about nginx, so Node never adds it by itself.

The `: ping\n\n` line every 30 s is there so bytes keep passing even when there is no news, and no machine on the way closes the connection for being silent. The browser skips it, by the `:` rule.

### Ending the Reply: What res.end() Sends
`res.end()` ends the HTTP reply. It does not close the TCP connection. What it sends depends on how the reply's length is marked.

**Normal reply**: `res.end("ok\n")` with nothing sent before. Node counts the 3 bytes itself:

```text
HTTP/1.1 200 OK\r\n
Content-Length: 3\r\n
\r\n
ok\n
```

No end marker is needed. The browser knows the body ends after 3 bytes.

**Chunked reply** (SSE, or any reply with earlier `res.write()` calls and no `Content-Length`):

```js
res.write("data: delivered\n\n");
res.end();
```

```text
11\r\ndata: delivered\n\n\r\n     <- the write (0x11 = 17 bytes)
0\r\n\r\n                         <- from res.end(): the 0 chunk, "body finished"
```

In both cases the connection stays open afterwards and can carry the next request. Node closes it with FIN after `res.end()` only if either side sent `Connection: close` (section 98).

### Reconnecting
`EventSource`'s rules (part of the HTML rules browsers follow) say: whenever the connection breaks or the server ends the reply, wait a few seconds and send the same GET again. The browser cannot tell whether the server meant to end, because many things end a stream with a normal `0\r\n\r\n` without the shop's program deciding to stop:

```text
web2's program is restarted                 Node ends open replies on the way down
nginx's time limit is reached               nginx ends the reply to the browser
web2 is taken out of the list (section 94)  the reply ends, other servers are still working
```

In all of these, the page still wants updates, and reconnecting gets them. So `res.end()` alone does not stop the stream.

The new GET runs the handler from the start, and the handler's first act is to send the current status. So if "in oven" was sent while the phone had no signal, the reconnected page still gets `in oven` as its first message.

The browser does not know what the messages mean, so it never decides to stop by itself, except when the tab is closed. A planned stop has its own signals, which cannot happen by accident:

```text
page JS calls events.close()               after it sees "delivered"
server answers the reconnect GET with      HTTP/1.1 204 No Content
```

A common pattern: the server sends `data: delivered\n\n` and calls `res.end()`, and the page calls `events.close()` when it sees `delivered`.

### Who Does What
```text
page JS        calls new EventSource once; gets message text in onmessage; calls close() at the end
browser        sends the GET, removes chunk markers, splits at empty lines, removes "data: ",
               calls onmessage; reconnects by itself if the reply ends or the connection breaks
nginx (P)      passes bytes on at once (proxy_buffering off, or X-Accel-Buffering: no)
web2 program   writes "data: ...\n\n" for news and ": ping\n\n" every 30 s
```

### Limits
* One direction only, server to browser. The browser sends data with ordinary requests.
* Text only (UTF-8).
* With HTTP/1.1, each open stream holds one of the browser's 6 connections to that name (section 88). With HTTP/2 it is one stream on the shared connection, so this limit does not apply.

### Name
This is **Server-Sent Events**, or **SSE**.

### The Next Problem
The customer wants to chat with the driver: messages going both ways, many times a minute. With SSE, the driver's messages arrive on the open reply, but each customer message is a separate POST request with all its headers. Could the browser and the server stop using HTTP's request/response rules on a connection and just send messages both ways?

---

## 102. Switching the Connection to Another Protocol

### The Idea
The browser opens a normal TCP connection and sends a normal HTTP request, but the request asks: "after this, let us stop speaking HTTP on this connection." If the server agrees, both sides switch to a different set of rules on the same TCP connection. Under the new rules, either side can send a message whenever it wants, with no requests and no replies.

### The Request That Asks to Switch
```text
GET /chat/57 HTTP/1.1\r\n
Host: www.bluepizza.com\r\n
Connection: Upgrade\r\n
Upgrade: websocket\r\n
Sec-WebSocket-Version: 13\r\n
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n
\r\n
```

* `Connection: Upgrade`: the `Connection` header from section 98, with a new value: "I want to change the protocol on this connection."
* `Upgrade: websocket`: which protocol to change to.
* `Sec-WebSocket-Version: 13`: which version of the WebSocket rules the browser follows.
* `Sec-WebSocket-Key`: 16 random bytes the browser picks for this one handshake.

The key is written using **base64**, a way to write any bytes using only letters, digits, `+` and `/`. Every 3 bytes become 4 characters, and `=` fills the last group if it is short. 16 bytes become 24 characters, ending in `==`.

### Why Only the Browser Writes Sec- Headers
The browser does not let page JavaScript set any header whose name starts with `Sec-`. If `fetch()` tries, the browser leaves the line out. So when a server sees `Sec-WebSocket-Key`, it knows the browser itself sent a real WebSocket request. Page JavaScript cannot fake one with `fetch()` to make a server switch. Because these headers share the start `Sec-`, one rule covers all of them, including ones added later.

### The Reply That Agrees
```text
HTTP/1.1 101 Switching Protocols\r\n
Connection: Upgrade\r\n
Upgrade: websocket\r\n
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n
\r\n
```

Status `101` means "agreed, switching now". Everything after this empty line, in both directions, follows the WebSocket rules instead of HTTP's.

### The Key and the Accept Value
`Sec-WebSocket-Accept` is the server's answer to the key. It uses **SHA-1**, a calculation that turns any input into 20 bytes. The same input always gives the same 20 bytes.

```text
1. server joins the key text and a fixed text written in the WebSocket rules:
   dGhlIHNhbXBsZSBub25jZQ==258EAFA5-E914-47DA-95CA-C5AB0DC85B11
2. SHA-1 of those characters gives 20 bytes:
   b3 7a 4f 2c c0 62 4f 16 90 f6 46 06 cf 38 59 45 b2 be c4 ea
3. those 20 bytes in base64 (28 characters):
   s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
4. server writes it in the reply:
   Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

The browser remembers the key it sent, does steps 1–3 itself, and compares its own 28 characters with the ones after `Sec-WebSocket-Accept:` in the reply. If they are the same, it switches. If not, it closes the connection.

Only a server that knows the WebSocket rules can produce the right value for a key that was just made up. So this proves the reply came from a WebSocket server, not from an ordinary HTTP server or a stored copy of an old reply.

### One Connection, Used Only for This
In HTTP/1.1 a connection carries one request at a time, and browsers open a **new** TCP connection for each WebSocket. The page's other GETs (menu, photos) go on the browser's other connections. Once switched, the connection never goes back to HTTP. It carries WebSocket messages until it is closed.

Everything happens on that one connection, with the same four values:

```text
SYN, SYN+ACK, ACK                  TCP handshake
GET /chat/57 ... Upgrade           HTTP request
HTTP/1.1 101 Switching Protocols   HTTP reply
pieces, both directions, any time  WebSocket messages (section 103)
close piece, then FIN              end
```

### A Separate Protocol
Polling, long polling and SSE are plain HTTP: ordinary requests and replies. SSE is just an HTTP reply whose body uses `text/event-stream` and never ends.

WebSocket is a separate protocol with its own rules. Only its start uses HTTP, one GET and one `101` reply, so it can share port 80 and pass through proxies like nginx. After the 101, no HTTP is spoken on that connection again.

### Name
This protocol is **WebSocket**. The switch with `101` is the **WebSocket handshake**. It is separate from TCP's handshake and comes after it.

### The Next Problem
After the 101 there are no requests, no replies and no `Content-Length`. How does each side know where one message ends and the next begins?

---

## 103. WebSocket Messages

### A Header, Then the Message
After the 101, every message goes on the connection as a small header followed by the message bytes. The rules call this a frame. To keep it apart from cable frames, these notes call it a **piece**, as with HTTP/2 (section 89).

```text
[ header ][ message bytes ]
```

The first 2 bytes of the header hold four things:

```text
last part?     yes or no. A long message can be split into several pieces. Usually yes.
kind           text, binary (any bytes, like a photo), close (ending the WebSocket),
               ping or pong (section 104)
scrambled?     no for pieces from the server, yes for pieces from the browser
length         how many message bytes follow
```

### Reading a Piece
The driver's side sends "on my way", which is 9 characters:

```text
header:   last part = yes, kind = text, scrambled = no, length = 9      2 bytes
message:  on my way                                                    9 bytes
```

The browser reads the 2 header bytes and learns "text, 9 bytes". It reads the next 9 bytes, which make one complete message, and passes "on my way" to the page's JavaScript. The byte after that starts the next piece's header.

This is the length-prefix method from section 82. So one `send("ok")` on one side gives exactly one message `"ok"` on the other, never split and never joined with the next.

### Longer Messages
The length space in the header is 7 bits, so it can hold 0 to 127. The rules use it like this:

```text
value in length space    meaning
0 - 125                  that is the length
126                      the real length is in the next 2 bytes (up to 65,535)
127                      the real length is in the next 8 bytes (larger)
```

The receiver always reads the first 2 header bytes, then looks at the length space:

```text
message size    length space says    header size
9 bytes         9                    2 bytes
1,000 bytes     126                  2 + 2 = 4 bytes   (next 2 bytes hold 1,000)
100,000 bytes   127                  2 + 8 = 10 bytes  (next 8 bytes hold 100,000)
```

### No Reply
WebSocket has no request/response rule. When the server sends "on my way", the browser sends nothing back. Those 11 bytes are all the message costs.

With HTTP, a customer message sent as a POST must get a reply, because that is HTTP's rule (section 97):

```text
HTTP:       POST request (about 100 bytes)  ->   then   <- reply "HTTP/1.1 200 OK ..." (about 50+ bytes)
WebSocket:  piece (11 bytes)                ->   nothing comes back
```

TCP's acks still happen in both cases, but those are sent by the kernels, not the programs, and they are the same either way.

### Scrambling
**Scrambled** means each message byte is changed with a random value before sending, so the bytes on the wire are not the bytes the page wrote. The server reverses the change and gets the original back.

The browser picks 4 random bytes for each piece, called the **mask**. It combines message byte 1 with mask byte 1, message byte 2 with mask byte 2, and so on. Byte 5 uses mask byte 1 again. The combining is **XOR**: compare the two bytes bit by bit, and write 1 where the bits differ and 0 where they are the same.

The letter `o` with mask byte 18:

```text
o          0110 1111
mask 18    0001 0010
XOR        0111 1101    = the character }
```

The server does XOR with the same mask byte again and gets `0110 1111`, which is `o`. Doing XOR twice with the same value always gives back the original.

### Why Browser Pieces Are Scrambled
Some old machines on the path, like a school's proxy F (section 93), read the bytes on connections that pass through them and look for things like `GET ... HTTP/1.1`. They do not know WebSocket. When such a machine sees the `101`, it does not understand that the connection has switched, and keeps reading the bytes as if they were still HTTP.

Without scrambling, a bad website could make F keep a fake version of a real page:

1. A student opens a page from `www.badsite.com`. The person who runs that site wrote both the page's JavaScript and the server program.
2. The page opens a WebSocket to its own server, through F. The server agrees with `101`. F passes everything on but still treats the connection as HTTP.
3. The page's JavaScript sends a WebSocket message whose text is exactly:

   ```text
   GET http://www.bluepizza.com/menu HTTP/1.1\r\n
   Host: www.bluepizza.com\r\n
   \r\n
   ```

   F reads these bytes as a new request for bluepizza's menu. But it sends them on the connection it already has open, which leads to badsite's server.
4. badsite's server sends back bytes that look like an HTTP reply: `HTTP/1.1 200 OK`, headers, and a fake menu with different prices or a fake order form.
5. F stores this as its copy of `www.bluepizza.com/menu`.
6. For as long as that copy is kept, every student who asks for bluepizza's menu gets the fake page from F. bluepizza's real server is never contacted.

With scrambling, step 3 does not work. The page writes `GET http://...`, but the browser XORs it with 4 random bytes it chose, so the bytes on the wire are unreadable, and F does not see a request. Researchers showed this attack working against real proxies in 2011, which is why the scrambling rule is in the WebSocket rules.

The server's pieces are not scrambled, because page JavaScript does not choose what the server sends.

### Full Examples
**Server to browser, "on my way" (11 bytes):**

```text
byte 1     1 000 0001       last part = yes, (3 unused bits), kind = 0001 = text
byte 2     0 000 1001       scrambled = no, length = 9
bytes 3-11 on my way        the message, as is
```

**Browser to server, "ok" (8 bytes):**

```text
byte 1     1 000 0001       last part = yes, kind = text
byte 2     1 000 0010       scrambled = yes, length = 2
bytes 3-6  18 52 86 120     the mask, 4 random bytes picked by the browser
byte 7     }                o scrambled with 18
byte 8     _                k scrambled with 52
```

The server reads byte 2, sees "scrambled = yes, length 2", reads the 4 mask bytes, then the 2 message bytes, and reverses the XOR to get `ok`.

### Header Size
The mask is part of the header. It comes right after the length bytes and before the message bytes.

```text
part                          when                                   bytes
first 2 bytes                 always                                 2
extra length                  message 126 - 65,535 bytes             +2
                              message larger than that               +8
mask                          piece sent by the browser              +4
```

So a header is 2 to 14 bytes, followed by the message bytes.

### The Next Problem
There is a proxy in the middle. nginx does not pass the browser's `Connection` line on to web2, because it applies to one connection only (section 98). So the request that asks to switch reaches web2 without `Connection: Upgrade`, and web2 never switches. What has to change in nginx, and what do the Node.js and browser programs look like?

---

## 104. WebSocket Through nginx, and the Programs

### What nginx Needs
In nginx's settings file (section 96):

```text
location /chat/ {                              # these lines apply to paths starting with /chat/
    proxy_pass http://shop_servers;            # send to the list web1-web4
    proxy_http_version 1.1;                    # talk HTTP/1.1 to web2
    proxy_set_header Upgrade $http_upgrade;    # add an Upgrade line to the request to web2
    proxy_set_header Connection "upgrade";     # add "Connection: upgrade" to the request to web2
    proxy_read_timeout 3600s;                  # allow 1 hour with no bytes, instead of 60 s
}
```

* `proxy_http_version 1.1`: by default nginx talks HTTP/1.0 to the web servers, and switching with `Upgrade` exists only in HTTP/1.1.
* `proxy_set_header`: adds a header to the request nginx sends to web2. `$http_upgrade` is nginx's name for the value of the browser's `Upgrade` line, here `websocket`. These two lines put back what nginx would otherwise leave out, so web2 receives a request asking to switch.

### What nginx Does After the Switch
web2 replies `101`. nginx passes the 101 to the browser and from then on stops reading HTTP on both connections. It copies every byte from the browser's connection into web2's connection, and every byte from web2's back, without looking at them. There are still two TCP connections, browser–P and P–web2. The WebSocket pieces go through unchanged.

### The Server Program (Node.js)
Node's built-in `http` module does not do the server side of WebSocket. The common library for it is `ws`. It checks the `Upgrade` and `Sec-WebSocket-Key` lines, computes `Sec-WebSocket-Accept`, writes the 101, and then reads and writes pieces: header, length, removing the scrambling.

```js
const http = require("http");
const { WebSocketServer } = require("ws");

const server = http.createServer(/* handler for normal requests */);
const wss = new WebSocketServer({ server });   // takes requests that ask to switch

const rooms = new Map();                        // order number -> open sockets (customer, driver)

wss.on("connection", (socket, req) => {         // runs after the 101 is sent
  const id = req.url.split("/")[2];             // "/chat/57" -> "57"
  if (!rooms.has(id)) rooms.set(id, new Set());
  rooms.get(id).add(socket);

  socket.on("message", (data, isBinary) => {    // one complete message
    for (const other of rooms.get(id)) {
      if (other !== socket) other.send(data, { binary: isBinary });
    }
  });

  socket.on("close", () => rooms.get(id).delete(socket));
});

server.listen(80);
```

**isBinary:** `ws` always gives the message to the code as bytes (a Node `Buffer`). `isBinary` says which kind the piece's header had: `false` for text, `true` for binary. Passing `{ binary: isBinary }` to `send()` makes the forwarded piece the same kind as the original. Without it, `ws` sends a `Buffer` as binary, so the driver's browser would get `e.data` as raw bytes (a `Blob`) instead of the string `"where are you?"`.

### The Browser Program
```js
const ws = new WebSocket("ws://www.bluepizza.com/chat/57");

ws.onopen = () => ws.send("where are you?");   // runs after the 101 arrives
ws.onmessage = (e) => show(e.data);            // "on my way"
ws.onclose = () => show("chat ended");
```

`ws://` is the address form for WebSocket without encryption. The browser turns it into a TCP connection to port 80 and the GET request with the `Upgrade` lines. `wss://` is the encrypted form, which comes with TLS.

### The Room, Step by Step
The customer's browser (C) and the driver's phone (D) both opened `/chat/57` and both reached the same web2 program. After both connect, web2's memory is:

```text
rooms:  "57" -> { socketC, socketD }
```

C sends "where are you?" (14 characters):

```text
1. C's page JS        ws.send("where are you?")
2. C's browser        builds a piece: text, scrambled, length 14, sends it
3. nginx              copies the bytes to web2's connection
4. ws on web2         reads the piece, removes the scrambling,
                      runs the "message" handler of socketC with data = "where are you?", isBinary = false
5. the shop's code    goes through rooms.get("57") = { socketC, socketD }
                        socketC: same as the sender, skipped
                        socketD: socketD.send(data, { binary: false })
6. ws on web2         builds a piece: text, not scrambled, length 14, writes it on D's connection
7. D's app            onmessage gets "where are you?"
```

When D replies "on my way", the same steps run the other way. The handler of socketD runs, skips socketD, and sends to socketC.

### Keeping a Silent Chat Open
If nobody types for an hour, nginx's 1-hour limit closes the connection. The piece kinds include two for this: **ping** and **pong**. The server sends a ping piece every 30 s with `socket.ping()`, and the browser answers each one with a pong piece by itself. The page's JavaScript never sees them. Bytes keep passing through nginx, and the server also learns that the browser is still there.

### Who Does What
```text
page JS        new WebSocket(...), send(), onmessage, onclose
browser        TCP connection, GET with Upgrade + key, checks Accept, builds and scrambles pieces,
               reads pieces, answers pings
nginx (P)      adds Upgrade/Connection lines for web2, then copies bytes both ways
ws library     checks the request, writes 101, reads/writes pieces, removes scrambling
shop's code    decides what to do with each message (here: pass it to the other side)
```

Same limit as section 100: `rooms` lives in one process's memory. If the customer's WebSocket goes to web1 and the driver's goes to web3, they do not see each other. The servers then need to pass messages between them, which is not covered here.

### The Next Problem
The code above uses the library `ws`. Other projects use `socket.io`, and Postman has separate options for "WebSocket" and "Socket.IO". What is the difference, and what do "client" and "server" mean when both sides can send at any time?

---

## 105. WebSocket Clients, Servers and Libraries

### Client and Server
The two sides are different only at the start, plus one rule after it. Once the switch is done, both can send whenever they want:

```text
                    client                                    server
before              connects to an address and port           waits on a port (listen) for connections
the switch          sends GET with Upgrade and the key,       reads the GET, computes Accept, sends 101
                    checks the Accept value
pieces it sends     must be scrambled                         not scrambled
after that          sends and receives any time               sends and receives any time
closing             either side can                           either side can
```

It is the same split as TCP itself: one side calls `connect()`, the other waits with `listen()`. After the handshake, both are equal.

### Where Each Side Comes From
* **Browser client**: built into the browser. `new WebSocket("ws://...")` is part of every browser, like `fetch()`, so no library is needed.
* **ws**: a Node.js library that follows the WebSocket rules exactly. It gives Node both roles:
  * `new WebSocketServer(...)`: the server role. The web2 program in section 104 uses this.
  * `new WebSocket("ws://...")`: the client role, for a Node.js program that connects to some other WebSocket server, for example a script acting as the driver's phone app for testing.

`ws` exists because Node.js had no WebSocket support for a long time. Newer Node versions (22 and later) include a built-in `WebSocket` client, but still no built-in server.

### socket.io: Built on Top of WebSocket
**socket.io** is a Node.js library that does not change the WebSocket rules. It sends ordinary WebSocket messages and puts its own text format inside them. It is the same pattern as every layer so far: HTTP bytes inside TCP's data, DNS bytes inside UDP's data. Here, socket.io's text goes inside a WebSocket message's data:

```text
TCP data:          [ WebSocket piece header ][ message data                  ]
message data:                                 42["chat","where are you?"]
                                              ^ socket.io's format
```

When a socket.io client sends `socket.emit("chat", "where are you?")`, the WebSocket message text is `42["chat","where are you?"]`. The `4` means "a message" and the `2` means "a named event" in socket.io's own rules, followed by JSON with the name and the data. The WebSocket part only knows "a text message of 27 characters". The socket.io library on each side reads `42` and the JSON.

socket.io adds features on top: named messages (`socket.emit("chat", ...)` instead of plain text), rooms built in, automatic reconnect, and falling back to long polling if WebSocket cannot connect. It also connects to its own path, `/socket.io/?EIO=4&transport=websocket`, and sends its own keep-alive messages (`2` and `3`).

socket.io's server sits on a lower library of its own called engine.io, and engine.io uses `ws` by default for its WebSocket connections.

**socket.io-client** is the matching library for the browser side.

### They Do Not Mix
A plain WebSocket client cannot talk to a socket.io server, and socket.io-client cannot talk to a plain `ws` server. Each side expects a different format inside the messages. So a socket.io server needs socket.io-client in the browser (or a matching client in another language). That is why Postman has two separate options:

```text
Postman "WebSocket"    sends and shows plain WebSocket messages
Postman "Socket.IO"    speaks socket.io's format: you pick an event name and data
```

### The Next Problem
Everything so far (HTTP, SSE, WebSocket) travels as readable bytes, and every machine the frames pass through holds them in memory. What stops those machines from reading a password sent in a POST body?

---

## 106. Anyone on the Path Can Read the Bytes

### The Problem
A customer logs in to bluepizza from a café's Wi-Fi. The browser sends:

```text
POST /login HTTP/1.1\r\n
Host: www.bluepizza.com\r\n
Content-Type: application/x-www-form-urlencoded\r\n
Content-Length: 28\r\n
\r\n
user=meera&password=tomato42
```

On the way, the frames pass through or reach:

```text
the air            every wireless chip in range receives the café's air frames (section 50)
the café's box     holds every frame in memory to do NAT (section 59)
provider routers   hold every frame in memory to look up the to-IP
```

Each of these holds the whole frame, data included. Nothing stops any of them from reading `password=tomato42`.

There are three separate problems:

```text
1. read      a machine on the path reads the password
2. change    a machine on the path changes bytes, for example the prices in the menu reply
3. pretend   a machine answers as if it were bluepizza (like the fake DNS answers in section 84)
```

### The Idea
Before sending, the browser turns the readable bytes into unreadable bytes using a secret value that only it and bluepizza's server know. The server turns them back using the same value. Machines on the path see only the unreadable bytes.

* The secret value is called a **key**.
* Turning readable bytes into unreadable ones is **encryption**. Turning them back is **decryption**.
* Using the same key for both is called **symmetric** encryption.

### Why the WebSocket Mask Is Not This
The mask (section 103) used XOR with 4 bytes, but the mask was written in the piece itself, so anyone could reverse it. It was never meant to hide anything.

Even if the 4 bytes were kept secret, XOR with a short repeated key would not be enough. Say the browser XORs everything with 4 secret bytes k1 k2 k3 k4, repeated. A machine on the path knows an HTTP request starts with `POST`. It XORs the first 4 unreadable bytes with `P`, `O`, `S`, `T` and gets k1 k2 k3 k4. Now it can turn everything back.

### AES
The method used in practice is **AES**, the **Advanced Encryption Standard**.

```text
input     16 readable bytes + a key (16, 24 or 32 bytes; 16 and 32 are the common ones)
output    16 unreadable bytes
reverse   the same key turns the 16 unreadable bytes back into the readable ones
```

Longer data is handled 16 bytes at a time.

**It is an algorithm**: a fixed list of steps. For a 16-byte key, it repeats one round 10 times (12 times for a 24-byte key, 14 for a 32-byte key). Each round replaces every byte using a fixed table, moves bytes to new positions, mixes groups of 4 bytes together, and XORs the result with bytes made from the key. Any program can do these steps in ordinary code, in any language.

**Why it is safe**: the rounds mix the bytes so that even someone who knows the readable bytes and sees the unreadable ones cannot work out the key. The only way is to try every possible key. With a 16-byte key there are 2^128 of them, about 3.4 × 10^38.

**Where it came from**: in 2001, NIST, the US government's standards office, chose it after a public competition. The winning design was called Rijndael, made by two Belgian researchers, Joan Daemen and Vincent Rijmen. AES is that design under its official name.

**It has not changed since 2001.** That is the point of a standard: every program has to turn the same input and key into the same output, or the two sides could not understand each other. No practical way to break it has been found. What has changed over the years is how AES is applied to data longer than 16 bytes, and how a change to the bytes on the way is detected (section 111).

**Special processor instructions**: a processor runs a fixed set of basic operations called instructions, like add two numbers, compare, or load from memory. In ordinary code, one AES round takes dozens of them. Around 2010, Intel and AMD added instructions that each do one entire AES round on 16 bytes (Intel calls them AES-NI). Phone processors (ARM) added similar ones. With them, one processor core can encrypt roughly several gigabytes per second (exact numbers not checked), so encryption takes very little time compared with sending the bytes.

### The Next Problem
AES works only if the browser and bluepizza's server already share the same secret key. They have never communicated before, and every byte they send each other passes through machines that can read it. How can they agree on a key that those machines cannot learn?

---

## 107. Agreeing on a Key in Front of Everyone

### What Is Needed
The browser and the server should end up with the same secret number, while every byte they send each other can be read by machines on the path.

### One Piece of Math: Remainder
`x mod n` means the remainder after dividing x by n. For example, `25 mod 23 = 2`, because 25 = 1 × 23 + 2.

### The Exchange, With Small Numbers
Two numbers are public, written in the rules, and everyone knows them: **23** and **5**.

```text
step                                   browser                        server
1. pick a secret number, never sent    6                              15
2. compute 5^secret mod 23             5^6 mod 23 = 8                 5^15 mod 23 = 19
3. send that result to the other       sends 8  ------------->
                                                <-------------        sends 19
4. compute (received)^secret mod 23    19^6 mod 23 = 2                8^15 mod 23 = 2
```

Both end up with **2**. Neither 6 nor 15 was ever sent.

**Why both get the same number**: the browser computed (5^15)^6 and the server computed (5^6)^15. Both are 5^(6×15) = 5^90, and the remainder steps do not change that. So both get 5^90 mod 23 = 2.

### What a Machine on the Path Sees
It sees 23, 5, 8 and 19. To get 2, it needs one of the secrets: a number x where `5^x mod 23 = 8`. With these small numbers it can try x = 1, 2, 3, ... and find 6 within a few tries.

With real sizes, the numbers are about 600 digits long. Trying every x would take longer than any computer could run, and no faster general method is known. Computing `5^x mod n` forwards is fast. Going backwards from the result to x is not.

### Names
This is the **Diffie–Hellman key exchange**, published by Whitfield Diffie and Martin Hellman in 1976. These notes call the two values that are sent (8 and 19 here) the **exchange values**.

TLS today mostly uses a version of the same idea called **X25519**. It uses a different kind of math, and its secret numbers and exchange values are 32 bytes each instead of 600-digit numbers. The shared result is then put through a fixed calculation that turns it into the AES key.

### The Next Problem
This stops a machine that only reads. But a machine M on the path can also change bytes. M can do its own exchange with the browser (pretending to be the server) and its own with the server (pretending to be the browser):

```text
browser  <--- key 1 --->  M  <--- key 2 --->  server
```

M decrypts everything from the browser with key 1, reads it, encrypts it again with key 2 and sends it on. Neither side notices. How can the browser know that the exchange value it received really came from bluepizza's server and not from M?

---

## 108. Proving Who Sent a Value

### What Is Needed
A way for bluepizza's server to attach something to its exchange value that only bluepizza's server could have made, and that the browser can check.

### A Pair of Keys
bluepizza's server has two keys that were made together as a pair:

```text
PRIV-B    private key: stays on bluepizza's server, never sent to anyone
PUB-B     public key:  anyone can have a copy
```

There are two fixed calculations that every program knows:

```text
sign(message, private key)                 -> signature (some bytes)
check(message, signature, public key)      -> yes or no
```

The rule: `check` says **yes** only if the signature was made by `sign` on exactly that message, with the private key that belongs to that public key.

### Example 1: Normal
bluepizza's server wants to send the message "my value is 19".

```text
server:   sign("my value is 19", PRIV-B)  -> SIG-1
sends:    "my value is 19" + SIG-1
browser:  check("my value is 19", SIG-1, PUB-B)  -> yes
```

### Example 2: M Changes the Message
M changes it to "my value is 10" and keeps SIG-1.

```text
browser:  check("my value is 10", SIG-1, PUB-B)  -> no    (SIG-1 was made for "19", not "10")
```

### Example 3: M Signs With Its Own Key
M has its own pair, PRIV-M and PUB-M.

```text
M:        sign("my value is 10", PRIV-M)  -> SIG-M
browser:  check("my value is 10", SIG-M, PUB-B)  -> no    (made with PRIV-M, not PRIV-B)
```

### Example 4: M Wants a "Yes" for Its Own Message
It would need `sign("my value is 10", PRIV-B)`. M cannot do that, because PRIV-B never leaves bluepizza's server.

### What a Signature Is
A **signature** is bytes attached to a message that show two things: which private key made them, and that the message has not been changed since.

Compare it with the TCP checksum (section 76). If M changes bytes, M can just recompute the checksum, because anyone can. A signature can only be made by whoever holds the private key.

### How It Is Used Here
In practice the signed message is not one number. The server takes its copy of all the handshake messages so far, including both exchange values, runs a fixed calculation that turns them into 32 bytes (SHA-256, the same kind of calculation as SHA-1 in section 102), and signs those 32 bytes. If M changed any of those messages, `check` says no. Section 111 shows exactly which messages.

### Names
The checking key is the **public key**, and the signing key is the **private key**. This "private" has nothing to do with private IP addresses. One common signing method is **RSA**, from Rivest, Shamir and Adleman, 1977. TLS also allows other methods, built on the same kind of math as X25519. The math inside `sign` and `check` is not covered here.

### The Next Problem
The browser needs bluepizza's public key to run `check`. If the server sends it during the connection, M can replace it with PUB-M and sign with PRIV-M. The check then passes, for M. How can the browser know which public key really belongs to `www.bluepizza.com`?

---

## 109. Someone the Browser Already Trusts

### The Idea
The browser cannot trust a public key that arrives over the same path as M. But it can trust a public key that was **signed by someone whose public key it already has**, if it got that key before any connection, not over the network.

### The List Inside the Browser
Every operating system or browser comes with a list of public keys from a small number of organizations. On Ubuntu the list is a set of files under `/etc/ssl/certs/`. Firefox keeps its own list. These organizations are called **certificate authorities (CAs)**. The list has around 150 entries (exact count not checked). One example is **Let's Encrypt**, a non-profit that signs for free.

### The Key Pair Is Made on bluepizza's Server
The CA never makes or gives out bluepizza's private key. bluepizza's server makes its own pair and sends only the public key to the CA:

```text
1. on bluepizza's server   a program (usually certbot, Let's Encrypt's tool) makes a key pair
                           private key -> saved in a file on the server's disk, never sent anywhere
                           public key  -> put into the request to the CA
2. CA                      checks that the request comes from whoever runs the name (below)
3. CA -> server            sends back the certificate: the name + the public key, signed by the CA
```

### What the CA Checks Before Signing
The request says "the public key for `www.bluepizza.com` is PUB-B, please sign that." Let's Encrypt has to make sure the request comes from whoever runs `www.bluepizza.com`:

1. Let's Encrypt replies with a random text, for example `k7Qz...`.
2. bluepizza's server must make that text available at `http://www.bluepizza.com/.well-known/acme-challenge/...`.
3. Let's Encrypt looks up `www.bluepizza.com` in DNS itself, sends a GET to that path, and checks that the text is there.

Only whoever controls the real server for that name can do step 2.

### The Certificate
Then Let's Encrypt signs a small document with its own private key:

```text
name            www.bluepizza.com
public key      PUB-B
valid from      2026-10-01
valid until     2026-12-30
signed by       Let's Encrypt
signature       made with Let's Encrypt's private key over all the lines above
```

This signed document is a **certificate**. Let's Encrypt's certificates are valid for 90 days. Whether that has changed is not checked.

### Two Separate Checks: Signature and Name
A passing signature check does not mean the name is correct. They are two separate checks, and both have to pass.

**The signature check** means: "these exact bytes were signed by this CA, and not one byte has changed since." It is done in three steps:

```text
1. browser runs SHA-256 over the certificate's lines (name, key, dates)    -> 32 bytes, call it X
2. browser uses the CA's public key on the signature                       -> 32 bytes, call it Y
3. X equals Y?  yes -> pass,  no -> fail
```

**What it does not tell**: which name the browser wanted. Say M runs `www.badsite.com` and got a real certificate for it from Let's Encrypt:

```text
M's certificate            name: www.badsite.com, signed by Let's Encrypt
signature check            passes: Let's Encrypt really signed exactly these bytes
name check                 browser asked for www.bluepizza.com, certificate says www.badsite.com -> fail
```

If M edits the name in its certificate to `www.bluepizza.com`, step 1 gives a different X, but the signature still gives the old Y. X is not Y, so the signature check fails. So each option fails one check:

```text
M's certificate unchanged    signature passes, name fails
M's certificate edited       name passes, signature fails
```

Only a certificate that Let's Encrypt signed for `www.bluepizza.com` passes both, and Let's Encrypt gives one only to whoever controls bluepizza's real server.

### The Certificate Alone Proves Nothing
A certificate is public. Anyone can copy it, including M. What proves the server is bluepizza's is the signature over the handshake (section 108), which needs the private key file. M can send bluepizza's certificate, but without the private key it cannot make that signature.

With certbot, the two files end up here:

```text
/etc/letsencrypt/live/www.bluepizza.com/privkey.pem     the private key (made on this server)
/etc/letsencrypt/live/www.bluepizza.com/fullchain.pem   the certificate + the intermediate's (below)
```

In nginx, two lines point to them:

```text
ssl_certificate      /etc/letsencrypt/live/www.bluepizza.com/fullchain.pem;
ssl_certificate_key  /etc/letsencrypt/live/www.bluepizza.com/privkey.pem;
```

### The Chain
The CA's own private key is valuable. If it were stolen, the thief could sign certificates for any name. So the CA keeps that key on machines that are not connected to any network, and uses it only rarely, to sign a certificate for a second key pair called an **intermediate**. The intermediate's key signs the site certificates every day.

```text
ISRG Root X1 (Let's Encrypt's key in the browser's list)
   signs ->  intermediate certificate
                signs ->  www.bluepizza.com certificate
```

The server sends its own certificate plus the intermediate's. The browser checks each signature up the chain until it reaches a key in its list. The key in the list is called the **root**.

### The Next Problem
There are now four parts: AES, Diffie–Hellman, the signature and the certificate. How do they fit together?

---

## 110. The Four Parts Together

### Each Part Fixes the Problem Left by the One Before
```text
1. AES                makes the data unreadable on the path.
                      Problem: both sides need the same secret key first.

2. Diffie-Hellman     gives both sides the same secret number (the 2 in section 107),
                      without sending it. That number becomes the AES key.
                      Problem: M in the middle can do this exchange with each side separately.

3. Signature          bluepizza's server signs the values it sent, using its private key.
                      The browser checks them with bluepizza's public key.
                      Problem: how does the browser get bluepizza's real public key?

4. Certificate        a document saying "this public key belongs to www.bluepizza.com",
                      signed by a CA whose public key is already in the browser's list.
```

Read from the bottom up: the certificate gives the browser bluepizza's real public key. With it, the browser checks the signature, which proves the exchange values came from bluepizza and not from M. The exchange gives both sides the same secret. That secret is the AES key, and AES makes all the HTTP bytes unreadable.

### The Values, in Plain Words
The next sections use these names:

* **Exchange value**: what each side sends in the Diffie–Hellman step, like the 8 and the 19 in section 107. Each is made from a secret number that is never sent.
* **The key**: the AES key both sides compute from the two exchange values.
* **bluepizza's certificate**: the CA-signed document with bluepizza's name and public key.
* **bluepizza's handshake signature**: bluepizza's server signs its copy of all handshake messages so far with its private key.
* **Finished check**: a short value each side computes from the key and its copy of all handshake messages. If the other side computes the same value, both have the same key and saw the same messages. It has nothing to do with TCP's FIN.

### The Next Problem
All of this has to happen at the start of the connection, before any HTTP is sent. In what order are these values sent, who sends them (the browser program or the kernel), and how many round trips does it take?

---

## 111. The TLS Handshake, Step by Step

### Short Answers First
* **When**: after the TCP handshake (section 74), before any HTTP.
* **Kernel?** No. It runs inside the program, as a library. nginx and Node.js use one called OpenSSL, Chrome uses BoringSSL, and Firefox uses NSS. The kernel sees these bytes as ordinary TCP data and cannot read them.
* **A protocol?** Yes. It has its own rules for which bytes go where and what each side does. Its name is **TLS**, **Transport Layer Security**. The current version, TLS 1.3, was published in 2018 (RFC 8446).
* **OSI layer?** It does not fit the numbering cleanly (section 80). It sits between TCP (4) and HTTP (7). Some call it layer 6, others count it as part of the application. Either way: above TCP, below HTTP.
* **Round trips**: 1 for TLS 1.3, after TCP's 1. The older version 1.2 needed 2.

### Trip and Round Trip
* A **trip** is bytes going one way, laptop to server or server to laptop. Say it takes 25 ms.
* A **round trip** is there and back: one side sends something and waits for the answer. That is 50 ms.

Counting round trips means counting how many times one side has to stop and wait for an answer before it can continue.

### Who Is Who
```text
laptop                                         server (P)
page JavaScript       the shop's page code     nginx's HTTP part    reads requests, writes replies
browser's HTTP part   writes/reads HTTP text   nginx's TLS part     library inside nginx (OpenSSL)
browser's TLS part    library in the browser   server kernel        TCP, IP
laptop kernel         TCP, IP
```

The TLS parts are code inside the browser program and inside the nginx program:

```text
the program's HTTP part   writes "GET /menu HTTP/1.1 ..."         reads the readable reply
the program's TLS part    encrypts it                             decrypts back into HTTP bytes
-------------------- program / kernel boundary --------------------
kernel (TCP, IP)          sends the TLS bytes as TCP data         gives received TCP data to the TLS part
```

### Copies of the Handshake Messages
Both sides keep a copy of every handshake message they sent and received, in readable form:

```text
server's copy:   [browser's hello][server's hello][certificates]
browser's copy:  [browser's hello][server's hello][certificates]
```

The server signs its copy. The browser checks against its own copy. If M changed anything on the way, for example the server's exchange value, the browser's copy holds M's value while the server signed its real one, so `check` says no.

### The Whole Connection
**TCP handshake: round trip 1, 0–50 ms**

1. Page JavaScript calls `fetch("https://www.bluepizza.com/menu")`.
2. The browser's HTTP part asks the laptop kernel to connect to `198.51.100.7` port 443.
3. The laptop kernel sends SYN. The server kernel replies SYN+ACK. The laptop kernel sends ACK right away, in its own frame, and only then does `connect()` return to the browser.

**TLS handshake starts: round trip 2, 50–100 ms**

4. The browser's TLS part picks a secret number and computes its exchange value. It writes a hello message to the laptop kernel: "I want `www.bluepizza.com`, I can use AES, here is my exchange value." This is readable, because no key exists yet.
5. The laptop kernel sends it as TCP data, in the frame after the ACK:

   ```text
   [MAC group][IP group: to 198.51.100.7][TCP group: to port 443, ACK+PSH][TLS header: type 22 handshake, length ~300][hello, readable][CRC]
   ```

6. The server kernel gives the bytes to nginx's TLS part. nginx's TLS part picks its own secret number, computes its exchange value, and computes **the key**.
7. nginx's TLS part writes four messages to the server kernel:

   ```text
   server's hello: "here is my exchange value"    readable (the browser has no key yet)
   bluepizza's certificate + intermediate's       encrypted with the key
   bluepizza's handshake signature                encrypted with the key
   server's Finished check                        encrypted with the key
   ```

   These are about 3,000 bytes. A frame carries at most 1,460 data bytes (section 77), so the server kernel sends them in 3 frames.
8. The laptop kernel puts the bytes in order and gives them to the browser's TLS part, which:
   * computes **the key** from the server's exchange value and its own secret number
   * decrypts the certificates, the signature and the Finished check
   * checks the certificate, then the handshake signature, then the Finished check (section 112)
   * if any check fails, closes the connection

**TLS handshake ends; HTTP starts: round trip 3, 100–150 ms**

9. The browser's TLS part writes its own Finished check, encrypted. The TLS handshake is done on the browser's side.
10. The browser's HTTP part writes the readable request to the browser's TLS part:

    ```text
    GET /menu HTTP/1.1\r\nHost: www.bluepizza.com\r\n\r\n        (47 bytes)
    ```

11. The browser's TLS part encrypts it (details below) and writes it to the laptop kernel.
12. The laptop kernel sends the Finished check and the request:

    ```text
    [MAC group][IP group][TCP group: to port 443][TLS header: type 23, length ..][Finished check, unreadable]
                                                 [TLS header: type 23, length 64][64 unreadable bytes][CRC]
    ```

13. The server kernel gives the bytes to nginx's TLS part. It checks the browser's Finished check, then reads the next record's length (64), checks the TAG, and decrypts back to the 47 request bytes. It gives those to nginx's HTTP part.
14. nginx's HTTP part reads `GET /menu` and writes the readable reply. nginx's TLS part encrypts it the same way, and the server kernel sends it.
15. The browser's TLS part decrypts the reply and gives the readable HTTP bytes to the browser's HTTP part. That part gives the body to page JavaScript, and `fetch` returns.

### Why the Lone ACK Adds No Wait
A round trip is counted when one side has to receive an answer before it can send its next message. No answer to an ACK is ever sent (an ACK is never acked, section 74), and the laptop does not need anything back before sending the hello:

```text
0 ms      laptop kernel sends SYN
50 ms     SYN+ACK arrives; laptop kernel sends ACK
~50 ms    browser's TLS part writes the hello; laptop kernel sends it right after the ACK
75 ms     server receives the ACK, then the hello
100 ms    server's hello, certificates, etc. arrive at the laptop
```

### What Literally Gets Encrypted
For the request in step 11:

```text
input to AES:   the 47 request bytes + 1 byte meaning "this is HTTP data"   = 48 readable bytes
AES output:     48 unreadable bytes + a 16-byte TAG                         = 64 bytes
adds header:    type 23, version, length 64                                 = 5 bytes, readable
written to the laptop kernel: 69 bytes
```

The **TAG** is computed from the key and the encrypted bytes. The receiver recomputes it. If M changed even one byte, the TAG does not match and the receiver closes the connection. M cannot make a new TAG because it does not have the key. This solves problem 2 from section 106 (change).

The server's encrypted handshake messages in step 7 are encrypted the same way.

### Round Trips
```text
round trip 1   TCP handshake                       0 - 50 ms
round trip 2   TLS handshake (steps 4 - 8)         50 - 100 ms
round trip 3   Finished check + request, reply     100 - 150 ms
```

Without TLS, the reply would arrive at 100 ms. TLS adds one round trip.

### Names
* Steps 4–9 are the **TLS handshake**.
* HTTP inside TLS is **HTTPS**.

In Node.js, this is the difference between the `http` module and the `https` module: `https` is `http` with the TLS part between the code and the kernel.

### Port 443
HTTPS uses port 443. Plain HTTP stays on 80. They use separate ports because a server has to know what the first bytes on a new connection will be: a TLS hello (binary) or HTTP text like `GET /`.

```text
http://www.bluepizza.com    -> browser connects to port 80, sends HTTP text
https://www.bluepizza.com   -> browser connects to port 443, starts with a TLS hello
```

Many sites run both, but the program on port 80 only replies `301 Moved Permanently` with a header line `Location: https://www.bluepizza.com/...`, which tells the browser to repeat the request at the HTTPS address.

### The Next Problem
Step 8 says "checks the certificate, then the handshake signature, then the Finished check". What exactly does each check compare, and what does each one stop?

---

## 112. The Browser's Checks, One by One
The browser's TLS part does all of these after decrypting the server's messages. The server sends two certificates: bluepizza's own, and the intermediate's (section 109).

### Check 1: Was bluepizza's Certificate Made by a CA in My List?
This happens in two hops.

**1a.** bluepizza's certificate says "signed by: Let's Encrypt intermediate".

* The browser takes the intermediate's public key from the intermediate's certificate.
* It runs `check(bluepizza's certificate lines, the signature at the bottom of it, intermediate's public key)`.
* Yes means the intermediate signed exactly these lines: this name, this public key, these dates.

**1b.** The intermediate's certificate says "signed by: ISRG Root X1".

* The browser looks for ISRG Root X1 in its own built-in list and takes that public key.
* It runs `check(intermediate certificate lines, its signature, root's public key from the list)`.
* Yes means the root signed the intermediate.

**What it stops**: M making up its own certificate for `www.bluepizza.com`. M's signature does not lead to any key in the list.

### Check 2: Is the Name the One I Asked For?
* A certificate lists the names it covers, for example `bluepizza.com` and `www.bluepizza.com`.
* The browser compares that list with the name from the address, `www.bluepizza.com`.

**What it stops**: M sending its own real certificate for `www.badsite.com`. Check 1 passes, this one fails.

### Check 3: Is Today Inside the Dates?
* The browser compares "valid from" and "valid until" with the laptop's clock.
* If the laptop's clock is wrong by months, valid sites fail this check.

**What it stops**: use of old certificates, whose private keys might have been stolen or leaked since.

### Check 4: Did the Holder of bluepizza's Private Key Sign This Handshake?
* The browser has its own copy of the handshake messages so far: its hello, the server's hello (with the server's exchange value), and the certificates.
* It runs `check(its copy, bluepizza's handshake signature, bluepizza's public key from the certificate)`.
* Yes means whoever signed has bluepizza's private key and saw exactly the same messages, including the same exchange values.

**What it stops**:

* M sending bluepizza's real certificate: M has no private key to sign with.
* M replacing the server's exchange value: the browser's copy then differs from what bluepizza signed.

### Check 5: Does the Server Have the Same Key?
* The browser computes the Finished check it expects, from the key and its copy of all handshake messages.
* It compares that with the server's Finished check it just decrypted.
* Yes means the server computed the same key and has the same copy of every message.

Checks 1–4 prove who the server is. This one proves that the server ended up with the same AES key the browser has.

### On the Server's Side
In step 13 of section 111, nginx's TLS part does check 5 the other way round, with the browser's Finished check. That is how the server finds out if M changed the browser's hello on the way.

### When a Check Fails
The browser closes the connection and shows a warning page instead of the site. In Chrome:

```text
check 1 fails    NET::ERR_CERT_AUTHORITY_INVALID
check 2 fails    NET::ERR_CERT_COMMON_NAME_INVALID
check 3 fails    NET::ERR_CERT_DATE_INVALID
check 4 or 5     the connection is closed with an error (exact page not checked)
```

### What M Can Do, All Together
```text
reads the bytes                  sees the hello messages (name, exchange values), everything else is unreadable
replaces the exchange value      check 4 fails: M cannot sign without bluepizza's private key
sends its own certificate        check 1 or check 2 fails
sends bluepizza's certificate    check 4 fails
changes encrypted bytes          the TAG does not match
```

### The Next Problem
These notes have shown the IP group, the TCP group and HTTP's text byte by byte. What do TLS's own bytes look like?

---

## 113. What TLS Bytes Look Like
TLS bytes come in two levels: **records** on the outside, and **messages** inside the records.

### Level 1: The Record (the "TLS Group")
Everything the TLS part writes to the kernel is a sequence of records. Each record is a 5-byte header plus content. This is the length-prefix method from section 82:

```text
field     size      meaning
type      1 byte    22 = handshake message (readable)
                    23 = encrypted content
                    21 = alert (an error, e.g. "bad certificate", just before closing)
version   2 bytes   always 3.3, kept so old middle machines do not reject the record;
                    the real version is given inside the hello
length    2 bytes   how many content bytes follow (at most 16,384 readable bytes,
                    plus a little more for the TAG once encrypted)
content   length    one or more messages, readable or encrypted
```

### Level 2: Handshake Messages, Inside the Content
Level 1's content is a box. Level 2 describes what is inside that box when it holds handshake messages. It is like the IP group and the TCP group: the IP group only says "data follows", and the TCP group's rules describe what that data looks like.

Each handshake message has its own small header:

```text
field     size      meaning
type      1 byte    1 = client hello      2 = server hello      8 = extra settings
                    11 = certificate      15 = handshake signature   20 = Finished check
length    3 bytes   size of the body
body      length    depends on the type
```

The browser's hello, nested:

```text
[record header: type 22, version 3.3, length 300]     <- level 1: 5 bytes
[content: 300 bytes]                                  <- level 1 only says "300 bytes follow"
   inside those 300 bytes (level 2):
   [message type 1, message length 296]               <- 4 bytes
   [message body: version, random, ..., extensions]   <- 296 bytes
```

4 + 296 = 300, so this content is exactly one message. The box can also hold several messages back to back, as in the server's encrypted record below.

### The Client Hello, Field by Field
```text
[record: type 22, version 3.3, length ~300]
  [message: type 1 (client hello), length ~296]
    [version 3.3]
    [random: 32 bytes]                         new random bytes for every connection
    [session id: 32 bytes]                     kept only for old middle machines
    [methods I can use: 13 01, 13 02, 13 03]   13 01 = AES with a 16-byte key
                                               13 02 = AES with a 32-byte key
                                               13 03 = ChaCha20, used where the processor has no AES instructions
    [compression: none]                        kept only for old machines
    [extensions, each one = type (2 bytes), length (2 bytes), value:
       server name           www.bluepizza.com
       versions I support    1.3
       key share             X25519 + browser's exchange value (32 bytes)
       signing methods I can check
       next protocol         h2, http/1.1]
```

* **random**: makes every handshake's copy of messages different, so a signature recorded from an old connection cannot be used again in a new one.
* **server name**: called **SNI** (Server Name Indication). The server needs it because one server at one IP can run both `www.bluepizza.com` and `www.greencafe.com` (section 86), and it has to know which certificate to send before any HTTP arrives.
* **next protocol**: how the two sides choose the HTTP version. The browser lists what it can speak, and the server picks one. Its name is **ALPN** (Application-Layer Protocol Negotiation). This is why browsers use HTTP/2 only with encryption (section 89): it is chosen here, inside TLS.

### The Server's Messages
```text
[record: type 22]                                              readable
  [message: type 2 (server hello)]
    [version 3.3][random: 32 bytes][session id: copied]
    [method chosen: 13 01]
    [extensions: version 1.3, key share: X25519 + server's exchange value (32 bytes)]

[record: type 23][~3,000 encrypted bytes + 16-byte TAG]        unreadable on the path; after decryption:
  [message: type 8  (extra settings)]        e.g. next protocol chosen: h2
  [message: type 11 (certificate)]           bluepizza's certificate + the intermediate's
  [message: type 15 (handshake signature)]   signing method + the signature
  [message: type 20 (Finished check)]        32 bytes
  [1 byte: real type = handshake]
```

The record's content is one box holding four messages, each with its own type and length.

### After the Handshake
```text
[record: type 23, version 3.3, length 64][64 bytes: 48 encrypted + 16-byte TAG]
```

After decryption, the 48 bytes are the 47 HTTP bytes plus 1 byte giving the **real type**. The outside type is always 23, even when the record holds something else. Some non-HTTP records are still sent after the handshake:

```text
real type   what is inside           example after the handshake
23          HTTP bytes               the GET request, the reply
21          alert                    "close notify": TLS's own "I am closing now" message
22          handshake message        "new key": switch to a fresh AES key on a long connection
```

The receiving TLS part decrypts the content, reads the last byte, and then knows what to do: pass the bytes to HTTP, handle an alert, or handle a handshake message. Because this byte is encrypted too, a machine on the path cannot tell which of these a record is.

### Where It Sits in a Frame
```text
[MAC group][IP group][TCP group][TLS record header][TLS content][CRC]
```

TLS records are TCP data, the same way HTTP was TCP data before. HTTP is now inside the TLS content, encrypted.

### What the School's Proxy Sees
With HTTPS, the `Host:` line is inside the encrypted HTTP, so F (section 93) cannot read it. F sees the name outside HTTP, in two places:

1. **The SNI in the client hello.** It is sent before the key exists, so it is readable.
2. **With the proxy setting on**, the browser first sends F one short plain HTTP request, `CONNECT www.bluepizza.com:443 HTTP/1.1`, which means "open a TCP connection to this name and port, then copy bytes both ways". F reads the name there. After that, F only copies the encrypted bytes.

### The Next Problem
In sections 94–95, P and Q sit in front of web1–web4. With HTTPS, the browser does its TLS handshake with whatever answers at `198.51.100.7`. Which machine needs the certificate and private key, and can P still read the path to route `/order`?

---

## 114. Where TLS Ends When There Is a Load Balancer

### Case 1: P (L7, nginx) Ends TLS
P has the certificate and private key on its own disk. In nginx's settings file:

```text
server {
    listen 443 ssl;                     # wait for connections on port 443, use TLS on them
    server_name www.bluepizza.com;      # these settings are for this name
    ssl_certificate     /etc/letsencrypt/live/www.bluepizza.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/www.bluepizza.com/privkey.pem;

    location / {
        proxy_pass http://shop_servers; # send to web1-web4 in plain HTTP
    }
}
```

`ssl` is the old name for TLS. SSL (Secure Sockets Layer) was its earlier version, and nginx kept the word.

One request:

```text
1. browser's TLS part  <-- TLS handshake -->  nginx's TLS part on P
2. browser's TLS part      sends the encrypted request
3. nginx's TLS part        decrypts it -> readable "POST /order ..."
4. nginx's HTTP part       reads the path, picks web4, adds X-Forwarded-For
5. P's kernel              sends the readable request to 10.0.0.14 port 80, on a second connection
6. reply comes back        nginx's TLS part encrypts it for the browser
```

The TLS connection is between the browser and P only. Between P and web4 the bytes are readable, but they only travel inside the shop's local network.

Ending TLS at the proxy is called **TLS termination**.

**What it gives**:

* The certificate and private key live in one place, P, not on four servers.
* P can read HTTP, so it can route `/order` to web4, add `X-Forwarded-For`, and speak HTTP/2 to the browser.
* web1–web4 spend no processor time on encryption.

**What it costs**: P sees every password and order in readable form. Whoever controls P controls all of that.

### Case 2: Q (L4) Passes TLS Through
Q only changes the to-IP in each frame (section 95). It has no key, so the TLS records go through it unchanged:

```text
1. browser's TLS part  <-- TLS handshake, through Q -->  TLS part of the program on web2
2. Q                       sees only [TLS header: type 23][unreadable bytes]
```

The TLS connection is between the browser and web2 directly. So **each** of web1–web4 needs a copy of the certificate and the private key, because the browser could be sent to any of them.

This is called **TLS passthrough**. Q still cannot read the path, add `X-Forwarded-For`, or route `/order` anywhere specific.

**One thing Q can read**: the client hello is readable, including the SNI name. An L4 balancer can read that name and pick a group of servers by it without decrypting anything. In nginx this is the `ssl_preread` setting.

### Side by Side
```text
                           P (TLS termination)          Q (TLS passthrough)
TLS handshake is with      P                            web1 - web4
certificate + private key  on P only                    on every web server
can read path / headers    yes                          no (only the SNI name)
bytes P/Q -> web server    readable, or a second TLS    the browser's TLS records, unchanged
```

### Ending TLS Without Reading HTTP
Ending TLS and reading HTTP are separate things. TLS sits below HTTP, so a machine can decrypt TLS and still never read the HTTP inside.

On AWS, the Application Load Balancer (L7) ends TLS, with the certificate stored in AWS. The Network Load Balancer (L4) can either pass TLS through, like Q, or end TLS itself. When it ends TLS:

* It cannot pass frames along as they arrive. It has to take part in the handshake itself (receive the hello, send its own hello and the certificate over several frames, wait for the browser's Finished check), and a TLS record can be up to about 16 KB spread over many frames. The TAG check needs the whole record, so it collects every frame of a record before decrypting.
* After decrypting, it writes the readable bytes into its own second connection to the server, and its kernel builds new frames. So it works like P: two TCP connections, new frames. The only difference from P is that it never reads the HTTP inside, and it picks a server once per connection.

By the rule in section 95, "the highest layer it reads", such a balancer reads more than layer 4, because TLS is above TCP. AWS and most people still call it L4, using the name loosely to mean "does not read HTTP and picks a server once per connection". The pure L4 case is Q with TLS passthrough, which reads only the IP and TCP groups.

### TLS Between P and the Web Servers
`https://` in `proxy_pass` tells nginx to use TLS on the connection to the web server:

```text
proxy_pass http://shop_servers;    plain HTTP to web2, readable
proxy_pass https://shop_servers;   TLS handshake with web2 (exchange, key, AES), then HTTP inside it
```

TLS's rules always include the Diffie–Hellman exchange and AES. A TLS 1.3 handshake without a key exchange does not exist, so "use TLS" means "do the exchange and encrypt". nginx does not need a separate setting for that.

Both sides have to agree. web2's program must be listening with TLS, for example Node's `https` module given a key file and a certificate file. If nginx sends a TLS hello to a program that expects plain HTTP, that program reads binary bytes instead of `GET /`, and the connection fails.

### Encryption Without Checking the Certificate
The server always sends a certificate. What is optional is the client's check of it. Browsers always check. nginx checks web2's certificate only with `proxy_ssl_verify on`. Its default is off.

So a common setup for P to web1–web4:

* Each web server gets a **self-signed certificate**: one the server signs with its own private key instead of a CA's. One `openssl` command makes it.
* nginx connects with `proxy_pass https://...` and does not check it.
* The exchange still runs, so all bytes between P and web2 are encrypted with AES.

**What is lost**: the certificate check is what stops M from section 107, a machine that sits between P and web2 and does a separate exchange with each. Without the check, P cannot tell web2 from M. So this protects against machines that only read the shop's network, not against one that pretends to be web2. The question is not whether the shop trusts web1–web4. It is whether anything between P and them could pretend to be them.

**Other options**:

* **The shop's own CA**: the shop makes one CA key pair itself, signs web1–web4's certificates with it, and gives P the CA's public key (`proxy_ssl_trusted_certificate` with `proxy_ssl_verify on`). Now P really checks, without Let's Encrypt.
* **No certificate at all**: TLS 1.3 also allows a pre-shared key, where both sides are given the same secret in advance and use it instead of a certificate. It is uncommon for this. Whether nginx supports it on the `proxy_pass` side is not checked.

### The Next Problem
So far the shop owns P, the switch and web1–web4 in its own room. Suppose it rents computers from a company like AWS instead. There is no room, cable or switch it can touch. How does it get a local network like `10.0.0.x`, a public address for P, and NAT?

---

## 115. What "Renting a Computer" Actually Is

### The Physical Part
AWS owns large buildings full of physical computers. Say each one has 96 processor cores and 384 GB of memory. AWS's own cables, switches and routers join them. Only AWS staff touch them.

### The Shop's Part of One Computer
The shop asks AWS for "a computer with 2 cores and 4 GB of memory". AWS does not hand over a whole physical computer. A program run by AWS on the physical computer splits it, and gives 2 cores and 4 GB to a pretend computer. That pretend computer runs its own Linux kernel. Its kernel sees a processor, memory and a network card, the same as on a real computer.

* **Virtual machine (VM)**: a pretend computer made from part of a physical one.
* **EC2 instance**: AWS's name for a rented VM. EC2 = Elastic Compute Cloud.

### The Network Card Is Not a Card
The network card inside the VM is not a physical card. When web1's kernel puts a frame on its card, a part run by AWS on the physical computer receives those bytes. The frame does not go straight onto a cable. These notes call this **AWS's part** on the physical computer.

### Other Customers on the Same Computer
The same physical computer also runs VMs for other customers, such as greencafe. Each customer picks its own private addresses (section 58), so both can use `10.0.0.x`:

```text
physical computer H1               physical computer H2
  bluepizza web1   10.0.0.11         bluepizza web2   10.0.0.12
  greencafe app1   10.0.0.11         greencafe app2   10.0.0.12
```

### The Next Problem
web1's kernel sends a frame to `10.0.0.12`. Two VMs have that address, bluepizza's web2 and greencafe's app2, and they are on another physical computer. How does AWS deliver the frame only to bluepizza's web2, and make sure greencafe's VMs never see it?

---

## 116. VPC

### One Table per Customer
AWS keeps a separate table for each customer's network. Each row says which physical computer a VM's address lives on. Every frame a VM sends is looked up only in its own customer's table.

```text
table for bluepizza (id vpc-111)      table for greencafe (id vpc-222)
  10.0.0.11 -> physical computer H1     10.0.0.11 -> physical computer H1
  10.0.0.12 -> physical computer H2     10.0.0.12 -> physical computer H2
```

Real IDs are longer: `vpc-` followed by 17 hex characters. `vpc-111` is a placeholder.

### web1 Sends a Frame to 10.0.0.12
1. web1's kernel needs web2's MAC address, so it sends an ARP broadcast (section 15): "who has `10.0.0.12`?" AWS's part on H1 receives it. It does not send the broadcast anywhere. It reads the bluepizza table and answers web1 with a MAC address itself.
2. web1's kernel sends the frame: MAC group, IP group (from `10.0.0.11`, to `10.0.0.12`), TCP group, data.
3. AWS's part on H1 knows the frame came from a bluepizza VM. It reads the bluepizza table: `10.0.0.12 -> H2`.
4. AWS's part on H1 puts the whole frame, unchanged, inside a new packet with its own outer header: from H1's address, to H2's address, network ID `vpc-111`. The outer addresses belong to AWS's own building network, not to `10.0.0.x`. This is encapsulation (section 19) once more: one group inside another.

   ```text
   [outer header: from H1, to H2, vpc-111][web1's frame: MAC group][IP group][TCP group][data]
   ```

5. AWS's switches and routers carry it from H1 to H2, reading only the outer header.
6. AWS's part on H2 removes the outer header, reads `vpc-111`, and gives the inner frame to bluepizza's web2. web2's kernel sees a normal frame from `10.0.0.11`.

greencafe's app2 on H2 never gets the frame, because the network ID was `vpc-111`, not `vpc-222`.

AWS's exact outer header format is not public, so the details of step 4 are not checked.

### Name
One customer's separate network, with its own address range and its own table, is a **VPC** (Virtual Private Cloud). The shop picks the address range when it creates the VPC, for example `10.0.0.0` to `10.0.255.255`, written `10.0.0.0/16` (section 27).

### The Next Problem
The VPC is fully private right now. Nothing on the internet can reach `10.0.0.x`, and nothing in the VPC can reach the internet. P needs a public address that browsers can reach, and web1–web4 should stay unreachable from the internet. The shop has no router box of its own here. How does AWS split the VPC into a part that can talk to the internet and a part that cannot?

---

## 117. Subnets and Route Tables

### Splitting the Range
The shop splits the VPC's range into smaller ranges. Each one is a **subnet**:

```text
VPC        10.0.0.0/16    10.0.0.0 to 10.0.255.255
subnet A   10.0.1.0/24    10.0.1.0 to 10.0.1.255
subnet B   10.0.2.0/24    10.0.2.0 to 10.0.2.255
```

The addresses change from the room version in section 94:

```text
P            10.0.1.10                 (subnet A)
web1-web4    10.0.2.11 to 10.0.2.14    (subnet B)
```

### Five Addresses AWS Keeps
In every subnet, AWS keeps `.0`, `.1`, `.2`, `.3` and `.255` for itself. `.1` is the default gateway (section 26): where the VM's kernel sends frames for addresses outside its subnet. In the room, the home box's router part held that address. Here AWS's part on the physical computer answers for `.1`. So P cannot be `10.0.1.1`.

### A Route Table per Subnet
Each subnet is linked to a **route table**. AWS's part on the physical computer reads it for every packet a VM sends. As in section 27, when two rows match, the one with the larger number after the slash wins.

```text
route table for subnet A
  10.0.0.0/16  -> local               (inside the VPC: use the table from section 116)
  0.0.0.0/0    -> internet gateway    (every other address)

route table for subnet B
  10.0.0.0/16  -> local
```

The **internet gateway** is AWS's exit from the VPC to the internet. The shop adds one to the VPC. How it works is in section 118.

### Three Packets
```text
from    to            row that matches                  result
web2    10.0.2.11     10.0.0.0/16 -> local              delivered inside the VPC
web2    8.8.8.8       none (subnet B's table)           dropped; web2's kernel gets no reply
P       8.8.8.8       0.0.0.0/0 -> internet gateway     sent to the internet gateway
```

### Name
AWS calls a subnet whose route table has a row to the internet gateway a **public subnet**, and one without that row a **private subnet**. Nothing else makes a subnet public or private.

### The Next Problem
P's kernel only knows its address `10.0.1.10`. As in section 58, routers on the internet have no rows for `10.x.x.x`. How does a browser reach P at a public address like `198.51.100.7`, and what does the internet gateway do to P's packets on the way out and on the way in?

---

## 118. Internet Gateway

### One Public Address for One Private Address
The shop asks AWS for a public address and attaches it to P. The internet gateway then keeps this row:

```text
internet gateway table (bluepizza VPC)
  198.51.100.7  <->  10.0.1.10   (P)
```

There are two kinds of public address:

* **The automatic one**: changes when the VM is stopped and started again.
* **Elastic IP**: stays the same until the shop gives it back to AWS.

### A Browser Connects to P (Incoming)
1. The browser's packet goes from `203.0.113.50 : 51000` to `198.51.100.7 : 443`. Internet routers carry it to AWS, because AWS's range includes that address (section 58).
2. The internet gateway finds `198.51.100.7` in its table, rewrites the to-IP to `10.0.1.10`, and recomputes the checksums. Ports are not changed.
3. The VPC table (section 116) gives `10.0.1.10 -> physical computer H3`. The packet is encapsulated, carried to H3, and unwrapped.
4. P's kernel sees a packet from `203.0.113.50 : 51000` to `10.0.1.10 : 443`.

### P Replies (Outgoing)
1. P's kernel sends from `10.0.1.10 : 443` to `203.0.113.50 : 51000`.
2. Subnet A's route table matches `0.0.0.0/0 -> internet gateway`.
3. The internet gateway rewrites the from-IP to `198.51.100.7` and recomputes the checksums.
4. Internet routers carry it to the browser.

P's kernel never sees `198.51.100.7`. `ip addr` on P shows only `10.0.1.10`.

### Difference From the Home Box NAT
```text
                               home box (section 59)              internet gateway
devices per public address     many                               exactly one
ports                          changed                            unchanged
new connection from outside    dropped, no row (section 60)       allowed, the row is fixed
```

Because the row is fixed, a browser can start a new connection to P.

### What a VM Needs to Talk to the Internet
Both of these:

* a route table row `0.0.0.0/0 -> internet gateway`
* a public address in the internet gateway table

web1–web4 have neither. If web1 were in subnet A without a public address, the internet gateway would have no row for `10.0.2.11` and would drop its packets.

### The Next Problem
web1–web4 still need to make outgoing connections, for example to download updates with `apt` or to call a payment company's server. Nobody on the internet should be able to start a connection to them. How do they get out without a public address of their own?

---

## 119. NAT Gateway

### What It Is
A **NAT gateway** is a NAT, like the home box's in section 59, that AWS runs inside the shop's VPC. The shop puts it in subnet A and gives it two addresses:

```text
NAT gateway   private 10.0.1.50 (subnet A)   Elastic IP 198.51.100.20

internet gateway table now:
  198.51.100.7   <->  10.0.1.10   (P)
  198.51.100.20  <->  10.0.1.50   (NAT gateway)
```

The shop adds one row to subnet B's route table:

```text
route table for subnet B
  10.0.0.0/16  -> local
  0.0.0.0/0    -> NAT gateway
```

### web1 Downloads an Update From 192.0.2.80 : 80 (Outgoing)
1. web1's kernel sends from `10.0.2.11 : 40000` to `192.0.2.80 : 80`.
2. Subnet B's route table matches `0.0.0.0/0 -> NAT gateway`. The packet goes to the NAT gateway.
3. The NAT gateway rewrites the from part to `10.0.1.50 : 61000`, recomputes the checksums, and stores a row:

   ```text
   inside IP : port      outside port    other end
   10.0.2.11 : 40000     61000           192.0.2.80 : 80
   ```

4. The NAT gateway sends the packet. It is in subnet A, so subnet A's route table matches `0.0.0.0/0 -> internet gateway`.
5. The internet gateway rewrites the from-IP `10.0.1.50` to `198.51.100.20` (section 118). The update server sees a connection from `198.51.100.20 : 61000`.

### The Reply (Incoming)
1. The reply goes to `198.51.100.20 : 61000`. The internet gateway rewrites the to-IP to `10.0.1.50`.
2. The NAT gateway finds port 61000 in its table and rewrites the to part to `10.0.2.11 : 40000`.
3. The packet reaches web1's kernel.

### Nobody Outside Can Start a Connection
This works like the home box: many private addresses share one public address, and ports are changed. Someone on the internet sends a new packet to `198.51.100.20 : 62000`. The NAT gateway has no row for port 62000, so it drops it, exactly as in section 60.

### Why It Sits in Subnet A
Its own packets need the row `0.0.0.0/0 -> internet gateway`. Only subnet A's route table has it. In subnet B, the NAT gateway's packets would have no way out.

### The Next Problem
Nothing limits ports yet. Any program listening on P, on any port, can be reached from the internet at `198.51.100.7`. Inside the VPC, any VM can connect to any other VM on any port. How does the shop say "P accepts only ports 80 and 443 from the internet, and web1–web4 accept connections only from P"?

---

## 120. Security Groups

### What It Is
A **security group** is a list of allow rules attached to a VM's network card. AWS's part on the physical computer checks it before a packet reaches the VM, and after a packet leaves the VM. The VM's kernel does not do this check, and never sees the packets that are blocked.

* **Inbound rules**: for packets coming to the VM.
* **Outbound rules**: for packets leaving the VM.
* Only allow rules exist. Anything no rule allows is dropped.
* A new security group has no inbound rules, and one outbound rule that allows everything.

### The Shop's Two Security Groups
```text
sg-p   (attached to P)
  inbound:  TCP port 80   from 0.0.0.0/0
            TCP port 443  from 0.0.0.0/0
  outbound: everything    to 0.0.0.0/0

sg-web (attached to web1-web4)
  inbound:  TCP port 80   from sg-p
  outbound: everything    to 0.0.0.0/0
```

* `from sg-p` means "from any VM that has sg-p attached". Right now that is P, `10.0.1.10`.
* Port 80 on web1–web4 is the port the web program listens on, as in section 94.

### The Connection Table
AWS's part also keeps a table of the connections it has allowed. A packet that belongs to a stored connection is allowed in both directions, even if no rule matches it. Because it keeps this table, a security group is **stateful**.

### Four Cases
1. **A browser connects to P on port 443.** The inbound rule for 443 matches, so the packet is delivered and the connection is stored. P's replies pass because of the stored row.
2. **Someone connects to P on port 22.** No rule matches, and AWS's part drops the packet. It sends nothing back, so this is not the RST "connection refused" from section 94. The connecting side's kernel resends its SYN a few times and then gives up. On Linux with default settings, that takes about 2 minutes.
3. **web3 connects to web1 on port 80.** web3 does not have sg-p, so the packet is dropped.
4. **web1 downloads an update (section 119).** The outbound rule allows it, and the connection is stored. The reply comes in from `192.0.2.80 : 80`. No inbound rule in sg-web allows that address, but the stored row lets it in.

### The Next Problem
Security groups can only allow. P allows port 443 from `0.0.0.0/0`. Suppose the range `203.0.113.0/24` keeps sending bad requests to P. The shop wants to block that one range for the whole of subnet A, without editing every VM's security group. How?

---

## 121. Network ACLs

### What It Is
A **network ACL** is a numbered list of rules attached to a subnet. ACL = access control list. AWS checks it when a packet enters or leaves the subnet. Packets between two VMs in the same subnet are not checked by it.

### Three Differences From a Security Group
* It has **deny** rules as well as allow rules.
* Rules are read from the lowest number up. The first rule that matches decides, and later rules are not read.
* It keeps no connection table, so it is **stateless**. A reply is checked against the rules like any new packet.

### The Shop's Network ACL for Subnet A
Only the browser-to-P part is shown. A full list also needs rows for the NAT gateway and for P's connections to web1–web4.

```text
inbound
  100  all traffic     from 203.0.113.0/24   DENY
  200  TCP 443         from 0.0.0.0/0        ALLOW
  210  TCP 80          from 0.0.0.0/0        ALLOW
  *    all traffic     from 0.0.0.0/0        DENY

outbound
  100  TCP 1024-65535  to 0.0.0.0/0          ALLOW
  *    all traffic     to 0.0.0.0/0          DENY
```

`*` is the last rule. It is always there and cannot be removed.

The browser in section 118 was at `203.0.113.50`, which is inside the blocked range. So the normal customer here is meera, at the example address `198.18.0.25`.

### Three Cases
1. **The bad range connects** (`203.0.113.9 : 50000` to P:443). Rule 100 matches first, so the packet is dropped. Rule 200 is never read.
2. **meera connects** (`198.18.0.25 : 51000` to P:443). Rule 100 does not match, rule 200 does: allowed. Then P's security group sg-p checks it, and allows it too. Both checks must allow a packet.
3. **P replies** (`10.0.1.10 : 443` to `198.18.0.25 : 51000`). The network ACL has no stored connection, so it checks the outbound rules. Port 51000 is the from-port meera's laptop kernel picked when it opened the connection (section 7). Linux picks from 32768-60999 by default, Windows from 49152-65535. That is why outbound rule 100 allows 1024-65535. Without it the reply is dropped, even though sg-p would allow it.

### Order of Checks
For a packet from the internet to P:

```text
internet gateway -> network ACL of subnet A -> security group sg-p -> P's kernel
```

A reply goes through the same checks in reverse order.

### Side by Side
```text
                     security group                    network ACL
attached to          a VM's network card               a subnet
rules                allow only                        allow and deny, numbered, first match decides
connection table     yes (stateful)                    no (stateless), replies need their own rules
default              inbound: nothing allowed          the VPC's default one allows everything
                     outbound: everything allowed      both ways
```

### Why Network ACLs Are Rarely Seen
They are not deprecated. Every VPC has one, and every subnet is linked to one (true as of mid-2026; AWS's current documentation is not checked). What AWS retired in August 2023 was **EC2-Classic**: the older network from before VPCs, where all customers' VMs sat in one shared network and only security groups separated them.

People rarely touch network ACLs because the default one allows all traffic both ways, so a VPC works without anyone opening it. Most shops write all their rules in security groups, and add network ACL rules only for what a security group cannot do, mainly a deny like rule 100 above. Since a network ACL keeps no connection table, every rule also needs a matching reply rule, such as the 1024-65535 range. A wrong reply rule drops traffic with no error message, so people avoid editing them unless they need to.
