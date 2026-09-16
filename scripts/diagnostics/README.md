# AX9000 内核崩溃采集

这些脚本为已经运行的 AX9000 固件加载匹配的 pstore/ramoops 模块，并在后续启动时将保留的记录归档到闪存。安装不会重启网络或设备。

## 适用范围

- 设备：`xiaomi,ax9000`
- 内核：`6.12.91`
- kernel 包指纹：`3ca07581b60107336a14a0678bbe242b`
- 源码：Qosmio `openwrt-ipq` 提交 `d6848fa2ea00193b5b7d3973e3990da7f608027c`，包含本项目设备补丁
- 模块：`reed_solomon.ko`、`pstore.ko`、`ramoops.ko`

模块必须从相同源码、内核配置及补丁构建。安装器会核对设备、kernel 包指纹和模块校验文件；不支持强制忽略版本。升级固件或更换内核后应重新构建模块，不能复用旧包。

## 安装

将三个模块、`modules.sha256` 和本目录中的三个脚本放在路由器的同一临时目录，执行：

```sh
sh install-crash-capture.sh
```

安装器将模块复制到 `/lib/modules/6.12.91/`，创建并启用 `/etc/init.d/ax9000-crash-capture`。模块通过此服务加载，不写入 `modules.d`，以确保设置内存布局之后才绑定 ramoops。

## 内存布局与归档

设备树已经预留 `0x51200000` 开始的 1 MiB 内存。脚本核对该范围后，使用上游 ramoops 模块参数分配：

| 用途 | 大小 |
| --- | --- |
| 每条崩溃记录 | 128 KiB，共 5 个记录槽 |
| 连续内核控制台记录 | 256 KiB |
| 用户态诊断标记 | 128 KiB |

设备树原有 `record-size` 仅为 4 KiB。服务使用设备的 `driver_override` 防止默认布局绑定，然后通过模块参数创建标准 ramoops 平台实例，使用同一块已经预留的内存，不修改固件设备树。

- 内核记录入口：`/sys/fs/pstore/`
- 启动归档目录：`/root/router-logs/crashes/`
- 最近 8 份归档按单调序号保留，避免启动初期时钟尚未同步造成排序错误。
- 每份记录包括校验文件及归档时的设备上下文。上下文中的模块列表属于归档启动，不代表发生故障前的模块状态。
- `console-ramoops-*` 是上一轮运行的内核输出；`dmesg-ramoops-*` 是发生 Oops/panic 时的转储；`pmsg-ramoops-*` 是诊断标记。
- RAM 留存依赖重启过程没有清除预留内存，不保证断电后仍可读取。

## 验证

```sh
lsmod | grep -E 'pstore|ramoops|reed_solomon'
mount | grep pstore
dmesg | grep -E 'pstore|ramoops'
/etc/init.d/ax9000-crash-capture enabled
```

可写入 `/dev/kmsg`、`/dev/pmsg0` 标记，只卸载再加载 `ramoops`，检查旧记录及闪存归档是否包含标记。这验证了内存记录、恢复和归档链路，不等同于整机重启或真实 panic 验证。不要为了验证采集而主动触发生产路由器崩溃。

## 停用

```sh
/etc/init.d/ax9000-crash-capture disable
```

服务的 `stop` 不卸载已运行的记录器，以保留关机阶段日志。需要立即停用时，可在已归档记录后执行 `rmmod ramoops`；持久系统日志配置由独立的 OpenWrt 日志服务管理。
