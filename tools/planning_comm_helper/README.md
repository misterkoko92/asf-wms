# Planning Communication Helper

Local helper used by `asf-wms` to open:

- WhatsApp conversations without auto-send
- Outlook drafts with HTML and attachments
- planning PDF generated from `Planning.xlsx` through Excel automation only

The helper listens on `127.0.0.1` and is intended to be packaged for macOS and Windows.

Autostart installation:

- macOS: `./.venv/bin/python -m tools.planning_comm_helper.autostart install`
- Windows: `.\.venv\Scripts\python.exe -m tools.planning_comm_helper.autostart install`

Autostart removal:

- macOS: `./.venv/bin/python -m tools.planning_comm_helper.autostart uninstall`
- Windows: `.\.venv\Scripts\python.exe -m tools.planning_comm_helper.autostart uninstall`

Notes:

- On macOS the installer writes `~/Library/LaunchAgents/com.asf.planning_comm_helper.plist`.
- On Windows the installer writes a hidden startup launcher in the current user's Startup folder and a runner script under `%LOCALAPPDATA%\ASF\planning_comm_helper\`.
