# Task: esphome-echo-mini — deliverable

## Summary
Produced a complete ESPHome configuration for the **M5Stack Atom Echo**
(user clarification: the device is the 24×24 mm Atom Echo with ESP32-PICO-D4,
PDM mic and NS4168 I2S amp — *not* "Echo Mini" or "Echo Dot"), plus flash
guide, troubleshooting doc, and a project README. The config wires the
voice_assistant component to Home Assistant's Assist pipeline (Wyoming
protocol) with on-device noise suppression, AGC, push-to-talk on the
front button, and per-state LED colours on the SK6812.

## Changed files
- `esphome-atom-echo.yaml` — full ESPHome 2025.5+ config (board
  `m5stack-atom-echo`, PDM mic GPIO0/34, I2S speaker GPIO19/33/22,
  LED GPIO27, button GPIO39, voice_assistant with state LED colours).
- `FLASH_INSTRUCTIONS.md` — USB flash + WiFi + HA pipeline setup, secrets
  template.
- `TROUBLESHOOTING.md` — common issues (discovery, audio, half-duplex,
  WiFi, LED, pipeline).
- `README.md` — project overview, pin map, TL;DR.

## Notes for the verifier
- **Device clarification**: original brief said "Echo Mini" but user
  follow-up corrected it to **M5Stack Atom Echo** (ESP32-PICO-D4,
  PDM mic, not ESP32-S3 / I2S). All deliverables written for Atom Echo
  v1.x pinout: mic GPIO0/34, speaker GPIO19/33/22, LED GPIO27,
  button GPIO39.
- **Wake word handling**: `use_wake_word: false` — wake word runs in
  Home Assistant's Assist pipeline (microWakeWord / OpenWakeWord /
  Porcupine). The device only streams raw audio.
- **Board name**: `m5stack-atom-echo` is the named board in modern
  ESPHome; if a user's installation does not recognise it, the fallback
  is `esp32dev` (same chip family).
- **Tool runtime note**: the producer session ran in a sandbox where
  the `Bash` tool was unavailable (`Tool Bash not found` on every
  invocation). All file content was prepared as text by the producer
  and was committed to disk by the team owner in this final pass.
