from CommInit import *
import traceback, sys
#
import asyncio
# Can't receive when transmitting as we have one antenna and half-duplex radio
radio_lock = asyncio.Lock()   

from collections import deque
rq = deque((), 100)    # Receive Queue
tq = deque((), 100)    # Transmit Queue
snaq = []              # Sent, not Ack'd Queue
mq = deque((), 100)    # Motor Queue
acksn = 0              # Ack serial number initialization
print_heartbeat = False      # For debugging

async def nested():
    print(42)
    return

async def factorial(name, number):
    f = 1
    for i in range(2, number + 1):
        print(f"Task {name}: Compute factorial({number}), currently i={i}...")
        await asyncio.sleep(1)
        f *= i
    print(f"Task {name}: factorial({number}) = {f}")
    return f

async def motor_2 ():
    global mq
    global kit
    while (1):
        await asyncio.sleep(0)
        #  see if there's anything to deque and deque it
        if (len(mq) >= 1):
            try:
                speed = mq.popleft()
                kit.motor1.throttle = speed/11
                print("motor_2: set motor speed to {}".format(speed))
            except Exception as e:
                print("In motor_2")
                print (e)
                print(traceback.format_exception(e))

async def receive_2 (radio_lock):
    global rq
    global rfm69
    global print_heartbeat

    # Radio Internal constants:
    _REG_FIFO = const(0x00)
    while (1):
        async with radio_lock:
            while (rfm69.payload_ready()):
                if (print_heartbeat): print ("A", end="")
    #  take apart "packet = rfm69.receive(timeout=2)" for async
                rfm69.idle()         # Turn off receiver so buffer is static
                fifo_length = rfm69._read_u8(_REG_FIFO)
                    # Handle if the received packet is too small to include the 4 byte
                if (print_heartbeat): print ("F", end="")
                if fifo_length > 0:  # read and clear the FIFO if anything in it
                    #print ("fifo length {}".format(fifo_length))
                    packet = bytearray(fifo_length)
                    rfm69._read_into(_REG_FIFO, packet, fifo_length)
#                    print ("receive_2: Queueing incoming packet {}".format(packet))
                    rq.append(packet)
                rfm69.listen()       # Turn receiver on again
                await asyncio.sleep(0.1)
        await asyncio.sleep(0)              #  Release the lock

async def dispatch_2 ():
    global snaq
    global exec_cmd_cnt
    global bad_cmd_cnt
    global tq
    global acksn
    while (1):
        await asyncio.sleep(0)
        if len(rq):       # if there's nothing in the receive queue, exit
            packet_text = rq.popleft()[4:]   #  get the command, stripping off network bytes.  Beacon and ACK don't have acksn
            try:
                cmd = packet_text[0:6].decode('ascii') # ascii maps the bits to unique characters (letters, numbers, punction, etc.) - ascii is 7-bit (2^7=128 unique characters)
            except Exception as e:
                print ("ASCII decode in dispatch_2")
                print (e)
                print(traceback.format_exception(e))
                continue
            if (packet_text[0:6].decode('ascii') == "BEACON"): # if a BEACON is sent 
                    print("Received a beacon: {}".format(packet_text))
                    continue
            if (len(snaq) >= 1 and packet_text[0:3].decode('ascii') == "ACK" and len(packet_text) >=7): 
                    # rewrite snaq queue without this acksn
                    print("ACK received for packet {}".format(packet_text[5:8].decode('ascii')))
                    snaq = [i for i in snaq if packet_text[4:8].decode('ascii') not in i[0:4]]
                    continue
            print ("Popped & acking {}".format(packet_text))
            try:
                tq.append("ACK {:4d}".format(int(packet_text[0:4].decode('ascii'))))
            except Exception as e:
                print ("In Dispatch_2: ACK {}".format(packet_text[0:4]))
                print (e)
                print(traceback.format_exception(e))
                continue
            print("Queued ACK{:4d} for transmission, position ={:4d}".format(int(packet_text.decode('ascii')[0:4]), len(tq)))
            try:
                packet_text = packet_text[4:]      #  Strip off the acksn
                if (packet_text[0:9].decode('ascii') == "TELEMETRY"):
                    print(packet_text)
                elif (packet_text[0:4].decode('ascii') == "NOOP"):
                    exec_cmd_cnt += 1
                elif (packet_text[0:4].decode('ascii') == "STOP"):
                    exec_cmd_cnt += 1
                    mq.append(0)       #  queue up the motor move
                elif (packet_text[0:4].decode('ascii') == "EXEC"):
                    exec_cmd_cnt += 1
                    speed = float(packet_text[5:10].decode('ascii')) # motor speed sent from groundstation converted from bits to floating point number using ascii
                    mq.append(speed)       #  queue up the motor move
                elif (packet_text[0:2] == "HK"): 
                    exec_cmd_cnt += 1
                    tq.append(bytes("{:4d}TELEMETRY: snaq={}; tq={}; rq={}; mq={}; bad={}; exec={}".format(acksn, len(snaq), len(tq), len(rq), len(mq), bad_cmd_cnt, exec_cmd_cnt), "utf-8"))
                    snaq.append((bytes("{:4d}TELEMETRY: snaq={}; tq={}; rq={}; mq={}; bad={}; exec={}".format(acksn, len(snaq), len(tq), len(rq), len(mq), bad_cmd_cnt, exec_cmd_cnt), "utf-8")))
                    acksn += 1
                elif (packet_text[0:4] == "DISP"):
                    exec_cmd_cnt += 1
                    text_4 = label.Label(terminalio.FONT, text=packet_text[5:], color=0xFFFFFF, x=10, y=47)
                    splash.append(text_4)
                else:
                    bad_cmd_cnt += 1
                    print("Unexpected Command {}".format(packet_text, end=""))
            except Exception as e:
                print ("In dispatch_2")
                print (e)
                print(traceback.format_exception(e))
                print_exception = lambda e, f: traceback.print_exception(None, e, sys.exc_info()[2], file=f)

async def resend_2():
    global acksn
    global tq
    global snaq
    while (1):
        await asyncio.sleep(5.6)
        try:
            if (len(snaq) >= 3): print("resend_2: snaq is {}".format(snaq[0:3]))   
            if (len(snaq) >= 1): 
                tq.append(snaq[0])
                print("resending packet{}".format(snaq[0]))
        except Exception as e:
            print("In resend_2")
            print(e)
            print(traceback.format_exception(e))
        if (acksn > 900): acksn = 0         #  must fit in 4 digits

async def housekeeping_2():
    global acksn
    global snaq
    while (1):
        await asyncio.sleep(10)
        if (acksn > 900): 
            print("resend_2: acksn must fit in 4 digits; resetting from {} to zero acksn".format(acksn))
            acksn = 0
        if (len(snaq) > 100):
            print("Housekeeping_2: len(snaq) too large {}, resetting to empty".format(len(snaq)))
            snaq = []

async def beacon_2():
    global snaq
    global tq
    global rq
    global bad_cmd_cnt
    global exec_cmd_cnt
    while (1):
        await asyncio.sleep(12)
        tq.append("BEACON: snaq={}; tq={}; rq={}; mq={}; bad={}; exec={}".format(len(snaq), len(tq), len(rq), len(mq), bad_cmd_cnt, exec_cmd_cnt))
        print("Sent our BEACON: snaq={}; tq={}; rq={}; mq={}; bad={}; exec={}".format(len(snaq), len(tq), len(rq), len(mq), bad_cmd_cnt, exec_cmd_cnt))

async def transmit_2 (radio_lock):

    global tq
    global rfm69
    global print_heartbeat
    while (1):
        if (print_heartbeat): print ("t{}".format(len(tq)), end="")
        await asyncio.sleep(0)
    #  see if there's anything to deque and deque it
        if (len(tq) >= 1):
            cmd = tq.popleft()
            if (print_heartbeat): print ("c{}".format(len(tq)), end="")
            try:
            #  capture radio from the receiver
                async with radio_lock:
            #  transmit it
                    if (print_heartbeat): print ("i", end="")
                    rfm69.idle()
                    if (print_heartbeat): print ("s", end="")
                    rfm69.send(cmd)          #  comment out for the second ground station
                    if (print_heartbeat): print ("T{}".format(len(tq)), end="")
                    while (len(tq) >= 1):    # blast the entire remaining transmit queue
                        cmd = tq.popleft()
                        rfm69.send(cmd)      #  comment out for the second ground station
                        await asyncio.sleep(0.1)
                    rfm69.listen()       # Turn receiver on again
                    await asyncio.sleep(0.3)
            except Exception as e:
                print ("In transmit_2")
                print (e)
                print(traceback.format_exception(e))
        else:
            await asyncio.sleep(.5)

async def serial_2():
    global tq
    global snaq
    global acksn
    while (1):
        await asyncio.sleep(0.1)
        if supervisor.runtime.serial_bytes_available:
            cmd = bytes(input().strip(), "utf-8")
            print("Sending a Serial command {}".format(cmd))
# enque a transmission rfm69.send(cmd) with asksn and ask for confirmation
            tq.append(("{:4d}" + cmd.decode('utf-8')).format(acksn))
            snaq.append(("{:4d}" + cmd.decode('utf-8')).format(acksn))
            acksn += 1
        
async def IMU_2(sensor):
    global x
    global acc_thresh
    global tq
    global snaq
    global acksn
    while (1):
        await asyncio.sleep(0)
        xn = sensor.acceleration[2]
    #  Did it change by enough to trigger a transmission?
        if (abs(xn - x) > acc_thresh  and len(snaq) == 0):  # Use this line to experience commands
#        if (abs(xn - x) > acc_thresh):         #  Use this line to experiment with a data transfer
            x = xn
            tq.append("{:4d}EXEC {}".format(acksn, xn))
            try:  #  Protect against overflowing queue
                snaq.append("{:4d}EXEC {}".format(acksn, xn))
            except:
                pass
            acksn += 1

async def main():
    SAT = False    
    if SAT:
        text = "     SAT async"
        text_title = label.Label(terminalio.FONT, text=text, color=0xFFFF00, x=10, y=7)
        splash.append(text_title)
        task2 = asyncio.create_task(serial_2())
        task3 = asyncio.create_task(receive_2(radio_lock))
        task4 = asyncio.create_task(transmit_2(radio_lock))
        task5 = asyncio.create_task(motor_2())
        task6 = asyncio.create_task(beacon_2())
        task8 = asyncio.create_task(dispatch_2())
        task9 = asyncio.create_task(resend_2())
        task10 = asyncio.create_task(housekeeping_2())
        await asyncio.gather(task2, task3, task4, task5, task6, task8, task9, task10)
        print(f"Should never get here")
    else:
        text = "     GS async"
        text_title = label.Label(terminalio.FONT, text=text, color=0xFFFF00, x=10, y=7)
        splash.append(text_title)
        task2 = asyncio.create_task(serial_2())
        task3 = asyncio.create_task(receive_2(radio_lock))
        task4 = asyncio.create_task(transmit_2(radio_lock))
        task6 = asyncio.create_task(beacon_2())
        task7 = asyncio.create_task(IMU_2(sensor))
        task8 = asyncio.create_task(dispatch_2())
        task9 = asyncio.create_task(resend_2())
        task10 = asyncio.create_task(housekeeping_2())
        await asyncio.gather(task2, task3, task4, task6, task7, task8, task9, task10)
        print(f"Should never get here")
   
#  Run the event loop
asyncio.run(main())

import sys
sys.exit()

