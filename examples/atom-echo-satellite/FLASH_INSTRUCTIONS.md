# Flash M5Stack Atom Echo as HA Voice Satellite

## 0. Prerequisites
- M5Stack Atom Echo (the small 24×24 mm cube, **not** Atom Echo Dot, **not**
  AtomS3 Echo — different hardware, different config).
- USB-C cable (data + power). Some cheap charge-only cables do not work.
- 2.4 GHz WiFi with reasonable signal at the device location. Atom Echo uses
  the original ESP32 which only supports 2.4 GHz.
- Home Assistant 2024.4 or newer (Assist pipeline + Wyoming).

## 1. Install ESPHome

You need *one* of these — pick whichever is easier for you.

### Option A — ESPHome Web (browser, no install)
1. Open https://web.esphome.io/ in a Chromium-based browser
   (Chrome / Edge / Brave; Firefox may need extra steps for USB).
2. Click **CONNECT** and pick the serial port that appears when you plug the
   Atom Echo in.
3. Click **INSTALL** and either provide a pre-built `.bin` (compile first with
   the CLI) or use the **"Open ESPHome Builder"** flow if available.

### Option B — ESPHome CLI (recommended for repeat use)
```bash
pipx install esphome      # or: pip install esphome
esphome version           # should be >= 2025.5.0
```

## 2. Prepare project files
Put both files in the same folder:
```
atom-echo/
├── esphome-atom-echo.yaml
└── secrets.yaml
```
Edit `secrets.yaml` and set `wifi_ssid`, `wifi_password`, plus
`api_encryption_key` (generate with `openssl rand -base64 32`).

Example `secrets.yaml`:
```yaml
wifi_ssid: "YourSSID"
wifi_password: "YourWifiPassword"
ap_fallback_password: "atomecho1234"
api_encryption_key: "BASE64_KEY_GENERATED_BY_HA_OR_ESPHOME_CLI"
ota_password: "another-long-random-string"
```

## 3. First flash (over USB)
1. Connect Atom Echo via USB-C to your computer.
2. The device enumerates as a serial port. On Linux it's typically
   `/dev/ttyUSB0`; on macOS `/dev/cu.usbserial-*`; on Windows `COMx`.
3. Run:
   ```bash
   esphome run esphome-atom-echo.yaml
   ```
   Pick the USB serial port when prompted. First flash takes 3–5 minutes.
4. When asked to enter WiFi creds, you can either:
   - rely on the `secrets.yaml` you filled in (CLI picks them up), or
   - hold the front button for ~5 s at boot to start the fallback AP
     `M5Stack Atom Echo Fallback` and configure WiFi through the captive
     portal (http://192.168.4.1).
5. After the device boots it prints its IP and `API` connection status over
   the serial log — useful to confirm it joined WiFi.

## 4. Add to Home Assistant
1. **Settings → Devices & Services → Integrations → Add Integration**.
2. Search for **ESPHome** and pick it.
3. The Atom Echo should appear automatically on the same network (mDNS /
   `.local`). If not, click **Set up another instance of ESPHome** and
   enter the IP shown on the serial log.
4. When prompted, paste the `api_encryption_key` from `secrets.yaml` (or the
   key you configured in HA when first adopting it).
5. You should now see entities:
   - `button.atom_echo_button` (the front button)
   - `light.atom_echo_led` (status LED)
   - `sensor.atom_echo_wifi_rssi`
   - `text_sensor.atom_echo_esphome_version`
   - and a `voice_assistant` media device.

## 5. Create a Voice Assistant pipeline (Wyoming)
The Atom Echo does not run wake-word/STT/TTS locally — it is a thin
streaming satellite. All the brains live in HA's Assist pipeline.

1. **Settings → Voice assistants → Assistants → Create assistant**
   - Name: `Atom Echo`
   - Language: your choice
2. **Settings → Voice assistants → Pipelines → Create pipeline**
   - Name: `Atom Echo`
   - Assistant: `Atom Echo`
   - **Wake word** (the wake word is processed by HA): pick
     `microWakeWord` (recommended) or `wyoming` Porcupine. Configure at
     least one wake word in the **Wake words** section.
   - **Speech-to-text**: e.g. `Whisper` (Home Assistant Cloud) or
     `Whisper local` (faster-whisper add-on) or Wyoming `Vosk`.
   - **Text-to-speech**: e.g. `Home Assistant Cloud Piper` (fast) or
     `Wyoming Piper` (self-hosted). Add the corresponding Wyoming add-on
     first if you go self-hosted.
   - **Intent recognition**: default `Home Assistant`.
3. Open the pipeline and scroll to **Expose** → tick **Atom Echo** as a
   satellite for this pipeline. You can also set the **announce
   response** / **play wake-up / end tones** here.
4. Done. The next time the Atom Echo reconnects, the on-device LED will
   show the pipeline state (blue = listening, yellow = thinking, etc.).

## 6. Daily use
- Press the front button once to start a session *without* a wake word
  (or to push-to-talk).
- Hold the button ≥ 1 s to cancel an in-flight session.
- Say your wake word (e.g. "Hey Jarvis") — Atom Echo's blue LED will pulse.
- Speak, wait for the answer, listen.

## 7. Updating firmware later
- All subsequent flashes can be done **over-the-air** from HA:
  *Settings → Devices & Services → ESPHome → Atom Echo → Update → Upload
  firmware*. Or via CLI:
  ```bash
  esphome run esphome-atom-echo.yaml --device atom-echo.local
  ```
