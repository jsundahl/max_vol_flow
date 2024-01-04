import datetime

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


# TODO: something like binary search?
# TODO: test with fan at 100%
def run_test(start_flow, temp, length):
    """
    Run a flow test on the printer.

    @param start_flow - The starting flow rate to extrude at in mm^3/s.
    @param temp - The temperature to extrude at.
    @param length - The length of filament to extrude.
    """
    max_pos_xy = [200, 200]
    pos_xy = [20, 20]
    _run_gcode(
        f"""
        ; home
        G28
        ; move to initial position
        G90
        G1 X{pos_xy[0]} Y{pos_xy[1]} F{XY_TRAVEL_SPEED}
        """
    )

    for flow in range(start_flow, 999):
        file_path = flow_test(volumetric_rate=flow, temp=temp, length=length)
        if contains_extruder_click(file_path):
            print(f"Extruder click detected at {flow} mm^3/s")
            break

        # move over 10mm, possibly up 10mm
        if pos_xy[0] + 10 > max_pos_xy[0]:
            pos_xy[1] += 10
            pos_xy[0] = 20
        _run_gcode(f"G1 X{pos_xy[0]} Y{pos_xy[1]} F{XY_TRAVEL_SPEED}")

    # stop heating extruder
    _run_gcode("M109 S0")
    return


if __name__ == "__main__":
    # run_test()
    pass
