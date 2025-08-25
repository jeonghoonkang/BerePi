# OLED IP Display

Simple example using **piroman5** Raspberry Pi OLED driver (based on `luma.oled`) to show the current IP address and timestamp on a small OLED screen. The fan on BCM pin 18 of the piroman5 max board is automatically controlled based on the CPU temperature and can be limited to a percentage of a two-minute interval with the ``--fan-duty`` option.


## Installation

Install the required Python packages with pip (use `sudo` on Raspberry Pi OS):

```bash
pip3 install -r requirements.txt
sudo pip3 install luma.core luma.oled 
sudo apt install libgpiod-dev

```

## Running

Add an entry to ``crontab`` so the script runs every two minutes:

```bash
*/2 * * * * /usr/bin/python3 /path/to/ip_display.py
```

To run the fan for less than the full two minutes when the CPU is cool, pass a percentage with ``--fan-duty`` (default is ``100``):

```bash
*/2 * * * * /usr/bin/python3 /path/to/ip_display.py --fan-duty 75
```

Each run updates the OLED with the current IP address and the date/time (including seconds). The fan is powered on when the script starts. It remains on whenever the CPU temperature is 50 °C or higher and, when cooler, runs only for the specified portion of the two-minute cycle.

The display also shows the current fan duty setting as ``Duty: <percentage>/120s`` on the last line.

