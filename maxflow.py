import csv
import datetime

import numpy as np 
import requests


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
        raise GCodeError(gcode.value, response.status_code, response.text)


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
  
    timestamp = datetime.datetime.now().isoformat()
    accel_filename = f"/tmp/adxl345-{timestamp}-{volumetric_rate}.csv"

    cmd = f"""
        ; Ensure the extruder is at the correct temperature
        M109 S{temp} 

        ; Start accelerometer measurement
        ACCELEROMETER_MEASURE NAME={timestamp}-{volumetric_rate}

        ; Wait for 1 second to collect background noise
        G4 P1000

        ; Extrude at rate X for time t
        G1 E{length} F{linear_rate}

        ; Stop accelerometer measurement
        ACCELEROMETER_MEASURE NAME={timestamp}-{volumetric_rate}
        """
 
    _run_gcode(cmd)

    return accel_filename

file_path = flow_test(10, 215, 50)
print(f"Accelerometer data saved to {file_path}")

# Constants
sampling_rate = 3125  # Hz
window_size = 256  # Size of each FFT window
overlap = window_size // 2  # 50% overlap
bg_noise_duration = 1  # Duration of background noise data in seconds

# Read CSV data
with open(file_path, 'r') as csvfile:
    csv_reader = csv.reader(csvfile)
    next(csv_reader)  # Skip header
    data = [row[1:] for row in csv_reader if not row[0].startswith('#')]  # Extract data, skip comments

# Transpose and convert to NumPy array
data_array = np.array(data, dtype=float).T

# Calculate number of samples for the noise period
noise_samples = sampling_rate * bg_noise_duration

# Define a Hanning window
window = np.hanning(window_size)

# Function to calculate STFT using NumPy
def stft(data, window, step):
    # Number of windows
    num_windows = (len(data) - window_size) // step + 1
    
    # Initialize the STFT matrix
    stft_matrix = np.empty((num_windows, window_size), dtype=np.complex_)
    
    # Calculate STFT
    for i in range(num_windows):
        start = i * step
        end = start + window_size
        windowed_data = data[start:end] * window
        stft_matrix[i, :] = np.fft.fft(windowed_data)
    
    # Return the frequency bins and the STFT matrix
    freq_bins = np.fft.fftfreq(window_size, d=1/sampling_rate)
    return freq_bins, stft_matrix

# TODO: check that we're not double skipping the timestamp
for axis_data in data_array[1:]:
    # Calculate STFT for noise and signal
    _, noise_stft = stft(axis_data[:noise_samples], window, overlap)
    freq_bins, signal_stft = stft(axis_data, window, overlap)
    
    # Calculate average noise spectrum and subtract from signal
    avg_noise_spectrum = np.mean(np.abs(noise_stft), axis=0)
    signal_stft_magnitude = np.abs(signal_stft) - avg_noise_spectrum[None, :]
    
    # Clip negative values to zero
    signal_stft_magnitude = np.clip(signal_stft_magnitude, a_min=0, a_max=None)
    
    # Optional: Save or process the resulting magnitude spectrogram data
    # ...

# The 'signal_stft_magnitude' variable now holds the magnitude spectrogram with background noise subtracted.

# TODO: check the gcode script is good.
# then hardcode the path to the file in flow_test
# then start checking the fft stuff
# if that looks good then write data to csv and sftp and plot it
