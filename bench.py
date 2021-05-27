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
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from adt import adt as sealed
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
    link: Optional["Packet"] = field(repr=False)
    id: int
    kind: Kind
    a1: int = 0
    a2: List[int] = field(default_factory=list)

    def __post_init__(self):
        self.a1 = 0
        self.a2 = [0] * (BUFSIZE + 1)


@sealed
class Register:
    PACKET: Packet
    VALUE: int


alphabet = "0ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass
class Task:
    id: int
    pri: int
    wkq: Optional[Packet]
    state: SocketState
    fn: Callable
    v1: Register
    v2: Register

    def __post_init__(self):
        global tasklist
        tasktab.entries[self.id + 1] = self
        self.link = tasklist
        tasklist = self


@dataclass
class Tasktab:
    limit: int
    entries: List[Optional[Task]]


tasktab: Tasktab = Tasktab(10, [None] * 10)


# Variables used in global statements
tasklist = None
tcb = None
taskid = 0
v1: Register = Register.VALUE(0)
v2: Register = Register.VALUE(0)
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
    while tcb is not None:
        pkt = None

        sw = tcb.state
        done = False
        if sw == SocketState.WAITPKT:
            pkt = tcb.wkq
            tcb.wkq = pkt.link
            if tcb.wkq is None:
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

        if sw in [
            SocketState.WAIT,
            SocketState.HOLD,
            SocketState.HOLDPKT,
            SocketState.HOLDWAIT,
            SocketState.HOLDWAITPKT,
        ]:
            tcb = tcb.link
            done = True

        if not done:
            return


def wait():
    tcb.state |= SocketState.WAITBIT
    return tcb


def holdself():
    global holdcount
    holdcount += 1
    tcb.state |= SocketState.HOLDBIT
    return tcb.link


def findtcb(id: int) -> Optional[Task]:
    t = None
    limit = tasktab.limit
    if 1 <= id and id <= limit:
        t = tasktab.entries[id + 1]
    if t is None:
        print("Bad task id %i" % id)
    return t


def release(id) -> Optional[Task]:
    t = findtcb(id)
    if t is None:
        return t

    t.state &= SocketState.NOTHOLDBIT
    if t.pri > tcb.pri:
        return t

    return tcb


def qpkt(pkt):
    global qpktcount
    t = findtcb(pkt.id)
    if t is None:
        return t

    qpktcount += 1

    pkt.link = None
    pkt.id = taskid

    if t.wkq is None:
        t.wkq = pkt
        t.state |= SocketState.PKTBIT
        if t.pri > tcb.pri:
            return t
    else:
        append(pkt, t.wkq)

    return tcb


def idlefn(pkt):
    global v1, v2
    v2 = Register.VALUE(v2.value() - 1)
    if v2.value() == 0:
        return holdself()

    if (v1.value() & 1) == 0:
        v1 = Register.VALUE((v1.value() >> 1) & MAXINT)
        return release(InterfaceState.I_DEVA)
    else:
        v1 = Register.VALUE(((v1.value() >> 1) & MAXINT) ^ 0xD008)
        return release(InterfaceState.I_DEVB)


def workfn(pkt):
    global v1, v2
    if pkt is None:
        return wait()
    else:

        v1 = Register.VALUE(
            (InterfaceState.I_HANDLERA + InterfaceState.I_HANDLERB - v1.value())
        )
        pkt.id = v1.value()

        pkt.a1 = 0
        for i in range(0, BUFSIZE + 1):
            value = v2.value()
            value += 1
            if value > 26:
                value = 1
            v2 = Register.VALUE(value)
            pkt.a2[i] = ord(alphabet[v2.value()])
        return qpkt(pkt)


def handlerfn(pkt):
    global v1, v2
    if pkt is not None:
        if pkt.kind == Kind.K_WORK:
            link = None if v1.is_value() else v1.packet()
            x = Packet(link, 0, Kind.K_DEV)
            append(pkt, x)
            v1 = Register.PACKET(x.link)
        else:
            link = None if v2.is_value() else v2.packet()
            x = Packet(link, 0, Kind.K_DEV)
            append(pkt, x)
            v2 = Register.PACKET(x.link)

    if v1.is_packet():
        workpkt: Packet = v1.packet()
        count = workpkt.a1

        if count > BUFSIZE:
            v1 = (
                Register.PACKET(workpkt.link)
                if workpkt.link is not None
                else Register.VALUE(0)
            )
            return qpkt(workpkt)

        if v2.is_packet():
            devpkt: Packet = v2.packet()
            v2 = (
                Register.PACKET(devpkt.link)
                if devpkt.link is not None
                else Register.VALUE(0)
            )
            devpkt.a1 = workpkt.a2[count]
            workpkt.a1 = count + 1
            return qpkt(devpkt)
    return wait()


def devfn(pkt):
    global v1
    if pkt is None:
        if v1.is_value() and v1.value() == 0:
            return wait()
        pkt: Packet = v1.packet()
        v1 = Register.VALUE(0)
        return qpkt(pkt)
    else:
        v1 = Register.PACKET(pkt)
        if tracing:
            trace(pkt.a1)
        return holdself()


def append(pkt, ptr):
    pkt.link = None
    while ptr.link:
        ptr = ptr.link

    ptr.link = pkt


def bench(iters):
    global tcb, qpktcount, holdcount, tracing, layout

    for i in range(iters):
        wkq = None

        v1 = Register.VALUE(1)
        v2 = Register.VALUE(Count)
        Task(InterfaceState.I_IDLE, 0, wkq, SocketState.RUN, idlefn, v1, v2)

        wkq = Packet(None, 0, Kind.K_WORK)
        wkq = Packet(wkq, 0, Kind.K_WORK)

        v1 = Register.VALUE(InterfaceState.I_HANDLERA)
        v2 = Register.VALUE(0)
        Task(InterfaceState.I_WORK, 1000, wkq, SocketState.WAITPKT, workfn, v1, v2)

        wkq = Packet(None, InterfaceState.I_DEVA, Kind.K_DEV)
        wkq = Packet(wkq, InterfaceState.I_DEVA, Kind.K_DEV)
        wkq = Packet(wkq, InterfaceState.I_DEVA, Kind.K_DEV)

        v1 = Register.VALUE(0)
        v2 = Register.VALUE(0)
        Task(
            InterfaceState.I_HANDLERA, 2000, wkq, SocketState.WAITPKT, handlerfn, v1, v2
        )

        wkq = Packet(None, InterfaceState.I_DEVB, Kind.K_DEV)
        wkq = Packet(wkq, InterfaceState.I_DEVB, Kind.K_DEV)
        wkq = Packet(wkq, InterfaceState.I_DEVB, Kind.K_DEV)

        Task(
            InterfaceState.I_HANDLERB, 3000, wkq, SocketState.WAITPKT, handlerfn, v1, v2
        )

        wkq = None
        Task(InterfaceState.I_DEVA, 4000, wkq, SocketState.WAIT, devfn, v1, v2)
        Task(InterfaceState.I_DEVB, 5000, wkq, SocketState.WAIT, devfn, v1, v2)

        tcb = tasklist

        qpktcount = holdcount = 0

        tracing = False
        layout = 0

        schedule()

        if qpktcount == Qpktcountval and holdcount == Holdcountval:
            pass
        else:
            return False


# Perform the Bench mark:
if __name__ == "__main__":
    bench(3)
