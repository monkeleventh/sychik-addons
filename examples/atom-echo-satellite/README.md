# M5Stack Atom Echo — HA Voice Satellite

ESPHome firmware + setup guide for the **M5Stack Atom Echo** (the original
24 × 24 mm cube with a single button, RGB LED, PDM microphone and small
NS4168-driven speaker) so it works as a **voice satellite** for Home
Assistant through the **Assist pipeline** (Wyoming-compatible).

## What is inside this folder

| File                       | Purpose |
|----------------------------|---------|
| `esphome-atom-echo.yaml`   | Full ESPHome config: ESP32-PICO-D4 + PDM mic + I2S speaker + LED + button + voice_assistant with AEC/NS/AGC and per-state LED colours. |
| `FLASH_INSTRUCTIONS.md`    | Step-by-step: install ESPHome CLI / Web, prepare `secrets.yaml`, flash over USB, add to HA, create a Wyoming/Assist pipeline. |
| `TROUBLESHOOTING.md`       | Common issues: device not discovered, no audio, half-duplex, WiFi, LED, pipeline. |
| `README.md`                | This file. |

## Hardware at a glance

- **MCU**: ESP32-PICO-D4 (Xtensa LX6 dual-core, 240 MHz). Not ESP32-S3.
- **Mic**: PDM MEMS (SPM1423-style) on **GPIO0 (CLK) / GPIO34 (DATA)**.
- **Speaker**: NS4168 I2S mono amp on **GPIO19 / GPIO33 / GPIO22**.
- **LED**: SK6812 (NeoPixel-compatible) on **GPIO27**.
- **Button**: Tactile, active-low, internal pull-up, on **GPIO39**.

## What the device does — and does not do

- ✅ Streams 16 kHz mono PCM from the PDM mic to Home Assistant.
- ✅ Plays back TTS audio through the I2S amp + mini speaker.
- ✅ Renders voice-pipeline state on the RGB LED.
- ✅ Push-to-talk via the front button.
- ❌ Does **not** detect a wake word on its own — wake word, STT and
  intent classification all run in HA (microWakeWord / OpenWakeWord /
  Porcupine, Whisper, HA intents).

## Quick start (TL;DR)

```bash
pipx install esphome
# create secrets.yaml from the template in FLASH_INSTRUCTIONS.md
esphome run esphome-atom-echo.yaml     # flash over USB
# then in HA: Settings → Devices & Services → ESPHome → auto-discovered
# → Settings → Voice assistants → Pipelines → expose Atom Echo
```

## Tested with
- ESPHome 2025.5.x and newer
- Home Assistant 2025.x (Assist pipeline + Wyoming)
- Atom Echo hardware revision 1.0 / 1.2 (M5Stack official store)
- Add-ons: microWakeWord, Whisper, Piper

## License & warranty
Provided as-is, no warranty. Verify the pinout against your specific
board revision if you hand-built the wiring. The M5Stack Atom Echo is
identical across most known revisions, but clones from AliExpress may
differ — always check the schematic before connecting external hardware.
