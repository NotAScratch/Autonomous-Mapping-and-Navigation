#!/usr/bin/env bash
# Install Barrier on the Jetson (the CLIENT: it receives the laptop's keyboard and mouse).
# Run on the Jetson:  bash install_jetson.sh
set -euo pipefail

sudo apt-get update
sudo apt-get install -y barrier

# Barrier only works on an X11 desktop, not Wayland.
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    echo "WARNING: this desktop runs Wayland. Log out, click the gear icon, choose 'Ubuntu on Xorg'."
fi

# Start the Barrier window automatically when the desktop logs in.
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/barrier.desktop <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Barrier
Exec=barrier
X-GNOME-Autostart-enabled=true
DESKTOP

echo
echo "Done. Barrier $(dpkg-query -W -f='${Version}' barrier) installed."
echo "This Jetson's hostname (name the screen this on the laptop): $(hostname)"
echo "Next: run 'barrier &' -> Client -> untick Auto config -> enter the laptop's IP -> Start."
