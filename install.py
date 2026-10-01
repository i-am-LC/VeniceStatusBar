#!/usr/bin/env python3
"""Install the indicator for the current user, without root privileges."""
import os
from pathlib import Path
import shutil


def desktop_argument(path):
    value = str(path)
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\' + char)
    return '"' + value.replace('\\', '\\\\').replace('%', '%%') + '"'


def install(source, data_home, config_home):
    target = data_home / 'venice-indicator'
    target.mkdir(parents=True, exist_ok=True)
    script = target / 'venice_indicator.py'
    shutil.copyfile(source / 'venice_indicator.py', script)
    script.chmod(0o755)
    template = (source / 'deployment/venice-indicator.desktop').read_text()
    desktop = template.replace('@SCRIPT_PATH@', desktop_argument(script))
    autostart = config_home / 'autostart'
    autostart.mkdir(parents=True, exist_ok=True)
    entry = autostart / 'venice-indicator.desktop'
    entry.write_text(desktop)
    entry.chmod(0o644)
    return script, entry


if __name__ == '__main__':
    home = Path.home()
    data_home = Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share')
    config_home = Path(os.environ.get('XDG_CONFIG_HOME') or home / '.config')
    if not data_home.is_absolute() or not config_home.is_absolute():
        raise SystemExit('XDG_DATA_HOME and XDG_CONFIG_HOME must be absolute paths')
    script, entry = install(Path(__file__).resolve().parent, data_home, config_home)
    print(f'Installed: {script}\nAutostart: {entry}')
    print('Quit any running instance, then launch the installed script with /usr/bin/python3.')
