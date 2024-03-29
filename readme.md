# Printer Flow Rate Test Script for Creality K1/Max

## Disclaimer!
This is just something I developed quickly for myself with no unit tests. I'm
just some random guy on the internet so use this at your own peril. Also
the script's max flow rate results may differ from practical sustained
extrusion rates. Short peaks may be tolerated by the printer, but sustained
high rates could cause issues.

## Overview
This script conducts a volumetric flow rate test to identify the maximum
volumetric flow your printer can achieve. This script works by extruding at a
certain rate and using the accelerometer to check for extruder clicking. The
rate to extrude at is determined by a binary search from the given min flow to
the given max flow.

## Demo
The following is 4x speed with homing and heating cut for those of you with
short attention spans ;). Typically it takes a little under 5 minutes to run if
you're starting cold.

https://github.com/jsundahl/max_vol_flow/assets/24578556/86fd0837-0958-4221-968e-b8b979bc4e4c


## Requirements
- K1 printer (you could probably make this work on a different printer with some small tinkering)
- Python3 (pre-installed on any klipper machine)
- NumPy (pre-installed on any klipper machine)
- `requests` library

To install `requests`, SSH into your main board and execute:
```
python3 -m pip install requests
```

## Usage
Run the script with the following arguments:
- `--temp`: Extrusion temperature (°C).
- `--min-flow`: The minimum flow rate (mm^3/s). Defaults to 5.
- `--length`: Filament length to extrude (mm). Defaults to 50.
- `--max-flow`: Maximum flow rate to test (mm^3/s). Defaults to 30.

Don't stomp or hit your printer during the test or you'll screw it up.
