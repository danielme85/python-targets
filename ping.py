import os, sys
from time import sleep

currentdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(currentdir)))
from LoRaRF import SX126x
import time
import json
import uuid


# Begin LoRa radio and set NSS, reset, busy, IRQ, txen, and rxen pin with connected Raspberry Pi gpio pins
# IRQ pin not used in this example (set to -1). Set txen and rxen pin to -1 if RF module doesn't have one
busId = 0; csId = 0
resetPin = 18; busyPin = 20; irqPin = 16; txenPin = 6; rxenPin = -1
LoRa = SX126x()
print("Begin LoRa radio")
if not LoRa.begin(busId, csId, resetPin, busyPin, irqPin, txenPin, rxenPin) :
    raise Exception("Something wrong, can't begin LoRa radio")

LoRa.setDio2RfSwitch()
# Set frequency to 868 Mhz
print("Set frequency to 915 Mhz")
LoRa.setFrequency(915000000)

# Set RX gain. RX gain option are power saving gain or boosted gain
#print("Set RX gain to power saving gain")
#LoRa.setRxGain(LoRa.RX_GAIN_POWER_SAVING)                       # Power saving gain

# Configure modulation parameter including spreading factor (SF), bandwidth (BW), and coding rate (CR)
# Receiver must have same SF and BW setting with transmitter to be able to receive LoRa packet
print("Set modulation parameters:\n\tSpreading factor = 7\n\tBandwidth = 125 kHz\n\tCoding rate = 4/5")
sf = 7                                                          # LoRa spreading factor: 7
bw = 125000                                                     # Bandwidth: 125 kHz
cr = 5                                                          # Coding rate: 4/5
LoRa.setLoRaModulation(sf, bw, cr)

# Configure packet parameter including header type, preamble length, payload length, and CRC type
# The explicit packet includes header contain CR, number of byte, and CRC type
# Receiver can receive packet with different CR and packet parameters in explicit header mode
print("Set packet parameters:\n\tExplicit header type\n\tPreamble length = 12\n\tPayload Length = 15\n\tCRC on")
headerType = LoRa.HEADER_EXPLICIT                               # Explicit header mode
preambleLength = 8                                             # Set preamble length to 12
payloadLength = 255                                             # Initialize payloadLength to 15
crcType = True                                                  # Set CRC enable
LoRa.setLoRaPacket(headerType, preambleLength, payloadLength, crcType)

# Set syncronize word for public network (0x3444)
print("Set syncronize word to 0xF3")
LoRa.setSyncWord(0x12)

print("\n-- LoRa Receiver --\n")

jsonData = {
    "command": "status",
    "id": uuid.uuid4(),
}

LoRa.beginPacket()
LoRa.write(json.dumps(jsonData))
LoRa.endPacket()
LoRa.wait()