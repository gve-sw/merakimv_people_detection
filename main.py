""" Copyright (c) 2021 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
           https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied. 
"""

import json
import time

import paho.mqtt.client as mqtt
import requests
from requests.auth import HTTPBasicAuth

import time
import datetime
from subprocess import Popen
import logging

from env_var import CAMERA_SERIAL, MQTT_SERVER, MQTT_PORT, MESSAGE_RECIPIENT, AGE_THRESHOLD

logging.basicConfig(level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

# Track the persons in a dictionary
obj_tracker = {}

def current_milli_time():
    return round(time.time() * 1000)

# connection notification that the script is running
def on_connect(client, userdata, flags, rc):
    print("connected with code: " + str(rc))
    client.subscribe(MQTT_TOPIC)


# The callback for when a PUBLISH message is received from the mqtt server
def on_message(client, userdata, msg):
    global obj_tracker
    payload = json.loads(msg.payload.decode("utf-8", "ignore"))

    ts = payload["ts"]
    objects = payload["objects"]

    if not objects:
        logging.info("There are currently no tracked objects in the frame")
    else:
        logging.info("Detected objects:")
        logging.info(payload["objects"])

    oid_keys = []

    for obj in objects:
        # If it is not a person, then we skip this object
        if not obj["type"] == "person":
            continue
        
        # Store object id in oid
        oid = obj["oid"]
        # Add oid to oid_keys
        oid_keys.append(oid)

        # If it is a new object, then add object to obj_tracker
        if oid not in obj_tracker:
            obj_to_add = {}
            obj_to_add["ts_start"] = ts
            obj_to_add["age"] = current_milli_time() - ts
            obj_to_add["alerted"] = 0
            obj_tracker[oid] = obj_to_add
        # If object is already present in obj_tracker, then update age
        else:
            obj_tracker[oid]["age"] = current_milli_time() - obj_tracker[oid]["ts_start"]
        
        # If person is exceeding threshould, then send alert and snapshot
        if obj_tracker[oid]["age"] > AGE_THRESHOLD and obj_tracker[oid]["alerted"] == 0:
            obj_tracker[oid]["alerted"] = 1

            ts = current_milli_time()
            ts_in_datetime = datetime.datetime.fromtimestamp(ts/1000).strftime('%Y-%m-%d %H:%M:%S')

            alert_message = f"""Alert: suspicious activity detected. Snapshot is taken from camera with serial number {CAMERA_SERIAL} at {ts_in_datetime}. 
            The suspect has been detected for more than {round(AGE_THRESHOLD/1000)} seconds"""

            # send alert and snapshot in a new process
            Popen(f'python3 send.py "{alert_message}" {MESSAGE_RECIPIENT} {CAMERA_SERIAL} {ts}', shell=True)

        logging.info("obj_tracker:")    
        logging.info(obj_tracker)    

    # Only keep the objects that are seen in the current objects list
    # If object is not in list, then assume it is out of frame
    obj_tracker_temp = {}
    for key in oid_keys:
        obj_tracker_temp[key] = obj_tracker[key]
    obj_tracker.clear()
    obj_tracker = obj_tracker_temp

    time.sleep(5)


if __name__ == "__main__":
    MQTT_TOPIC = "/merakimv/" + CAMERA_SERIAL + "/raw_detections"
    try:
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(MQTT_SERVER, MQTT_PORT, 60)
        client.loop_forever()

    except Exception as ex:
        print("[MQTT]failed to connect or receive msg from mqtt, due to: \n {0}".format(ex))
