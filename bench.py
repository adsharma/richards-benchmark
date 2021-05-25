#!/usr/bin/env python3
#  C version of the systems programming language benchmark
#  Author:  M. J. Jordan  Cambridge Computer Laboratory.
#
#  Modified by:  M. Richards, Nov 1996
#    to be ANSI C and runnable on 64 bit machines + other minor changes
#  Modified by:  M. Richards, 20 Oct 1998
#    made minor corrections to improve ANSI compliance (suggested
#    by David Levine)
#  Translated to Python by: A. Meyers, Mar 2010 USA

# To run this program type something like:

#   python
#   import bench
#   import profile
#   profile.run('bench.bench()')

# or (under Linux)

#   time python bench.py

# For character-based output.
from sys import stdout
from dataclasses import dataclass
from enum import IntEnum, IntFlag
from typing import Any, Callable, Optional, List, Union

# Change False to True for a version that obeys
# the main loop 100x more often)

Count = 10000
Qpktcountval = 23246
Holdcountval = 9297


MAXINT = 32767

BUFSIZE = 3

class InterfaceState(IntEnum):
    I_IDLE = 1
    I_WORK = 2
    I_HANDLERA = 3
    I_HANDLERB = 4
    I_DEVA = 5
    I_DEVB = 6


class SocketState(IntFlag):
    RUNBIT = 0
    PKTBIT = 1
    WAITBIT = 2
    HOLDBIT = 4
    NOTPKTBIT = ~1
    NOTWAITBIT = ~2
    NOTHOLDBIT = 0xFFFB

    RUN = RUNBIT
    RUNPKT = RUNBIT | PKTBIT
    WAIT = WAITBIT
    WAITPKT = WAITBIT | PKTBIT
    HOLD = HOLDBIT
    HOLDPKT = HOLDBIT | PKTBIT
    HOLDWAIT = HOLDBIT | WAITBIT
    HOLDWAITPKT = HOLDBIT | WAITBIT | PKTBIT


class Kind(IntEnum):
    K_DEV = 1000
    K_WORK = 1001

@dataclass
class Packet:
    link: Union["Packet", int]
    id: int
    kind: Kind
    a1: int = 0

    def __post_init__(self):
        self.a1 = 0
        self.a2 = [0] * (BUFSIZE + 1)


alphabet = "0ABCDEFGHIJKLMNOPQRSTUVWXYZ"

tasktab: List[Union[int, "Task"]] = [10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]


@dataclass
class Task:
    id: int
    pri: int
    wkq: Union[int, "Task"]
    state: SocketState
    fn: Callable
    v1: Union[int, "Task"]
    v2: Union[int, "Task"]
    def __post_init__(self):
        global tasklist
        tasktab[self.id] = self
        self.link = tasklist
        tasklist = self

# Variables used in global statements
tasklist = 0
tcb = None
taskid = 0
v1: Union[int, Task, Packet] = 0
v2: Union[int, Task, Packet] = 0
qpktcount = 0
holdcount = 0
tracing = 0
layout = 0


def trace(a):
    global layout
    layout -= 1
    if layout <= 0:
        stdout.write("\n")
        layout = 50

    stdout.write(chr(a))


def schedule():
    global tcb, taskid, v1, v2
    while tcb != 0:
        pkt = 0
        assert isinstance(tcb, Task)

        sw = tcb.state
        done = False
        if sw == SocketState.WAITPKT:
            pkt = tcb.wkq
            tcb.wkq = pkt.link
            if tcb.wkq == 0:
                tcb.state = SocketState.RUN
            else:
                tcb.state = SocketState.RUNPKT

        if sw in [SocketState.WAITPKT, SocketState.RUN, SocketState.RUNPKT]:
            taskid = tcb.id
            v1 = tcb.v1
            v2 = tcb.v2
            if tracing:
                trace(taskid + ord("0"))

            newtcb = tcb.fn(pkt)
            tcb.v1 = v1
            tcb.v2 = v2
            tcb = newtcb
            done = True

        if sw in [SocketState.WAIT, SocketState.HOLD, SocketState.HOLDPKT, SocketState.HOLDWAIT, SocketState.HOLDWAITPKT]:
            tcb = tcb.link
            done = True

        if not done:
            return


def wait():
    assert isinstance(tcb, Task)
    tcb.state |= SocketState.WAITBIT
    return tcb


def holdself():
    global holdcount
    holdcount += 1
    assert isinstance(tcb, Task)
    tcb.state |= SocketState.HOLDBIT
    return tcb.link


def findtcb(id: int) -> Union[int, Task]:
    t = 0
    if 1 <= id and id <= tasktab[0]:
        t = tasktab[id]
    if t == 0:
        print("Bad task id %i" % id)
    return t


def release(id) -> Union[int, Task]:
    t = findtcb(id)
    if t == 0:
        return 0

    assert isinstance(t, Task)
    assert isinstance(tcb, Task)
    t.state &= SocketState.NOTHOLDBIT
    if t.pri > tcb.pri:
        return t

    return tcb


def qpkt(pkt):
    global qpktcount
    t = findtcb(pkt.id)
    if t == 0:
        return t
    assert isinstance(t, Task)
    assert isinstance(tcb, Task)

    qpktcount += 1

    pkt.link = 0
    pkt.id = taskid

    if t.wkq == 0:
        t.wkq = pkt
        t.state |= SocketState.PKTBIT
        if t.pri > tcb.pri:
            return t
    else:
        append(pkt, t.wkq)

    return tcb


def idlefn(pkt):
    global v1, v2
    assert isinstance(v1, int)
    assert isinstance(v2, int)
    v2 -= 1
    if v2 == 0:
        return holdself()

    if (v1 & 1) == 0:
        v1 = (v1 >> 1) & MAXINT
        return release(InterfaceState.I_DEVA)
    else:
        v1 = ((v1 >> 1) & MAXINT) ^ 0xD008
        return release(InterfaceState.I_DEVB)


def workfn(pkt):
    global v1, v2
    if pkt == 0:
        return wait()
    else:

        assert isinstance(v1, int)
        assert isinstance(v2, int)
        v1 = InterfaceState.I_HANDLERA + InterfaceState.I_HANDLERB - v1
        pkt.id = v1

        pkt.a1 = 0
        for i in range(0, BUFSIZE + 1):
            v2 += 1
            if v2 > 26:
                v2 = 1
            pkt.a2[i] = ord(alphabet[v2])
        return qpkt(pkt)


def handlerfn(pkt):
    global v1, v2
    if pkt != 0:
        if pkt.kind == Kind.K_WORK:
            x = Packet(v1, 0, Kind.K_DEV)
            append(pkt, x)
            v1 = x.link
        else:
            x = Packet(v2, 0, Kind.K_DEV)
            append(pkt, x)
            v2 = x.link

    if v1 != 0:
        workpkt = v1
        count = workpkt.a1

        if count > BUFSIZE:
            v1 = v1.link
            return qpkt(workpkt)

        if v2 != 0:

            devpkt = v2
            v2 = v2.link
            devpkt.a1 = workpkt.a2[count]
            workpkt.a1 = count + 1
            return qpkt(devpkt)
    return wait()


def devfn(pkt):
    global v1
    if pkt == 0:
        if v1 == 0:
            return wait()
        pkt = v1
        v1 = 0
        return qpkt(pkt)
    else:
        v1 = pkt
        if tracing:
            trace(pkt.a1)
        return holdself()


def append(pkt, ptr):
    pkt.link = 0
    while ptr.link:
        ptr = ptr.link

    ptr.link = pkt


def bench():
    global tcb, qpktcount, holdcount, tracing, layout
    wkq = 0

    print("Bench mark starting")

    Task(InterfaceState.I_IDLE, 0, wkq, SocketState.RUN, idlefn, 1, Count)

    wkq = Packet(0, 0, Kind.K_WORK)
    wkq = Packet(wkq, 0, Kind.K_WORK)

    Task(InterfaceState.I_WORK, 1000, wkq, SocketState.WAITPKT, workfn, InterfaceState.I_HANDLERA, 0)

    wkq = Packet(0, InterfaceState.I_DEVA, Kind.K_DEV)
    wkq = Packet(wkq, InterfaceState.I_DEVA, Kind.K_DEV)
    wkq = Packet(wkq, InterfaceState.I_DEVA, Kind.K_DEV)

    Task(InterfaceState.I_HANDLERA, 2000, wkq, SocketState.WAITPKT, handlerfn, 0, 0)

    wkq = Packet(0, InterfaceState.I_DEVB, Kind.K_DEV)
    wkq = Packet(wkq, InterfaceState.I_DEVB, Kind.K_DEV)
    wkq = Packet(wkq, InterfaceState.I_DEVB, Kind.K_DEV)

    Task(InterfaceState.I_HANDLERB, 3000, wkq, SocketState.WAITPKT, handlerfn, 0, 0)

    wkq = 0
    Task(InterfaceState.I_DEVA, 4000, wkq, SocketState.WAIT, devfn, 0, 0)
    Task(InterfaceState.I_DEVB, 5000, wkq, SocketState.WAIT, devfn, 0, 0)

    tcb = tasklist

    qpktcount = holdcount = 0

    print("Starting")

    tracing = False
    layout = 0

    schedule()

    print("\nfinished")

    print("qpkt count = %i  holdcount = %i" % (qpktcount, holdcount))

    print("These results are", end=" ")
    if qpktcount == Qpktcountval and holdcount == Holdcountval:
        print("correct")
    else:
        print("incorrect")

    print("end of run")
    return 0


# Perform the Bench mark:
if __name__ == "__main__":
    bench()
