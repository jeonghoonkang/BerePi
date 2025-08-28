import lgpio

for target in (0, '/dev/gpiochip0', 'gpiochip0', 'pinctrl-rp1'):
    try:
        h = lgpio.gpiochip_open(target)
        print("OK:", target)
        lgpio.gpiochip_close(h)
    except Exception as e:
        print("FAIL:", target, e)


import gpiod

for target in (0, '/dev/gpiochip0', 'gpiochip0', 'pinctrl-rp1'):
    try:
        chip = gpiod.Chip(target)
        print(f"OK:: {target}")
        chip.close()
    except Exception as e:
        print(f"FAIL: {target} {e}")

