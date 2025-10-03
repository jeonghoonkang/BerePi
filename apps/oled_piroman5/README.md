# OLED IP Display

Simple example using **piroman5** Raspberry Pi OLED driver (based on `luma.oled`) to show the current IP address and timestamp on a small OLED screen. The fan on BCM pin 18 of the piroman5 max board is automatically controlled based on the CPU temperature and can be limited to a percentage of a two-minute interval with the ``--fan-duty`` option.

For a display-only variant that leaves the fan untouched, use `oled_piroman.py` which renders the same information without attempting any fan control.


## Installation

Install the required Python packages with pip (use `sudo` on Raspberry Pi OS):

```bash
pip3 install -r requirements.txt
sudo pip3 install luma.core luma.oled 
sudo apt install libgpiod-dev

```

## Running

### `ip_display.py`

Add an entry to ``crontab`` so the script runs every two minutes:

```bash
*/2 * * * * /usr/bin/python3 /path/to/ip_display.py
```

To run the fan for less than the full two minutes when the CPU is cool, pass a percentage with ``--fan-duty`` (default is ``100``):

```bash
*/2 * * * * /usr/bin/python3 /path/to/ip_display.py --fan-duty 75
```

Each run updates the OLED with the current IP address and the date/time (including seconds). The fan is powered on when the script starts. It remains on whenever the CPU temperature is 50 °C or higher and, when cooler, runs only for the specified portion of the two-minute cycle.

The display's last line shows the configured fan duty and updates every five seconds with the remaining time in the two-minute interval, e.g. ``Duty: 75%/120s L115s``.

The line above the duty information shows the current CO₂ concentration read from a serial sensor (e.g. ``CO2 450ppm``).

At startup the script lists all detected USB serial ports and logs the one used for the CO₂ sensor connection.

Two helper functions, ``cpu_fan_on()`` and ``led_fan_on()``, are available if you need to manually activate the CPU fan or its RGB LED fan from other scripts.

For a standalone utility that simply powers the fan and its LEDs on, run
``fan_on.py`` in this directory:

```bash
python3 fan_on.py
```

The script leaves the fan and LEDs running after it exits so you can use it
for quick manual testing.

### `oled_piroman.py`

If you only need to refresh the OLED without any fan control, schedule
``oled_piroman.py`` instead:

```bash
*/2 * * * * /usr/bin/python3 /path/to/oled_piroman.py
```

This variant shows the IP address, date/time, CPU temperature and CO₂ level.
Its last line counts down the remaining time in the two-minute interval,
for example ``L115s``.


```bash
*/2 * * * * /usr/bin/python3 /path/to/ip_display.py --fan-duty 75
```

Each run updates the OLED with the current IP address and the date/time (including seconds). The fan is powered on when the script starts. It remains on whenever the CPU temperature is 50 °C or higher and, when cooler, runs only for the specified portion of the two-minute cycle.

The display's last line shows the configured fan duty and updates every five seconds with the remaining time in the two-minute interval, e.g. ``Duty: 75%/120s L115s``.

The line above the duty information shows the current CO₂ concentration read from a serial sensor (e.g. ``CO2 450ppm``).

At startup the script lists all detected USB serial ports and logs the one used for the CO₂ sensor connection.

Two helper functions, ``cpu_fan_on()`` and ``led_fan_on()``, are available if you need to manually activate the CPU fan or its RGB LED fan from other scripts.

For a standalone utility that simply powers the fan and its LEDs on, run
``fan_on.py`` in this directory:

```bash
python3 fan_on.py
```

The script leaves the fan and LEDs running after it exits so you can use it
for quick manual testing.


```bash
*/2 * * * * /usr/bin/python3 /path/to/ip_display.py --fan-duty 75
```

Each run updates the OLED with the current IP address and the date/time (including seconds). The fan is powered on when the script starts. It remains on whenever the CPU temperature is 50 °C or higher and, when cooler, runs only for the specified portion of the two-minute cycle.

The display's last line shows the configured fan duty and updates every five seconds with the remaining time in the two-minute interval, e.g. ``Duty: 75%/120s L115s``.

The line above the duty information shows the current CO₂ concentration read from a serial sensor (e.g. ``CO2 450ppm``).

At startup the script lists all detected USB serial ports and logs the one used for the CO₂ sensor connection.


```bash
*/2 * * * * /usr/bin/python3 /path/to/ip_display.py --fan-duty 75
```

Each run updates the OLED with the current IP address and the date/time (including seconds). The fan is powered on when the script starts. It remains on whenever the CPU temperature is 50 °C or higher and, when cooler, runs only for the specified portion of the two-minute cycle.

The display's last line shows the configured fan duty and updates every five seconds with the remaining time in the two-minute interval, e.g. ``Duty: 75%/120s L115s``.

The line above the duty information shows the current CO₂ concentration read from a serial sensor (e.g. ``CO2 450ppm``).


### to do
- something
  
### SUDO , GPIO preperation
- sudo adduser {user} gpio 이 없다면, 아래줄 그룹 생성 부터 
- sudo addgroup gpio
- sudo adduser {user} gpio
- sudo vim /etc/udev/rules.d/99-gpio.rules
  - add below lines
  - SUBSYSTEM=="gpio", MODE="0660", GROUP="gpio"
  - SUBSYSTEM=="gpiomem", MODE="0660", GROUP="gpio"
