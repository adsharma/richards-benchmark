#!/usr/bin/env python
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

# Change False to True for a version that obeys
# the main loop 100x more often)

if False:
    Count           = 10000*100
    Qpktcountval    = 2326410
    Holdcountval     = 930563
else:
    Count           = 10000
    Qpktcountval    = 23246
    Holdcountval     = 9297


MAXINT          = 32767

BUFSIZE         = 3
I_IDLE          = 1
I_WORK          = 2
I_HANDLERA      = 3
I_HANDLERB      = 4
I_DEVA          = 5
I_DEVB          = 6
PKTBIT          = 1
WAITBIT         = 2
HOLDBIT         = 4
NOTPKTBIT       = ~1
NOTWAITBIT      = ~2
NOTHOLDBIT      = 0XFFFB

S_RUN           = 0
S_RUNPKT        = 1
S_WAIT          = 2
S_WAITPKT       = 3
S_HOLD          = 4
S_HOLDPKT       = 5
S_HOLDWAIT      = 6
S_HOLDWAITPKT   = 7

K_DEV           = 1000
K_WORK          = 1001

class Packet:
    def __init__(p,link, id, kind):
        p.link = link
        p.id = id
        p.kind = kind
        p.a1 = 0
        p.a2 = [0]*(BUFSIZE+1)

class Task:
    def __init__(t,id, pri, wkq, state, fn, v1, v2):
        global tasklist
        tasktab[id] = t
        t.link = tasklist
        t.id = id
        t.pri = pri
        t.wkq = wkq
        t.state = state
        t.fn = fn
        t.v1 = v1
        t.v2 = v2
        tasklist = t

alphabet = "0ABCDEFGHIJKLMNOPQRSTUVWXYZ"

tasktab  =  [10,0,0,0,0,0,0,0,0,0,0]

# Variables used in global statements
tasklist    =  0
tcb         = None
taskid      = 0L
v1          = 0L
v2          = 0L
qpktcount   =  0
holdcount   =  0
tracing     =  0
layout      =  0


def trace(a):
    global layout
    layout-=1
    if (layout <= 0 ):
        stdout.write('\n')
        layout = 50

    stdout.write(chr(a))

def schedule():
    global tcb,taskid,v1,v2
    while ( tcb != 0 ):
        pkt=0

        sw = tcb.state
        done = False
        if sw == S_WAITPKT:
            pkt = tcb.wkq
            tcb.wkq = pkt.link
            if tcb.wkq == 0:
                tcb.state = S_RUN
            else:
                tcb.state = S_RUNPKT

        if sw in [S_WAITPKT, S_RUN, S_RUNPKT]:
            taskid = tcb.id;
            v1 = tcb.v1;
            v2 = tcb.v2;
            if (tracing):
                trace(taskid+ord('0'))

            newtcb = tcb.fn(pkt)
            tcb.v1 = v1
            tcb.v2 = v2
            tcb = newtcb
            done = True

        if sw in [S_WAIT, S_HOLD, S_HOLDPKT, S_HOLDWAIT, S_HOLDWAITPKT]:
            tcb = tcb.link
            done = True

        if not done:
            return

def wait():
    tcb.state |= WAITBIT
    return (tcb)

def holdself():
    global holdcount
    holdcount +=1
    tcb.state |= HOLDBIT
    return (tcb.link)

def findtcb(id):
    t = 0
    if (1<=id and id<=tasktab[0]):
        t = tasktab[id]
    if (t==0):
        print "Bad task id %i"%id
    return(t)

def release(id):
    t = findtcb(id)
    if ( t==0 ):
        return (0)

    t.state &= NOTHOLDBIT
    if ( t.pri > tcb.pri ):
        return (t)

    return (tcb)

def qpkt(pkt):
    global qpktcount
    t = findtcb(pkt.id)
    if (t==0):
        return (t)

    qpktcount +=1

    pkt.link = 0
    pkt.id = taskid

    if (t.wkq==0):
        t.wkq = pkt
        t.state |= PKTBIT
        if (t.pri > tcb.pri):
            return (t)
    else:
        append(pkt, t.wkq)

    return (tcb)

def idlefn(pkt):
    global v1,v2
    v2 -=1
    if ( v2==0 ):
        return ( holdself() )

    if ( (v1&1) == 0 ):
        v1 = ( v1>>1) & MAXINT
        return ( release(I_DEVA) )
    else:
        v1 = ( (v1>>1) & MAXINT) ^ 0XD008
        return ( release(I_DEVB) )

def workfn(pkt):
    global v1,v2
    if ( pkt==0 ):
        return ( wait() )
    else:

        v1 = I_HANDLERA + I_HANDLERB - v1
        pkt.id = v1

        pkt.a1 = 0
        for i in range(0,BUFSIZE+1):
            v2 += 1
            if ( v2 > 26 ):
                v2 = 1
            pkt.a2[i] = ord(alphabet[v2])
        return ( qpkt(pkt) )

def handlerfn(pkt):
    global v1,v2
    if ( pkt!=0):
        if pkt.kind==K_WORK:
            x = Packet(v1,0,0)
            append(pkt, x)
            v1 = x.link
        else:
            x = Packet(v2,0,0)
            append(pkt, x)
            v2 = x.link

    if ( v1!=0 ):
        workpkt = v1
        count = workpkt.a1

        if ( count > BUFSIZE ):
            v1 = v1.link
            return ( qpkt(workpkt) )

        if ( v2!=0 ):

            devpkt = v2
            v2 = v2.link
            devpkt.a1 = workpkt.a2[count]
            workpkt.a1 = count+1
            return( qpkt(devpkt) )
    return wait()

def devfn(pkt):
    global v1
    if ( pkt==0 ):
        if ( v1==0 ):
            return ( wait() )
        pkt = v1
        v1 = 0
        return ( qpkt(pkt) )
    else:
        v1 = pkt
        if (tracing):
            trace(pkt.a1)
        return ( holdself() )

def append(pkt, ptr):
    pkt.link = 0
    while ( ptr.link ):
        ptr = ptr.link

    ptr.link = pkt

def bench():
    global tcb, qpktcount, holdcount, tracing, layout
    wkq = 0

    print "Bench mark starting"

    Task(I_IDLE, 0, wkq, S_RUN, idlefn, 1, Count)

    wkq = Packet(0, 0, K_WORK)
    wkq = Packet(wkq, 0, K_WORK)

    Task(I_WORK, 1000, wkq, S_WAITPKT, workfn, I_HANDLERA, 0)

    wkq = Packet(0, I_DEVA, K_DEV)
    wkq = Packet(wkq, I_DEVA, K_DEV)
    wkq = Packet(wkq, I_DEVA, K_DEV)

    Task(I_HANDLERA, 2000, wkq, S_WAITPKT, handlerfn, 0, 0)

    wkq = Packet(0, I_DEVB, K_DEV)
    wkq = Packet(wkq, I_DEVB, K_DEV)
    wkq = Packet(wkq, I_DEVB, K_DEV)

    Task(I_HANDLERB, 3000, wkq, S_WAITPKT, handlerfn, 0, 0)

    wkq = 0
    Task(I_DEVA, 4000, wkq, S_WAIT, devfn, 0, 0)
    Task(I_DEVB, 5000, wkq, S_WAIT, devfn, 0, 0)

    tcb = tasklist

    qpktcount = holdcount = 0

    print "Starting"

    tracing = False
    layout = 0

    schedule()

    print "\nfinished"

    print "qpkt count = %i  holdcount = %i"%(
           qpktcount, holdcount)

    print "These results are",
    if (qpktcount == Qpktcountval and holdcount == Holdcountval):
        print "correct"
    else:
        print "incorrect"

    print "end of run"
    return 0

# Perform the Bench mark:
if __name__ == '__main__':
    bench()
