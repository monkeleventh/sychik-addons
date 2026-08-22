# Troubleshooting — M5Stack Atom Echo voice satellite

> Conventions: the device's serial log is your best friend. Re-attach with
> `esphome logs atom-echo.local` or via the web installer to see what is
> actually happening. Symptoms below assume you have access to the log.

---

## A. Device never appears in Home Assistant

1. **Wrong network / VLAN.** Atom Echo needs to be on the same L2/L3 network
   as HA, and `mDNS` must be allowed. Many consumer routers block mDNS
   across guest networks. Test:
   ```bash
   ping atom-echo.local
   ```
   If that fails, mDNS is filtered. Either:
   - enable mDNS reflection on the router / switch, or
   - add a static IP + manual entry in HA (Settings → ESPHome → Add →
     enter the IP).

2. **Encryption key mismatch.** HA shows
   `Can't connect to ESPHome API: Invalid encryption key`. Recreate
   `api_encryption_key` in `secrets.yaml`, reflash, and on the HA side go
   to the integration's overflow menu → **Reconfigure** and paste the same
   key.

3. **API port blocked.** ESPHome uses TCP `6053`. Make sure the firewall
   on the HA host and any intermediate router does not block it.

4. **Power-USB issue.** The tiny Atom Echo draws ~300 mA peaks on TX. Some
   laptops / hubs can't supply that; the device boots, prints a few lines,
   then reboots. Use a different cable or a powered USB hub.

5. **Flashed with someone else's firmware.** Hold the front button while
   plugging in USB, then re-flash with `esphome run ...` over USB — the
   button forces download mode.

---

## B. No sound from the speaker / device can't hear you

1. **PDM mic sample rate mismatch.** If you changed `sample_rate` in the
   YAML to anything other than `16000`, the HA pipeline will not recognise
   the stream. Stick to 16000 Hz mono.

2. **Wrong speaker pins / wrong I2S driver.** Atom Echo uses the **new**
   I2S driver. ESPHome 2024.6+ defaults to the new driver — do **not**
   set `use_legacy: true`. If you must keep an older ESPHome, then *do*
   set `use_legacy: true` and use the legacy `bck_pin`/`ws_pin`/`data_pin`
   field names.

3. **Speaker wired backwards / NS4168 SD pin.** NS4168 needs SD (shutdown)
   pulled high to enable the amp. On Atom Echo the schematic does that
   internally; if you wired your own breakout, the amp stays in shutdown
   and you hear nothing.

4. **Volume too low / `volume_multiplier` set wrong.** Start at `1.0` and
   adjust. Inside the Assist pipeline you can also tweak the TTS output
   gain.

5. **Mic mute button not set up.** With `use_wake_word: false` the mic is
   closed by default; it opens only on a wake-word trigger or a button
   press. Make sure your pipeline has a wake word configured, or that
   `voice_assistant.start` is fired (e.g. by a HA automation tied to a
   real button event).

6. **PDM data pin floating.** GPIO 34 on ESP32 is input-only — that's
   fine for PDM data (it's a clocked peripheral input), but make sure
   the pin is not also used by something else (a stray jumper, the
   wrong board preset).

---

## C. Half-duplex / echo / howl / clipped first syllable

These are symptoms of mic and speaker being open at the same time, or of
acoustic feedback.

1. **Acoustic feedback.** The Atom Echo speaker is loud for its size and
   sits a few cm from the mic. Enable `noise_suppression_level: 2` and
   `auto_gain: 31dBFS` in the `voice_assistant:` block (already in the
   provided YAML). On the HA side, enable AEC (acoustic echo
   cancellation) if your pipeline supports it (Wyoming `openwakeword`
   does, and the `microWakeWord` add-on has it as well).

2. **Clipped first word.** If the wake-word engine has not yet signalled
   the ESPHome device to start streaming, the first ~100–200 ms of your
   sentence are lost. This is a protocol limitation. Enable
   "Start listening immediately when wake word is detected" in the
   pipeline if available, or use a longer wake phrase.

3. **Both directions busy at once.** `voice_assistant` is full-duplex at
   the protocol level, but on a single-speaker + single-mic device you
   should still expect brief gaps while the TTS plays (the mic is
   streamed over the same WiFi, and the NS4168 amp is loud enough to
   saturate the mic if AEC is off). Lower `volume_multiplier` to `0.6`
   to start.

---

## D. WiFi keeps reconnecting / audio cuts out

1. **2.4 GHz only.** ESP32 does not do 5 GHz. Make sure your SSID is
   broadcast on 2.4 GHz or that the 5 GHz radio has the same SSID +
   password (most APs do this by default).

2. **Power save mode.** `power_save_mode: light` is a good trade-off. If
   you use `NONE` the device can overheat in a closed box; if you use
   `HIGH` the audio stream stalls every few seconds. Stick with `light`.

3. **RSSI below -75 dBm.** The `sensor.atom_echo_wifi_rssi` entity shows
   the signal. If it's worse than -75 dBm consistently, move the device
   closer to the AP or add a 2.4 GHz repeater.

4. **Captive portal stealing focus.** If the fallback AP
   `M5Stack Atom Echo Fallback` ever activates (e.g. wrong WiFi password
   typed in once), clients connected to the same AP will be redirected to
   the captive portal and break mDNS. Reflash the device with the right
   `wifi_ssid` / `wifi_password` in `secrets.yaml` to disable the AP.

5. **Static IP.** For reliability, add a static IP reservation in your
   router (DHCP reservation) or in the YAML:
   ```yaml
   wifi:
     manual_ip:
       static_ip: 192.168.1.50
       gateway:  192.168.1.1
       subnet:   255.255.255.0
       dns1:     1.1.1.1
   ```

---

## E. LED not behaving as expected

1. **Wrong chipset.** Atom Echo ships with **SK6812** (a 4-pin
   APA-102-like part, but wired as a single-wire NeoPixel). If you flash
   with `chipset: WS2812` on some clones it still works; on others it
   flickers. Try `chipset: SK6812` and `rgb_order: GRB`.

2. **Multiple `light.turn_on` racing.** Each `on_*` action calls
   `light.turn_on` and immediately returns. If you have a startup animation
   plus state actions, they overlap. Use `light.control` in a
   `script.execute` if you need sequencing.

3. **GPIO 27 conflicts.** Some clones repurpose GPIO 27 for the IR LED
   or an extra button. If `light.atom_echo_led` works but is wrong,
   inspect the PCB and adjust the pin.

---

## F. Voice pipeline shows "no wake word available"

You forgot to install a wake-word engine add-on. Go to
**Settings → Add-ons → Add-on Store**, install one of:
- **microWakeWord** (recommended, on-device friendly)
- **OpenWakeWord** Wyoming add-on
- **Porcupine** (requires a Picovoice key)

Then attach it to your pipeline.

---

## G. Useful commands cheat sheet

```bash
# View live logs
esphome logs atom-echo.local

# Compile only (no flash)
esphome compile esphome-atom-echo.yaml

# Over-the-air update
esphome run esphome-atom-echo.yaml --device atom-echo.local

# Validate config
esphome config esphome-atom-echo.yaml

# See raw decrypted HA ↔ device traffic
# (Settings → Devices & Services → ESPHome → device → ⋯ → Enable
#  diagnostic logging)
```

If nothing here helps, capture ~30 lines of serial log from a clean
reboot + one button press and post it on the
[ESPHome Discord](https://discord.gg/KhAMKrd) or
[Home Assistant community forum](https://community.home-assistant.io/c/esphome/)
with the device's `api.connected` state from the HA side.
