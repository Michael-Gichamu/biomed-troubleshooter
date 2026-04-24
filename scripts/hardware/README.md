# Hardware validators

Developer-facing validation scripts for the two USB multimeter chipsets this
project supports. **Not part of the automated test suite** — they talk to real
serial hardware (or, in `--mock` mode, feed synthetic frames through the
parser).

| Script                  | Meter chipset | Example meter       |
| ----------------------- | ------------- | ------------------- |
| `validate_ms8250d.py`   | MS8250D       | Mastech MS8250D     |
| `validate_dtm0660.py`   | DTM0660       | Generic FS9721-like |

## When to run

* After reseating / reflashing a CP210x USB-to-serial cable
* When bringing up a new meter unit
* When editing the frame parsers in `src/infrastructure/usb_multimeter.py`
  (run the `--mock` mode as a smoke test before committing)

## Usage

```bash
# Offline smoke test — no hardware required
python scripts/hardware/validate_ms8250d.py
python scripts/hardware/validate_dtm0660.py --mock

# Live capture — requires the meter connected via USB
python scripts/hardware/validate_ms8250d.py --live
python scripts/hardware/validate_dtm0660.py --live --port COM3
```

## Pytest coverage

The offline parser tests in these scripts will be extracted to
`tests/unit/test_usb_multimeter_parsers.py` as part of Phase E of the roadmap
(see `docs/plan/*.md`). Until then, this directory is the canonical home for
manual / semi-manual parser validation.
