# luci-app-frpc

AX9000WRTBuild local LuCI frontend for the frp client.

This package is based on `liuyi-htu/luci-app-frp`, but is intentionally
client-only:

- Registers `Services -> frp Client`.
- Uses the LuCI route `/admin/services/frpc`.
- Reads and writes only `/etc/config/frpc`.
- Controls only `/etc/init.d/frpc`.
- Depends on `frpc`, not `frps`.
- Provides `luci-i18n-frpc-zh-cn`.
- Groups settings into task-oriented tabs and keeps proxies on a separate tab.
- Supports validated TOML/INI raw configuration editing and previews the
  generated runtime INI while page configuration is active.
- Shows runtime state and bounded logs on one page.
- Uploads any named AArch64 frpc binary into the fixed `/usr/bin/frpc` path,
  with automatic backup and restore support.
- Enables boot startup when the service is started manually and disables boot
  startup when the service is stopped manually.

The runtime `frpc` package provides the init script, UCI config generator, and
the initial `/usr/bin/frpc` binary. This LuCI package adds a launcher and a
restricted rpcd manager for raw configuration, service, log, and core actions.

Build from the AX9000WRTBuild root with the normal firmware build flow, or from
inside the OpenWrt buildroot:

```sh
make package/luci-app-frpc/compile V=s
```

Generated package names are expected to look like:

```text
luci-app-frpc-2.0-r7.apk
luci-i18n-frpc-zh-cn-2.0-r7.apk
```
