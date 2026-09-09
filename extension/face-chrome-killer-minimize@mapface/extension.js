/* extension.js - Chrome minimize D-Bus API for Wayland */
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import Gio from 'gi://Gio';

const MinimizeInterface = `
<node>
  <interface name="org.mapface.ChromeMinimize">
    <method name="MinimizeChrome">
      <arg type="i" direction="out" name="count"/>
    </method>
  </interface>
</node>`;

export default class FaceChromeKillerMinimizeExtension extends Extension {
    enable() {
        this._impl = {
            MinimizeChrome: () => this._minimizeChrome(),
        };
        this._dbus = Gio.DBusExportedObject.wrapJSObject(
            MinimizeInterface,
            this._impl,
        );
        this._dbus.export(Gio.DBus.session, '/org/mapface/ChromeMinimize');
    }

    disable() {
        if (this._dbus) {
            this._dbus.unexport();
            this._dbus = null;
        }
    }

    _minimizeChrome() {
        let count = 0;
        for (const actor of global.get_window_actors()) {
            const mw = actor.meta_window;
            if (!mw || !mw.can_minimize())
                continue;

            const wmClass = (mw.get_wm_class() || '').toLowerCase();
            const wmInstance = (mw.get_wm_class_instance() || '').toLowerCase();
            const title = (mw.get_title() || '').toLowerCase();

            const isChrome =
                wmClass.includes('chrome') ||
                wmClass.includes('chromium') ||
                wmInstance.includes('chrome') ||
                wmInstance.includes('chromium') ||
                title.includes('google chrome') ||
                title.includes('chromium');

            if (isChrome) {
                mw.minimize();
                count++;
            }
        }
        return count;
    }
}
