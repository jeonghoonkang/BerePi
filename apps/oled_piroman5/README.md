# OLED IP Display

Simple example using **piroman5** Raspberry Pi OLED driver (based on `luma.oled`) to show the current IP address and timestamp on a small OLED screen. The fan on BCM pin 18 of the piroman5 max board is automatically controlled based on the CPU temperature.


## Installation

Install the required Python packages with pip (use `sudo` on Raspberry Pi OS):

```bash
pip3 install -r requirements.txt
sudo pip3 install luma.core luma.oled 
sudo apt install libgpiod-dev

```

## Running

Add an entry to ``crontab`` so the script runs every minute:

```bash
* * * * * /usr/bin/python3 /path/to/ip_display.py
```

Each run updates the OLED with the current IP address and the date/time (including seconds). The fan is powered on when the script starts. It remains on whenever the CPU temperature is 50 °C or higher and turns off once the temperature falls below that threshold.

