# Run on a Raspberry Pi (or any device)

**TL;DR:** This site is a single self-contained `index.html` — all the content is
baked in at build time. No database, no internet, no runtime dependencies. It even
works by double-clicking the file. Serve the folder with any tiny web server to
open it from your phone or another machine on the network.

## The one file that matters

`index.html` holds everything — every chapter, the search index, the diagrams.
Copy that one file anywhere and it works offline. The other files (`_site.css`,
`_app.js`, `_diagrams.js`, `build.js`, and the `.md` sources) are only needed if
you want to **edit the content and rebuild**.

## Option 1 — Python (already on every Pi), 30 seconds

```bash
cd /path/to/docs_mind/docs
python3 -m http.server 9001
```

Then open **http://localhost:9001** on the Pi, or **http://<pi-ip>:9001** from your
laptop or phone on the same network (find the IP with `hostname -I`).

## Option 2 — Always-on with systemd (survives reboot)

```bash
sudo tee /etc/systemd/system/docsmind-site.service >/dev/null <<'EOF'
[Unit]
Description=DocsMind learning site
After=network.target

[Service]
WorkingDirectory=/home/ajmalrasi/docs_mind/docs
ExecStart=/usr/bin/python3 -m http.server 9001
Restart=always
User=ajmalrasi

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now docsmind-site
```

Now it starts on boot and restarts if it crashes. Check it: `systemctl status
docsmind-site`. Logs: `journalctl -u docsmind-site -f`.

> Adjust `WorkingDirectory` and `User` to where you copied the folder. Pick a port
> that doesn't clash with anything else already running on the Pi (the KoiReader
> prep site uses 9000, so this one uses 9001).

## Copying to the Pi

From your computer:

```bash
scp -r docs_mind/docs pi@<pi-ip>:/home/ajmalrasi/docsmind-site
```

Or just copy the single `index.html` onto a USB stick — the whole site is a few
hundred KB of plain text.

## Editing the content

The `.md` files are the source of truth. Edit them, then rebuild:

```bash
cd docs_mind/docs
node build.js          # regenerates index.html
```

If you don't have Node on the Pi, edit the `.md` files on your laptop, run
`node build.js` there, and copy the new `index.html` over.

## Features baked in

- **Search:** type in the box for instant full-text search across all pages
  (↑/↓ to move, Enter to open).
- **Dark / light:** toggle with the ◐ button; the preference is remembered.
- **Quiz mode:** on any *Interview Prep* question page, hit "Quiz me · hide
  answers" to collapse every answer, then click a question to reveal it.
- **Outline:** long pages show an "On this page" jump list.
- **Diagrams:** the pipeline and cosine-similarity diagrams are inline SVG — they
  adapt to light/dark automatically.
- **Fully offline:** no CDN, no external fonts or scripts. Works on an air-gapped
  device, idles at near-zero CPU/RAM — fine on a Pi Zero.

→ Back to the [Overview](README.md).
