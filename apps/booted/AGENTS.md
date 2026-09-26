# Repository Guidelines

## Project Structure & Module Organization
- `apps/` holds service code grouped by feature; e.g., `apps/booted/booted_lcd.py` drives the LCD boot banner, while `apps/lcd_berepi/` and `apps/led_berepi/` expose shared display libraries.
- `scripts/` and root shell utilities (`startup_sw.sh`, `first_run_install.sh`) orchestrate provisioning and scheduled jobs; keep new automation scripts here.
- `setup/` contains environment bootstrap scripts such as `setup/init.sh`; run these on fresh Raspberry Pi images.
- `documents/`, `files/`, and `logs/` store hardware notes, reference assets, and captured outputs. Place hardware configs under `documents/` and keep generated logs out of version control.

## Build, Test, and Development Commands
- `python3 apps/booted/booted_lcd.py` verifies LCD output during development; run from the repo root so relative library paths resolve.
- `bash setup/init.sh` prepares a Pi with required packages and baseline configuration.
- `pytest apps/s3_utils` executes the maintained automated tests; add similar suites when extending other modules.
- `pip install -r apps/oled_piroman5/requirements.txt` (or matching module requirements file) installs per-app dependencies.

## Coding Style & Naming Conventions
- Default to Python 3 with PEP 8 spacing (4 spaces, `snake_case` filenames); keep module-level constants uppercase and include encoding headers only when necessary.
- Shell scripts should start with `#!/bin/bash`, be executable, and prefer descriptive `lower_snake_case` filenames (`cron_run.sh` style).
- Log hardware-specific paths (e.g., `/home/pi/devel/BerePi`) via constants to ease overrides; document non-default pins or buses in comments near usage.

## Testing Guidelines
- Name Python tests `test_<feature>.py` and mirror package structure under `apps/<module>/tests` or alongside implementation as in `apps/s3_utils/test_s3_utils.py`.
- Use `pytest.mark.skipif` for hardware-conditional checks and record manual validation steps in the PR when automation is not feasible.
- Aim to cover new data flows, sensor drivers, and command-line flags; add smoke scripts under `scripts/` for long-running edge cases.

## Commit & Pull Request Guidelines
- Follow the existing short, imperative commit style (`Add MinIO connection diagnostic script`, `Update README.md`); include scope prefixes when touching multiple subsystems.
- Reference linked issues or hardware tickets in the body, note Raspberry Pi model/OS tested, and attach logs or screenshots for UI-facing changes.
- PR descriptions should outline purpose, testing performed (`pytest`, hardware dry-run), and deployment or crontab updates needed.
