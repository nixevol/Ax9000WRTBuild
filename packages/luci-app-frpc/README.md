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

The runtime `frpc` package still provides the init script, UCI config generator,
and `/usr/bin/frpc` binary. This LuCI package only manages the client settings.

Build from the AX9000WRTBuild root with the normal firmware build flow, or from
inside the OpenWrt buildroot:

```sh
make package/luci-app-frpc/compile V=s
```

Generated package names are expected to look like:

```text
luci-app-frpc-2.0-r3.apk
luci-i18n-frpc-zh-cn-2.0-r3.apk
```
