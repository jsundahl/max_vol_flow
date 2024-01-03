import csv
import datetime

import matplotlib.pyplot as plt
import numpy as np 
import requests
import scipy.signal


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
    # host = "http://localhost:7125/printer/gcode/script"
    host = "http://printy.local:7125/printer/gcode/script"
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

    # Convert the volumetric rate to a linear rate
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
        ; move right above build plate
        ; TODO: make movement xy depend on rate? to avoid conflicts
        G1 Z5 F300

        ; Start accelerometer measurement
        ACCELEROMETER_MEASURE NAME={accel_name}

        ; Wait for 1 second to collect background noise
        G4 P1000

        ; extruder movement to relative
        M83
        ; Extrude at rate X for time t while moving up 5mm
        ; TODO: will I get better measurements with a different or no z speed?
        G1 E{length} F{linear_rate}

        ; Stop accelerometer measurement
        ACCELEROMETER_MEASURE NAME={accel_name}

        ; retract 1mm
        G1 E-1 F1800
 
        ; move back up 10mm
        G1 Z10 F300
        """
 
    _run_gcode(cmd)

    return accel_filename

# TODO: there's for sure going to be a discrepancy between this and your
# in-practice max flow since you can reach a peak for a short time and
# be fine, but you couldn't sustain say 18mm^3/s for more than 1 second.
# this might be able to be picked up by a slicer to really know the limits
# of max flow. There's also probably an equation that we're fitting to for
# this and if I can figure out what it is then it will be cash money.


def generate_spectrogram(file_path):
    def sigmoid(x):
        return 1 / (1 + np.exp(-x))

    def normalize_data(Sxx):
        Sxx_min = np.min(Sxx)
        Sxx_max = np.max(Sxx)
        return (Sxx - Sxx_min) / (Sxx_max - Sxx_min)

    data = np.genfromtxt(file_path, delimiter=',', skip_header=1)
    fs = 3125
    fig, axs = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    mmcubed = file_path.split('-')[-1][:-8]

    for idx, axis in enumerate(['X', 'Y', 'Z']):
        frequencies, times, Sxx = scipy.signal.spectrogram(data[:, idx + 1], fs)
        Sxx = normalize_data(Sxx)
        Sxx = sigmoid(Sxx * 10)
        axs[idx].pcolormesh(times, frequencies, Sxx, shading='gouraud')
        axs[idx].set_ylabel('Frequency [Hz]')
        axs[idx].set_title(f"{axis}-axis at {mmcubed} mm^3/s")

    plt.xlabel('Time [sec]')
    fig.colorbar(axs[0].collections[0], ax=axs, orientation='vertical', label='Intensity [dB]')
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()

def runtest():
    # home, move extruder carriage to back left
    # _run_gcode("G28\nG90\nG1 X15 Y200 F2000")
    _run_gcode("G90\nG1 X15 Y200 F2000")
    for flow in (5, 5, 5, 20, 20, 20):
        file_path = flow_test(flow, 215, 50)
        print(f"Accelerometer data saved to {file_path}")
        # move right 10mm
        _run_gcode("G91\nG1 X10 F2000\nG90")

    # stop heating extruder
    _run_gcode("M109 S0")
    return


def process_stuff():
    files = """
    adxl345-2024-01-02-17-00-29-5mm3s.csv
    adxl345-2024-01-02-17-01-26-5mm3s.csv
    adxl345-2024-01-02-17-02-04-5mm3s.csv
    adxl345-2024-01-02-18-21-41-10mm3s.csv
    adxl345-2024-01-02-18-22-48-10mm3s.csv
    adxl345-2024-01-02-18-23-13-10mm3s.csv
    adxl345-2024-01-02-18-25-03-11mm3s.csv
    adxl345-2024-01-02-18-25-46-12mm3s.csv
    adxl345-2024-01-02-18-26-09-13mm3s.csv
    adxl345-2024-01-02-18-26-31-14mm3s.csv
    adxl345-2024-01-02-18-26-52-15mm3s.csv
    adxl345-2024-01-02-18-27-13-16mm3s.csv
    adxl345-2024-01-02-18-27-33-17mm3s.csv
    adxl345-2024-01-02-18-27-53-18mm3s.csv
    adxl345-2024-01-02-18-28-12-19mm3s.csv
    adxl345-2024-01-02-17-02-40-20mm3s.csv
    adxl345-2024-01-02-17-02-59-20mm3s.csv
    adxl345-2024-01-02-17-03-18-20mm3s.csv
    """.split()
    file = files[-4]
    generate_spectrogram(f"./data/{file.strip()}")


if __name__ == "__main__":
    process_stuff()