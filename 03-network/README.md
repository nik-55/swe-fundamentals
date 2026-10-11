# Networking

## Contents

1. [Part 1: One Cable](#part-1-one-cable) (sections 1 to 6)
2. [Part 2: One Local Network](#part-2-one-local-network) (sections 7 to 10)
3. [Part 3: Many Local Networks](#part-3-many-local-networks) (sections 11 to 17)
4. [Part 4: Programs Talking](#part-4-programs-talking) (sections 18 to 32)
5. [Part 5: Wireless](#part-5-wireless) (sections 33 to 47)
6. [Part 6: The Internet](#part-6-the-internet) (sections 48 to 58)
7. [Part 7: HTTP](#part-7-http) (sections 59 to 64)
8. [Part 8: Proxies and Load Balancers](#part-8-proxies-and-load-balancers) (sections 65 to 70)
9. [Part 9: Pushing Updates to the Browser](#part-9-pushing-updates-to-the-browser) (sections 71 to 77)
10. [Part 10: TLS](#part-10-tls) (sections 78 to 85)
11. [Part 11: Cloud Networking](#part-11-cloud-networking) (sections 86 to 92)

---

# Part 1: One Cable

Two computers joined by one cable: how bits, frames and damage checks work, and how bytes reach a program's memory.

---

## 1. What a Network Is

A program can read and write its own computer's memory and disk, and nothing else. Its processor has no physical path to another computer's memory.

Two computers, A and B, sit on a desk. A has a file that a program on B needs. Without a network, a person copies the file to a USB stick and carries it over. That needs a person every time, and B cannot ask A for anything on its own.

A **network** is two or more computers joined by a physical connection, plus rules both follow, so that a program on A can send bytes and a program on B can receive them. With that, B can ask A for a file, use A's printer, or ask A to do work and send back the result.

## 2. The Cable and What Travels Through It

The connection is a cable with copper wires inside, plugged into a socket on each computer. Behind each socket is a small piece of hardware that turns bytes from memory into electrical signals on the wire, and on the other side turns signals back into bytes.

What travels is voltage (electrical pressure that can be raised or lowered). In the simplest version:

* The sender holds the wire at high voltage for a 1 and low voltage for a 0, each for a fixed short time, for example one billionth of a second. That fixed time is a **time slot**.
* The receiver measures the voltage once per time slot and writes down a 1 or a 0.
* Both must agree on the time slot in advance, or the receiver measures at the wrong moments and reads wrong bits.

Real cables use more complicated signal patterns, but the idea is the same: the sender changes the wire, the receiver measures it.

The wire always carries some voltage, even when A has nothing to send. So B needs a way to know where a message starts and ends.

## 3. Where a Message Starts and Ends

**The start.** Before every message, A sends a fixed pattern agreed in advance, for example `10101010` seven times, then `10101011`. B ignores the wire until it sees this pattern. The alternating part lets B line up its measuring moments with A's clock, since the two clocks are never exactly equal. The final `11` marks that the next bit is the first bit of the message.

**The end.** A stops sending and the wire goes quiet. A also leaves a short required gap before the next message, so two messages never run together.

The block of bits between the start pattern and the quiet gap is a **frame**: one message as it travels on the wire.

## 4. Detecting Damaged Frames

Electrical noise from nearby cables or motors can change the voltage, so a 1 sent by A can be measured as a 0 by B.

A adds a few bytes to the end of every frame, calculated from the rest of the frame. B runs the same calculation and compares. Simple version: the message is 5, 10 and 20, and A puts their sum, 35, at the end. If noise changes 10 into 11, B gets 36, the results differ, and B knows the frame is damaged.

Plain addition misses damage that adds 1 to one byte and subtracts 1 from another. Real hardware uses **CRC** (cyclic redundancy check), a calculation on the bits designed so that common damage almost never gives the same result. On a cable it is 4 bytes at the end of every frame.

B throws a damaged frame away. It does not tell A and does not ask for it again. Getting it resent is TCP's job (section 22).

## 5. Both Sides Sending at Once

If A and B change the voltage of one wire at the same moment, the signals mix and both frames are destroyed. This is a **collision**.

**Old fix: take turns.** Listen before sending, and send only if the wire is quiet. While sending, keep measuring; if the voltage is not what you are sending, someone else is sending too, so stop. Wait a random time and try again, so one side usually starts first next time. Only one side sending at a time is **half duplex**.

**Modern fix: separate wires.** A normal cable has 8 copper wires in 4 pairs. In the simplest case, one pair carries signals only from A to B and another only from B to A, so both can send at once without mixing. This is **full duplex**. Faster cables use all four pairs both ways at once, with electronics that subtract their own outgoing signal from what they measure. Either way, a direct modern cable has no collisions.

## 6. From the Hardware to the Program

This uses the kernel, system calls and file descriptors from area 1.

1. **The hardware writes the frame into memory.** At startup the kernel reserves an area of RAM for incoming frames and tells the hardware where it is. A frame that passes the CRC check is written straight into that RAM without the processor copying it. This is **DMA** (direct memory access).
2. **The hardware tells the processor** with an electrical signal called an **interrupt**. The processor pauses and runs a kernel function from the **driver**, the part of the kernel written for this exact hardware. The driver knows where the frame is and how long it is.
3. **The kernel finds the receiving program.** A program that wants incoming bytes asks the kernel for a **socket**: a kernel object with its own receive buffer, reached through a file descriptor, the same way `open()` gives one for a file. The kernel copies the frame's bytes into that buffer. How it picks the right socket when several programs receive bytes is section 19.
4. **The program reads the bytes** with `read()` or `recv()`, a system call that copies them from the receive buffer into the program's memory. If the buffer is empty, the program blocks (waits) until a frame arrives, the same blocking measured in area 2.

```text
wire -> hardware -> RAM (DMA) -> interrupt -> driver -> socket receive buffer -> recv() -> program memory
```

Sending is the reverse: `send()` copies the bytes into kernel memory, the driver tells the hardware where they are, and the hardware turns them into voltage.

---

# Part 2: One Local Network

More than two computers: MAC addresses, the switch, and finding a MAC address with ARP.

---

## 7. Three Computers

A cable between every pair does not scale: 50 computers would need 49 sockets each and 1,225 cables. Instead every computer gets one cable to a box in the middle. The simplest box, a **hub**, copies whatever comes in on one socket out of every other socket.

Now A's frame for B also reaches C, and nothing in the frame says which computer it is for.

**MAC address.** When the hardware behind a socket is made, the factory stores a unique 6-byte number in it, written like `3c:52:82:1a:4f:e0`. The first 3 bytes identify the manufacturer, assigned by a standards body. The manufacturer picks the last 3 so none of its products repeat. This is the **MAC address** (media access control address). It identifies a piece of hardware, not a program or a person.

```text
[start pattern][to: 6 bytes][from: 6 bytes][message][CRC]
```

The hardware reads the 6 "to" bytes and compares them with its own MAC. If they match, the frame goes to RAM and the kernel. If not, the hardware drops it right there, without interrupting the processor. The "from" address tells B where to reply.

The hub still sends every frame out of every socket. That wastes cable time, and all computers share one signal path through the hub, so collisions come back.

## 8. The Switch

**Read, look up, decide.** Every machine that handles frames does three things: read a few bytes from the frame's **header** (the fixed bytes at the start of a frame that describe it), look them up in a table, and make one decision: send it out a particular wire, hand it to a program, rewrite it, or drop it. For each machine below, the useful questions are: which bytes does it read, what table does it use, what does it decide, and why does that table exist.

A **switch** learns where each computer is from the "from" address of every frame. Its table is `MAC address -> socket`, empty at power on. A is on socket 1, B on 2, C on 3:

1. **A sends to B.** The switch adds `A -> 1`. It has no row for B, so it copies the frame out of every other socket. This is **flooding**. C receives it and drops it.
2. **B replies to A.** The switch adds `B -> 2`, finds `A -> 1`, and sends the frame out of socket 1 only. C never sees it.
3. From now on, A and B's frames go only between sockets 1 and 2. When C sends anything, the switch adds `C -> 3`.

A row is deleted after about 5 minutes with no frames from that MAC, so a computer that moves to another socket is learned again from its next frame.

Each switch socket has its own path and every cable is full duplex, so A -> B and C -> A can happen at the same moment. Collisions go away.

**One frame at a time on each cable.** If A and C both send to B at once, the switch cannot put both on B's cable: at any instant a wire has one voltage. It holds one frame in memory, its **queue**, and sends it right after the other. Several conversations on one computer work the same way: a browser and a chat program are both in progress, but their frames take turns on the cable. A 1500-byte frame takes about 0.012 milliseconds at 1 Gbit/s, so the turns are short and all conversations seem to move together. This is area 2's concurrency without parallelism.

If A and C each send at the full 1 Gbit/s, together they push 2 Gbit/s into B's 1 Gbit/s cable. The queue fills, and the switch drops new frames. The senders' kernels notice, resend and slow down (sections 22 and 24).

## 9. Finding a MAC Address

A's program only knows it wants "computer B". It does not know the 6-byte number in B's hardware, and that number changes when B's hardware is replaced.

**IP address.** Whoever sets up the network gives each computer a number, stored in its kernel settings: A `192.168.1.1`, B `192.168.1.2`, C `192.168.1.3`. This is an **IP address** (Internet Protocol address): 4 bytes, written as four numbers from 0 to 255. People choose it, so it stays the same when hardware is replaced. The bigger reason IP addresses exist is in section 11.

**ARP.** A's kernel keeps a table `IP address -> MAC address`. B is not in it yet, so A asks:

1. A sends a frame to `ff:ff:ff:ff:ff:ff`, a special MAC meaning "everyone". All hardware accepts it and every switch floods it. This is a **broadcast**: "Who has 192.168.1.2? Reply to 192.168.1.1 at MAC `aa:aa:...`."
2. C sees it is not its IP and ignores it.
3. B saves A's IP and MAC, since it needs them to reply, and answers A's MAC only: "192.168.1.2 is at MAC `bb:bb:...`."
4. A adds `192.168.1.2 -> bb:bb:...` and can now fill in "to" in its real frame.

Rows expire after a few minutes without use, so replaced hardware is picked up automatically. `ip neigh` shows the table.

These rules are **ARP** (Address Resolution Protocol). A **protocol** is a set of rules two computers agree on: the format of each message and what to do when one arrives. Section 18 comes back to the word.

## 10. Switches Cabled in a Circle

An extra cable between switches gives a backup path if one cable breaks:

```text
   switch 1
   /      \
switch 2 -- switch 3
```

**What goes wrong.** A switch floods a broadcast out of every socket except the one it came in on. A's ARP broadcast goes from switch 1 to 2 and 3, they flood it to each other, then back to 1, which floods it again. Copies circle in both directions forever. The MAC group has no counter that would stop them, and switches never read anything else. Each new broadcast adds more copies, and within seconds the cables are full. MAC tables also break, because a switch sees A's MAC arriving on different sockets from one moment to the next. This is a **broadcast storm**.

**The fix.** Switches send each other small messages and agree on one center, the switch with the lowest ID number. Each keeps only its shortest path toward the center and turns off forwarding on any socket that would close a circle:

```text
   switch 1  (center)
   /      \
switch 2 xx switch 3     (xx = turned off)
```

Now there is exactly one path between any two switches. The switch 2 to switch 3 cable stays plugged in but carries nothing. If the switch 1 to switch 2 cable breaks, the missing messages are noticed and the extra socket is turned back on. This protocol is **STP** (Spanning Tree Protocol). "Tree" means a layout with no circles.

---

# Part 3: Many Local Networks

Joining local networks with routers: IP addresses, routing tables, TTL, and how a computer gets its settings.

---

## 11. Computers in Another Building

A second building has its own switch and computers D, E and F. Joining the two switches works for a few hundred computers, but every switch would need a row for every computer, and every ARP broadcast would reach every computer. At world scale that is impossible. The groups have to stay separate, with something between them that forwards frames but not broadcasts.

**Group the addresses.** Building 1 uses `192.168.1.x` (A .1, B .2, C .3), building 2 uses `192.168.2.x` (D .4, E .5, F .6). A group of computers that reach each other through switches alone and receive each other's broadcasts is a **local network**. Each gets its own address **prefix**, the shared first part of the address.

**The router.** A **router** is a computer with one socket cabled to each building's switch. Each socket has its own MAC and its own IP, for example `192.168.1.254` on the building 1 side.

**A's decision.** A's kernel settings say: "my local network is everything starting with 192.168.1", and "send anything else to 192.168.1.254". That router address is the **default gateway**. To B, same prefix: ARP for B's MAC and send directly. To D, different prefix: send to the router.

**Two addresses, two jobs.** For the frame to D, A writes the router's MAC in "to MAC", because the router takes it next, and D's IP in "to IP", because D is the final destination:

```text
[start][to MAC][from MAC][from IP][to IP][message][CRC]
```

A MAC address says which machine on this cable takes the frame next, and only means something inside one local network. An IP address says where the frame should end up, and means something everywhere.

**What the router does:**

1. Its building 1 socket accepts the frame, because "to MAC" is its own.
2. It looks up "to IP" `192.168.2.4` in its table: `192.168.1.x -> socket 1`, `192.168.2.x -> socket 2`.
3. It finds D's MAC with ARP on building 2's side. The router can do this because its socket 2 is cabled to building 2's switch, so it is a member of building 2's local network, one local network per socket.
4. It builds a new frame: "from MAC" its own socket 2 MAC, "to MAC" D's MAC, the IP part and message unchanged, a new CRC.

D's kernel sees its own IP in "to IP" and gives the message to the program it is for (section 19).

The switches never read IP and never do ARP. The rule: whoever puts a frame on a cable writes "to MAC" for the next machine on that local network. In building 1 that is A, writing the router's MAC. In building 2 it is the router, writing D's MAC.

**The router's two tables.** The **routing table** (prefix -> socket) answers "which socket does this frame go out of?", with one row per local network. The **ARP table** (IP -> MAC) answers "what goes in 'to MAC' for the last step?", and holds only recently used computers on networks the router is cabled to.

This is why IP addresses exist: building 2 could have 200 computers and the routing table still needs one row for all of them. Routers further away need only that prefix row and never store D's MAC (section 12).

## 12. Networks Not Cabled to the Router

Building 3 (`192.168.3.x`, with G at `192.168.3.7`) is cabled to a second router, R2. R2 is cabled to R1 by a short cable that is a tiny local network of its own: R1's end is `10.0.0.1`, R2's end `10.0.0.2`.

```text
building 1 --- R1 --- R2 --- building 3
               |
          building 2
```

R1 gets a new kind of row:

```text
prefix          send to                 out of
192.168.1.x     directly                socket 1    (ARP for the destination's MAC)
192.168.2.x     directly                socket 2
192.168.3.x     next router 10.0.0.2    socket 3    (ARP for the next router's MAC)
```

A frame from A to G:

```text
step         from MAC              to MAC     from IP   to IP
A -> R1      A                     R1 (s1)    A         G      A: not my prefix, send to the default gateway
R1 -> R2     R1 (socket 3)         R2         A         G      R1: row says next router 10.0.0.2
R2 -> G      R2 (building 3 side)  G          A         G      R2: 192.168.3.x is directly on one of its sockets
```

The MAC pair is rewritten at every step, and both IP addresses stay the same the whole way, so G knows the frame came from A. Each router only decides the next step. None knows the whole path.

**The default route.** A router cannot list every network in the world, so its table can have one row that matches any address, written `0.0.0.0/0`: "if nothing else matches, send to this next router". A's default gateway is this same row in A's own table. A computer runs the same lookup as a router, usually with two rows (`192.168.1.x directly`, `everything else -> 192.168.1.254`). `ip route` shows them. When several rows match, the most specific wins: `192.168.3.7` matches both `192.168.3.x` and "everything else", and the `192.168.3.x` row is used.

**Where rows come from.** On small networks a person types them. On large ones, routers send each other messages like "I can reach 192.168.3.x, send it through me" and build their tables from them. Between companies on the internet this is done with BGP (Border Gateway Protocol), not covered here.

## 13. Loops and the Hop Counter

A router does not remember frames it has seen and does not know the full path. Say someone types R2's row for `192.168.3.x` as "next router R1" instead of "directly". R1's correct row says "next router R2". A frame for G then goes R1 -> R2 -> R1 -> R2 forever. Every new frame for building 3 joins the loop, the cable and queues fill, and frames for every other destination start being dropped too.

**The fix: TTL.** The IP part of the header carries a small number. Every router subtracts 1 before forwarding and throws the frame away when it reaches 0. Starting at 3, the looping frame dies on its third router. The field is **TTL** (time to live). It was meant as seconds, but every router subtracts 1, so it counts router steps, called **hops**. TTL does not fix the wrong row. It only makes a looping frame disappear until someone fixes it.

There is no single cable from a laptop to a server in another country, so frames always cross many routers: laptop -> home router -> provider's routers -> ... -> the server's router -> server. Linux starts TTL at 64. A frame to another country might pass about 15 routers and arrive with 49 left. Only a looping frame reaches 0. 64 is more than any real path needs and small enough that a loop ends quickly. TTL also means a frame cannot stay in transit forever, which TCP relies on when it closes a connection (section 26).

**ICMP.** A router that throws a frame away at TTL 0 sends a short message back to the sender: "I threw away your frame because its count ran out". Without it the sender would only see that no reply came. **ICMP** (Internet Control Message Protocol) is the format for short status and error messages like this one. `ping` also uses it.

## 14. How the Header Parts Fit Together

The frame carries the same fields as before, grouped by who reads them. A's program sends `hi` to B:

```text
1. program gives the kernel:      hi
2. the IP code puts in front:     [from IP 192.168.1.1, to IP 192.168.1.2, TTL 64] hi
3. the hardware adds:             [to MAC bb.., from MAC aa.., type 0x0800] [from IP .., to IP .., TTL 64] hi [CRC]
```

B's kernel reads left to right and removes one group at a time until only `hi` is left. Putting one group inside another is **encapsulation**. Each group is a **layer**. Part 4 adds one more group between the IP group and `hi`, the one that says which program gets the bytes (section 19).

**"What is inside" fields.** After removing the MAC group, the next bytes are just bytes: they could be an IP group, or an ARP message, which has a different layout. So each group carries a field naming the next group. The MAC group's **type** says `0x0800` for an IP group or `0x0806` for ARP. The IP group's **protocol** field does the same job for what comes after it (values in section 21). B reads type `0x0800` and passes the rest to the IP code, which checks that "to IP" is B's own and passes the rest on.

**Who reads which group.** A switch reads only the MAC group. A router removes the MAC group, reads the IP group, subtracts 1 from TTL, and adds a new MAC group. It never reads past the IP group. Only the two end computers read what comes after it.

## 15. Switches, Routers and Why Both Addresses

**Two jobs.** A switch joins computers inside one local network: it reads 6 bytes and uses a table it fills by itself, so it needs no setup and is cheap per socket. A router joins different local networks: it reads the IP group, uses prefixes, lowers TTL, rewrites the MAC group and does not forward broadcasts, so it needs settings and does more work per frame. A large building has many switches and a few routers. A data center rack usually has a 48-socket switch on top joining its servers, with a few cables up to routers.

**The home box** called a "router" is several devices in one case: a router, whose own socket (often labeled WAN) goes to the internet provider, and a switch, the sockets usually labeled LAN, where computers reach each other without the router part reading IP. It also hands out addresses (section 16) and does NAT (section 50).

**Why MAC when IP exists.** A switch could map IP addresses to sockets instead. Three reasons it does not:

1. **The frame needs a "next machine" field separate from the final destination.** From A to G (section 12), "to IP" is G the whole way, but on building 1's switch the frame must go to R1, and G is not even on that switch.
2. **A computer must send frames before it has an IP address.** A new laptop asks for one by sending a frame (section 16), and needs an address that already exists: the MAC from the factory. ARP messages also have no IP group at all.
3. **The cable layer was designed to carry more than IP.** In the 1970s and 80s several protocols shared the same cables, which is what the type field is for. Hardware drops frames for other computers by comparing 6 bytes at a fixed position, without understanding any protocol.

**Why IP inside one local network.** With only one local network, MAC alone would do. IP is needed because of routers, but programs always use IP, near or far. A program calls `sock.connect(("192.168.1.2", 7000))` (7000 is a port, section 19) and never handles a MAC. The kernel looks up the routing table (local, or the default gateway), finds that machine's MAC in its ARP table or with an ARP broadcast, and writes it in "to MAC".

## 16. Getting an IP Address Automatically

A computer needs three settings: its IP address (`192.168.1.23`), its local network (everything starting with `192.168.1`) and its default gateway (`192.168.1.254`). They live in the kernel. A person can set them with commands, which are lost on reboot:

```bash
sudo ip addr add 192.168.1.5/24 dev eth0         # address and local network prefix on the cable socket eth0
sudo ip route add default via 192.168.1.254      # the "everything else" row: the default gateway
```

or in a settings screen that a program turns into the same commands at startup (Ubuntu: Settings -> Network -> IPv4 -> Manual). `ip addr` and `ip route` show the result. Typing is slow and error-prone: two computers with the same IP get each other's frames, and a laptop would need new settings in every place.

**Ask everyone.** Same trick as ARP. One machine on the local network, at home the home box, hands out settings and keeps a list so it never gives an address twice. It is a **DHCP server** (Dynamic Host Configuration Protocol). The laptop knows only its own MAC:

1. **Laptop -> everyone** (broadcast): "My MAC is `aa:aa:...`. I need settings."
2. **Server -> that MAC**: "Use 192.168.1.23. Your local network is 192.168.1. Your gateway is 192.168.1.254."

The real protocol has two more messages, "I am taking this one" and "confirmed", because a network can have several DHCP servers and the laptop must say whose offer it took. The messages use UDP (section 21).

**The lease.** The address is loaned for a set time, for example 24 hours. Halfway through, the laptop asks to keep it, sending only that request straight to the server. If the laptop leaves, the lease runs out and the address can go to someone else. A laptop rejoining a network usually asks for its previous address and gets it back if it is free. The messages run when the cable is plugged in or Wi-Fi connects (NetworkManager sends the first one on Ubuntu), at boot, and at renewal, and finish in well under a second.

**Where the DHCP server sits.** On the same local network, because the first message is a broadcast and routers do not forward broadcasts. Its own address is typed by hand, since it cannot ask anyone. Addresses typed by hand are **static addresses**. Machines others must find at a known address (routers, DHCP servers, printers, servers) usually get them.

## 17. What /24 Means

An IP address is 4 bytes, 32 bits. `/24` means "the first 24 bits are the local network part", which is the first 3 bytes. So `192.168.1.0/24` is every address starting with `192.168.1`: `192.168.1.0` to `192.168.1.255`, 256 addresses. `.0` names the local network itself and `.255` means "every computer on this local network", so 254 are usable.

```text
/24   first 3 bytes fixed    256 addresses
/16   first 2 bytes fixed    65,536 addresses
/8    first 1 byte fixed     about 16.7 million addresses
/26   first 26 bits fixed    64 addresses, e.g. 192.168.1.0 to 192.168.1.63
```

The number does not have to fall on a byte boundary. That is how one block is split into smaller local networks. "Subnet" (subnetwork) means one local network, especially one made by such a split.

The kernel compares only the first N bits of an address with a row. A laptop's table as `ip route` prints it:

```text
default via 192.168.1.254 dev eth0
192.168.1.0/24 dev eth0
```

The second line is the "directly" row. `default` is `0.0.0.0/0`: zero bits must match, so every address matches. When several rows match, the larger number after the slash wins, because it is more specific.

A **subnet mask** writes the same information as a 4-byte number with 1s in the network part: `/24` is `255.255.255.0`. The kernel keeps an address's bits where the mask has 1s and zeroes the rest: `192.168.1.23` gives `192.168.1.0`, which is the local network, while `192.168.2.4` gives `192.168.2.0`, which is not, so it goes to the default gateway.

---

# Part 4: Programs Talking

Getting bytes to the right program and getting them there whole: ports, UDP, TCP, frame sizes, ICMP and layers.

---

## 18. What a Protocol Is

Parts 1 to 3 get a frame to the right computer. This part gets the bytes to the right program, and gets them there whole.

When A sends a cable frame to B, both sides agreed in advance on the order of the fields (start pattern, to MAC, from MAC, type, ..., CRC), the size of each (a MAC is 6 bytes, the CRC 4), and what each side does (the receiver drops a frame whose CRC does not match; a computer answers ARP only for its own IP). If B expected the to-MAC 2 bytes later than where A put it, B would read the wrong 6 bytes and drop every frame. The bytes mean something only because both follow the same written rules.

A **protocol** is a written set of rules: which bytes go where, what each means, and what each side does in reply. The cable frame rules, ARP, and the IP group (from IP, to IP and TTL, each in a fixed place) are three protocols.

## 19. Which Program Gets the Bytes

The kernel receives every frame first, and needs a number in the frame that says which program the bytes are for. The process ID cannot be it: a program gets a new one every time it starts, and the sender cannot see the receiver's process IDs.

**Ports.** A fixed number is agreed instead. A program asks its kernel "give me every frame for number 7000" (the system call is `bind()`), and the kernel writes that in a table. The number is a **port**: 2 bytes, so 0 to 65535. Two programs cannot have the same port, or the kernel could not choose.

```text
B's kernel:   port 7000 -> chat program      port 6600 -> music program

A's frame:    [MAC group][IP group: to 192.168.1.24][from port 50001, to port 7000]["hi"]
```

B's kernel reads "to port" 7000 and gives "hi" to the chat program. If no program asked for that port, no program gets the bytes. What the kernel sends back then is in sections 21 (UDP) and 26 (TCP).

"From port" tells B where to reply: `[to A][from port 7000, to port 50001]["hello"]`. A's program did not choose 50001. The kernel picked an unused one. Ports picked like this are **ephemeral ports** (temporary ports). Linux picks them from 32768 to 60999, about 28,000 numbers. The receiving side's port must be known in advance, so programs agree on fixed numbers: web servers use 80, name servers 53 (section 53).

## 20. Where Frames Get Dropped

On a cable network a frame is lost in two places, and in neither case is the sender told:

```text
where              why                                                   how often
the cable          noise flips bits, the CRC fails, the chip drops it    rare on a good cable
                   (section 4)
a router's line    frames arrive faster than the outgoing cable can      the most common cause
                   send; the line fills, new frames are dropped
```

Wireless adds a third place, in the air (section 39).

`send("hi")` returns as soon as the kernel copies the bytes into its own memory for that connection, the **send buffer**. It waits only when that buffer is full, never for B. If a router drops the frame later, neither the kernel nor the program hears about it.

The router sends no "slow down" message. The drop is the only signal: the ack never comes back, and the sender's kernel then slows down (section 24). Many computers share one router and none knows about the others, so the line fills before any of them slows down. UDP has no such rule. The kernel sends as fast as the program gives it bytes.

## 21. UDP

With only ports, a lost frame stays lost: nothing on a cable acks it, the router tells nobody, and B cannot miss a frame it never heard of. The small group from section 19 is a real protocol with exactly this behaviour. Its group is always 8 bytes, between the IP group and the data:

```text
[MAC group][IP group, protocol 17][ UDP group, 8 bytes ]["hi"][CRC]
                                    from port   2 bytes
                                    to port     2 bytes
                                    length      2 bytes   (this group plus the data)
                                    checksum    2 bytes   (computed from the bytes, like the CRC)
```

The IP group's **protocol** field (section 14) says what comes after it, the way the MAC group's type field does: 17 for UDP, 6 for TCP (section 22 on), 1 for ICMP (section 29).

The sender's kernel fills in both ports, the length (8 + 2 = 10 for "hi") and the checksum. The receiver's kernel recomputes the checksum and drops the frame if it differs, then gives the data to the program on "to port". If no program has that port, it drops the frame and sends back an ICMP "port unreachable" message (section 29), limited to a few per second by Linux. That is the whole protocol: no waiting for a reply, no resending, no numbering. Routers pass the UDP group along unread.

A program picks UDP when it starts, and from then on its kernel adds this group to everything it sends. **UDP** = User Datagram Protocol. A **datagram** is one piece of data sent in one frame, on its own.

**The bytes for "hi"**, in hex (base 16, two hex digits per byte):

```text
from port 50001   C3 51       C3 51 = 195 × 256 + 81 = 50001
to port   7000    1B 58       1B 58 =  27 × 256 + 88 = 7000
length    10      00 0A
checksum          e.g. 4F 2E
data      "hi"    68 69       'h' is 68, 'i' is 69
```

Two bytes make one number: the first counts 256s, the second counts ones, the way "42" has 4 tens and 2 ones. The largest is `FF FF` = 65535, which is why ports stop there. The 256s byte goes first in every network protocol, called **network byte order**. A laptop's processor stores the ones byte first, so the kernel swaps the two bytes when it writes a port.

**Why a length field.** A cable frame must be at least 64 bytes, so a frame with only "hi" gets zero bytes added before the CRC. The length tells B the data is 10 − 8 = 2 bytes, so the zeros are ignored. The IP group has a length too, so this is partly a second copy, kept so the UDP group can be checked on its own.

**When UDP is enough.** Name lookups (DNS, section 53): the question fits in one frame, and the program asks again if no answer comes within about 1 second. Voice calls: each frame carries about 20 ms of sound, and a resent one would arrive too late to play, so skipping it (a short click) is better.

## 22. Numbering the Bytes

A sends a 1 MB photo to B. With UDP, lost frames go unnoticed. To keep numbers simple, say each frame carries 1000 bytes (really 1460, section 28), so the photo needs 1000 frames.

* **Rule 1:** A writes in every frame the position of its first byte in the photo: 0, 1000, 2000, ... This is the **sequence number**. B can see which positions are still empty.
* **Rule 2:** B replies with the next position it wants. "Ack 1000" means "I have everything before 1000, send 1000 next". This is the **ack number**.
* **Rule 3:** A keeps a copy of each frame until an ack covers it. If none does within a set time, for example 200 ms, A sends the copy again.

```text
A sends          B has                  B replies
0      ->        0-999                  ack 1000
1000   -> lost
2000   ->        0-999, 2000-2999       ack 1000   (still missing 1000-1999)
... 200 ms pass, no ack covers frame 1000 ...
1000   ->        0-2999                 ack 3000
```

B holds 2000–2999 and gives it to its program only after 1000–1999 arrives, so the program always gets bytes in order with no gaps.

**The ack can be lost too.** Then A resends a frame B already has. The number tells B these positions are filled, so B drops the copy and acks again. So the number does two jobs: it puts bytes back in order and lets B drop copies.

**Why the ack says "everything before".** One number covering everything before it is a **cumulative ack**. A lost "ack 2000" does not matter once "ack 3000" arrives. And repeated acks tell A something is missing: B answers every frame after the gap with "ack 1000" again, and after 3 repeats A resends the missing frame at once instead of waiting 200 ms. This is **fast retransmit**. B can also report the pieces it holds after the gap, so A resends only what is missing. TCP supports this as an option (section 27) called **selective ack**.

This ack comes from B's kernel across every router, so a drop anywhere means no ack, and A resends. These are the first rules of **TCP** (Transmission Control Protocol), which has its own group where the UDP group would be.

## 23. Sending Without Waiting

A and B are in different cities: a frame takes 25 ms to arrive and the ack 25 ms to come back. Waiting for each ack costs 50 ms per frame, so 1000 frames take 50 seconds, and the cable sits idle most of that time.

**Rule 4: many frames before any ack.** Say A may have 10 unacked frames out. It sends 10, and each returning ack frees a place that A fills at once. Each 50 ms trip now moves 10 frames: 5 seconds in total, or 0.5 seconds with 100 allowed. Rule 3 still applies to every frame.

**Rule 5: every ack says how much room is left.** B's kernel holds bytes until B's program reads them. If the program reads slowly, that memory fills, so every ack also carries B's free room:

```text
ack 5000, room 8000 bytes   -> A may have at most 8000 unacked bytes out
ack 6000, room 0 bytes      -> A stops until B reports room again
```

The number of unacked bytes A may have out is the **window**, and B's room number is the **window field** in the TCP group. Each ack moves the allowed range forward, so it is also called a **sliding window**. When the room is 0, A sends a tiny frame every so often to ask "is there room now?". The receiver controlling the sender's speed this way is **flow control**. While A cannot send, bytes stay in A's send buffer (section 20), and once it is full, `send()` waits. A slow `read()` on B makes `send()` on A wait.

## 24. What the Path Can Take

B's room says nothing about the routers on the way. B may report room for 1,000,000 bytes while a router's line holds only 200 frames (section 20). Routers answer no questions about their lines. All A can see is whether acks come back.

**Rule 6: A keeps a second limit of its own** and sends no more than the smaller of this limit and B's room. Start at 10 frames (Linux's default), double it whenever a whole trip's frames are acked, and on a loss cut it in half and then add 1 frame per trip:

```text
trip    1    2    3    4    5     6                  7          8     9    ...
limit   10   20   40   80   160   320 (line full,    160 (cut,  161   162  slowly up, halves at the next loss
                                  frames dropped)    resend)
```

So A's limit stays near what the path can take, down when it is busy, back up when it is quiet. Ten computers sharing the router each see their own drops and lower their own limit. None knows about the others, but together they bring the line back under 200.

A full router line that drops frames is **congestion**. A's own limit is the **congestion window**. The doubling at the start is **slow start**: it grows fast, but starts at 10 frames instead of full speed. The whole mechanism is **congestion control**, separate from the room number, which only protects B's memory. Linux uses a variant called CUBIC, which cuts to about 70% and grows back faster.

A new connection starts at 10 frames and works its way up, so a short one sending a few hundred KB may finish before reaching full speed. This is one reason programs reuse one connection for many requests.

## 25. Starting a Connection

Before any data, B's kernel must set aside memory for the new conversation (next byte expected, room, space for out-of-order frames) and learn where A's numbers begin.

**Random start.** A frame from a conversation a minute ago with the same ports could still arrive late. If every conversation started at 0, B would take those old bytes as new. So each side picks a random starting number. The sequence field is 4 bytes, 0 to about 4.3 billion, so an old frame almost never fits the new range. Both sides pick one, because B's bytes need numbers too.

**Rule 7: three frames before any data.** The TCP group has single-bit fields called flags (section 27). **SYN** (synchronize) means "this is my starting number". **ACK** means "read the ack number in this frame".

```text
1. A -> B:  SYN,       seq 4000                "my numbers start at 4000"
2. B -> A:  SYN + ACK, seq 9000, ack 4001      "got yours; mine start at 9000"
3. A -> B:  ACK,       ack 9001                "got yours"
```

Frame 3 tells B that A received B's starting number. Each frame also carries its sender's room. This exchange is the **handshake**.

**What takes a number.** Each side keeps a counter, and the seq field shows its value when the frame is sent. Only things that must be acked and resent if lost take a number: each data byte, the SYN, and the FIN (section 26). So A's SYN shows 4000, the plain ACK after it shows 4001 and takes nothing, and "hi" shows 4001 with h = 4001, i = 4002. A plain ACK is never acked itself, or the ack of the ack would need an ack forever. A lost ACK is covered by the next one. With the random start, photo byte 0 from section 22 is really number 4001.

**What the programs do.** The kernels do the handshake. B's program calls `bind()` on port 7000, then `listen()` (accept handshakes on this port), then `accept()`, which waits. A's program calls `connect()`, its kernel sends the SYN, and `connect()` waits for the SYN + ACK. When frame 3 reaches B, `accept()` returns a new file descriptor for this connection, so B's program has one per connection plus the listening one. If no program on B called `listen()` on that port, B's kernel answers the SYN with the **RST** (reset) flag, meaning "nothing here", and `connect()` fails with `Connection refused`. UDP answers the same case with ICMP "port unreachable".

**Four values.** A and C can pick the same port 50001, since each kernel picks its own. So B's kernel keeps each connection under four values, from the IP and TCP groups:

```text
A's IP : A's port      B's IP : B's port
192.168.1.23 : 50001   192.168.1.24 : 7000    -> next byte expected, room, held frames
192.168.1.25 : 50001   192.168.1.24 : 7000    -> a different connection
```

A conversation set up like this is a **connection**. Each line of `ss -tan` is one such row. The 28,000 ephemeral ports (section 19) are a limit per destination, because the "to" values differ for other servers.

After the handshake nothing on the wire has changed. A connection is a record in each kernel's memory (the four values, both sequence numbers, the latest room, the send and receive buffers), and the handshake makes the two records start out in agreement.

## 26. Ending a Connection

When A is done, B may still have bytes to send, so each side ends its own direction.

**Rule 8: FIN.** A frame with the **FIN** (finish) flag means "I have no more bytes to send". It takes one number, so it is acked and resent like data. After the photo (bytes 4001 to 1,004,000) and B's "ok" (9001 to 9002):

```text
1. A -> B:  FIN, seq 1004001      A's program called close(): "I'm done sending"
2. B -> A:  ACK 1004002
            ... B could still send bytes here ...
3. B -> A:  FIN, seq 9003         B's program called close(): "I'm done too"
4. A -> B:  ACK 9004
```

If B has nothing more to send, its kernel often puts frames 2 and 3 together (FIN + ACK), so the close takes three frames.

**How B's program learns A is done.** It reads in a loop. `read()` returns whatever bytes have arrived, or waits if none have, so it normally never returns 0 bytes. Once the FIN has arrived and every byte before it has been read, the next `read()` returns 0 at once. That empty result is the only sign the program gets. It never sees the FIN frame.

**`shutdown()` vs `close()`.** `shutdown(fd, SHUT_WR)` sends FIN and closes only A's sending direction, so A can still read B's bytes. `close(fd)` also sends FIN but gives up the file descriptor, so A cannot read anymore, and if B sends bytes after that, A's kernel answers with RST. The FIN on the wire is the same in both cases.

**CLOSE_WAIT and TIME_WAIT** are two values of a field in each kernel's record that says which stage the connection is at:

```text
step  frame             A's record      B's record
1     A -> B  FIN       (waiting)
2     B -> A  ACK                       CLOSE_WAIT
3     B -> A  FIN                       (waiting)
4     A -> B  ACK       TIME_WAIT       deleted
      60 seconds later  deleted
```

* **CLOSE_WAIT (on B):** A's direction is closed and B's kernel waits for B's program to call `close()`. It cannot send B's FIN by itself, since the program might still have bytes to send. A program that forgets to close piles up CLOSE_WAIT records and runs out of file descriptors, a common bug in real servers.
* **TIME_WAIT (on A):** both are finished, but the side that sent the first FIN keeps the record 60 seconds on Linux.

**Why TIME_WAIT exists.** First, frame 4 can be lost. B then resends its FIN, and if A had deleted its record, its kernel would answer RST and B would see an error although all bytes arrived. Second, old frames must disappear. Say connection 1 (A port 50000 to B port 7000) has a frame with seq 3000 delayed in a router. A resends it and the connection finishes. Connection 2 starts at once with the same four values and a random start of 2500. The delayed seq 3000 arrives, fits what B expects, and B's program gets old bytes in the new connection. While A's record is in TIME_WAIT, A will not reuse those four values, so the late copy finds no connection and is thrown away. TIME_WAIT assumes a frame cannot be in transit longer than some maximum, which TTL enforces (section 13). It is twice that maximum, rounded on Linux to 60 seconds.

**If an old frame does get in.** If its number is outside the range B expects, B throws it away. If it is inside, B accepts it: the CRC passes because the frame is not damaged, the four values match, and the program gets wrong bytes with no error. Linux also puts a timestamp from the sender's clock, which only goes up, in each frame's TCP options, and B drops frames older than the latest one. This almost never happens, because everything must be true at once: delayed over 60 seconds when routers hold frames for milliseconds, same four values out of 28,000 ports and never reused in TIME_WAIT, a sequence number inside B's range (about 1 in 65,000 for a 64 KB range), and a passing timestamp.

Programs that need correct data also add their own checks. **TLS** (the encryption used by HTTPS, Part 10) checks every block with a key made fresh for each connection, so a frame from another connection fails and the connection ends with an error. Downloads and package installs compare a hash of the whole file, for example SHA-256, with a known value. Databases checksum their pages and log records. These also catch damage TCP misses: the CRC protects a frame only on the cable, a router with faulty memory can damage bytes after checking them, and TCP's 16-bit checksum is weak (section 27). Lower layers make errors rare, and a program that cannot accept any checks the data itself, end to end.

**Cost of TIME_WAIT.** Each record holds its four values for 60 seconds. A program that opens and closes thousands of short connections to one server can use up all 28,000 ephemeral ports, and then `connect()` fails. One more reason to reuse connections.

**RST: the fast ending.** One frame, no ack, no wait. A kernel that sends or receives RST deletes the connection at once and throws away bytes not yet sent or read. The other program gets an error ("connection reset") instead of the empty read. RST is sent when a frame arrives for a connection that does not exist, for example after its record was deleted (section 51 shows a case), and when a program closes while unread bytes are still in its kernel, so the other side knows not everything was taken. A program that exits normally without unread bytes gets a normal FIN, sent by the kernel.

## 27. The TCP Group

It sits where the UDP group was, and is at least 20 bytes:

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

```text
field            size       what it holds                                                       rule
from/to port     2+2 bytes  sender's and receiver's port                                        ports
sequence number  4 bytes    number of this frame's first data byte, or of the SYN/FIN itself    1, 7, 8
ack number       4 bytes    the next number expected from the other side                        2
len              4 bits     length of the TCP group itself, in 4-byte units                     -
rsv              4 bits     reserved, 0                                                         -
flags            8 bits     eight yes/no bits                                                   7, 8
window           2 bytes    room: how many more bytes this frame's sender can accept           5
checksum         2 bytes    damage check over the TCP group, the data, and both IPs             check
urgent pointer   2 bytes    almost never used, 0                                                -
options          0-40 bytes extra settings, mostly in SYN frames                                -
```

**len** counts only the TCP group: 5 means 20 bytes, 6 means 24 (one 4-byte option), 15 the maximum, 60. Options vary in size, so the receiver needs len to find the data. TCP has no data length field: the receiver computes it from the IP group's total length minus both groups. UDP is the reverse, a fixed 8-byte group with a length that covers group plus data.

**Flags** are 8 bits in 1 byte, one yes/no answer each:

```text
bit:      CWR ECE URG ACK PSH RST SYN FIN
SYN:       0   0   0   0   0   0   1   0      = 02
SYN+ACK:   0   0   0   1   0   0   1   0      = 12
```

SYN, FIN and RST are from sections 25 and 26. **ACK** is set on every frame after the first SYN. The ack number's 4 bytes are always present, but in the first SYN there is nothing to ack, so they are 0 and the ACK bit 0 says "ignore them". **PSH** (push) means "give the data to the program now", and Linux sets it on the last frame of each send call. **URG** marks the urgent pointer valid and is almost never used. **ECE** and **CWR** are for routers that mark a frame to signal congestion instead of dropping it, the one exception to "routers only drop". It needs both ends and the routers to support it, and Linux does not ask for it on its own outgoing connections.

**Options** are written as 1 byte kind, 1 byte length, then the value. **MSS** (kind 2, length 4) says "send me at most this many data bytes per frame" (section 28). **Window scale** fixes a limit of the 2-byte window field: at most 65535, which with a 50 ms round trip allows only about 1.3 MB per second on any cable. With this option in its SYN a side says "multiply every window I send by 128" (or another power of 2), so a window field of 8000 means 1,024,000 bytes. A real Linux SYN carries a few more options, not covered here.

**Checksum vs CRC.** The chip adds the MAC group and the CRC, and the CRC covers one trip from one chip to the next. A router checks it, removes it, changes the TTL, and computes a new one. The checksum is written once by A's kernel and checked only by B's kernel. Both are needed because inside a router the frame sits in memory with no CRC. If a memory fault damages a byte there, the router computes a new CRC over the damaged bytes, and only the end-to-end checksum catches it.

The congestion window, the copies kept for resending and the timers are not fields. They exist only in the sender's kernel memory.

## 28. How Big a Frame Can Be

The **MTU** (maximum transmission unit) is the most bytes a frame can carry after the MAC group: IP group + TCP or UDP group + data. On a cable it is 1500, and the kernel stores one MTU number per chip. It is a size rule, not a speed. Reasons for a limit: hardware and switches reserve fixed-size memory slots for frames; while one frame is on a cable everything else for that cable waits, so a 10 MB frame would block everyone; and one damaged bit throws the whole frame away, which costs far less at 1500 bytes than at 10 MB.

The whole cable frame is MAC group 14 + up to 1500 + CRC 4 = up to 1518 bytes. 1500 is a default. Data centers often set 9000 (**jumbo frames**), which works only if every chip and switch on that local network accepts it, since a switch set to 1500 drops larger frames. Some providers add 8 bytes of their own on the cable to the house, so its MTU is 1492. Every machine on one local network must use the same value.

The **MSS** (maximum segment size) is the most data bytes per frame: 1500 − 20 (IP) − 20 (TCP) = 1460. Each side writes its own MSS in its SYN, and both use the smaller. A 10 MB `send()` becomes about 7,200 frames.

**A smaller MTU on the path.** Say the provider's cable is 1492: `laptop --1500-- [home box] --1492-- company router -- ... -- S`. Two things handle this automatically, which is why nobody normally sets an MTU by hand:

1. **The box rewrites the MSS in the SYN.** It knows its own provider cable is 1492, so it changes the MSS option in passing SYNs, both ways, from 1460 to 1452 (1492 − 40).
2. **A router reports "too big".** For a smaller cable further away, Linux sets a "do not split" bit in the IP group of TCP frames. A router that gets a frame too big for its next cable drops it and sends an ICMP message (section 29) back: "too big, the most I can take is 1492". The sender's kernel remembers 1492 for that destination, makes smaller frames and resends the lost data. This is **path MTU discovery**.

Without the "do not split" bit, IP lets the router split the frame and the receiver joins the pieces. Linux avoids that for TCP, because losing one piece loses the whole frame.

## 29. ICMP

**ICMP** (Internet Control Message Protocol) is the protocol routers and kernels use to send short messages about delivery problems back to a frame's sender, like the TTL message in section 13. Its group sits right after the IP group (protocol 1), and it has no ports: the message is for the sender's kernel, not a program.

```text
type        1 byte    what kind of message
code        1 byte    more detail within that type
checksum    2 bytes   damage check
extra       4 bytes   depends on the type
copy        the IP group and the next 8 bytes from the frame that caused the problem
```

The copied 8 bytes hold the from and to ports, so the sender's kernel knows which connection the message is about.

```text
type  code   meaning                    when
11    0      TTL reached 0              section 13
3     4      too big, cannot split      path MTU (section 28); "extra" holds the allowed size
3     3      no program on that port    a UDP frame for a port nobody asked for (section 21)
8     0      echo request               sent by `ping`
0     0      echo reply                 the other kernel's answer
```

`ping` checks whether a machine is reachable without any program listening: the other computer's kernel itself answers type 8 with type 0.

## 30. A Full TCP Conversation, Every Field

Two buildings on cable, as in section 11. A sends "hi", D answers "ok", both close. ARP tables are already filled, and the starting numbers are A = 4000, D = 9000.

```text
A  192.168.1.1   MAC aa:aa:aa:aa:aa:aa   port 50001
R  socket 1: 192.168.1.254  MAC 11:11:11:11:11:11      socket 2: 192.168.2.254  MAC 22:22:22:22:22:22
D  192.168.2.4   MAC dd:dd:dd:dd:dd:dd   port 7000 (a program on D is listening)

A --cable-- switch 1 --cable-- R --cable-- switch 2 --cable-- D
```

**Frame 1, the SYN, on building 1's cable**, after the start pattern. MAC group: to `11:11:..` (R socket 1), from `aa:aa:..` (A), type `0x0800`. TCP group: ports 50001 -> 7000, seq 4000, ack 0 (ignored, ACK bit 0), len 6 (24 bytes), flags SYN only, window 64240, MSS option 1460. Then 2 zero bytes of padding, because 14 + 20 + 24 + 4 = 62 is under the 64-byte minimum (D ignores them, since the IP total length says 44), and the CRC.

The IP group, all 20 bytes:

```text
field                   size     value               meaning
version                 4 bits   4                   IP version 4: 4-byte addresses
header length           4 bits   5                   5 × 4 = 20 bytes
service                 1 byte   0                   priority marks; 0 = normal
total length            2 bytes  44                  IP group + TCP group + data: 20 + 24 + 0
identification          2 bytes  7238                a number for this frame, used only if a router splits it
flags + split position  2 bytes  "do not split" = 1  section 28; position is used only when split
TTL                     1 byte   64                  section 13
protocol                1 byte   6                   a TCP group comes next
header checksum         2 bytes  computed            damage check on these 20 bytes only
from IP                 4 bytes  192.168.1.1         the original sender
to IP                   4 bytes  192.168.2.4         the final destination
```

**After R**, on building 2's cable, exactly five things have changed: to MAC (now D), from MAC (now R socket 2), TTL (63), the IP header checksum (recomputed because TTL changed) and the CRC. Everything else, including the whole TCP group, is the same. Every frame crosses R this way.

**All 9 frames.** Fixed in every frame: type 0x0800, version 4, header length 5, service 0, "do not split", protocol 6, urgent pointer 0. The identification changes per frame, and checksums and CRC are computed per frame.

```text
#  direction  IP total  seq    ack    len  flags     window  data
1  A -> D     44        4000   0      6    SYN       64240   none (MSS option)
2  D -> A     44        9000   4001   6    SYN, ACK  64240   none (MSS option)
3  A -> D     40        4001   9001   5    ACK       64240   none
4  A -> D     42        4001   9001   5    ACK, PSH  64240   "hi"
5  D -> A     42        9001   4003   5    ACK, PSH  64240   "ok"
6  A -> D     40        4003   9003   5    ACK       64240   none
7  A -> D     40        4003   9003   5    FIN, ACK  64240   none
8  D -> A     40        9003   4004   5    FIN, ACK  64240   none
9  A -> D     40        4004   9004   5    ACK       64240   none
```

* **len 6, then 5:** only the SYNs carry the 4-byte MSS option, since the sides agree on it once.
* **Frames 3 and 4 both show seq 4001:** the plain ACK takes no number. "hi" is then 4001 and 4002.
* **Frame 5, ack 4003:** D got 4001 and 4002, and sends "ok" in the same frame as the ack.
* **Frames 6 and 7 both show 4003:** frame 7's FIN takes 4003, so D acks 4004. D's FIN takes 9003, so A acks 9004.
* **IP total length** is 20 + 20 or 24 + data, for example 42 = 20 + 20 + 2.
* **After frame 9**, A keeps the four values for 60 seconds in TIME_WAIT.

## 31. Layers and IP

A frame now has four groups: MAC, IP, TCP or UDP, and data, each added for a different problem. They stay separate because each machine reads only its own part: a switch reads 6 bytes (section 14), a router reads the IP group and never the TCP group. With one big set of rules, every switch and router would have to understand all of it. Each group can also be replaced on its own:

* **Cable vs air:** Part 5 replaces the cable with radio waves, and only the MAC group changes (section 45).
* **TCP vs UDP:** routers forward both the same way. Only the protocol field changes.
* **A new kind of program** puts its own data in, and no switch, router or kernel changes.

Inside the kernel too, the TCP code hands its group to the IP code, the IP code to the driver, and none reads the others' fields.

**Numbers.** Each group is a **layer** (section 14), and the layers are numbered, as in "L4 load balancer":

```text
number  name           what is in the frame            examples
1       physical       voltage on the cable            cable signals (Part 5: radio waves)
2       data link      MAC group + CRC                 cable frame, ARP
3       network        IP group                        IP, ICMP
4       transport      TCP or UDP group                TCP, UDP
7       application    the program's data              DNS questions, HTTP
```

"L4" means "reads up to the TCP or UDP group", "L7" means "also reads the program's data". The numbers come from OSI, an older 7-layer design whose protocols are almost unused today, but whose numbering was kept. TCP/IP has no separate group for layer 5 (session: starting, pausing and resuming a conversation) or 6 (presentation: data format, such as text encoding or encryption). Programs handle both in their own data, so on a real frame they are part of layer 7.

Two do not fit neatly. ARP has no IP group and never passes a router, so it is layer 2. ICMP sits where TCP or UDP would, but it reports IP problems and has no ports, so it counts as layer 3.

**IP as a protocol.** An IP address is one field. **IP** (Internet Protocol) is the whole set of rules, the 20-byte layout above plus what each machine does:

* **Sender's kernel:** fills in both IPs, sets TTL to 64 and the protocol number, and looks up "to IP" in its routing table: send directly or to the default gateway.
* **Each router:** checks the header checksum and drops the frame if it does not match. It lowers TTL, and at 0 drops the frame and sends ICMP "TTL reached 0" back. It picks a socket from its routing table. If the frame is too big for that socket and "do not split" is set, it drops it and sends ICMP "too big". Otherwise it computes a new header checksum and sends the frame out.
* **Receiver's kernel:** checks that "to IP" is its own, and passes the rest to the TCP, UDP or ICMP code by protocol number.

IP does not ack, resend, keep order or slow down. A router that cannot deliver drops the frame. That is why TCP runs on top of it. This is IP version 4, with 4-byte addresses. Version 6, with longer addresses, is not covered here.

## 32. Where One Message Ends

A's program calls `send("hi")` and then `send("there")`. TCP numbers bytes, not sends, so D's kernel keeps one buffer of bytes in order with nothing between them. If both frames arrive while D's program is busy, one `read(1024)` returns "hithere". It can also go the other way: if "there" arrived split across two frames, one `read()` might return "the" and the next "re". The sending side keeps no boundaries either: if the bytes do not all fit in the send buffer, `send()` waits or returns early with how many it took, and the program must call it again with the rest (Python's `sendall()` repeats the call itself).

So the two programs need their own rule, in the data at layer 7, for where a message ends. This is roadmap experiment 2, "No message boundaries". Three common ways:

1. **Length first.** `00 02 h i 00 05 t h e r e`: D reads 2 bytes (2), then exactly 2 more ("hi"), then 2 bytes (5), then 5 more ("there"). D keeps calling `read()` until each count is reached, so split arrivals do not matter.
2. **A special end byte**, such as newline `0A`: `h i 0A t h e r e 0A`. D reads until `0A`. A message cannot contain `0A` itself without an extra rule.
3. **One message per connection.** A sends "hi" and FIN, and D reads until `read()` returns 0. The simplest, but every message costs a handshake and a close.

A program's own rules, for how messages are marked and what their bytes mean, are an **application protocol**: the layer 7 part. DNS (section 57) and HTTP (section 59) are two, built later.

---

# Part 5: Wireless

The same frames carried by radio waves instead of a cable, up to the access point and the home box.

---

## 33. Radio Waves and Channels

Two laptops, A and B, in one room, no cable, no encryption. A's program sends `hi` to B's program, as in section 14.

Each laptop has a **wireless chip**, hardware like the one behind the cable socket, connected to a short piece of metal called an **antenna**. To send, the chip pushes an electric current back and forth along A's antenna very fast. A current that keeps changing direction produces a **radio wave**: changing electric and magnetic force that spreads from the antenna in every direction at the speed of light, without needing air. When the wave reaches B's antenna, it creates a very small current there, swinging at the same rate, and B's chip measures it.

```text
cable:     A's chip -> voltage on copper -> B's chip
wireless:  A's chip -> current in A's antenna -> wave through the room -> small current in B's antenna -> B's chip
```

**Frequency** is how many times per second the current swings. Laptop chips use about 2.4 or 5 billion swings per second, written **2.4 GHz** and **5 GHz** (gigahertz). Like an FM radio set to 98.3, a chip set to one frequency measures only waves at that frequency, and others do not disturb it. The usable frequencies are divided into numbered **channels**:

```text
2.4 GHz group:   channel 1 = 2.412   channel 6 = 2.437   channel 11 = 2.462   (billion per second)
5 GHz group:     channel 36 = 5.180  channel 40 = 5.200  channel 44 = 5.220
```

A and B must be set to the same channel to hear each other. Choosing the same channel replaces plugging in a cable. Below, both use channel 36.

## 34. Putting Bits on the Wave, and Noise

As on the cable (section 2), A sends one value per time slot and B measures once per slot. On the cable each slot had two choices, high or low voltage. Each choice is a **level**. On wireless, the wave's swings can be made one of several agreed sizes per slot: with 2 levels (small = 0, big = 1) a slot carries 1 bit, with 4 sizes (`00`, `01`, `10`, `11`) it carries 2 bits. The slots per second stay the same, so 4 levels carry twice as many bits per second. Real chips vary both the size and the timing of the swings: the slowest setting has 2 combinations (1 bit per slot), the fastest on modern chips 1024 (10 bits per slot).

The **signal** is A's wave as it arrives at B. **Signal strength**, how big its swings are, drops with distance and walls, and A cannot change it. **Noise** is the tiny random electrical activity always present on every frequency. It adds a small random amount to what B measures, the same size whether A is near or far.

**Why far away needs fewer levels.** In made-up units, noise adds or subtracts up to 2:

```text
B far, 4 levels arrive as     0   3   6   9     A sends 6 (10), noise +2 -> B measures 8, closer to 9 -> reads 11: wrong
B far, 2 levels arrive as     0           9     A sends 9 (1), noise -2 -> B measures 7, still near 9 -> reads 1: right
B close, 4 levels arrive as   0  30  60  90     noise +2 -> 62, still clearly 60: right
```

Fewer levels sit further apart, so noise cannot push one near another. Close by, the signal is strong, so more levels and more bits per second work. Far away, fewer levels make a weak signal readable. That is why wireless is slower in a far room. A cable's signal strength stays the same, so it does not have this problem.

## 35. Speed Per Frame, Busy and Quiet

**On a cable**, the speed is agreed once at plug-in: the two pieces of hardware list the speeds they support, for example 100 Mbit/s and 1 Gbit/s, and pick the highest they share (**auto-negotiation**). **In the air**, signal strength changes all the time, when someone walks between the laptops, a door closes or a laptop moves. So A's chip picks the number of levels again for each frame, based on how its recent frames got through. B cannot know that choice in advance, so every frame starts with two parts sent at the slowest setting, which both chips know:

```text
[start pattern][short header: speed + length][rest of the frame at that speed]
 ^--- both sent at the slowest setting ---^
```

The start pattern does the same job as on the cable. From the **short header**, B's chip learns the setting for the rest of the frame and its length, so it knows when the frame ends.

**Busy and quiet.** Waves are always present, at least as noise, so "is A sending?" cannot mean "is there any wave?". B's chip measures wave strength on channel 36. **Busy** means stronger than a fixed limit built into the chip, or a recognized start pattern, even a weak one. **Quiet** means nothing stronger than noise.

## 36. Finding Each Other

In the air there is no plug. B does not know that A exists or which channel it uses.

About 10 times per second (every 102.4 ms), A's chip sends a short **beacon** frame, whether anyone listens or not: to MAC `ff:ff:ff:ff:ff:ff` (everyone, like the ARP broadcast), from A's MAC (wireless chips have factory MACs too, section 7), a name typed in A's settings such as "a-laptop", and channel 36. The name is the **SSID** (service set identifier), the name shown in a laptop's list of wireless networks.

B tries the channels one at a time, listening about a tenth of a second on each and noting beacons. This is **scanning**, and its result is the list you see when you click the wireless icon. To save time B can also send a short "is anyone here?" frame on each channel. When a person picks "a-laptop", B's chip switches to channel 36 and sends A "I want to join", and A replies "accepted". That replaces plugging in a cable. From then on they send frames to each other's MACs on channel 36.

## 37. The Wireless Frame

A's kernel builds the IP and TCP groups exactly as for the cable (sections 14 and 27). Only the outer group, built by the chip, differs:

```text
cable:     [start pattern][to MAC][from MAC][type 0x0800]                                   [IP group][TCP group] hi [CRC]
wireless:  [start pattern][short header][kind][to MAC][from MAC][hw seq][type 0x0800]      [IP group][TCP group] hi [CRC]
```

**kind** says data, ack, beacon or join request, which the cable did not need because every frame carried data. **hw seq** is a hardware-level sequence number (section 39). The rest is as on the cable. The real frame has a third MAC field, used once a box in the middle is involved (section 43).

## 38. Taking Turns in the Air

The cable had separate wire pairs for each direction (section 5). The air has one channel 36 shared by both laptops. If A and B send at the same moment, the waves add up and each receives a mix: a **collision**. So only one can send at a time, half duplex. And unlike the old shared cable, A cannot notice a collision while sending: its own wave at its own antenna is millions of times stronger than B's, and most chips cannot send and receive on the antenna at the same time. So collisions must be avoided before they happen, and A learns a frame arrived only when B replies.

**The sending rules**, for 5 GHz channels (a **microsecond** is a millionth of a second):

1. **Listen.** If channel 36 is busy, wait until it is quiet.
2. **Fixed wait.** Wait until it has been quiet for 34 microseconds.
3. **Random wait.** Pick a random number from 0 to 15 and count down that many 9-microsecond slots, only while the channel stays quiet. If someone else starts, pause and later continue from where you stopped.
4. **Send** the whole frame at 0. A cannot detect a collision, so it never stops partway.
5. **B checks the CRC.** If it fails, B drops the frame and does nothing else.
6. **B acks.** If it passes, B's chip waits 16 microseconds and sends a short frame with kind = ack and to MAC = A. 16 microseconds is about the shortest time to finish receiving, check the CRC and switch the antenna to sending. The number is fixed in the standard.
7. **No ack.** A assumes the frame was damaged, doubles the random range (0 to 31, then 0 to 63, ...) and goes back to step 1. After a fixed number of tries, often 7, it gives up on the frame.

These rules are **CSMA/CA** (carrier sense multiple access with collision avoidance). "Carrier sense" means listening before sending.

**The waits in order.** A has two frames, B has one of its own. A's frame 1 has just ended:

```text
time (microseconds)       what happens
0                         A's frame 1 ends
16                        B's chip sends the ack (B's own frame must wait 34 + random, so it cannot go first)
ack ends + 34             A (frame 2) and B (own frame) both finish the fixed wait; A picked 3 slots, B picked 11
+ 27 (3 slots)            A reaches 0 and sends frame 2; B has counted 3, sees busy, pauses with 8 left
frame 2 ends + 16         B's chip sends the ack for frame 2
ack ends + 34 + 72        B's 8 remaining slots run out, B sends its own frame; A acks it 16 later
```

* **Ack 16, new data at least 34.** The ack always goes before any new data, so A learns at once that its frame arrived. With equal waits, B's data could go first, A would see no ack and resend a frame B already has.
* **The random part.** A and B finish the fixed 34 at the same moment. Without it they would collide every time. With 3 and 11, A goes first and B holds off.
* **B keeps its leftover 8.** If A has a third frame it picks a new number, say 12, and B's 8 runs out first. The one that has waited longer gets its turn sooner, and neither laptop keeps the channel.
* **Doubling after a failure** makes it less likely the two pick the same number again.

## 39. The Hardware Ack and hw seq

16 microseconds is too short for an interrupt, the driver and the kernel to run. The chip has its own small processor and program, so it builds and sends the ack itself:

```text
                  hardware ack (wireless)         TCP ack (kernel)
built by          B's wireless chip               B's kernel TCP code
covers            one frame, just received        bytes, by sequence number
travels           only from B's antenna to A's    to the other program's computer
sent after        16 microseconds                 usually within milliseconds
```

The hardware ack only means "the frame reached my antenna undamaged". Wireless adds it because collisions and noise are much more common in the air. TCP still runs above it unchanged, because the frame can still be lost later, for example when B's kernel drops it because the socket's receive buffer is full (section 23), or when a router further on drops it. The chip gets its ack as soon as the next antenna has the frame, and moves on:

```text
A ~~air~~ access point -- switch -- router -- ... -- B
  ack here               no acks on any of these
```

**hw seq.** If B's ack is damaged, A resends and B gets the frame twice. B's chip sees the same hw seq as A's last frame, drops the copy and acks again: the same fix as section 22, at chip level, so the kernel rarely sees duplicates.

**Where wireless frames get dropped.** Wireless adds a third place to section 20's two: in the air, after too many tries. When the air is very busy or the signal weak, for example two rooms from the access point, the chip gives up after its tries (section 38, step 7) and adds 1 to a counter of failed frames in the driver. The program is never told. Only TCP's timer on A finds out. An access point also drops frames like a router does when frames from its cable arrive faster than it can send them into the air.

## 40. Others Nearby Can Receive Every Frame

The wave goes in every direction, so any device nearby on channel 36 receives every bit. On a cable, someone would have to plug into the wire.

The bits cannot be hidden, but A and B can change the bytes so they are useless without a secret only the two know. Tiny version with the secret 7: `h i` are bytes 104 105, A adds 7 and sends 111 112, B subtracts 7. Turning bytes into unreadable bytes with a secret is **encryption**, the secret is the **key**, and turning them back is **decryption**. A one-byte key has only 256 values, which a nearby laptop could try. Real wireless chips use a method called **AES** with a 16-byte key, far too many values to try, and it mixes the bytes so patterns do not show.

The MAC group stays readable, because B's chip must read "to MAC" first. A nearby laptop can still see which devices talk, when and how much, but not what they say. These rules are the "WPA2" or "WPA3" setting in a laptop. An "open" network with no password sends the bytes unencrypted.

**Wireless encryption vs TLS.** A cable normally has no encryption (an optional one, MACsec, is used mostly in data centers and large companies).

```text
                      who encrypts           protects
wireless (WPA2/3)     the wireless chip      only the air between two antennas
TLS                   the programs           the whole path, program to program (Part 10)
```

Wireless encryption ends at the receiving antenna, and the frame travels raw on any cable after it. The two are used together.

## 41. Three Laptops on One Channel

Laptop C joins the same way B did (section 36). The air already does a hub's job (section 7): A's wave reaches both B and C, and each chip keeps only frames whose "to MAC" is its own. B keeps `hi` and acks after 16 microseconds. C receives the whole frame, finds a correct CRC, sees the MAC is not its own and drops it without an ack. And now, while A sends to B, the channel is busy for C too. All three share the time on one channel.

**Why nobody can start in the ack gap.** C sees A's frame end, a 16-microsecond gap, then B's ack. C needs 34 microseconds of quiet *in a row* before its random countdown, and B's ack starts at 16, so C's count breaks and starts again from 0 when the ack ends. If C could send after 16, its frame and B's ack would mix at A: A would get no ack and resend (B drops the copy using hw seq), and C would get no ack either.

**Why not one channel per pair.** A chip measures one channel at a time (section 33). If C used channel 40, it would never receive anything A or B send, and switching channels means missing every frame on its own channel. So laptops that need to reach each other share one channel and take turns.

**Two senders pick the same number.** After an ack, A and C both count 34 microseconds and both pick 5 slots, so both reach 0 at 79 and send. The waves mix and both CRCs fail. Neither notices while sending (section 38), so both whole frames are wasted, where the old cable would have stopped early. Both get no ack and double the range: say A picks 12 and C 25. A sends first, and C pauses with 13 left and continues after A's frame, the ack and 34 of quiet. With two laptops this was rare, because B mostly sent acks. With three, two often want the channel at once:

```text
range     chance both pick the same
0 to 15   1 in 16, about 6%
0 to 31   1 in 32, about 3%
0 to 63   1 in 64, about 1.5%
```

## 42. Laptops That Cannot Hear Each Other

A and C are at opposite ends of a long house, with B in the middle, 15 m from each. Both reach B, but at C's antenna A's wave is below the busy limit (section 35), so to C it is noise, and the same the other way. A sends a 200-microsecond frame to B. At 50, C wants to send, hears only quiet, counts 34 and 3 slots, and sends at 111. At B the waves mix, both CRCs fail, no ack, both double their range and retry.

The random wait does not help here. When all three hear each other, A and C collide only if both reach 0 in the same 9-microsecond slot, otherwise the later one sees busy and pauses. Here C never hears A, so it collides whenever it starts anywhere in A's 200 microseconds, about 22 slots. With a range of 0 to 15, almost any pick lands inside A's frame, and every failed try wastes a whole frame. A **node** is any device that sends and receives on a network. This is the **hidden node problem**. Through a hub, every computer heard every frame, so "busy" was the same for all.

**RTS and CTS.** B is the only one that hears both, so B announces how long the channel will be busy. The "kind" field gets two values, **RTS** (request to send, A -> B, "I want to send you a frame", 20 bytes) and **CTS** (clear to send, B -> A, "go ahead", 14 bytes). Every frame also gets a **duration** field after "kind": how many microseconds the channel stays busy after this frame, until the whole exchange ends. A chip that receives a frame not meant for it starts a timer from the duration and treats the channel as busy until it runs out, whatever its antenna measures. At the slowest setting an RTS takes about 52 microseconds, a CTS and an ack about 44:

```text
time (microseconds)   air                          A                  B               C
before 0              quiet                        34 + random slots
0 to 52               A's RTS, duration 336        sends RTS          receives it     hears nothing
68 to 112             B's CTS, duration 276        receives it        sends CTS       receives CTS, timer to 112 + 276 = 388
128 to 328            A's data                     sends hi           receives it     timer says busy
344 to 388            B's ack                      receives it        sends ack       timer says busy
388                   quiet                        done                               timer ends, counts 34 of quiet

RTS duration = 16 + CTS 44 + 16 + data 200 + 16 + ack 44 = 336
CTS duration = 16 + data 200 + 16 + ack 44             = 276
```

C still cannot hear A's RTS, so the RTS itself can collide, but that loses 52 microseconds instead of a 200-microsecond frame. The cost is 52 + 16 + 44 + 16 = 128 extra microseconds per frame, more than a small frame itself, so chips use RTS and CTS only above a frame size set in the chip.

## 43. The Access Point

RTS and CTS stop A and C from talking over each other, but if A wants to send to C, A's wave never reaches C, and laptops do not forward frames for each other.

An **access point** is a small box in the middle whose only job is to be the center of the wireless network. It sends the beacons, every laptop joins it, and every frame goes laptop -> access point -> laptop, even between two laptops side by side. It fixes reach, and it fixes hidden laptops: every laptop hears the access point, so its CTS sets everyone's timer. The cost is that each frame crosses the channel twice.

**Why the air needs a third MAC.** The access point does a switch's job (section 8) and never touches the IP or TCP group. On a cable, A's wire goes only to the switch, so the frame names only the final destination. In the air, A's wave reaches every chip in range, including C if C is close, so the frame must also say which chip takes it now and sends the hardware ack. Only one chip may ack, or the acks would collide. So a wireless frame has three MACs:

```text
receiver      the chip that should take this wave now and send the hardware ack
transmitter   the chip sending this wave now
third MAC     the other end: final destination on the way in, original sender on the way out

                      receiver        transmitter     third MAC
A -> access point     access point    A               C
access point -> C     C               access point    A
```

If C hears the first frame, it sees receiver = access point and drops it.

**A frame through the access point.** The access point keeps a list of joined laptops, filled when it sends "accepted" (unlike a switch, which learns from frames). A knows C's MAC from ARP and the access point's from its beacon. With 200-microsecond data frames and 44-microsecond acks:

```text
time (microseconds)   who sends        what
before 0                               A waits 34 of quiet + random slots
0 to 200              A                frame 1: receiver = access point, third = C
216 to 260            access point     hardware ack to A ("the access point has it", not "C has it")
260 to 348                             access point finds C in its list, waits 34 + 6 slots like any sender
348 to 548            access point     frame 2: receiver = C, transmitter = access point, third = A
564 to 608            C                hardware ack to the access point
```

Then C's kernel takes over as on the cable (section 6). The TCP ack comes back the same way. One `hi` uses about 608 microseconds of channel time, against about 260 sent directly.

**Nobody gives out turns.** The access point never says "A, send now". Each chip, the access point's included, decides by itself from what it measures and its own random number: busy or timer running, wait; quiet for 34, count slots; count at 0, send. With every chip following the same rules, collisions are rare, and a missing ack leads to a retry.

## 44. Two Wireless Networks in One Room

A second access point with its own laptops is in the same room. On **different channels** (36 and 44), neither ever receives the other's waves, so they are fully independent. Many access points scan at startup and pick a quiet channel; others use the channel in their settings.

On the **same channel**, the rules keep working across both, because they depend only on waves: a chip waits for any busy wave whichever network sent it, collisions between the networks are retried the same way, frames for the other network are dropped, and CTS timers apply to everyone. The networks stay independent in what they read, but not in time: one wave at a time, so each gets less channel time. People call this a "congested channel", but it is not section 24's congestion (a full router queue). Its name is **co-channel interference**. The 2.4 GHz group has only three channels that do not overlap (1, 6 and 11). The 5 GHz group has more, but in a building with many networks some must share.

## 45. From the Air to the Cable

The access point also has a cable socket, with computer D plugged in: `A ~~~ air ~~~ [access point] ---- cable ---- D`. It knows air devices from joining, and cable devices from the "from MAC" of arriving frames, like a switch. A knows D's MAC from ARP and does not care that D is on a cable.

```text
air frame:    [receiver: access point][transmitter: A][third: D][type 0x0800][IP group: A -> D][TCP group] hi [CRC]
cable frame:  [to MAC: D][from MAC: A][type 0x0800][IP group: unchanged][TCP group: unchanged] hi [new CRC]
```

The access point acks A, removes the fields that matter only in the air (kind, duration, hw seq, the receiver/transmitter split), keeps the two end MACs, copies everything else and computes a new CRC. D's reply goes the opposite way. A device that joins two kinds of network at the MAC level, rebuilding the MAC part but never touching the IP group, is a **bridge**.

In layer terms (section 31), wireless replaces only layers 1 and 2: waves instead of voltage, and a different MAC group. The IP and TCP groups are byte for byte the same, so TCP never knows part of the path was wireless. The frame size stays too: the air allows 2304 bytes after the MAC group, but cable frames carry at most 1500 (section 28), so wireless networks use an MTU of 1500 as well.

## 46. The Home Box, With Wireless

Most home boxes also have an access point inside, connected to the switch:

```text
                     [ home box ]
 internet line ---- router
                      |
 cable sockets 1-4 -- switch ---- access point ~~~ air ~~~ laptops
```

The router and switch do their jobs from section 15. So a laptop in the air and a computer on cable socket 2 are on the same local network, and a frame between them goes laptop -> access point -> switch -> socket 2 without a router reading it.

## 47. Local Networks Joined Over Wireless

A router reads only the IP group, so it does not care whether a local network is wireless. Section 11 again, with an access point plugged into each building's switch:

```text
A, B, C ~~~ air ~~~ [AP1] -- switch 1 --(s1) R (s2)-- switch 2 -- [AP2] ~~~ air ~~~ D, E, F
192.168.1.x                                                                         192.168.2.x
```

A (`192.168.1.1`) sends `hi` to D (`192.168.2.4`). D is not on A's prefix, so A sends to its default gateway `192.168.1.254` and finds R(s1) with ARP. That broadcast reaches everyone in building 1 through AP1, but R does not forward it.

```text
step                       where           next machine      sender on this step   third MAC   IP group
1. A -> AP1                air, bldg 1     receiver = AP1    transmitter = A       R(s1)       A -> D, TTL 64
2. AP1 -> switch 1 -> R    cable, bldg 1   to = R(s1)        from = A              none        A -> D, TTL 64
3. R -> switch 2 -> AP2    cable, bldg 2   to = D            from = R(s2)          none        A -> D, TTL 63
4. AP2 -> D                air, bldg 2     receiver = D      transmitter = AP2     R(s2)       A -> D, TTL 63
```

AP1 acks A and rebuilds the frame as a cable frame. R does exactly what it did in section 11. AP2 finds D in its joined list, rebuilds an air frame, and D acks AP2. In step 4, the third MAC is R(s2), not A, because a MAC only has meaning inside one local network, and in building 2 the frame came from the router. A's IP is still in the IP group. Both buildings can use channel 36: they are far apart and walls weaken the wave, so each hears the other only as noise. R never learns that A or D is wireless.

---

# Part 6: The Internet

Houses in different cities: internet providers, public and private addresses, NAT, and DNS.

---

## 48. Houses in Different Cities

Your house is one local network, and a friend's house in another city is another. In section 11 one router joined two buildings because both were cabled to it. Between cities there is no cable, and you cannot lay one yourself.

Companies lay cables under streets and between cities, and put routers where cables meet. Each house gets one cable from the company's nearest router and pays every month. This company is an **internet provider**.

The cable plugs into the home box (sections 15 and 46), into one socket separate from the others that belongs to the router part. It is usually labeled **WAN** (wide area network: the company's cables, covering a large area). The other sockets are labeled **LAN** (local area network: your own).

```text
laptops ~~~ [access point] -- switch -- (LAN side) router (WAN side) ---- company's router
             your home local network                       one cable, like R1-R2 in section 12

home router's table:   192.168.1.x -> directly (your home)      everything else -> the company's router
```

A router needs one socket per local network it joins, or it has nothing to choose between. The home router has two: one inside the box to the switch, and the WAN socket. The LAN sockets are switch sockets. If the company's cable went into a switch socket, the company's router would become part of your local network: your ARP broadcasts would reach the company, and frames would never pass through your router.

Every house and office does this, and the companies' routers are cabled to each other across cities and countries. The **internet** is all these local networks (homes, offices, and the computers that run websites) joined by routers that many companies own. No single company owns it. Nothing new happens to a frame there: it is sections 11 to 13 repeated across many routers.

## 49. Two Houses With the Same Addresses

S runs a website at `198.51.100.7`. Home boxes come from the factory set up the same way, so laptop A in house 1 and laptop X in house 2 can both be `192.168.1.23`:

```text
house 1:  laptop A 192.168.1.23 -- [home box H1] --\
                                                    [company router P] -- ... -- S 198.51.100.7
house 2:  laptop X 192.168.1.23 -- [home box H2] --/
```

A's frame reaches S, since routers read only "to IP". But S's reply to `192.168.1.23` cannot be delivered: P would need `192.168.1.x` pointing to two different cables.

**Why houses reuse addresses.** 4 bytes give about 4.3 billion addresses, fewer than the world's phones, laptops and servers. So three ranges were set aside for use only inside a local network: `10.0.0.0/8`, `172.16.0.0/12` and `192.168.0.0/16`. Any house or office may reuse them, and routers between companies have no rows for them. Every other address belongs to exactly one machine, handed out in ranges to companies by organizations that track who has which.

* **Private address:** from the three reused ranges. It means something only inside one local network.
* **Public address:** belongs to one machine in the world, so routers anywhere can have a row leading to it. `198.51.100.7` is public.

**What each house gets.** The provider owns ranges of public addresses. The home box asks for one over the WAN cable (or a person types one the company gave), and it is set on the WAN socket only: H1 gets `203.0.113.10`, H2 `203.0.113.20`. Now P's rows are unique. Other companies' routers send `203.0.113.x` toward this provider because it tells them so, with the automatic messages from section 12. Typing an address yourself does not work: an address works only if routers have rows leading to your cable, and only the company sets those. A made-up address gets no replies, or sends them to whoever really owns it.

**Example addresses.** Three small ranges, `192.0.2.0/24`, `198.51.100.0/24` and `203.0.113.0/24`, are never given to any company. They exist for books and tutorials, so readers who copy an example do not send frames to someone's real machine. These notes use them for that reason.

## 50. NAT

S replies to the "from IP" it sees, so A's private address cannot be it, and A, B and C share the house's one public address. The home box changes the frame on the way out.

**Going out.** A (`192.168.1.23 : 50001`) sends to S (`198.51.100.7 : 80`). The box picks an unused port of its own, say 40001, writes a row in a table, replaces "from IP" with its public address and "from port" with 40001, and the router part sends the frame out of the WAN socket as usual:

```text
before:  from 192.168.1.23 : 50001   to 198.51.100.7 : 80
after:   from 203.0.113.10 : 40001   to 198.51.100.7 : 80
```

**Coming back.** S replies to `203.0.113.10 : 40001`, which routers can reach. The box finds row 40001 and changes "to" back to `192.168.1.23 : 50001`. S never sees A's private address.

**Two laptops, same port.** B (`192.168.1.24`) also picks 50001 by chance, since each kernel picks its own (section 19). The box gives B another outside port:

```text
inside IP : port        outside port    other end
192.168.1.23 : 50001    40001           198.51.100.7 : 80     (A)
192.168.1.24 : 50001    40002           198.51.100.7 : 80     (B)
```

S sees two connections that differ by port (section 25). If the box changed only the IP, both replies would come to `203.0.113.10 : 50001` and the box could not tell them apart, which is why the port changes too.

Changing addresses and ports at the box is **NAT** (network address translation). It is the one exception to "a router never reads past the IP group" (section 14). The box deletes each row a short time after the connection ends. NAT is needed only because several devices share one public address. In section 11 every computer had its own address, so nothing was rewritten.

**Where NAT sits.** It is a step in the router part, at its WAN side, not a separate chip. Most home boxes are small computers running Linux, and the NAT table lives in that kernel's memory next to the router's rows:

```text
going out:  1. router part reads to-IP 198.51.100.7, decides: WAN socket
            2. NAT changes from 192.168.1.23 : 50001 to 203.0.113.10 : 40001, writes the row
coming in:  1. frame arrives for 203.0.113.10 : 40001
            2. NAT finds row 40001, changes "to" to 192.168.1.23 : 50001
            3. router part reads the new to-IP, decides: LAN side
```

Coming in, NAT must run first: before the change, the to-IP is the box's own address and the router part would not know which laptop it is for.

## 51. Frames Nobody Inside Asked For

A frame arriving for a port with no row, say `203.0.113.10 : 40050`, belongs to no connection started inside, so the box has no inside address for it and drops it. Laptops inside can start connections with anyone, because a row is made on the way out. Nobody outside can start one with a laptop inside: their first frame, the SYN (section 25), finds no row.

**Port forwarding.** A runs a program on port 7000 and a friend in another city wants to connect. The fix is a row typed into the box's settings by hand, `outside port 7000 -> 192.168.1.23 : 7000`, never deleted automatically. The friend connects to `203.0.113.10 : 7000`, the box changes the to-IP and sends it to A, and replies go out through the same row. This is the only way an unasked frame gets through the box.

**After a connection closes**, its row still exists for a while, so S could still send a frame that reaches the laptop. Three things limit this:

1. **Only S can use the row.** Most boxes, including Linux-based ones, forward only frames whose "from" is exactly the row's other end, `198.51.100.7 : 80`. Some boxes do not check this.
2. **The row does not last.** The box sees the FINs pass (section 26) and deletes the row a short time later, about 2 minutes on Linux-based boxes.
3. **The laptop's kernel rejects it.** Port 50001 was picked for `connect()`, nobody called `listen()` on it, and the connection is closed, so the kernel answers RST (section 25) and no program sees the frame.

**Who can reach whom.** A laptop can start a connection to any machine routers can reach where a program is listening. A server in a data center: yes, it is set up for that. A friend's laptop in another city: only if the friend's box has a port forwarding row (your own box makes its NAT row automatically). A friend's laptop in the same house: yes, directly at its private address, because the frame goes laptop -> access point -> switch -> laptop (section 46) and never passes the router part or NAT. The other direction always works: anyone you connect to can reply.

## 52. One Laptop in Two Networks

A laptop with two wireless chips, or with a cable and Wi-Fi at once, can be in two local networks, like R in section 11. Each chip has its own MAC and gets its own address.

**Different ranges, no conflict.** Home Wi-Fi gives `192.168.0.23`, office Wi-Fi `192.168.1.40`, and the routing table gets a row per network:

```text
192.168.0.x       directly, out of chip 1
192.168.1.x       directly, out of chip 2
everything else   next router 192.168.0.1 out of chip 1, priority 600
everything else   next router 192.168.1.1 out of chip 2, priority 601
```

The two "everything else" rows match the same addresses, so each has a priority number, the **metric**, and the lower wins. All outside traffic goes out of chip 1, and chip 2 is used only for `192.168.1.x`. On Ubuntu, NetworkManager sets the metric by connection type (a cable gets a lower number than Wi-Fi, so it wins), and it can be changed in the connection's settings.

**Same range, conflict.** If both networks use `192.168.0.x`, two rows match the same prefix and the metric always picks one. A printer at `192.168.0.50` is reachable only on the winning network. Nothing breaks completely, but that whole range goes to one of the two networks. Being in both networks also does not make the laptop pass frames between them. Linux has that switched off by default.

## 53. Names Instead of Numbers

People remember words, not `198.51.100.7`, and the address changes if the website moves to another data center. So people type `www.bluepizza.com` and the computer finds the current address.

**A file on every computer.** The first fix was a text file with one line per name, `198.51.100.7    www.bluepizza.com`. Linux still has it, at `/etc/hosts`. When the network was a few hundred computers in the 1970s and early 80s, one organization kept the master file and every computer downloaded copies. It stops working at scale: hundreds of millions of names would make a huge file of mostly unused lines, every change would need fresh copies everywhere, and every change would go through one organization.

**Asking a name server.** Instead, a computer asks for only the name it needs. Say one computer, N at `198.51.100.53`, holds the whole list, and a program on it listens on port 53, agreed in advance like port 80 for web servers (section 19). N's address is one of A's settings, like the default gateway:

```text
question:  [IP: A -> 198.51.100.53][UDP: from port 50123 to port 53]  "what is the address of www.bluepizza.com?"
answer:    [IP: 198.51.100.53 -> A][UDP: from port 53 to port 50123]  "www.bluepizza.com is 198.51.100.7"
```

Then A's program calls `connect(("198.51.100.7", 80))`. A computer that answers name questions is a **name server**. It uses UDP (section 21) because the question and answer each fit in one frame. TCP would need a handshake and FINs to carry two small frames. If no answer comes within about 1 second, A asks again.

One name server is not enough, for the same reasons as the single file: billions of questions a day for one machine, every change going through whoever runs it, and if it is off, no name works anywhere.

## 54. Splitting the Names

The list is split by the parts of the name, read from right to left. Each level of name servers knows only who handles the next part. A pizza shop owns `bluepizza.com`. Its website computer `www.bluepizza.com` is at `198.51.100.7`. It rents a name server from DNSHost, `ns1.dnshost.net` at `203.0.113.53`. One of the com servers is at `192.0.2.10`.

```text
root server:                      com                ->  ask the com server at 192.0.2.10
com server (192.0.2.10):          bluepizza.com      ->  ask ns1.dnshost.net at 203.0.113.53
ns1.dnshost.net (203.0.113.53):   www.bluepizza.com  ->  198.51.100.7
```

Looking up `www.bluepizza.com` takes three UDP questions to port 53: the root says "for com, ask 192.0.2.10", the com server says "for bluepizza.com, ask ns1.dnshost.net at 203.0.113.53", and that server answers `198.51.100.7`. The 13 root server addresses are a fixed list built into name server programs, the file idea again for 13 lines.

This fixes all three problems. Root servers answer only about the last part, and com servers only about `.com` names. The shop edits its own lines on its own name server, and the company that sold it the name added the `bluepizza.com -> ask ns1.dnshost.net` line to the com servers once. Each level has several servers, so one being off stops nothing.

A name with everything under it, like `bluepizza.com`, is a **domain**. This whole split system is **DNS** (Domain Name System).

## 55. The Resolver and Its Memory

Three questions before every connection, from every computer, would flood the root and com servers. So the laptop holds one name server address in its settings, given by the home box along with the others (section 16), and asks it one question. That server might be the home box passing questions on, the provider's, or a large shared one like Google's `8.8.8.8` or Cloudflare's `1.1.1.1`. A different one can be typed into the laptop's network settings. It holds the 13 root addresses, asks root, com and bluepizza's server itself, and sends back the final answer. A name server that does the asking for others is a **resolver**.

The resolver keeps every answer in memory, not only the final one:

```text
remembered:  com -> ask 192.0.2.10      bluepizza.com -> ask 203.0.113.53      www.bluepizza.com -> 198.51.100.7

later question                         what the resolver does                       questions sent
another laptop: www.bluepizza.com      answers from memory                          0
someone: mail.bluepizza.com            skips root and com, asks 203.0.113.53        1
someone: other.com                     skips root, asks the com server              2
```

A resolver used by thousands of laptops rarely asks the root servers. The laptop and browser also keep short-term copies, so repeated connections often send no question at all.

Each answer carries a number of seconds set by the name's owner, for example 300, after which the resolver deletes it and asks again. This is also called **TTL**, a different field from the IP group's hop counter (section 13). A long TTL, say 1 day, means few questions, but after an address change resolvers keep giving the old one until their copy expires. A short TTL, say 60 seconds, spreads a change within a minute but brings more questions.

## 56. Kinds of Records

One line in a name server's list is a **record**: name, type, value and TTL. The type says what the value means:

```text
name                 type     value                     TTL      meaning
www.bluepizza.com    A        198.51.100.7              300      this is the address
bluepizza.com        NS       ns1.dnshost.net           86400    ask that server about this domain
bluepizza.com        NS       ns2.dnshost.net           86400    a second one, in case one is off
www.bluepizza.com    CNAME    bluepizza.hostco.net      3600     look up that name instead
```

**NS** (name server) records are the "ask this server" lines on the root and com servers. Their value is a name, but the resolver needs an IP to send to, so the com servers also send the name server's address in the same answer (`ns1.dnshost.net A 203.0.113.53`). The root servers do the same for each com server.

**CNAME** (canonical name, "the real name") says "this name is another name for that one". Say the shop rents its website computer from a hosting company, `hostco.net`, which moves customers between machines. With an A record the shop would edit it at every move. With the CNAME, hostco keeps the A record for `bluepizza.hostco.net` current, and the shop never edits anything. The resolver gets the CNAME, looks up `bluepizza.hostco.net`, answers the laptop with that address, and remembers both records, each for its own TTL.

**How many steps.** Each "ask this other server" is one step, and three is the common case with nothing in memory. A university that gives its computer science department its own name server makes `www.cs.someuni.edu` four steps. A CNAME starts a new lookup, up to three more steps. An NS answer that gives only a server's name, without its address, needs that name looked up first.

## 57. A DNS Message, Byte by Byte

A DNS question or answer fits in one UDP datagram. The DNS message is the data after the UDP group, with its own 12-byte header inside the data:

```text
[MAC group][IP group: from 192.168.1.23, to 192.168.1.254, protocol 17][UDP group: 50123 -> 53][DNS message][CRC]
```

**The question from A to the resolver:**

```text
header (12 bytes)
  ID              3A 7F    a random number; the answer carries the same one
  flags           01 00    "this is a question; please do the asking for me"
  questions       00 01    1 question follows
  answers, name servers, extra records    00 00 each
question
  name     03 77 77 77                       3, "www"
           09 62 6C 75 65 70 69 7A 7A 61     9, "bluepizza"
           03 63 6F 6D                       3, "com"
           00                                0 = end of name
  type     00 01    A (1 = A, 2 = NS, 5 = CNAME)
  class    00 01    always 1 in practice
```

The name has no dots: each part is one length byte and its letters, and a 0 byte ends it. That is method 1 from section 32, inside the name.

**The answer from the resolver:**

```text
header
  ID              3A 7F    same as the question
  flags           81 80    "this is an answer; I did the asking; no error"
  questions 00 01, answers 00 01, name servers 00 00, extra records 00 00
question          (copied back unchanged)
answer record
  name     C0 0C           "the same name as at byte 12 of this message"
  type     00 01           A
  class    00 01
  TTL      00 00 01 2C     300 seconds
  length   00 04           the value is 4 bytes
  value    C6 33 64 07     198.51.100.7
```

* **ID:** A can have several questions out at once, and UDP does not track which datagram answers which (section 58), so the ID matches them.
* **C0 0C** points back to byte 12, where the name starts, instead of writing it again.
* **The four counts** say how many records of each kind follow. A com server's answer puts the NS record and its address in "name servers" and "extra records".
* **The end:** one datagram is one whole message, and UDP's length marks its end. UDP never joins datagrams the way TCP joins bytes, so DNS needs no boundary rule of its own.

The laptop's message ends at the resolver. The resolver writes its own new questions, each a new datagram from its own address and port, with a new ID:

```text
1. laptop   -> resolver       ID 3A7F   "www.bluepizza.com?"  (please do the asking)
2. resolver -> root           ID 91C2   "www.bluepizza.com?"  -> NS for com + com server's address
3. resolver -> 192.0.2.10     ID 4E08   "www.bluepizza.com?"  -> NS for bluepizza.com + 203.0.113.53
4. resolver -> 203.0.113.53   ID B713   "www.bluepizza.com?"  -> A 198.51.100.7
5. resolver -> laptop         ID 3A7F   A 198.51.100.7
```

In steps 2 to 4 the "please do the asking" flag is off, so root and com answer only with what they hold.

## 58. UDP Has No Connection

UDP's kernel table has one row per program's port (`port 50123 -> DNS program`, for datagrams from anyone). TCP's has one row per connection, with sequence numbers, window, copies, timers and state. When A sends a UDP question, its kernel writes no row saying "expect a reply from 192.168.1.254 port 53". It sends the frame and keeps nothing. That is what "UDP has no connection" means.

The reply still comes back: the resolver's kernel gives its program A's IP and port from the frame, the program sends a new datagram to `192.168.1.23 : 50123`, and A's kernel delivers it to the program on that port. To UDP it is just another datagram. Two questions from the same port get both answers on that port in either order. "Question and answer" belong to DNS's rules, and the ID matches them.

**`connect()` on UDP** sends nothing. It only adds the other end to the kernel's row: after `connect(("192.168.1.254", 53))`, datagrams for port 50123 from anyone else are not given to the program, and `send()` needs no address. This is a "connected UDP socket", but unlike a TCP connection there is no handshake, the other side knows nothing, the row holds only the other end's IP and port, and lost datagrams stay lost and unordered.

**Fake DNS answers.** Without `connect()`, a datagram from any IP reaches the program, and anyone can write any "from IP" into a frame, so they can pretend to be the resolver without seeing A's question. Two things stop it. The program remembers the ID and where it asked, and throws away answers from elsewhere or with another ID (with `connect()`, the kernel does the address check; the ID check stays in the program, since the kernel never reads DNS data, and most DNS code on Linux uses `connect()`). And guessing is hard: the faker must guess the ID (1 in 65,536) and A's random port (1 in about 28,000), together about 1 in 1.8 billion, and arrive before the real answer.

A resolver that does accept a fake answer keeps it for the TTL the faker wrote, and gives every laptop that asks the faker's address. This is **DNS cache poisoning**, and it is why the ID and port are random instead of counting up.

---

# Part 7: HTTP

What a browser and a web server write into a TCP connection, from HTTP/1.1 to HTTP/3.

---

## 59. HTTP: Asking for a Page

**Request and response belong to the programs.** TCP gives two programs two byte streams, one each way, in order with no gaps. Whether one message is a "request" and the next a "response" is decided by the programs' own layer 7 rules. TCP's acks are not responses: the kernels write them and the program never sees them. Either side can send at any time, as in a chat program. TCP's record holds sequence numbers and windows, not "which question this answers". So the difference between UDP and TCP is not request and response: TCP has a connection and delivers every byte in order, UDP sends separate datagrams and guarantees nothing. Request and response are added by a layer 7 protocol, as DNS does with its ID. A program can also send over TCP and never read anything, like a program sending log lines to a log server all day. Acks still flow back without data. If the other program stops reading, its room drops to 0 and eventually `send()` waits (rule 5). If the connection breaks, for example by RST, the next `send()` returns an error.

**The request.** The browser has a TCP connection open to `198.51.100.7` port 80 and wants the page `/menu`, bytes the server stores, for example in a file. The request says what to do (`GET`, "give me"), which page (`/menu`, a **path**), which version of the rules (`HTTP/1.1`), and which website (`Host: www.bluepizza.com`). Each line ends with the two bytes `0D 0A` (written `\r\n`), and an empty line ends the request (method 2 from section 32):

```text
GET /menu HTTP/1.1\r\n             20 bytes
Host: www.bluepizza.com\r\n        25 bytes
\r\n                                2 bytes   <- empty line: request is over
```

**Why the Host line.** One computer can run several websites, all on port 80, because the browser always connects to port 80 and the person only types a name. For example, a hosting company rents one computer to many shops (like hostco, section 56): `www.bluepizza.com` and `www.greencafe.com` both have A records `198.51.100.7`, and one web server program on port 80 holds `/sites/bluepizza/menu` and `/sites/greencafe/menu`. The TCP connection carries only the IP, so the browser writes the name it looked up, and the program picks the folder.

**Lines.** HTTP/1.1 requests are text, one byte per letter, digit or space. A **line** is a run of bytes ended by `0D 0A`. Line 1 holds the action, path and version separated by spaces. Each line after it holds one piece of information as `Name: value`. `0D` and `0A` are control bytes from old terminals, where one moved the print position back to the left and the other moved it down a line. The request arrives as part of one byte stream (section 32), possibly in several pieces, so the server reads until it sees the four bytes `0D 0A 0D 0A`: the end of the last line, then the empty line.

**The reply** says whether it worked (`200 OK`: found, here it is; `404 Not Found`: no page with that path), what kind of bytes the page is (`Content-Type`, the same job as the MAC type and IP protocol fields), where the page ends, and the page. The page can contain any bytes, including `0D 0A 0D 0A`, so its end is marked by its length first, `Content-Length` (method 1 from section 32). For the 26-byte menu `Margherita 8\n` + `Pepperoni 10\n`:

```text
HTTP/1.1 200 OK\r\n
Content-Type: text/plain\r\n
Content-Length: 26\r\n
\r\n
Margherita 8\nPepperoni 10\n
```

The browser reads lines until the empty line, then exactly 26 more bytes. Other `Content-Type` values: `text/html` (a web page the browser draws), `image/jpeg` (a photo). In HTTP/1.1 the first line and headers are always text, while the body can be any bytes, since it is never searched for `0D 0A`.

**Names.** `GET /menu HTTP/1.1` is the **request line**, and `GET` the **method**. `HTTP/1.1 200 OK` is the **status line**, and `200` the **status code**. Each `Name: value` line is a **header**. The bytes after the empty line are the **body**. These rules are **HTTP** (Hypertext Transfer Protocol; "hypertext" is text with links to other pages). All of it is layer 7, plain bytes in the TCP data that routers and TCP never look at.

**Why not end the request with FIN.** FIN (method 3) closes only the browser's sending direction, so the reply would still arrive. But then the browser could not send another request on that connection, and a page needs many, each needing a new handshake and a fresh congestion window of 10 frames (rule 6). So the request ends with the empty line, and the next request goes on the same connection. When it does close is in section 70. If the connection is lost before the reply, the reply has nowhere to go: the server replies only on the request's connection, and cannot open one to the browser, which sits behind NAT with no row for connections from outside (section 51). The browser opens a new connection and sends the request again.

## 60. Sending Data to the Server

To order one Margherita, the order goes in the request's body, the same place the page went in the reply. Three things change from GET:

1. **Method `POST`.** `GET` means "give me this page" and must not change anything on the server. Browsers repeat GETs freely, for example on reload, so an order sent with GET would be placed twice. Data the server should act on uses `POST`.
2. **A path for the part that takes orders**, `/order`.
3. **A body, with `Content-Type` and `Content-Length`.** A common format for small data is `name=value` pairs joined by `&`, labeled `application/x-www-form-urlencoded`.

```text
POST /order HTTP/1.1\r\n                                     HTTP/1.1 200 OK\r\n
Host: www.bluepizza.com\r\n                                  Content-Type: text/plain\r\n
Content-Type: application/x-www-form-urlencoded\r\n          Content-Length: 18\r\n
Content-Length: 23\r\n                                       \r\n
\r\n                                                         order 57 received\n
item=margherita&count=1
```

A GET has no body and no `Content-Length`, so its body length is 0. Requests and replies have the same shape: first line, headers, empty line, optional body.

**Query parameters.** Values can also go in the path after a `?`: `GET /menu?size=large&veg=yes HTTP/1.1`. The part before `?` picks the page. The part after is the **query**, and each pair is a **query parameter**. Use the query with GET for which version of a page is wanted, such as search words or a filter, which changes nothing and is safe to repeat. Use the body with POST for data the server acts on, and anything large: servers limit the request line, often to about 8 KB, while a body can be megabytes. A space, `&` or `=` inside a value would break the splitting, so they are written as `%` and the byte in hex: `search=blue%20pizza`. The query uses the same format as the form body, but no `Content-Type`, which only ever describes the body.

## 61. Many Files on One Page

The `/menu` page now shows 10 photos, so the browser needs 11 files. On one HTTP/1.1 connection, a whole reply must be read before the next can start, so everything waits behind a large photo.

**Pipelining.** The browser sends all 11 requests back to back. Replies still come back in request order, because a reply has no field saying which request it answers, so a 5 MB photo 2 still holds up the small photos after it. It is part of the HTTP/1.1 rules, but browsers removed it: replies still had to come in order, and some servers and machines in between handled it wrongly, sending replies mixed up or not at all. Programs that are not browsers, such as command-line HTTP tools, can still use it.

**Several connections.** Browsers open up to 6 TCP connections to the same website name and send one request at a time on each, so the big photo blocks only its own connection:

```text
connection 1:  page      -> photo 6
connection 2:  photo 1   -> photo 7
connection 3:  photo 2 (5 MB) .........................
connection 4:  photo 3   -> photo 8         (connections 5 and 6 likewise)
```

The limits: each connection costs a handshake (50 ms with a 50 ms round trip), each starts at 10 frames and learns the path separately while competing with the others at router lines, the server keeps 6 records per browser, and it is still capped at 6. The root cause of both problems: a reply has no label, so a connection carries one reply at a time, start to finish.

HTTP/1.1 sites are still fast. With a short round trip, say 10 ms, a few extra handshakes cost little. A reply can say how long the browser may keep the file, for example a day, so the next visit sends no request. Sites join many small code files into one. Files are spread over names like `img1.bluepizza.com` and `img2.bluepizza.com`, since the limit is per name. And often a server placed in front of the website speaks HTTP/2 (section 62) to the browser and HTTP/1.1 to the website's server: a proxy (section 65).

## 62. HTTP/2

With a label on every piece, one connection can carry all 11 replies mixed together, and the browser sorts the pieces by label. Each request and reply is cut into pieces, each starting with a 9-byte binary header:

```text
length      3 bytes   how many bytes follow this 9-byte header
type        1 byte    0 = DATA (body bytes), 1 = HEADERS (the headers)
flags       1 byte    one bit means "this is the last piece of this request or reply"
stream ID   4 bytes   the label: which request this piece belongs to
```

HTTP/2 calls these pieces **frames**, a different thing from the cable and air frames in Parts 1 to 5: a few bytes inside the TCP data. One request plus its reply is a **stream** and shares one number. The browser uses odd numbers (1, 3, 5, ...). The server can start streams of its own with even numbers, so the two never pick the same one. Stream 0 is for messages about the whole connection, such as a settings message at the start.

```text
browser -> server:  HEADERS 1 GET /menu    HEADERS 3 GET /photo1.jpg    HEADERS 5 GET /photo2.jpg (5 MB) ...
server -> browser:  HEADERS 1 200 text/html    DATA 1 page, last    HEADERS 5 200 image/jpeg    DATA 5 16 KB
                    HEADERS 3 200 image/jpeg    DATA 3 all of photo 1, last    DATA 5 16 KB    DATA 5 ...
```

The server sends pieces from any stream in any order, so small photos finish while the big one is still going.

**Pieces are sent whole.** The stream ID appears only in a piece's header. The reader counts `length` bytes and puts all of them into that stream. If stream 3's piece were put inside stream 5's, the reader would take its header and bytes as photo 2, then read leftover photo 2 bytes as the next header, and everything after would be garbage. So mixing happens only between whole pieces. A DATA piece carries at most 16,384 bytes by default, so a 5 MB photo is about 320 pieces. The receiver can allow up to about 16 MB through the settings message, but small pieces mean a small reply never waits behind more than 16 KB of a big one, and the receiver needs only 16 KB of memory per piece. TCP knows nothing of pieces: one 16,384-byte piece spreads over about 12 cable frames, and the program reads 9 bytes, then `length` bytes, and repeats (method 1, section 32).

**What it fixes from section 61:** one handshake instead of six, one congestion window shared by all requests, no cap of 6, and one server record instead of six. Headers are also binary: a header sent once, like `Host: www.bluepizza.com`, is later referred to by a small number. Browsers use HTTP/2 only on encrypted connections, agreed during the encryption setup (section 84).

**In a server program.** The "one request" a server's code sees is a stream. In Node, the `http2` library reads each 9-byte header, adds the bytes to that stream's table, and once a stream's headers have arrived builds `req` and `res` objects and calls the handler. `res.write()` and `res.end()` are cut into DATA pieces with that stream's ID and mixed onto the same connection. So a handler runs once per request either way: per request on one of up to 6 connections in HTTP/1.1, per stream on one shared connection in HTTP/2. Node's usual `http` module, which Express is built on, speaks only HTTP/1.1. Often a Node server stays on HTTP/1.1 behind a server that speaks HTTP/2 to browsers.

## 63. One Lost Frame Stops Every Stream

All 11 streams travel in one TCP connection. Say a cable frame with part of photo 2 is lost:

```text
frame 20   bytes of a photo 2 piece (stream 5)     lost
frame 21   bytes of a photo 1 piece (stream 3)     arrives
frame 22   last bytes of photo 1 (stream 3)        arrives
```

The browser's kernel holds frames 21 and 22, because frame 20's bytes come first (rule 2), so `read()` returns nothing past frame 19. Photo 1 is complete in kernel memory, but the browser cannot reach it. The server resends frame 20 at least one round trip later, often 200 ms or more, and then `read()` returns 20, 21 and 22 at once. The HTTP/2 labels cannot help, because they are inside the bytes, and TCP knows only one line of numbered bytes. On a good cable losses are rare. On weak Wi-Fi or a phone network, losing 2 of every 100 frames stops all streams each time, and HTTP/1.1 with 6 connections can be faster, since a loss stops only one connection.

Everyone waiting behind the first in line is **head-of-line blocking**, the same problem as section 61. HTTP/2 removed it at the HTTP level, but it is still there in TCP underneath.

## 64. QUIC and HTTP/3

The fix is a transport that keeps order per stream. The browser cannot change TCP: its rules live in every kernel, and boxes in between expect exactly TCP or UDP. But it can use UDP, which adds only ports and a checksum, passes every kernel and box already, and gets NAT rows by port like TCP. So the new rules are code inside the browser and the server program, carried as UDP data:

```text
HTTP/2:  [MAC][IP, protocol 6 ][TCP group               ][HTTP/2 pieces][CRC]
HTTP/3:  [MAC][IP, protocol 17][UDP group][QUIC group   ][QUIC pieces  ][CRC]
                                ports only  numbering, acks: done by the program
```

To every router and box it is just a UDP datagram. The program does all of TCP's work itself (sections 22 to 26): numbering, acks, resending, both windows and the handshake. The difference: each stream counts its own byte positions ("stream 5, bytes 32768 to 34167"), so a lost datagram of photo 2 holds back only stream 5, and photo 1's datagrams go to the browser at once.

It also survives an address change. A TCP connection is identified by the four values, so when a phone moves from Wi-Fi to the mobile network, every TCP connection breaks. QUIC puts its own connection number in every datagram, so the server recognizes the phone at its new address.

The costs: the program does work the kernel used to do, so it uses more processor time. Some networks block UDP except port 53, and then the browser falls back to TCP and HTTP/2. A server announces HTTP/3 with a header in an earlier HTTP/2 reply, and the browser tries it on the next connection.

The transport is **QUIC** (it started as an abbreviation, now it is just a name), and HTTP on top of it is **HTTP/3**. `GET`, `/menu`, `200`, headers and body mean the same in HTTP/1.1, 2 and 3. Only how they are cut up and carried changes. In Chrome's developer tools, Network tab, the "Protocol" column shows `h3` or `h2`. For a small website on a good connection the difference is small, which is why HTTP/1.1 still works fine for many sites.

---

# Part 8: Proxies and Load Balancers

A computer between the browser and the website: reverse and forward proxies, L4 and L7 load balancing, and keep-alive.

---

## 65. A Proxy in Front of the Website

Parts 8 and 9 use plain HTTP. Encryption comes in Part 10.

At lunch time, 50,000 browsers connect to bluepizza's one website computer at `198.51.100.7`, too many for it. The shop adds three more computers with the same website, but DNS gives one address and every browser connects to it.

**A program in front.** Put one more computer, P, at `198.51.100.7`, and give the four website computers private addresses behind it (section 49). P has two sockets like any router (section 48), but runs a program that reads HTTP:

```text
                                        shop's local network 10.0.0.x
browser ---- ... ---- [P] 198.51.100.7 | 10.0.0.1 ---- switch ---- web1 10.0.0.11
                                                       |---- web2 10.0.0.12
                                                       |---- web3 10.0.0.13
                                                       |---- web4 10.0.0.14
```

1. The browser looks up `www.bluepizza.com`, gets `198.51.100.7`, does a TCP handshake with P on port 80, and sends `GET /menu`.
2. P's program reads until the empty line, so it has the whole request (section 59).
3. P picks one of the four, say web2, opens its **own** TCP connection from `10.0.0.1 : 51000` to `10.0.0.12 : 80`, and sends the same request with one extra header, `X-Forwarded-For: 203.0.113.10`, which tells web2 the browser's real address (section 69).
4. web2 replies to P, and P writes the same bytes to the browser on the first connection.

There are two separate connections, each with its own handshake, sequence numbers and windows: browser `203.0.113.10 : 40001` to P `198.51.100.7 : 80`, and P `10.0.0.1 : 51000` to web2 `10.0.0.12 : 80`. A router or NAT box reads MAC and IP (and ports for NAT) and passes the browser's frames through. P reads the whole request, ends the browser's connection, opens its own, and can choose by path, for example `/order` to web4. Because it opens its own connection, it can even speak HTTP/2 to the browser and HTTP/1.1 to web2: the "server placed in front" from sections 61 and 62.

A program that receives requests and sends them on for someone else is a **proxy**. One in front of the servers, on the website owner's side, is a **reverse proxy**. The browser does not know it exists and thinks P is the website. A common program for this is nginx.

## 66. A Proxy Next to the Browsers

A school wants all 500 students' browsers to go through one computer of its own, F, so it can block some websites and keep copies of popular pages. F sits in the school's local network next to the browsers (`10.1.0.5`, port 3128). Each browser is set to use it: in Ubuntu, Settings -> Network -> Network Proxy, or pushed by the school automatically. So students cannot just remove the setting, the school's router drops frames from student computers to port 80 unless they go to F.

1. The student types `www.bluepizza.com/menu`. With the proxy setting on, the browser does **not** look up the name. It connects to F and sends `GET http://www.bluepizza.com/menu HTTP/1.1`, with the full address in the request line so F knows which website to go to.
2. If the name is on F's block list, F replies `403 Forbidden` at once and never contacts the website.
3. If F has a stored copy that the website's reply allowed to be kept and whose time limit has not passed (the same kind of limit as the browser's own copies, section 61), F replies from it.
4. Otherwise F looks up the name, opens its **own** connection to `198.51.100.7 : 80`, sends the request with the normal `/menu` path, stores a copy of the reply, and passes the reply on.

The website only ever sees the school's public address.

```text
                  forward proxy (F)               reverse proxy (P)
sits next to      the browsers                    the website's servers
set up by         the browsers' owner (school)    the website's owner (shop)
who knows         browsers must be set to use it  browsers do not know it exists
used for          blocking, copies, logging       spreading requests, one public address
```

The mechanics are the same: read the HTTP request, open a separate connection, pass the request on and the reply back. A proxy on the browsers' side is a **forward proxy**, or just "a proxy" in everyday speech. With encryption, F can see the website's name but not the path or body (section 84).

## 67. Picking a Server, and Skipping a Broken One

P holds the four addresses and picks one for every request.

**Round robin:** P keeps a counter. Request 1 to web1, 2 to web2, 3 to web3, 4 to web4, 5 to web1 again. Its weakness: a menu request takes about 5 ms and a photo upload about 2 s, so web2 can get three uploads in a row while web1 sits idle.

**Least connections:** P opened every connection to the servers itself (section 65), so it knows how many are open to each (say 2, 9, 4, 3), and the next request goes to the one with the fewest, web1.

**When web3 is off**, what P sees depends on what is broken:

```text
what is broken                  what P's kernel sees                            what P's connect() gets
computer switched off           no ARP reply, so no MAC to send to              fails after about 3 s ("no route to host")
computer on, program stopped    web3's kernel sends RST (no listener, sec. 25)  fails right away ("connection refused")
program running but stuck       handshake works, but no reply ever comes        P waits until its own time limit, e.g. 60 s
```

Left alone, every fourth request fails or waits. So every 5 seconds P sends each server its own small request, `GET /health`, which the web program answers `200 OK` when it is working. Each check waits up to 2 seconds. After 3 failures in a row, P marks the server down and leaves it out:

```text
0 s     GET /health to web3     no answer by 2 s  -> fail 1
5 s     GET /health to web3     no answer by 7 s  -> fail 2
10 s    GET /health to web3     no answer by 12 s -> fail 3 -> web3 marked down
```

So P notices about 12 seconds after web3 went off. Any 200 resets the count, and after 2 good answers in a row a down server is put back. "In a row" matters because a single check can fail on a working server: busy with three uploads for 2.5 seconds, web3 answers after the 2-second limit, and the next check gets a normal 200. These requests are **health checks**, and 5 s, 2 s, 3 and 2 are example settings the shop chooses.

A request already sent to web3 when it stopped: if it was a GET, P can send it to web4, because a GET must not change anything (section 60). If it was a POST to `/order`, P cannot know whether web3 saved the order, and sending it again could place it twice, so P returns an error.

Spreading requests over several servers and skipping broken ones is **load balancing** ("load" is each server's amount of work). A machine that does it is a **load balancer**. P is a reverse proxy that also load balances.

## 68. A Load Balancer That Reads Less

Every machine that passes frames on holds the whole frame. The difference is which bytes it looks at, and whether it must wait for more frames:

```text
byte position in frame    what is there
0 - 13                    MAC group
26 - 29 / 30 - 33         from IP / to IP
34 - 35 / 36 - 37         from port / to port
54 - ...                  data: "GET /menu HTTP/1.1\r\n..."
```

A router (section 11) looks only at bytes 30–33 and sends the whole frame out, data untouched. P's kernel hands the data to nginx, which collects it until `0D 0A 0D 0A` and only then picks a server.

**The idea.** A new machine, Q, replaces P at `198.51.100.7` and is the router for web1–web4, so their replies go out through it, the way a laptop's frames go through the home box (section 15). Q looks only at the IP and TCP groups, the four values (section 25):

1. The browser `203.0.113.10 : 40001` sends a SYN to `198.51.100.7 : 80`.
2. A SYN means a new connection, so Q picks a server (section 67), say web2, and writes a row: `203.0.113.10, 40001 -> 10.0.0.12`.
3. Q changes the to-IP to `10.0.0.12` and recomputes the IP header checksum and the TCP checksum, which also covers both IPs. Ports, seq and data stay the same.
4. web2's SYN+ACK comes from `10.0.0.12 : 80`, and Q changes the from-IP back to `198.51.100.7`. Otherwise the browser's kernel would find no matching connection and answer RST (section 26).
5. Every later frame from `203.0.113.10 : 40001` matches the row and must go to web2, which holds this connection's sequence numbers. web4 would answer RST.

There is **one** TCP connection, browser to web2. Q does no handshake. It changes addresses and passes frames on, plus a router's usual work (new MACs, TTL lowered by 1). It has one row per connection, made when a SYN arrives and removed after FIN, RST, or a long silence.

**Q does not wait.** Q decides from bytes inside each frame, so it sends each frame on before the next arrives. With a request split over 3 frames 1 ms apart, Q sends them at 0, 1 and 2 ms. P sends nothing until frame 3 brings `0D 0A 0D 0A`.

**P builds new frames, Q does not.** At P, the kernel copies each browser frame's data bytes into the connection's memory, acks the browser, and frees the frame. nginx `read()`s the bytes and `write()`s them on its second connection, and the kernel builds new frames with new MAC, IP and TCP groups: from `10.0.0.1 : 51000` instead of the browser, to web2 instead of P, P's own sequence numbers, and the same request plus `X-Forwarded-For`. The HTTP lines are data bytes, so they go on to web2. What P drops is the browser frame's MAC, IP and TCP groups, and three frames in can go out as two, since the kernel packs bytes into frames of up to 1460 (the MSS). Q changes a few bytes in the frame it received and sends that same frame.

**What Q gains:** little work per frame (one lookup, one rewrite, no reading up to an empty line, no second connection, no copying into a program), it works for any TCP program, not only HTTP (for example a database on port 5432), and web2 sees the browser's real address, so no `X-Forwarded-For`. **What Q loses:** it never sees the path, so it cannot send `/order` to web4. It picks once per connection, so 100 requests on one open connection (section 59) all go to web2. It cannot resend a GET elsewhere, since it does not know where requests start and end. And it cannot speak HTTP/2 to the browser and HTTP/1.1 to web2.

**Q vs a router and vs NAT:**

```text
                       router (R, section 11)           Q                                   home box NAT (section 50)
looks at               to-IP only (layer 3)             both IPs and ports (layer 4)        both IPs and ports
the to-IP              names the final computer         Q's own address: "the shop"         the box's own address
changes                nothing                          to-IP in, from-IP out               from-IP and port out
rows                   one per address range,           one per connection, made by Q       one per connection, made by
                       typed or automatic (sec. 12)     when a SYN arrives from outside      the laptop's first frame out
chooses a computer?    no                               yes, one of web1-web4               no: the laptop chose
no matching row        -                                SYN gets a new row and server       dropped (section 51)
```

So Q is close to NAT running the other way round, plus choosing which inside computer gets each new connection.

**Names**, from the layer numbers in section 31: P is an **L7 load balancer** (reads up to HTTP, picks once per request, two connections). Q is an **L4 load balancer** (reads up to the TCP group, picks once per connection, one connection). NAT also reads up to layer 4 but is just called NAT. nginx is usually set up as L7. The Linux kernel has an L4 balancer called IPVS. On AWS, the "Network Load Balancer" is L4 and the "Application Load Balancer" is L7. Large sites often use both: L4 machines in front, each sending connections to several L7 machines.

## 69. What P Does With the Bytes

**X-Forwarded-For.** web2's connection is with P, so its kernel reports every request as coming from `10.0.0.1`. The shop's program may need the real address, for example for logs or to refuse an address sending 1000 requests a second. P knows it, so it adds `X-Forwarded-For: 203.0.113.10` before sending the request on. A browser can write its own line with any address. nginx then appends the real one, `X-Forwarded-For: 1.2.3.4, 203.0.113.10`, so web2 should trust only the last address, the one P wrote. "X-" was the old way to mark a header not in the official HTTP rules. Q does not need it, since web2 sees the real from-IP.

**The reply** comes back the way the request went. nginx holds both connections open and writes web2's reply on the second into the first, and the browser gets it on the connection it sent the request on.

**nginx's settings** are lines in a text file, `/etc/nginx/nginx.conf`, each a name and a value ending in `;`. A missing line means the default value.

**A large request body.** nginx needs only the headers to pick web2. For the body it has two ways, set by `proxy_request_buffering on;` (way 1, the default) or `off;` (way 2):

```text
way 1 (default)   keep the whole body first, then send it to web2
                  (first 16 KB in memory on a 64-bit machine, the rest in a file on P's disk)
way 2             send each part of the body to web2 as soon as it arrives
```

`client_max_body_size` limits the body, and without it nginx refuses anything over 1 MB with `413 Request Entity Too Large`. A shop accepting 5 GB uploads must raise it.

Way 1 is the default because the web program often handles only a few requests at a time. Say web2 runs 4 copies of the shop's program, each handling one request start to end and doing nothing else while reading a body. A phone uploads 50 MB at 1 MB/s. With way 2, one copy is busy for 50 s, and 4 slow phones block every menu request. With way 1, nginx takes 50 s receiving, then sends it over the shop's 1 Gbit/s cable (about 125 MB/s), so one copy is busy for about 0.4 s. nginx can afford the wait because one nginx process handles thousands of connections: it asks the kernel which ones have new bytes, handles them, and asks again, never waiting on one connection. A second reason: if web2 fails partway, nginx still has the full body and can send it to another server (section 67). If the web program works like nginx (Node.js does), the first reason matters less. For very large uploads like 5 GB, writing everything to disk first costs time and space, so shops use way 2 for that path or upload straight to separate storage.

**The reply going back.** A **buffer** is memory where bytes wait before being sent on. web2 has a 1 MB reply for a phone that takes 100 KB/s, so the phone needs 10 s:

```text
proxy_buffering on;  (default)   takes bytes from web2 as fast as web2 sends, keeps what the     web2 busy about 8 ms
                                 phone has not taken in buffers (and a disk file if needed),
                                 sends to the phone as soon as it has bytes
proxy_buffering off;             takes bytes from web2 only as fast as the phone takes them      web2 busy about 10 s
```

The two settings share a word but differ. For the request, "buffering" waits for the whole body, because that gives web2 one fast burst and allows resending. For the reply, it does not wait for everything, because waiting gains nothing: web2 is free either way and the phone would only start later. It means web2 does not wait for the slow phone. One side effect (section 73): with `proxy_buffering on`, a small part of a reply, say 30 bytes, can sit in nginx's buffer instead of reaching the browser at once.

## 70. One Reply per Request, and Keeping the Connection Open

**One reply per request is HTTP's rule.** TCP only carries bytes both ways (section 59). HTTP adds that the server must send exactly one response for each request. TCP does not enforce it: a program on web2 that never replies just breaks HTTP's rules. DNS and HTTP are both layer 7 protocols whose rules cover only their data: DNS in UDP datagrams, HTTP in a TCP byte stream (or QUIC in HTTP/3). HTTP/1.1 matches replies to requests by order (section 61), HTTP/2 by stream ID (section 62).

**Time limits.** HTTP gives no number, so each program sets its own. nginx waits up to 60 s for web2 by default. If web2 refuses the connection (RST), nginx answers the browser `502 Bad Gateway`. If web2 sends nothing for 60 s, `504 Gateway Timeout`. If a connection closes before any reply, the browser shows an error page, in Chrome `ERR_EMPTY_RESPONSE`.

**Keeping the connection open.** After the first reply, the browser sends no FIN. Both kernels keep the connection's record, and the next request goes on it without a new handshake:

```text
0 s     SYN, SYN+ACK, ACK         connection opened once
0 s     GET /order/57/status  ->  reply
5 s     GET /order/57/status  ->  reply      same connection, no handshake
```

Once either side closes it, the next request needs a new connection and handshake. HTTP controls this with one header. `Connection: close` means "after this reply, this connection will be closed". `Connection: keep-alive` means "keep it open". HTTP/1.0 closes after each reply unless the request says keep-alive. HTTP/1.1 stays open unless either side says close, so the header usually appears only when someone wants to close. Staying open needs each reply to mark its end, with `Content-Length` or chunks (section 73), otherwise closing is the only end marker (method 3, section 32).

**Who calls `close()`.** The kernel never reads HTTP. The program reads the header and calls `close()` after writing the full reply, and then the kernel sends FIN. If the browser's request has `Connection: close`, the server writes the full reply and closes. The browser reads it, then `read()` returns 0 and it closes too. If the server's reply has `Connection: close` (with `Content-Length: 26`), the server closes after writing. The browser reads the 26 body bytes, sends no more requests on that connection, and closes. Its next request goes on a new connection.

**How long it stays open** with no requests is each program's own limit: nginx 75 s, Node.js 5 s (it also sends `Keep-Alive: timeout=5` in replies to tell the browser), Firefox 115 s. Whichever limit comes first closes it with FIN. Each open connection takes memory in the server's kernel and in nginx even when idle, which is why server limits are short: with 75 s, 10,000 browsers that load one page and go quiet hold 10,000 connections for 75 s. nginx also has a maximum number of connections, past which new ones wait or are refused.

**With a proxy**, the header applies only to the connection it travels on. P holds two connections, so nginx does not pass the browser's `Connection` line on to web2, and decides separately whether its own connection to web2 stays open.

---

# Part 9: Pushing Updates to the Browser

How the server tells the browser about news: polling, long polling, SSE and WebSocket.

---

## 71. Asking Again and Again

A customer orders a pizza. Ten minutes later the kitchen marks order 57 ready on web2, and the page should show "order 57 is ready" at that moment. But in HTTP the server replies only after the browser sends a request.

The order page has a small JavaScript program that the browser runs, and it knows the order number, 57. Every 5 seconds it sends `GET /order/57/status`, and web2 replies `cooking\n` (with `Content-Length: 8`) until the kitchen marks it ready, when the next reply is `ready\n`. The requests share one open connection (section 70), so there is no handshake each time.

The cost: over the 10 minutes the page sends 600 / 5 = 120 requests, and 119 of them get "cooking". With 1000 customers waiting, the shop gets 200 requests per second, almost all answered "cooking". And the news can be up to 5 seconds late. Asking every second cuts that to 1 second but makes 5 times as many requests. Asking every 30 seconds makes fewer, but can be 30 seconds late.

Sending the same request on a timer to check for news is **polling**.

## 72. Holding the Request Until There Is News

Instead of answering "cooking", web2 can hold the request. The browser sends `GET /order/57/wait`. web2's program checks order 57: if it is ready, it replies at once. If not, it does not reply, and keeps the request in a list in memory (`waiting for order 57: connection from P, port 51000`). When the kitchen marks the order ready, the program finds that entry and writes `ready\n` on that connection. The page shows it within milliseconds. It is still one request and one reply, within HTTP's rules. The reply just comes late.

**What goes wrong while it waits:**

1. **Time limits on the way.** nginx's 60 s limit (section 70) would end the request with `504 Gateway Timeout`. So the program replies `waiting\n` by itself after, say, 30 s, and the page sends a new `/wait` at once. Over 10 minutes that is about 20 requests instead of 120.
2. **Open connections.** Every waiting customer holds a connection to P and one from P to web2, all idle: 2000 for 1000 customers. A program running 4 copies that each handle one request at a time could hold only 4 waiting requests. Long polling needs a program that handles many connections at once, like nginx or Node.js.
3. **News between requests.** If the order becomes ready right after a `waiting` reply, the next `/wait` checks the state first and replies at once.

**In Node.js.** The function given to `http.createServer` is the **handler**. It runs once for every request, and `res` is the object it writes the reply on. Here the kitchen's screen sends `POST /order/57/ready` to the same program:

```js
const http = require("http");
const status = new Map([["57", "cooking"]]);  // order number -> "cooking" or "ready"
const waiting = new Map();                    // order number -> list of res objects not answered yet

function reply(res, text) {
  res.writeHead(200, { "Content-Type": "text/plain", "Content-Length": Buffer.byteLength(text) });
  res.end(text);
}

http.createServer((req, res) => {
  const [, id, action] = req.url.match(/^\/order\/(\d+)\/(\w+)$/) || [];
  if (req.method === "GET" && action === "wait") {
    if (status.get(id) === "ready") return reply(res, "ready\n");
    waiting.set(id, [...(waiting.get(id) || []), res]);       // no news: keep res, reply later
    const timer = setTimeout(() => reply(res, "waiting\n"), 30000);
    res.on("close", () => {                                    // reply sent or browser gone
      clearTimeout(timer);
      waiting.set(id, (waiting.get(id) || []).filter((r) => r !== res));
    });
    return;                                                    // handler ends, nothing sent yet
  }
  if (req.method === "POST" && action === "ready") {
    status.set(id, "ready");
    for (const r of waiting.get(id) || []) reply(r, "ready\n"); // the late replies go out now
    return reply(res, "ok\n");
  }
  res.writeHead(404); res.end();
}).listen(80);
```

**No busy waiting.** When the handler returns without `res.end()`, the connection stays open with no reply. Node does not loop and check. It makes one kernel call (on Linux, `epoll_wait`) meaning "put this process to sleep until a connection has new bytes or my next timer is due", and uses no CPU while asleep. The kitchen's POST wakes it, and that handler finds the stored `res` objects and writes the replies.

One limit: `waiting` and `status` live in one process's memory, so this works only when the `/wait` and the kitchen's POST reach the same process. With web1–web4 behind P, they might not, and the servers would need to share the news, which is not covered here.

Holding a request until there is news or a time limit is **long polling**. Section 71's kind is sometimes called short polling.

## 73. One Reply That Never Ends

The shop wants several updates in a row: "cooking", "in oven", "out for delivery", then the driver's position every 2 seconds. With long polling, each update ends the reply and the browser must ask again. Instead, web2 sends the status line and headers at once and never ends the body. Each time there is news, it writes a few more body bytes on the same connection, and the browser reads each part as it arrives.

**Marking a body with no total length.** `Content-Length` is impossible, because nobody knows the length. HTTP/1.1's other way is the header `Transfer-Encoding: chunked`: the body is sent in **chunks**, each its length as hex text, `\r\n`, the bytes, `\r\n`. A chunk of length 0 ends the body. The length line and the trailing `\r\n` are **chunk markers**, not part of the body. This is the length-prefix method (section 32) done by HTTP. The browser needs the body's end to tell the page "this is the whole body" (`await res.text()` after `fetch()` returns only then), and to know which bytes on the connection belong to the next reply.

**The body format, `text/event-stream`**, is a `Content-Type` value like `text/plain`. The body is a series of **messages**, each a piece of news like `cooking`. A line starting `data: ` holds a message's text, an empty line ends the message, and a line starting `:` means nothing and is skipped. These rules call a message an "event", so "event stream" means messages arriving over time. The body must be UTF-8 text. Binary data, like a photo, would have to be turned into text characters first, about a third larger, so in practice it carries short text messages.

```text
data: a\n\ndata: b\n\ndata: c\n\ndata: d\n\n      -> onmessage("a"), ("b"), ("c"), ("d")
text "a\n\nb"   is sent as   data: a\ndata: \ndata: b\n\n   -> onmessage("a\n\nb")
```

Several messages can go in one write and one frame, and the browser still delivers each separately. Text with line breaks becomes one `data:` line per line of text, joined back with `\n`. JSON from `JSON.stringify` writes a line break as the two characters `\` and `n`, so it has no real line breaks at all.

**The bytes in order.** The browser sends `GET /order/57/events` with `Accept: text/event-stream`. `Accept` is a request header listing the body formats (`Content-Type` values) the browser wants. web2 replies at once and keeps writing:

```text
HTTP/1.1 200 OK\r\n
Content-Type: text/event-stream\r\n
Transfer-Encoding: chunked\r\n
\r\n
F\r\ndata: cooking\n\n\r\n             <- 0 s: 0xF = 15 bytes (6 + 7 + 2), message "cooking"
8\r\n: ping\n\n\r\n                    <- 30 s, skipped by the browser
F\r\ndata: in oven\n\n\r\n             <- 4 min
18\r\ndata: out for delivery\n\n\r\n   <- 9 min, 0x18 = 24 bytes
```

One write of four 9-byte messages (`data: a\n\n` ... `data: d\n\n`) is one 36-byte chunk: `24\r\n` (4 bytes), the 36 bytes, `\r\n` (2 bytes), 42 bytes of TCP data. The browser removes the markers, finds `\n\n` four times, and calls `onmessage` four times.

**Who parses.** `EventSource` is code built into the browser. The page's JavaScript calls `new EventSource("/order/57/events")` once, and the browser does the rest as bytes arrive: sends the GET, removes chunk markers, waits for the empty line (holding a message split across frames), removes `data: ` and calls the page's `onmessage("in oven")`. With `fetch()` instead, the page would get the raw `data: in oven\n\n` bytes and split them itself.

**Server (Node.js):**

```js
const listeners = new Map();   // order number -> open replies (res)
const send = (res, text) =>    // one data line per line of text, then the empty line
  res.write(text.split("\n").map((line) => `data: ${line}`).join("\n") + "\n\n");

// in the handler, for GET /order/<id>/events:
res.writeHead(200, { "Content-Type": "text/event-stream" });
send(res, status.get(id));                                   // current state first
listeners.set(id, [...(listeners.get(id) || []), res]);
const ping = setInterval(() => res.write(": ping\n\n"), 30000);
res.on("close", () => { clearInterval(ping); listeners.set(id, listeners.get(id).filter((r) => r !== res)); });
// res.end() is not called

// when the kitchen POSTs a new status text for <id>:
for (const r of listeners.get(id) || []) send(r, text);
```

The handler never writes `Transfer-Encoding: chunked`. With no `Content-Length`, Node adds it and wraps every `res.write()` in a chunk itself. The page's side:

```js
const events = new EventSource("/order/57/events");
events.onmessage = (e) => {
  document.getElementById("status").textContent = e.data;  // "cooking", "in oven", ...
  if (e.data === "delivered") events.close();              // stop, no more requests
};
```

**nginx in between.** Two defaults get in the way: its buffer (section 69), where a 15-byte message can sit instead of reaching the browser, and its 60 s limit (section 70). Both are set for the stream paths only:

```text
location ~ /events$ {               # these settings apply only to paths ending in /events
    proxy_pass http://shop_servers; # send these requests to the list web1-web4 (named elsewhere in the file)
    proxy_buffering off;            # send web2's bytes to the browser as soon as they arrive
    proxy_read_timeout 3600s;       # allow up to 1 hour with no bytes from web2, instead of 60 s
}
```

Or web2's program decides per reply by adding the header `X-Accel-Buffering: no`. nginx reads it, passes this reply's bytes on at once, and removes the line. Node never adds it by itself, since it knows nothing about nginx. The `: ping` every 30 s keeps bytes passing when there is no news, so no machine on the way closes the connection for being silent.

**What `res.end()` sends.** It ends the HTTP reply, not the TCP connection. For a normal reply, `res.end("ok\n")` with nothing written before, Node sends `Content-Length: 3` and the 3 bytes, with no end marker. For a chunked reply, after `res.write("data: delivered\n\n")`, `res.end()` sends the 0 chunk, `0\r\n\r\n`. Either way the connection stays open for the next request. Node closes it with FIN only if either side sent `Connection: close` (section 70).

**Reconnecting.** `EventSource`'s rules (part of the HTML rules browsers follow) say that whenever the connection breaks or the reply ends, the browser waits a few seconds and sends the same GET again. The browser cannot tell a planned end from an unplanned one: web2's program being restarted, nginx's time limit, or web2 being taken out of the list (section 67) all end the stream with a normal `0\r\n\r\n`, and the page still wants updates. So `res.end()` alone does not stop it. The new GET runs the handler from the start, which sends the current status first, so news sent while the phone had no signal still arrives. A planned stop has signals that cannot happen by accident: the page calls `events.close()`, or the server answers the reconnect with `204 No Content`. A common pattern: the server sends `data: delivered\n\n` and calls `res.end()`, and the page calls `events.close()` when it sees `delivered`.

**Limits:** one direction only, server to browser (the browser sends with ordinary requests). Text only. With HTTP/1.1, each open stream holds one of the browser's 6 connections to that name (section 61). With HTTP/2 it is one stream on the shared connection.

This is **Server-Sent Events**, or **SSE**.

## 74. Switching the Connection to Another Protocol

The customer wants to chat with the driver, messages both ways many times a minute. With SSE, each customer message would be a separate POST with all its headers. Instead, the browser opens a TCP connection and sends an HTTP request that asks: "after this, let us stop speaking HTTP on this connection." If the server agrees, both switch to different rules on the same connection, where either side sends messages whenever it wants, with no requests and no replies.

```text
GET /chat/57 HTTP/1.1\r\n                                HTTP/1.1 101 Switching Protocols\r\n
Host: www.bluepizza.com\r\n                              Connection: Upgrade\r\n
Connection: Upgrade\r\n                                  Upgrade: websocket\r\n
Upgrade: websocket\r\n                                   Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n
Sec-WebSocket-Version: 13\r\n                            \r\n
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n
\r\n
```

`Connection: Upgrade` is section 70's header with a new value: "I want to change the protocol on this connection". `Upgrade: websocket` names the protocol, and `Sec-WebSocket-Version: 13` the version of its rules. `Sec-WebSocket-Key` is 16 random bytes picked for this one handshake, written in **base64**: any bytes written using only letters, digits, `+` and `/`, 3 bytes to 4 characters, with `=` filling a short last group. 16 bytes become 24 characters ending in `==`. Status `101` means "agreed, switching now". Everything after its empty line, both ways, follows the new rules.

**Why only the browser writes `Sec-` headers.** The browser does not let page JavaScript set any header starting `Sec-`; `fetch()` leaves such lines out. So a server that sees `Sec-WebSocket-Key` knows the browser itself made a real WebSocket request, and page JavaScript cannot fake one to make a server switch. The shared start lets one rule cover all such headers, including future ones.

**The accept value.** It uses **SHA-1**, a calculation that turns any input into 20 bytes, always the same 20 for the same input. The server joins the key with a fixed text from the WebSocket rules (`dGhlIHNhbXBsZSBub25jZQ==258EAFA5-E914-47DA-95CA-C5AB0DC85B11`), takes the SHA-1 of it, and writes those 20 bytes in base64: `s3pPLMBiTxaQ9kYGzzhZRbK+xOo=`. The browser does the same with the key it sent and compares. If they match it switches, otherwise it closes. Only a server that knows the WebSocket rules can produce the right value for a key just made up, so this proves the reply came from a WebSocket server, not an ordinary HTTP server or a stored copy of an old reply.

**One connection, used only for this.** Browsers open a **new** TCP connection for each WebSocket, and the page's other requests use other connections. Once switched, it never goes back to HTTP:

```text
SYN, SYN+ACK, ACK                  TCP handshake
GET /chat/57 ... Upgrade           HTTP request
HTTP/1.1 101 Switching Protocols   HTTP reply
pieces, both directions, any time  WebSocket messages (section 75)
close piece, then FIN              end
```

Polling, long polling and SSE are plain HTTP: SSE is just a reply whose `text/event-stream` body never ends. **WebSocket** is a separate protocol. Only its start uses HTTP, one GET and one `101`, so it can share port 80 and pass through proxies like nginx. The switch is the **WebSocket handshake**, separate from and after TCP's.

## 75. WebSocket Messages

After the 101, every message goes as a small header and the message bytes. The rules call this a frame. These notes call it a **piece**, as with HTTP/2 (section 62). The header's first 2 bytes hold four things:

```text
last part?     yes or no; a long message can be split into several pieces (usually yes)
kind           text, binary (any bytes, like a photo), close (ending the WebSocket), ping or pong (section 76)
scrambled?     yes for pieces from the browser, no for pieces from the server
length         how many message bytes follow
```

The driver's side sends "on my way", 9 characters: 2 header bytes (last part, text, not scrambled, length 9) and 9 message bytes. The browser reads the header, then exactly 9 bytes, and passes one complete message to the page. The next byte starts the next header. This is the length-prefix method (section 32), so one `send("ok")` gives exactly one message `"ok"`, never split or joined.

The length space is 7 bits (0 to 127): 0–125 is the length itself, 126 means the real length is in the next 2 bytes (up to 65,535), 127 means the next 8 bytes. So a 9-byte message has a 2-byte header, 1,000 bytes a 4-byte one, 100,000 bytes a 10-byte one.

**No reply.** WebSocket has no request/response rule. The server's "on my way" costs those 11 bytes and nothing comes back. As an HTTP POST, a customer message would cost about 100 bytes of request plus a 50+ byte reply, because HTTP needs a reply (section 70). The kernels' TCP acks happen either way.

**Scrambling.** The browser picks 4 random bytes per piece, the **mask**, and combines message byte 1 with mask byte 1, byte 2 with mask byte 2, and so on, byte 5 with mask byte 1 again. The combining is **XOR**: compare bit by bit, write 1 where the bits differ and 0 where they are the same. `o` (0110 1111) XOR mask 18 (0001 0010) gives 0111 1101, the character `}`. XOR with the same value again gives back the original, so the server reverses it.

**Why browser pieces are scrambled.** Some old machines on the path, like the school's proxy F (section 66), read passing bytes looking for `GET ... HTTP/1.1`. They do not know WebSocket, miss the switch at `101`, and keep reading the bytes as HTTP. Without scrambling, a bad website could make F store a fake page:

1. A student opens a page from `www.badsite.com`, whose owner wrote both the page's JavaScript and the server program.
2. The page opens a WebSocket to its own server through F. F passes everything but still treats the connection as HTTP.
3. The page sends a message whose text is exactly `GET http://www.bluepizza.com/menu HTTP/1.1\r\nHost: www.bluepizza.com\r\n\r\n`. F reads it as a request for bluepizza's menu, but sends it on the connection it has open, to badsite's server.
4. badsite's server answers with bytes that look like an HTTP reply: `200 OK` and a fake menu with other prices or a fake order form.
5. F stores this as its copy of bluepizza's menu, and gives it to every student who asks, for as long as the copy is kept.

With scrambling, step 3 fails: the browser XORs the text with 4 random bytes it chose, so F sees no request. Researchers showed this attack against real proxies in 2011, which is why the rule exists. Server pieces are not scrambled, because page JavaScript does not choose what the server sends.

**Full examples:**

```text
server -> browser, "on my way" (11 bytes)
byte 1     1 000 0001       last part = yes, (3 unused bits), kind = 0001 = text
byte 2     0 000 1001       scrambled = no, length = 9
bytes 3-11 on my way

browser -> server, "ok" (8 bytes)
byte 1     1 000 0001       last part = yes, kind = text
byte 2     1 000 0010       scrambled = yes, length = 2
bytes 3-6  18 52 86 120     the mask
byte 7     }                o scrambled with 18
byte 8     _                k scrambled with 52
```

The mask is part of the header, after the length bytes. So a header is 2 bytes, plus 2 or 8 for a longer length, plus 4 for a mask from the browser: 2 to 14 bytes.

## 76. WebSocket Through nginx, and the Programs

nginx does not pass the browser's `Connection` line on to web2 (section 70), so the request to switch reaches web2 without `Connection: Upgrade`, and web2 never switches. The fix, in nginx's settings file (section 69):

```text
location /chat/ {                              # these lines apply to paths starting with /chat/
    proxy_pass http://shop_servers;            # send to the list web1-web4
    proxy_http_version 1.1;                    # talk HTTP/1.1 to web2 (the default is 1.0, which has no Upgrade)
    proxy_set_header Upgrade $http_upgrade;    # add an Upgrade line with the browser's value, here websocket
    proxy_set_header Connection "upgrade";     # add "Connection: upgrade"
    proxy_read_timeout 3600s;                  # allow 1 hour with no bytes, instead of 60 s
}
```

`proxy_set_header` adds a header to the request nginx sends to web2. These two lines put back what nginx would leave out. When web2 replies `101`, nginx passes it on and stops reading HTTP on both connections. From then on it copies every byte each way without looking. There are still two TCP connections, browser–P and P–web2, and the pieces go through unchanged.

**The server program.** Node's built-in `http` module does not do WebSocket's server side. The common library is `ws`: it checks the `Upgrade` and key lines, computes the accept value, writes the 101, and then reads and writes pieces, including removing the scrambling.

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
    for (const other of rooms.get(id)) if (other !== socket) other.send(data, { binary: isBinary });
  });
  socket.on("close", () => rooms.get(id).delete(socket));
});
server.listen(80);
```

`ws` always gives the message as bytes (a Node `Buffer`), and `isBinary` says what the piece's header said: `false` for text. Passing `{ binary: isBinary }` keeps the forwarded piece the same kind. Without it, `ws` sends a `Buffer` as binary, and the driver's browser would get raw bytes (a `Blob`) instead of the string.

**The browser program:**

```js
const ws = new WebSocket("ws://www.bluepizza.com/chat/57");
ws.onopen = () => ws.send("where are you?");   // runs after the 101 arrives
ws.onmessage = (e) => show(e.data);            // "on my way"
ws.onclose = () => show("chat ended");
```

`ws://` is WebSocket without encryption: a TCP connection to port 80 and the GET with the `Upgrade` lines. `wss://` is the encrypted form, with TLS (Part 10).

**The room, step by step.** The customer's browser C and the driver's phone D both opened `/chat/57` on the same web2 program, so `rooms` holds `"57" -> { socketC, socketD }`. C's page calls `ws.send("where are you?")`. C's browser builds a scrambled text piece of length 14 and sends it. nginx copies the bytes to web2. `ws` reads the piece, removes the scrambling, and runs socketC's "message" handler. The shop's code goes through the room, skips socketC as the sender, and calls `socketD.send(data, { binary: false })`. `ws` writes an unscrambled text piece on D's connection, and D's `onmessage` gets "where are you?". D's reply runs the same steps the other way.

**A silent chat.** If nobody types for an hour, nginx's 1-hour limit closes the connection. The **ping** and **pong** kinds are for this: the server sends a ping every 30 s with `socket.ping()`, and the browser answers each with a pong by itself, unseen by the page. Bytes keep passing through nginx, and the server learns the browser is still there. The same one-process limit as section 72 applies: a customer on web1 and a driver on web3 do not see each other.

## 77. WebSocket Clients, Servers and Libraries

The two sides differ only at the start, plus one rule after it, the same split as TCP's `connect()` and `listen()`:

```text
                    client                                    server
before              connects to an address and port           waits on a port for connections
the switch          sends GET with Upgrade and the key,       reads the GET, computes Accept, sends 101
                    checks the Accept value
pieces it sends     must be scrambled                         not scrambled
after that          sends and receives any time, either side can close
```

The **browser client** is built into every browser, like `fetch()`. **ws** is a Node.js library that gives Node both roles: `new WebSocketServer(...)` (section 76) and `new WebSocket("ws://...")`, for example a script acting as the driver's app for testing. It exists because Node had no WebSocket support for a long time. Node 22 and later include a built-in client, but still no server.

**socket.io** is a Node.js library that does not change WebSocket. It sends ordinary WebSocket messages with its own text format inside, the same pattern as every layer so far (HTTP inside TCP's data, DNS inside UDP's data). `socket.emit("chat", "where are you?")` sends the text message `42["chat","where are you?"]`: `4` means "a message" and `2` "a named event" in socket.io's rules, followed by JSON with the name and data. WebSocket only sees a 27-character text message. socket.io adds named messages, built-in rooms, automatic reconnect, and falling back to long polling if WebSocket cannot connect. It uses its own path, `/socket.io/?EIO=4&transport=websocket`, and its own keep-alive messages (`2` and `3`). Its server sits on its own lower library, engine.io, which uses `ws`. **socket.io-client** is the browser side.

They do not mix: a plain WebSocket client cannot talk to a socket.io server, nor socket.io-client to a plain `ws` server, because each expects a different format inside the messages. That is why Postman has "WebSocket" (plain messages) and "Socket.IO" (you pick an event name and data) as separate options.

---

# Part 10: TLS

Making the bytes unreadable and proving who the server is: AES, Diffie-Hellman, signatures, certificates and the TLS handshake.

---

## 78. Anyone on the Path Can Read the Bytes

A customer logs in to bluepizza from a café's Wi-Fi. The browser sends `POST /login` with the body `user=meera&password=tomato42`. On the way, every wireless chip in range receives the café's air frames (section 40), the café's box holds every frame in memory to do NAT (section 50), and every provider router holds every frame to look up the to-IP. Nothing stops any of them from reading the password. There are three separate problems:

```text
1. read      a machine on the path reads the password
2. change    a machine on the path changes bytes, for example the prices in the menu reply
3. pretend   a machine answers as if it were bluepizza (like the fake DNS answers in section 58)
```

**The idea** is the encryption from section 40, now done by the programs instead of the wireless chip. The browser turns readable bytes into unreadable ones with a secret value, the **key**, that only it and bluepizza's server know, and the server turns them back. Machines on the path see only unreadable bytes. Using the same key for both directions is **symmetric** encryption.

The WebSocket mask (section 75) is not this: it is written in the piece itself, so anyone can reverse it. Even a secret 4-byte key repeated with XOR fails: a machine on the path knows a request starts with `POST`, XORs the first 4 unreadable bytes with `P`, `O`, `S`, `T`, and gets the key.

**AES** (Advanced Encryption Standard) is the method used in practice. It takes 16 readable bytes and a key (16, 24 or 32 bytes; 16 and 32 are common) and gives 16 unreadable bytes. The same key turns them back. Longer data is handled 16 bytes at a time.

* **It is an algorithm**, a fixed list of steps that any program can run in ordinary code. With a 16-byte key it repeats one round 10 times (12 for 24 bytes, 14 for 32). Each round replaces every byte using a fixed table, moves bytes to new positions, mixes groups of 4 bytes, and XORs the result with bytes made from the key.
* **Why it is safe:** the rounds mix the bytes so that even someone who knows the readable bytes and sees the unreadable ones cannot work out the key, except by trying every key. A 16-byte key has 2^128, about 3.4 × 10^38.
* **It has not changed since 2001.** That is the point of a standard: every program must turn the same input and key into the same output, or the two sides could not understand each other. No practical way to break it has been found. What has changed is how AES is applied to data longer than 16 bytes, and how a change on the way is detected (section 82).
* Since about 2010, Intel, AMD and phone processors have instructions that each do one entire AES round, so encryption takes very little time compared with sending.

## 79. Agreeing on a Key in Front of Everyone

AES needs both sides to have the same key, but they have never talked before, and every byte between them can be read. They need to end up with the same secret number anyway.

One piece of math: `x mod n` is the remainder after dividing x by n, so `25 mod 23 = 2`. Two numbers are public, written in the rules: **23** and **5**.

```text
step                                   browser                        server
1. pick a secret number, never sent    6                              15
2. compute 5^secret mod 23             5^6 mod 23 = 8                 5^15 mod 23 = 19
3. send that result to the other       sends 8  ------------->
                                                <-------------        sends 19
4. compute (received)^secret mod 23    19^6 mod 23 = 2                8^15 mod 23 = 2
```

Both get **2**, and neither 6 nor 15 was sent. The browser computed (5^15)^6 and the server (5^6)^15, which are both 5^90, and the remainder steps do not change that.

A machine on the path sees 23, 5, 8 and 19. To get 2 it needs a secret: an x where `5^x mod 23 = 8`. With small numbers it tries x = 1, 2, 3, ... and finds 6. With real sizes, about 600 digits, trying every x would take longer than any computer could run, and no faster general method is known. Forward is fast, backward is not.

This is the **Diffie–Hellman key exchange** (Whitfield Diffie and Martin Hellman, 1976). These notes call the sent values, 8 and 19, the **exchange values**. TLS today mostly uses a version called **X25519**, with different math and 32-byte secrets and exchange values. The shared result goes through a fixed calculation that turns it into the AES key.

## 80. Proving Who Sent a Value

**M in the middle.** Diffie–Hellman stops a machine that only reads. But a machine M on the path can also change bytes. M does its own exchange with the browser, pretending to be the server, and another with the server, pretending to be the browser:

```text
browser  <--- key 1 --->  M  <--- key 2 --->  server
```

M decrypts everything from the browser with key 1, reads it, encrypts it again with key 2 and passes it on. Neither side notices. What is needed: something bluepizza's server attaches to its exchange value that only it could have made, and that the browser can check.

**A pair of keys.** bluepizza's server has two keys made together: **bluepizza's private key**, which never leaves the server, and **bluepizza's public key**, which anyone may have. Two fixed calculations are known to every program:

```text
sign(message, private key)                 -> signature (some bytes)
check(message, signature, public key)      -> yes or no
```

`check` says **yes** only if the signature was made by `sign` on exactly that message, with the private key that belongs to that public key.

```text
normal:          server signs "my value is 19" with bluepizza's private key -> signature 1
                 browser: check("my value is 19", signature 1, bluepizza's public key) -> yes
M changes it:    check("my value is 10", signature 1, bluepizza's public key) -> no   (signed "19", not "10")
M signs it:      check("my value is 10", M's signature, bluepizza's public key) -> no (made with M's private key)
M wants a yes:   needs sign("my value is 10", bluepizza's private key), which never leaves bluepizza's server
```

A **signature** is bytes attached to a message showing which private key made them and that the message has not changed since. Unlike the TCP checksum (section 27), which anyone can recompute after changing bytes, only the private key's holder can make one. In TLS the server signs not one number but 32 bytes calculated from its copy of all handshake messages so far, including both exchange values (with SHA-256, the same kind of calculation as SHA-1 in section 74). If M changed any of them, `check` says no (section 82).

The checking key is the **public key**, the signing key the **private key**, which has nothing to do with private IP addresses. A common signing method is **RSA** (Rivest, Shamir and Adleman, 1977). TLS also allows methods built on the same kind of math as X25519. The math inside `sign` and `check` is not covered here.

## 81. Someone the Browser Already Trusts

The browser needs bluepizza's public key to run `check`. If the server sends it during the connection, M can replace it with its own and sign with its own private key. So the browser cannot trust a public key that arrives over M's path. It can trust a public key **signed by someone whose public key it already has**, if it got that key before any connection, not over the network.

**The list.** Every operating system or browser comes with public keys from a small number of organizations, the **certificate authorities (CAs)**: on Ubuntu a set of files under `/etc/ssl/certs/`, and Firefox keeps its own list. It has around 150 entries. One is **Let's Encrypt**, a non-profit that signs for free.

**Getting signed.** The CA never makes or sees bluepizza's private key. On bluepizza's server, a program, usually certbot (Let's Encrypt's tool), makes the key pair, saves the private key to disk and sends only the public key in a request: "here is the public key for `www.bluepizza.com`, please sign that". Let's Encrypt must check that the request comes from whoever runs that name. It replies with a random text, for example `k7Qz...`. bluepizza's server must make that text available at `http://www.bluepizza.com/.well-known/acme-challenge/...`. Let's Encrypt looks up the name in DNS itself, GETs that path, and checks the text. Only whoever controls the real server can do that. Then it signs a small document with its own private key:

```text
name            www.bluepizza.com
public key      bluepizza's public key
valid from      2026-10-01
valid until     2026-12-30
signed by       Let's Encrypt
signature       made with Let's Encrypt's private key over all the lines above
```

This signed document is a **certificate**. Let's Encrypt's are valid for 90 days.

**Signature and name are two separate checks**, and both must pass. The signature check means "these exact bytes were signed by this CA and not one byte has changed": the browser runs SHA-256 over the certificate's lines (X), uses the CA's public key on the signature (Y), and compares X with Y. It says nothing about which name the browser wanted. Say M runs `www.badsite.com` and got a real certificate for it. Unchanged, its signature passes but the name fails. If M edits the name to `www.bluepizza.com`, X changes, Y does not, and the signature fails. Only a certificate Let's Encrypt signed for `www.bluepizza.com` passes both, and it gives one only to whoever controls bluepizza's real server.

**The certificate alone proves nothing.** It is public, and anyone, M included, can copy it. What proves the server is bluepizza's is the signature over the handshake (section 80), which needs the private key file. With certbot the files are `/etc/letsencrypt/live/www.bluepizza.com/privkey.pem` (the private key) and `fullchain.pem` (the certificate plus the intermediate's, below), and nginx points to them with `ssl_certificate_key` and `ssl_certificate`.

**The chain.** A stolen CA private key could sign certificates for any name. So the CA keeps it on machines with no network and uses it rarely, only to sign a certificate for a second key pair, the **intermediate**, whose key signs site certificates every day:

```text
ISRG Root X1 (Let's Encrypt's key in the browser's list)
   signs ->  intermediate certificate
                signs ->  www.bluepizza.com certificate
```

The server sends its certificate plus the intermediate's, and the browser checks each signature up the chain to a key in its list, the **root**.

## 82. The TLS Handshake, Step by Step

**Names for the values:**

* **Exchange value:** what each side sends in the Diffie–Hellman step, like 8 and 19 in section 79, made from a secret number never sent.
* **The key:** the AES key both compute from the two exchange values.
* **bluepizza's certificate:** the CA-signed document with its name and public key.
* **bluepizza's handshake signature:** the server's signature, with its private key, over its copy of all handshake messages so far.
* **Finished check:** a short value each side computes from the key and its copy of all handshake messages. If the other side computes the same value, both have the same key and saw the same messages. It has nothing to do with TCP's FIN.

**Short answers.** It runs after the TCP handshake (section 25), before any HTTP. It runs inside the program as a library, not in the kernel: nginx and Node.js use OpenSSL, Chrome uses BoringSSL, Firefox uses NSS. The kernel sees ordinary TCP data it cannot read. It is a protocol, **TLS** (Transport Layer Security). The current version, TLS 1.3, was published in 2018 (RFC 8446). It does not fit the layer numbering cleanly (section 31): it sits above TCP and below HTTP, and some call it layer 6. It takes 1 round trip after TCP's (TLS 1.2 needed 2). A **trip** is bytes going one way, say 25 ms. A **round trip** is there and back, 50 ms. Counting round trips means counting how often one side must stop and wait for an answer.

**Who is who:**

```text
laptop                                         server (P)
page JavaScript       the shop's page code     nginx's HTTP part    reads requests, writes replies
browser's HTTP part   writes/reads HTTP text   nginx's TLS part     library inside nginx (OpenSSL)
browser's TLS part    library in the browser   server kernel        TCP, IP
laptop kernel         TCP, IP
```

In each program, the HTTP part writes `GET /menu ...` and reads readable replies. The TLS part encrypts on the way down and decrypts on the way up. The kernel only carries the TLS bytes as TCP data. Both sides keep a readable copy of every handshake message sent and received: the browser's hello, the server's hello and the certificates. The server signs its copy and the browser checks against its own. If M changed the server's exchange value on the way, the copies differ and `check` says no.

**TCP handshake, round trip 1, 0–50 ms.**

1. Page JavaScript calls `fetch("https://www.bluepizza.com/menu")`.
2. The browser's HTTP part asks the laptop kernel to connect to `198.51.100.7` port 443.
3. The kernels exchange SYN and SYN+ACK. The laptop kernel sends the ACK at once in its own frame, and only then does `connect()` return.

**TLS handshake, round trip 2, 50–100 ms.**

4. The browser's TLS part picks a secret number, computes its exchange value, and writes a readable hello (no key exists yet): "I want `www.bluepizza.com`, I can use AES, here is my exchange value".
5. The laptop kernel sends it as TCP data, in the frame after the ACK: `[MAC][IP: to 198.51.100.7][TCP: to port 443, ACK+PSH][TLS header: type 22 handshake, length ~300][hello][CRC]`.
6. nginx's TLS part picks its own secret number, computes its exchange value, and computes **the key**.
7. nginx's TLS part writes four messages: its hello with its exchange value (readable, since the browser has no key yet), then encrypted with the key: bluepizza's certificate and the intermediate's, the handshake signature, and its Finished check. That is about 3,000 bytes, so 3 frames at 1,460 data bytes each (section 28).
8. The browser's TLS part computes **the key** from the server's exchange value and its own secret, decrypts the rest, and checks the certificate, the handshake signature and the Finished check (section 83). If any fails, it closes the connection.

**Handshake ends and HTTP starts, round trip 3, 100–150 ms.**

9. The browser's TLS part writes its own encrypted Finished check.
10. The browser's HTTP part writes the readable request, `GET /menu HTTP/1.1\r\nHost: www.bluepizza.com\r\n\r\n` (47 bytes), to its TLS part, which encrypts it.
11. The laptop kernel sends the Finished check and the request: `[TLS header: type 23][Finished check]` and `[TLS header: type 23, length 64][64 unreadable bytes]`.
12. nginx's TLS part checks the browser's Finished check, reads the next record's length, checks its TAG (below), decrypts the 47 request bytes, and gives them to nginx's HTTP part.
13. nginx's HTTP part writes the reply, which nginx's TLS part encrypts. The browser's TLS part decrypts it, and `fetch` returns the body to the page.

The lone ACK in step 3 adds no wait. A round trip counts when one side must receive an answer before sending again. An ACK is never answered (section 25), and the hello needs nothing back first, so it follows the ACK at about 50 ms. Without TLS the reply would arrive at 100 ms. TLS adds one round trip.

**What literally gets encrypted** for the request:

```text
input to AES:   the 47 request bytes + 1 byte meaning "this is HTTP data"   = 48 readable bytes
AES output:     48 unreadable bytes + a 16-byte TAG                         = 64 bytes
adds header:    type 23, version, length 64                                 = 5 bytes, readable
written to the laptop kernel: 69 bytes
```

The **TAG** is computed from the key and the encrypted bytes. The receiver recomputes it, and if even one byte was changed it does not match and the connection is closed. M cannot make a new TAG without the key. This solves problem 2 from section 78 (change). The server's encrypted handshake messages are encrypted the same way.

Steps 4–9 are the **TLS handshake**. HTTP inside TLS is **HTTPS**. In Node.js, the `https` module is `http` with the TLS part between the code and the kernel.

**Port 443.** HTTPS uses port 443 and plain HTTP stays on 80, because a server must know what the first bytes on a new connection will be: a binary TLS hello or HTTP text like `GET /`. Many sites run both, but the program on port 80 only replies `301 Moved Permanently` with `Location: https://www.bluepizza.com/...`, telling the browser to repeat the request at the HTTPS address.

## 83. The Browser's Checks, One by One

The browser's TLS part runs these after decrypting the server's messages, which include two certificates: bluepizza's and the intermediate's (section 81).

```text
check                                       how                                                    what it stops
1. made by a CA in my list?                 1a: check(bluepizza's certificate lines, its           M making up its own certificate for
                                            signature, the intermediate's public key)             www.bluepizza.com: its signature leads
                                            1b: check(intermediate's lines, its signature,         to no key in the list
                                            ISRG Root X1's public key from the built-in list)
2. is the name the one I asked for?         compare the certificate's names (e.g. bluepizza.com,   M sending its own real certificate for
                                            www.bluepizza.com) with the address's name             www.badsite.com: check 1 passes, this fails
3. is today inside the dates?               compare "valid from/until" with the laptop's clock;    old certificates, whose private keys may
                                            a clock wrong by months fails valid sites              have been stolen or leaked since
4. did bluepizza's private key holder       check(my copy of the handshake messages, the           M sending bluepizza's real certificate
   sign this handshake?                     handshake signature, bluepizza's public key)          (no private key to sign with), and M
                                                                                                   replacing the server's exchange value
                                                                                                   (my copy then differs from what was signed)
5. does the server have the same key?       compute the Finished check I expect from the key       a server that ended up with a different key
                                            and my copy, compare with the server's                 or saw different messages
```

Checks 1–4 prove who the server is. Check 5 proves it has the same AES key. In step 12 of section 82, nginx's TLS part does check 5 the other way round with the browser's Finished check, which is how the server finds out if M changed the browser's hello.

When a check fails, the browser closes the connection and shows a warning page instead of the site. In Chrome, check 1 gives `NET::ERR_CERT_AUTHORITY_INVALID`, check 2 `NET::ERR_CERT_COMMON_NAME_INVALID`, check 3 `NET::ERR_CERT_DATE_INVALID`, and checks 4 and 5 close the connection with an error.

## 84. What TLS Bytes Look Like

TLS bytes come in two levels: **records** outside and **messages** inside.

**The record** (the "TLS group"). Everything the TLS part writes is a sequence of records, each a 5-byte header plus content, the length-prefix method from section 32:

```text
field     size      meaning
type      1 byte    22 = handshake message (readable), 23 = encrypted content,
                    21 = alert (an error, e.g. "bad certificate", just before closing)
version   2 bytes   always 3.3, kept so old middle machines do not reject it; the real version is in the hello
length    2 bytes   content bytes that follow (at most 16,384 readable bytes, a little more with the TAG)
content   length    one or more messages, readable or encrypted
```

**Handshake messages** sit inside the content the way a TCP group sits inside the IP group's data, each with its own header: 1 byte type (1 client hello, 2 server hello, 8 extra settings, 11 certificate, 15 handshake signature, 20 Finished check) and 3 bytes length. The browser's hello is a 5-byte record header saying 300 bytes follow, and inside those 300 bytes a 4-byte message header (type 1, length 296) and the 296-byte body. A record can also hold several messages back to back.

**The client hello:**

```text
[record: type 22, version 3.3, length ~300]
  [message: type 1 (client hello), length ~296]
    [version 3.3]
    [random: 32 bytes]                         new random bytes for every connection
    [session id: 32 bytes]                     kept only for old middle machines
    [methods I can use: 13 01, 13 02, 13 03]   AES with a 16-byte key, AES with a 32-byte key,
                                               ChaCha20 (for processors without AES instructions)
    [compression: none]                        kept only for old machines
    [extensions, each type (2 bytes), length (2 bytes), value:
       server name           www.bluepizza.com
       versions I support    1.3
       key share             X25519 + browser's exchange value (32 bytes)
       signing methods I can check
       next protocol         h2, http/1.1]
```

* **random** makes every handshake's messages different, so a signature recorded from an old connection cannot be reused.
* **server name** is **SNI** (Server Name Indication). One server at one IP can run `www.bluepizza.com` and `www.greencafe.com` (section 59), and must know which certificate to send before any HTTP arrives.
* **next protocol** is how the sides choose the HTTP version: the browser lists what it speaks, the server picks. Its name is **ALPN** (Application-Layer Protocol Negotiation), and it is why browsers use HTTP/2 only with encryption (section 62).

**The server's messages:**

```text
[record: type 22]                                       readable
  [message: type 2 (server hello)]  version, random, session id copied, method chosen 13 01,
                                    extensions: version 1.3, key share: X25519 + server's exchange value
[record: type 23][~3,000 encrypted bytes + 16-byte TAG] unreadable on the path; after decryption:
  [type 8 extra settings, e.g. next protocol h2][type 11 certificates][type 15 signature][type 20 Finished, 32 bytes]
  [1 byte: real type = handshake]
```

**After the handshake** every record is `[type 23, version 3.3, length 64][48 encrypted + 16-byte TAG]`. After decryption, the last byte gives the **real type**. The outside type is always 23, so a machine on the path cannot tell what a record holds:

```text
real type   what is inside           example after the handshake
23          HTTP bytes               the GET request, the reply
21          alert                    "close notify": TLS's own "I am closing now" message
22          handshake message        "new key": switch to a fresh AES key on a long connection
```

In a frame, TLS records are TCP data, as HTTP was before, and HTTP is now inside the TLS content: `[MAC][IP][TCP][TLS record header][TLS content][CRC]`.

**What the school's proxy sees.** With HTTPS, the `Host:` line is encrypted, so F (section 66) cannot read it. F sees the name in two places outside HTTP: the readable SNI in the client hello, and, with the proxy setting on, one short plain request the browser first sends F, `CONNECT www.bluepizza.com:443 HTTP/1.1`, meaning "open a TCP connection to this name and port, then copy bytes both ways". After that, F only copies encrypted bytes.

## 85. Where TLS Ends When There Is a Load Balancer

With HTTPS, the browser does its TLS handshake with whatever answers at `198.51.100.7`. With P or Q (sections 67–68) in front, that is not web1–web4.

**Case 1: P (L7, nginx) ends TLS.** P has the certificate and private key on its own disk:

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

`ssl` is the old name: SSL (Secure Sockets Layer) was TLS's earlier version, and nginx kept the word. The browser's TLS part does the handshake with nginx's TLS part. nginx decrypts `POST /order ...`, its HTTP part picks web4 and adds `X-Forwarded-For`, and P's kernel sends the readable request to web4 on a second connection. The reply is encrypted by nginx for the browser. The TLS connection is browser to P only, and bytes between P and web4 are readable but stay in the shop's local network. This is **TLS termination**. It keeps the certificate and key in one place, lets P read HTTP (route by path, add `X-Forwarded-For`, speak HTTP/2 to the browser), and spares web1–web4 the encryption work. The cost: P sees every password and order, so whoever controls P controls all of that.

**Case 2: Q (L4) passes TLS through.** Q only changes the to-IP in each frame (section 68) and has no key, so the TLS records pass unchanged and the TLS connection is browser to web2 directly. Each of web1–web4 then needs the certificate and private key, since the browser could reach any of them. This is **TLS passthrough**. Q still cannot read the path or add `X-Forwarded-For`. But the client hello is readable, so an L4 balancer can read the SNI name and pick a group of servers by it without decrypting anything (in nginx, the `ssl_preread` setting).

**Ending TLS without reading HTTP.** These are separate things, since TLS sits below HTTP. On AWS the Application Load Balancer (L7) ends TLS with a certificate stored in AWS. The Network Load Balancer (L4) can pass TLS through like Q, or end TLS itself. When it does, it cannot pass frames on as they arrive: it takes part in the handshake, and must collect every frame of a record (up to about 16 KB) before the TAG check and decryption. Then it writes the readable bytes into its own second connection to the server. So it works like P, two connections and new frames, except that it never reads the HTTP and picks a server once per connection. By section 68's rule, "the highest layer it reads", that is above layer 4. AWS and most people still call it L4, meaning "does not read HTTP and picks once per connection". The pure L4 case is Q with passthrough.

**TLS between P and the web servers.** `proxy_pass https://shop_servers;` makes nginx do a TLS handshake with web2 (exchange, key, AES) and send HTTP inside it, instead of plain HTTP with `http://`. A TLS 1.3 handshake always includes the key exchange, so "use TLS" means "do the exchange and encrypt" with no separate setting. Both sides must agree: web2's program must listen with TLS, for example Node's `https` module with a key file and a certificate file. A program expecting plain HTTP that receives a TLS hello reads binary bytes instead of `GET /`, and the connection fails.

**Encryption without checking the certificate.** The server always sends a certificate. The client's check is optional. Browsers always check, but nginx checks web2's only with `proxy_ssl_verify on`, which is off by default. A common setup gives each web server a **self-signed certificate** (signed with its own private key instead of a CA's, made with one `openssl` command) and lets nginx connect without checking. The exchange still runs, so all bytes between P and web2 are encrypted with AES. What is lost is protection against M from section 80: a machine between P and web2 doing a separate exchange with each. This protects against machines that only read the shop's network, not one that pretends to be web2. The question is not whether the shop trusts web1–web4, but whether anything between P and them could pretend to be them. Other options: the shop makes its own CA key pair, signs web1–web4's certificates with it, and gives P the CA's public key (`proxy_ssl_trusted_certificate` with `proxy_ssl_verify on`), so P really checks without Let's Encrypt. Or TLS 1.3's pre-shared key, where both sides are given the same secret in advance instead of a certificate, uncommon for this.

---

# Part 11: Cloud Networking

The shop's network rented from AWS: VPC, subnets, internet gateway, NAT gateway, security groups and network ACLs.

---

## 86. What "Renting a Computer" Actually Is

So far the shop owns P, the switch and web1–web4 in its own room. Now it rents computers from a company like AWS instead, with no room, cable or switch it can touch.

AWS owns buildings full of physical computers, say each with 96 processor cores and 384 GB of memory, joined by AWS's own cables, switches and routers. When the shop asks for "a computer with 2 cores and 4 GB of memory", a program run by AWS on one physical computer splits it and gives 2 cores and 4 GB to a pretend computer. It runs its own Linux kernel, which sees a processor, memory and a network card as on a real computer.

* **Virtual machine (VM):** a pretend computer made from part of a physical one.
* **EC2 instance:** AWS's name for a rented VM (EC2 = Elastic Compute Cloud).

The VM's network card is not a physical card. When web1's kernel puts a frame on it, a part run by AWS on the physical computer receives the bytes. These notes call this **AWS's part**. The same physical computer runs VMs for other customers, such as greencafe, and each picks its own private addresses (section 49), so both can use `10.0.0.x`:

```text
physical computer H1               physical computer H2
  bluepizza web1   10.0.0.11         bluepizza web2   10.0.0.12
  greencafe app1   10.0.0.11         greencafe app2   10.0.0.12
```

## 87. VPC

A frame from bluepizza's web1 to `10.0.0.12` must reach only bluepizza's web2, not greencafe's app2. AWS keeps a separate table per customer network, saying which physical computer each VM address lives on, and looks up every frame only in its own customer's table:

```text
table for bluepizza (id vpc-111)      table for greencafe (id vpc-222)
  10.0.0.11 -> physical computer H1     10.0.0.11 -> physical computer H1
  10.0.0.12 -> physical computer H2     10.0.0.12 -> physical computer H2
```

Real IDs are `vpc-` followed by 17 hex characters. `vpc-111` is a placeholder.

1. web1's kernel sends an ARP broadcast (section 9) for `10.0.0.12`. AWS's part on H1 sends it nowhere: it reads the bluepizza table and answers web1 with a MAC address itself.
2. web1's kernel sends the frame: MAC group, IP group (`10.0.0.11` to `10.0.0.12`), TCP group, data.
3. AWS's part on H1 knows the frame came from a bluepizza VM, and the bluepizza table says `10.0.0.12 -> H2`.
4. It puts the whole frame, unchanged, inside a new packet with an outer header: from H1's address, to H2's, network ID `vpc-111`. The outer addresses belong to AWS's own building network. This is encapsulation (section 14) again: `[outer header: H1 -> H2, vpc-111][web1's frame]`. AWS's exact outer header format is not public.
5. AWS's switches and routers carry it using only the outer header.
6. AWS's part on H2 removes the outer header, reads `vpc-111`, and gives the inner frame to bluepizza's web2, whose kernel sees a normal frame from `10.0.0.11`. greencafe's app2 never gets it.

One customer's separate network, with its own address range and table, is a **VPC** (Virtual Private Cloud). The shop picks its range when creating it, for example `10.0.0.0/16` (section 17).

## 88. Subnets and Route Tables

The VPC is fully private: nothing on the internet can reach `10.0.0.x`, and nothing in it can reach the internet. P must be reachable from the internet, web1–web4 must not, and the shop has no router box of its own here.

The shop splits the VPC's range into **subnets**, and the room's addresses from section 67 change:

```text
VPC        10.0.0.0/16    10.0.0.0 to 10.0.255.255
subnet A   10.0.1.0/24    10.0.1.0 to 10.0.1.255     P at 10.0.1.10
subnet B   10.0.2.0/24    10.0.2.0 to 10.0.2.255     web1-web4 at 10.0.2.11 to 10.0.2.14
```

In every subnet AWS keeps `.0`, `.1`, `.2`, `.3` and `.255` for itself. `.1` is the default gateway (section 16), which in the room was the home box's router part. Here AWS's part answers for it, so P cannot be `10.0.1.1`.

Each subnet is linked to a **route table**, which AWS's part reads for every packet a VM sends. As in section 17, the larger number after the slash wins:

```text
route table for subnet A                                 route table for subnet B
  10.0.0.0/16 -> local (the VPC table, section 87)        10.0.0.0/16 -> local
  0.0.0.0/0   -> internet gateway (every other address)

web2 -> 10.0.2.11    matches local                            delivered inside the VPC
web2 -> 8.8.8.8      no row in subnet B's table               dropped; web2's kernel gets no reply
P    -> 8.8.8.8      matches 0.0.0.0/0 -> internet gateway    sent to the internet gateway
```

The **internet gateway** is AWS's exit from the VPC to the internet, which the shop adds to the VPC (section 89). A subnet whose route table has a row to it is a **public subnet**, one without is a **private subnet**. Nothing else makes a subnet public or private.

## 89. Internet Gateway

P's kernel only knows `10.0.1.10`, and internet routers have no rows for `10.x.x.x` (section 49). So the shop asks AWS for a public address and attaches it to P, and the internet gateway keeps the row `198.51.100.7 <-> 10.0.1.10`. The automatic kind of public address changes when the VM is stopped and started. An **Elastic IP** stays until the shop gives it back.

```text
incoming   browser 203.0.113.50 : 51000 -> 198.51.100.7 : 443
           internet routers carry it to AWS, which owns that range (section 49)
           internet gateway rewrites to-IP to 10.0.1.10, recomputes checksums, leaves ports alone
           VPC table: 10.0.1.10 -> H3; encapsulated, carried, unwrapped
           P's kernel sees 203.0.113.50 : 51000 -> 10.0.1.10 : 443
outgoing   P's kernel sends 10.0.1.10 : 443 -> 203.0.113.50 : 51000
           subnet A's table: 0.0.0.0/0 -> internet gateway, which rewrites from-IP to 198.51.100.7
```

P's kernel never sees `198.51.100.7`: `ip addr` on P shows only `10.0.1.10`. Unlike the home box (section 50), the internet gateway maps exactly one private address to each public one, leaves ports unchanged, and its row is fixed, so a browser can start a new connection to P, where the home box would drop it (section 51).

A VM needs both a route table row `0.0.0.0/0 -> internet gateway` and a public address in the gateway's table to talk to the internet. web1–web4 have neither. Even in subnet A without a public address, web1's packets would find no row in the gateway and be dropped.

## 90. NAT Gateway

web1–web4 still need outgoing connections, for example `apt` updates or a payment company's server, but nobody outside should be able to start one to them. A **NAT gateway** is a NAT like the home box's (section 50) that AWS runs in the shop's VPC. The shop puts it in subnet A with a private address and an Elastic IP, and points subnet B's other traffic at it:

```text
NAT gateway                  private 10.0.1.50 (subnet A), Elastic IP 198.51.100.20
internet gateway table       198.51.100.7 <-> 10.0.1.10 (P),   198.51.100.20 <-> 10.0.1.50 (NAT gateway)
route table for subnet B     10.0.0.0/16 -> local,   0.0.0.0/0 -> NAT gateway
```

**web1 downloads an update from `192.0.2.80 : 80`:**

1. web1's kernel sends from `10.0.2.11 : 40000`. Subnet B's table sends it to the NAT gateway.
2. The NAT gateway rewrites the from part to `10.0.1.50 : 61000`, recomputes checksums, and stores the row `10.0.2.11 : 40000 <-> port 61000 (to 192.0.2.80 : 80)`.
3. It sends the packet on. Being in subnet A, it matches `0.0.0.0/0 -> internet gateway`, which rewrites `10.0.1.50` to `198.51.100.20` (section 89). The update server sees `198.51.100.20 : 61000`.
4. The reply comes to `198.51.100.20 : 61000`. The internet gateway rewrites the to-IP to `10.0.1.50`, the NAT gateway finds row 61000 and rewrites to `10.0.2.11 : 40000`, and web1's kernel gets it.

As with the home box, many private addresses share one public address and ports change. A new packet from outside to `198.51.100.20 : 62000` finds no row and is dropped, exactly as in section 51. The NAT gateway must sit in subnet A, because its own packets need the `0.0.0.0/0 -> internet gateway` row, which only subnet A's table has.

## 91. Security Groups

So far any program on P, on any port, can be reached from the internet, and any VM can connect to any other on any port.

A **security group** is a list of allow rules attached to a VM's network card. AWS's part checks it before a packet reaches the VM and after one leaves, so the VM's kernel never sees blocked packets. **Inbound rules** cover packets coming to the VM, **outbound rules** packets leaving it. Only allow rules exist, and anything not allowed is dropped. A new security group has no inbound rules and one outbound rule allowing everything. The shop makes two:

```text
sg-p   (attached to P)           inbound:  TCP 80 from 0.0.0.0/0,  TCP 443 from 0.0.0.0/0     outbound: everything
sg-web (attached to web1-web4)   inbound:  TCP 80 from sg-p                                  outbound: everything
```

`from sg-p` means "from any VM that has sg-p attached", right now P. Port 80 on web1–web4 is the web program's port, as in section 67.

AWS's part also keeps a table of the connections it has allowed, and a packet belonging to a stored connection passes both ways even if no rule matches. Because of this table, a security group is **stateful**.

1. **A browser connects to P on 443.** The inbound rule matches, the packet passes, and the connection is stored, so P's replies pass.
2. **Someone connects to P on port 22.** No rule matches, and AWS's part drops the packet silently. This is not the RST "connection refused" from section 67: the connecting kernel resends its SYN a few times and gives up, about 2 minutes on Linux with default settings.
3. **web3 connects to web1 on 80.** web3 does not have sg-p, so it is dropped.
4. **web1 downloads an update (section 90).** The outbound rule allows it and the connection is stored. The reply from `192.0.2.80 : 80` matches no inbound rule, but the stored row lets it in.

## 92. Network ACLs

Security groups can only allow. Suppose `203.0.113.0/24` keeps sending bad requests to P, and the shop wants to block it for all of subnet A without editing every VM's security group.

A **network ACL** (access control list) is a numbered list of rules attached to a subnet, checked when a packet enters or leaves the subnet (not between two VMs in it). It differs from a security group in three ways: it has **deny** rules too; rules are read from the lowest number up and the first match decides; and it keeps no connection table, so it is **stateless** and a reply is checked like any new packet. The browser-to-P part of subnet A's ACL (a full list also needs rows for the NAT gateway and for P's connections to web1–web4):

```text
inbound                                              outbound
  100  all traffic  from 203.0.113.0/24  DENY          100  TCP 1024-65535  to 0.0.0.0/0  ALLOW
  200  TCP 443      from 0.0.0.0/0       ALLOW          *   all traffic     to 0.0.0.0/0  DENY
  210  TCP 80       from 0.0.0.0/0       ALLOW
  *    all traffic  from 0.0.0.0/0       DENY
```

`*` is the last rule, always there and impossible to remove. The browser in section 89 at `203.0.113.50` is inside the blocked range, so the normal customer here is meera at the example address `198.18.0.25`.

1. **The bad range connects** (`203.0.113.9 : 50000` to P:443). Rule 100 matches first and drops it. Rule 200 is never read.
2. **meera connects** (`198.18.0.25 : 51000` to P:443). Rule 100 does not match, rule 200 allows it, then sg-p allows it too. Both checks must allow a packet.
3. **P replies** to `198.18.0.25 : 51000`. With no stored connection, the outbound rules are checked. 51000 is the ephemeral port meera's kernel picked (section 19). Linux picks from 32768–60999 and Windows from 49152–65535, which is why outbound rule 100 allows 1024–65535. Without it the reply is dropped, even though sg-p would allow it.

A packet from the internet to P passes internet gateway -> subnet A's network ACL -> sg-p -> P's kernel, and a reply the same checks in reverse.
