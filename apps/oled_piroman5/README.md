# OLED IP Display

Simple example using **piroman5** Raspberry Pi OLED driver (based on `luma.oled`) to show the current IP address on a small OLED screen. The script also turns on the cooling fan connected to BCM pin 18 on the piroman5 max board using the `gpiod` package.

## Running

```bash
sudo python3 ip_display.py
```

The fan will remain on while the script is running.
