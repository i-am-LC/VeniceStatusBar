#!/usr/bin/env python3
"""Display Venice balances in a GTK status menu."""
import json
import math
import os
from pathlib import Path
import threading

import requests
import gi

gi.require_version('Gtk', '3.0')
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except ValueError:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
from gi.repository import Gtk, GLib

CONFIG_FILE = Path(GLib.get_user_config_dir()) / 'venice-indicator' / 'config.json'


def balance_text(data):
    balances = data['balances']
    def number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Invalid balance')
        return value
    diem = balances.get('diem')
    usd = balances.get('usd')
    allocation = data.get('diemEpochAllocation')
    diem_text = 'Diem: unavailable' if diem is None else f'Diem: {number(diem):.2f}'
    if diem is not None and allocation is not None:
        diem_text += f' / {number(allocation):.2f}'
    usd_text = 'USD: unavailable' if usd is None else f'USD: ${number(usd):.2f}'
    return f'{diem_text}  |  {usd_text}'


class VeniceCreditIndicator:
    def __init__(self):
        self.busy = False
        self.closed = False
        self.token = os.environ.get('VENICE_API_KEY', '').strip()
        if not self.token:
            try:
                self.token = json.loads(CONFIG_FILE.read_text())['api_key'].strip()
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                pass
        self.indicator = AppIndicator3.Indicator.new(
            'venice-credits', 'dialog-information-symbolic',
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title('Venice AI Balance')
        menu = Gtk.Menu()
        self.balance_item = Gtk.MenuItem(label='Loading…')
        self.balance_item.set_sensitive(False)
        menu.append(self.balance_item)
        menu.append(Gtk.SeparatorMenuItem())
        self.refresh_item = Gtk.MenuItem(label='Refresh Now')
        self.refresh_item.connect('activate', self.fetch_balance)
        menu.append(self.refresh_item)
        key_item = Gtk.MenuItem(label='Set API Key…')
        key_item.connect('activate', self.set_api_key)
        menu.append(key_item)
        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label='Quit')
        quit_item.connect('activate', self.quit)
        menu.append(quit_item)
        menu.show_all()
        self.indicator.set_menu(menu)
        self.fetch_balance()
        self.timer = GLib.timeout_add_seconds(30 * 60, self.fetch_balance)

    def set_api_key(self, widget=None):
        dialog = Gtk.Dialog(title='Venice API Key', flags=Gtk.DialogFlags.MODAL)
        dialog.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Save', Gtk.ResponseType.OK)
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_placeholder_text('Paste your Venice admin API key')
        entry.set_activates_default(True)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.get_content_area().pack_start(entry, True, True, 12)
        dialog.show_all()
        result = dialog.run()
        token = entry.get_text().strip()
        dialog.destroy()
        if result != Gtk.ResponseType.OK or not token:
            return
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as config:
                os.fchmod(config.fileno(), 0o600)
                json.dump({'api_key': token}, config)
        except OSError:
            self.balance_item.set_label('Could not save API key')
            return
        self.token = token
        self.fetch_balance()

    def fetch_balance(self, widget=None):
        if self.closed or self.busy:
            return True
        if not self.token:
            self.balance_item.set_label('Choose Set API Key… to connect')
            return True
        self.busy = True
        self.refresh_item.set_sensitive(False)
        self.balance_item.set_label('Refreshing…')
        threading.Thread(target=self.request_balance, args=(self.token,), daemon=True).start()
        return True

    def request_balance(self, token):
        try:
            with requests.get('https://api.venice.ai/api/v1/billing/balance',
                              headers={'Authorization': f'Bearer {token}'}, timeout=(5, 10)) as response:
                if response.status_code in (401, 403):
                    label = 'Authentication failed — check your admin API key'
                elif response.status_code == 429:
                    label = 'Rate limited — try again later'
                elif response.status_code != 200:
                    label = f'Venice API error ({response.status_code})'
                else:
                    label = balance_text(response.json())
        except requests.Timeout:
            label = 'Request timed out — try Refresh Now'
        except requests.exceptions.JSONDecodeError:
            label = 'Unexpected response from Venice'
        except requests.RequestException:
            label = 'Connection failed — check your network'
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            label = 'Unexpected response from Venice'
        GLib.idle_add(self.finish_refresh, token, label)

    def finish_refresh(self, token, label):
        if self.closed:
            return False
        self.busy = False
        self.refresh_item.set_sensitive(True)
        if token != self.token:
            self.fetch_balance()
        else:
            self.balance_item.set_label(label)
            self.indicator.set_title(f'Venice: {label}')
        return False

    def quit(self, widget=None):
        self.closed = True
        GLib.source_remove(self.timer)
        Gtk.main_quit()


if __name__ == '__main__':
    indicator = VeniceCreditIndicator()
    Gtk.main()
