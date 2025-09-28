import os, sys
from time import sleep

currentdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(currentdir)))
from LoRaRF import SX126x
from collections import deque
import time
import paho.mqtt.client as mqtt
import json
import datetime

# Define the maximum size of the history
MAX_SIZE = 10

# Initialize a deque to store the UUIDs.
# The 'maxlen' argument ensures the list never exceeds 10 items.
processed_messages = deque(maxlen=MAX_SIZE)

def should_process_message(message_id: str) -> bool:
    """
    Checks if a message has been processed. If not, it adds the ID to the
    history and returns True. If it has, it returns False.
    """
    if message_id in processed_messages:
        print(f"Message ID {message_id} was already processed.")
        return False
    else:
        processed_messages.append(message_id)
        print(f"Processing message ID {message_id}...")
        return True

def on_publish(client, userdata, mid):
    # reason_code and properties will only be present in MQTTv5. It's always unset in MQTTv3
    try:
        userdata.remove(mid)
    except KeyError:
        print("on_publish() is called with a mid not present in unacked_publish")
        print("This is due to an unavoidable race-condition:")
        print("* publish() return the mid of the message sent.")
        print("* mid from publish() is added to unacked_publish by the main thread")
        print("* on_publish() is called by the loop_start thread")
        print("While unlikely (because on_publish() will be called after a network round-trip),")
        print(" this is a race-condition that COULD happen")
        print("")
        print("The best solution to avoid race-condition is using the msg_info from publish()")
        print("We could also try using a list of acknowledged mid rather than removing from pending list,")
        print("but remember that mid could be re-used !")

unacked_publish = set()
mqttc = mqtt.Client()
mqttc.on_publish = on_publish
mqttc.user_data_set(unacked_publish)
mqttc.connect("localhost")
mqttc.loop_start()


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
print("Set syncronize word to 0x12	")
LoRa.setSyncWord(0x12)

print("\n-- LoRa Receiver --\n")

# Receive message continuously
while True :

    # Request for receiving new LoRa packet
    LoRa.request()
    # Wait for incoming LoRa packet
    LoRa.wait()

    # Put received packet to message and counter variable
    # read() and available() method must be called after request() or listen() method
    message = ""
    # available() method return remaining received payload length and will decrement each read() or get() method called
    while LoRa.available() > 1 :
        message += chr(LoRa.read())

    now = datetime.datetime.now()
    print(now)
    print(message)

    start_char_index = message.find("{")
    end_char_index = message.find("}") + len("}")

    if start_char_index != -1 and end_char_index != -1:
        extracted_text = message[start_char_index:end_char_index]
        #print(f"Extracted text: {extracted_text}")

        try:
            data = json.loads(extracted_text)
            if should_process_message(data["id"]):
                data["rssi"] = LoRa.packetRssi()
                data["snr"] = LoRa.snr()
                data["timestamp"] = time.time()

                msg_info = mqttc.publish("targets/hits", json.dumps(data), qos=1)
                unacked_publish.add(msg_info.mid)
                # Wait for all message to be published
                while len(unacked_publish):
                    time.sleep(0.1)
                    msg_info.wait_for_publish()

        except json.JSONDecodeError as e:
            print("Invalid JSON syntax:", e)


    # Print packet/signal status including RSSI, SNR, and signalRSSI
    print("Packet status: RSSI = {0:0.2f} dBm | SNR = {1:0.2f} dB".format(LoRa.packetRssi(), LoRa.snr()))

    print("\n")
    # Show received status in case CRC or header error occur
    status = LoRa.status()
    if status == LoRa.STATUS_CRC_ERR : print("CRC error")
    elif status == LoRa.STATUS_HEADER_ERR:
        print("Packet header error")
        sleep(2)
        continue
