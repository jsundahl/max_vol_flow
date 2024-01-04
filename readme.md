# Printer Flow Rate Test Script for Creality K1

## Disclaimer!
This is just something I developed quickly for myself with no unit tests. I'm
just some random guy on the internet so use this at your own peril. Also
the script's max flow rate results may differ from practical sustained
extrusion rates. Short peaks may be tolerated by the printer, but sustained
high rates could cause issues.

## Overview
This script conducts a volumetric flow rate test to identify the maximum
volumetric flow your printer can achieve. This script works by extruding at a
certain rate and using the accelerometer to check for extruder clicking.

## Requirements
- Python 3
- NumPy (pre-installed on K1 main board)
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

don't stomp or hit your printer during the test or you'll screw it up.
