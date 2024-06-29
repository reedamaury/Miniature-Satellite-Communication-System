import traceback

print("**************************** GPS Initialize *****************************")
import adafruit_gps
import board
import busio
import time

uart = busio.UART(board.TX, board.RX, baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(uart, debug=False) # Use UART/pyserial

gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0") # We only use fix and location data
gps.send_command(b"PMTK220,1000") # 1Hz, or 1000ms

print("**************************** I2C Initialize *************************")
i2c = board.I2C() # uses board.SCL and board.SDA
while not i2c.try_lock():
    pass
try:
    print(
        "I2C addresses found:",
        [hex(device_address) for device_address in i2c.scan()],
    )

finally:  # unlock the i2c bus when ctrl-c'ing out of the loop
    i2c.unlock()

print("**************************** Display Initialize *************************")
import adafruit_displayio_sh1107
import adafruit_bus_device
import adafruit_display_text
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_sh1107
displayio.release_displays()
try:
    display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)
    WIDTH = 128
    HEIGHT = 64
    BORDER = 2
    display = adafruit_displayio_sh1107.SH1107(display_bus, width=WIDTH, height=HEIGHT,
    rotation=0)
    # Make the display context
    splash = displayio.Group()
    display.show(splash)
    color_bitmap = displayio.Bitmap(WIDTH, HEIGHT, 1)
    color_palette = displayio.Palette(1)
    color_palette[0] = 0x000000 # Black
    bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
    splash.append(bg_sprite)
except Exception as e:
    print (e)
    print ("Warning: Can't initialize Display")

print("**************************** Serial Input Initialize ********************")
import supervisor

print("**************************** Radio Initialize ***************************")
import adafruit_rfm69
import digitalio
RADIO_FREQ_MHZ = 915.0
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.D5)
reset = digitalio.DigitalInOut(board.D6)
rfm69 = adafruit_rfm69.RFM69(spi, cs, reset, RADIO_FREQ_MHZ)
#rfm69.bitrate = 500        #normally 250000 bps min 500 so we can see it on the SDR
rfm69.send(bytes("Hello world!  Initializing version 2\r\n", "utf-8"))
rfm69.listen()

print("**************************** IMU feather Initialize *********************")
from adafruit_lsm6ds.lsm6dsox import LSM6DSOX
#i2c = busio.I2C(board.SCL, board.SDA)
sensor = LSM6DSOX(i2c)
print("Acceleration: X:%.2f, Y: %.2f, Z: %.2f m/s^2" % (sensor.acceleration))
print("Gyro X:%.2f, Y: %.2f, Z: %.2f degrees/s" % (sensor.gyro))
x = sensor.acceleration[2]

print("**************************** Motor Initialize ***************************")
from adafruit_motorkit import MotorKit
i2c=board.I2C()
dt = 0.3 # timestep
T = 3 # period
N = T / dt # total number of steps to taketry:
try:
    kit = MotorKit(i2c=i2c)
    for i in range(N):
        kit.motor1.throttle = 0.1
        time.sleep(dt)
    kit.motor1.throttle = 0.0
except Exception as e:
    print (e)
    print("Warning: No motor driver.  We can only be the Ground Station")

print("**************************** System Initialize *************************")
exec_cmd_cnt = 0
bad_cmd_cnt = 0
speed = 0
# acceleration changes larger than this trigger a transmission with an updated speed.
acc_thresh = 0.1
Beacon_Period = 60           # seconds
last_beacon = time.monotonic()-Beacon_Period
