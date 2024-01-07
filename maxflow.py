#!/usr/bin/env python3

import argparse
import contextlib
import datetime
import time

import numpy as np
import requests

XY_TRAVEL_SPEED = 6000
Z_TRAVEL_SPEED = 600
RETRACT_SPEED = 1800


class GCodeError(Exception):
    def __init__(self, command, status_code, response_text):
        self.command = command
        self.status_code = status_code
        self.response_text = response_text

    def __str__(self):
        return (
            f"G-code command {self.command} failed with status {self.status_code} and "
            f"response text {self.response_text}"
        )


def _run_gcode(gcode):
    host = "http://localhost:7125/printer/gcode/script"
    response = requests.post(host, json={"script": gcode})

    if response.status_code != 200:
        raise GCodeError(gcode, response.status_code, response.text)


def flow_test(volumetric_rate, temp, length):
    """
    Run a volumetric flow test on the printer.

    @param temp - The temperature to extrude at
    @param length - The length of filament to extrude
    @param volumetric_rate - The volumetric rate to extrude at in mm^3/s

    @return The path to the accelerometer data file
    """

    linear_rate = volumetric_rate * 60 / (3.14159 * 1.75**2 / 4)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    accel_name = f"{timestamp}-{volumetric_rate}mm3s"
    accel_filename = f"/tmp/adxl345-{accel_name}.csv"

    cmd = f"""
        ; G28
        ; Ensure the extruder is at the correct temperature
        M109 S{temp} 

        ; movement to absolute
        G90
        ; move near build plate
        ; TODO: make movement xy depend on rate? to avoid conflicts
        G1 Z5 F{Z_TRAVEL_SPEED}

        ; Start accelerometer measurement
        ACCELEROMETER_MEASURE NAME={accel_name}

        ; Wait for 1 second to collect background noise
        G4 P1000

        ; extruder movement to relative
        M83
        ; Extrude
        G1 E{length} F{linear_rate}

        ; Stop accelerometer measurement
        ACCELEROMETER_MEASURE NAME={accel_name}

        ; retract 1mm
        G1 E-1 F{RETRACT_SPEED}
 
        ; move back up 10mm
        G91
        G1 Z10 F{Z_TRAVEL_SPEED}
        G90
        """

    _run_gcode(cmd)

    return accel_filename


def contains_extruder_click(file_path):
    """
    Determine if the accelerometer data contains an extruder click.

    @param file_path - The path to the accelerometer data file

    @return True if the accelerometer data contains an extruder click, False otherwise.
    """
    data = np.genfromtxt(file_path, delimiter=",", skip_header=1)
    avg_accel = np.mean(data[:, 1:4], axis=1)

    # the first second is just background noise, so we can use that to determine
    # a threshold for what is a click and what is not.
    sample_hz = int(1 / (data[1, 0] - data[0, 0]))
    first_second_data = avg_accel[:sample_hz]
    mean = np.mean(first_second_data)
    std_dev = np.std(first_second_data)
    # use a crazy high z score to avoid false positives
    upper_bound = mean + 10 * std_dev

    return np.any(avg_accel[sample_hz:] > upper_bound)


@contextlib.contextmanager
def extruder_at_temp(temp):
    """
    Context manager to ensure the extruder is at the correct temperature.

    @param temp - The temperature to set.
    """
    try:
        _run_gcode(f"M109 S{temp}")
        yield
    finally:
        _run_gcode("M109 S0")


def run_test(min_flow, temp, length, max_flow):
    """
    Run a flow test on the printer.

    @param min_flow - The minimum flow rate to extrude at in mm^3/s.
    @param temp - The temperature to extrude at.
    @param length - The length of filament to extrude.
    @param max_flow - The maximum flow rate to extrude at in mm^3/s.
    """
    max_pos_xy = [200, 200]
    original_pos_xy = [20, 20]
    pos_xy = original_pos_xy.copy()
    _run_gcode(
        f"""
        ; home
        G28
        ; move to initial position
        G90
        G1 X{pos_xy[0]} Y{pos_xy[1]} F{XY_TRAVEL_SPEED}
        """
    )

    with extruder_at_temp(temp):
        low = min_flow
        high = max_flow
        click_flow = None

        while low <= high:
            mid = (low + high) // 2
            print(f"checking {mid} mm^3/s")
            file_path = flow_test(volumetric_rate=mid, temp=temp, length=length)
            # wait for csv file to be fully written
            time.sleep(5)
            if contains_extruder_click(file_path):
                print(f"Extruder click detected at {mid} mm^3/s")
                click_flow = mid
                high = mid - 1
            else:
                low = mid + 1

            # move over 10mm, possibly up 10mm
            pos_xy[0] += 10
            if pos_xy[0] > max_pos_xy[0]:
                pos_xy[1] += 10
                if pos_xy[1] > max_pos_xy[1]:
                    raise RuntimeError("Y max exceeded, something is very wrong.")

                pos_xy[0] = original_pos_xy[0]
            _run_gcode(f"G1 X{pos_xy[0]} Y{pos_xy[1]} F{XY_TRAVEL_SPEED}")

        if click_flow is not None:
            print(f"Max flow rate with no extruder click: {click_flow - 1} mm^3/s")
        else:
            print(f"No extruder click detected. Stopped at {max_flow} mm^3/s.")


class CLIArgs:
    def __init__(self, min_flow, temp, length, max_flow):
        self.min_flow = min_flow
        self.temp = temp
        self.length = length
        self.max_flow = max_flow

    @classmethod
    def from_argv(cls):
        parser = argparse.ArgumentParser(description="Run a flow test on the printer.")
        parser.add_argument(
            "--min-flow",
            type=int,
            default=5,
            help="The minimum flow rate to extrude at in mm^3/s.",
        )
        parser.add_argument(
            "--temp", type=int, required=True, help="The temperature to extrude at."
        )
        parser.add_argument(
            "--length",
            type=int,
            default=50,
            help="The length of filament to extrude in mm.",
        )
        parser.add_argument(
            "--max-flow",
            type=int,
            default=30,
            help="The maximum flow rate to extrude at in mm^3/s.",
        )

        args = parser.parse_args()

        return cls(args.min_flow, args.temp, args.length, args.max_flow)


if __name__ == "__main__":
    args = CLIArgs.from_argv()
    run_test(
        min_flow=args.min_flow,
        temp=args.temp,
        length=args.length,
        max_flow=args.max_flow,
    )

