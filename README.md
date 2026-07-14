# OpenWRT AX9000 NSS 固件构建器

这是一个面向桌面浏览器的本地 OpenWrt 固件构建控制台。当前仅支持 Xiaomi AX9000，构建源码固定为 Qosmio `openwrt-ipq` 的 `25.12-nss` 分支，并追加 AX9000 大分区、NSS、网络和硬件控制适配。

> [!WARNING]
> **本项目生成的 AX9000 固件仅适用于暗云大分区布局，不适用于小米官方分区布局！分区布局不匹配时严禁刷写，否则设备可能无法启动。**
>
> 暗云 U-Boot 下载地址：[https://mbd.pub/o/bread/mbd-ZJiXm55v](https://mbd.pub/o/bread/mbd-ZJiXm55v)
>
> 安装 U-Boot 或调整分区前，请确认设备型号与分区布局，并备份原始分区和当前配置。相关操作存在设备无法启动的风险，请确保具备可用的恢复方式。

## 功能概览

- **设备设置**：配置主机名、后台地址、主题、Web 服务器、语言、作者外链、固件签名、功能组合和防火墙后端。
- **软件包**：分别选择基础包、代理界面、Xray/Sing-box/Mihomo 核心，以及可搜索、分类和按源筛选的附加软件。
- **网络与无线**：配置 LAN、DHCP、IPv6、旁路由、PPPoE，以及按频段区分、统一名称或首次启动向导三种 Wi-Fi 模式。
- **AX9000 硬件**：提供 EMC2301 自动温控、手动风扇功率、实时温度与转速反馈，以及顶部 RGB 和正面灯控制。
- **软件源**：管理编译期 Git feeds，并为固件运行时选择或自定义 APK 镜像。
- **构建与产物**：通过 Docker 增量编译，查看可折叠实时日志，并下载单一时间戳 ZIP 产物。

## 环境要求

### 必需环境

| 组件 | 要求 | 用途 |
| --- | --- | --- |
| 操作系统 | 64 位 Windows 10 或 Windows 11 | 运行控制台与构建脚本 |
| WSL2 | 已启用硬件虚拟化与 WSL2 | Docker Desktop Linux 后端 |
| Docker Desktop | 使用 Linux 容器 | 隔离并执行 OpenWrt 编译 |
| Python | 3.11 或更高版本 | FastAPI 后端与构建配置脚本 |
| Node.js | 20 LTS 或更高版本 | Vue 3 前端工具链 |
| npm | 随 Node.js 安装 | 安装和构建前端依赖 |
| Git | 当前稳定版本 | 获取本项目及上游源码 |
| 浏览器 | 当前版本的桌面浏览器 | 使用网页控制台 |

### 推荐配置

- 4 核或更多 CPU
- 8 GB 或更多内存
- SSD 上至少保留 60 GB 可用空间
- 将 Docker Desktop 数据盘放在空间充足的磁盘

首次完整构建需要下载并生成大量源码、工具链和中间产物；当前 AX9000 增量构建卷的逻辑数据量可超过 50 GB。CPU 核心数、磁盘速度和网络质量会直接影响构建时间。

## 快速开始

### 安装依赖

```powershell
npm install
python -m pip install -r requirements.txt
```

也可以使用 `uv` 安装 Python 依赖：

```powershell
uv sync
```

### 启动控制台

```powershell
python start.py
```

`start.py` 始终使用当前 Python 解释器启动 FastAPI，不强制依赖 `uv`。服务启动后访问：

- 前端：<http://localhost:9000>
- 后端：<http://localhost:9001>

按 `Ctrl+C` 会同时停止前后端。需要分别调试时，使用两个终端运行：

```powershell
python -m uvicorn web.server.main:app --host 0.0.0.0 --port 9001 --reload
npm run web:dev
```

需要预览生产版前端时，使用两个终端分别运行：

```powershell
npm run api:serve
npm run web:preview
```

然后访问前端 <http://localhost:9000>；API 仍监听 <http://localhost:9001>。

### 构建代理

构建网络需要代理时，在启动服务前设置 `OPENWRT_BUILD_PROXY`：

```powershell
$env:OPENWRT_BUILD_PROXY='http://127.0.0.1:7897'
python start.py
```

Docker 构建会自动将回环地址转换为 `host.docker.internal`。

## 构建固件

网页控制台会把当前设置传入 Docker，并在“产物与日志”页面显示实时日志。也可以直接在 PowerShell 中构建：

```powershell
.\scripts\build-docker.ps1
```

指定并行线程或清理源码后重新构建：

```powershell
.\scripts\build-docker.ps1 -Jobs 8
.\scripts\build-docker.ps1 -Clean
```

构建缓存保存在 Docker 命名卷 `openwrt-build-work`，Compose、命令行脚本和网页构建共用该卷。普通增量构建会保留下载、工具链和中间产物；使用 `-Clean`，或在 Web 端右上角勾选“清理”后构建，会清理 OpenWrt 源码树并重新构建。

固件输出到 `outputs/ax9000/`。网页构建成功后会把固件、manifest、buildinfo、校验文件和配置打包为：

```text
OpenWRT-AX9000-YYYY-MM-DD_HH-mm-ss.zip
```

下载区只显示最终 ZIP。

## 软件包与软件源

### 软件包目录

首次运行会加载 `profiles/ax9000/package-catalog.json` 中的精选目录。点击“同步软件库”后，后端会从当前启用的 feeds 更新目录，默认包括：

- `openwrt/video`
- `openwrt/packages`
- `openwrt/luci`
- `openwrt/routing`
- `openwrt/telephony`
- `qosmio/nss-packages`
- `kiddin9/op-packages`

实际软件数量会随上游变化，同步缓存位于 `.runtime/catalog-sources/` 和 `.runtime/package-catalog/`。目录项由源码目录推导，一个 Makefile 生成多个子包时不一定会全部展开。

设备启动、网络、NSS 和 LuCI 所需的软件包会锁定；其他基础包可以取消。主题、Web 服务器、语言、功能组合、防火墙、代理界面和代理核心由统一预设解析，避免界面已勾选但最终固件缺少依赖。

### 编译 feeds 与运行时镜像

默认编译源保存在 `profiles/ax9000/feeds.json`。网页修改的 feeds 会随构建选项传入 Docker，并在 OpenWrt 执行 `feeds update/install` 前写入 `feeds.conf.default`。

编译 feeds 与固件运行后的 APK 镜像是两类独立配置：

- **编译 feeds**：提供参与固件编译的软件源码，只接受 HTTPS Git 地址和合法的源名称、分支名称。
- **运行时镜像**：用于刷机后的软件安装，可选择构建默认、OpenWrt 官方、腾讯云、阿里云、清华 TUNA、北外 BFSU 或自定义 HTTPS 地址；选择内置镜像时，构建前会检查其是否支持当前固件。

镜像切换只替换原有 `downloads.openwrt.org` 基础地址，不会叠加重复 feed。第三方镜像必须包含与当前固件完全匹配的版本、架构、APK 格式和签名信任链；内核模块还必须匹配当前内核 ABI。

## AX9000 技术说明

- 使用 Qosmio Linux 6.12、NSS 数据平面、NSS 驱动、ECM、QCA SSDK 和 `nss-firmware-ipq807x`。
- 设备树固定 LAN1 至 LAN4 为 QSGMII、WAN 为 SGMII，并保留完整 NSS 节点。
- `post-patch.sh` 将 Qosmio 双 UBI 布局改为单个 232 MiB `rootfs`，升级包只写入该分区。
- 大分区 UBI 中 `kernel` 为卷 0、`rootfs` 为卷 1，最终 DTB 从 `/dev/ubiblock0_1` 启动。
- 设备补丁加入 EMC2301/EMC2305 风扇控制、PWM 推挽输出、温控和 LED 支持。
- 构建过程生成 OpenWrt JSON 镜像信息，供设备识别和产物 metadata 使用。

### 温控与灯光

`luci-app-ax900-hardware` 是本项目针对 AX9000 自行编写的 LuCI 应用。它通过 Linux hwmon 和 LED 接口提供自动温控曲线、手动风扇功率、实时温度与转速状态，并支持顶部 RGB 灯的固定颜色、温度联动、循环和闪烁，以及正面系统灯、网络灯的独立控制。

构建产物包括：

- `sysupgrade`
- `factory.ubi`
- `initramfs-uImage.itb`
- `initramfs-factory.ubi`

### 刷写注意事项

1. 仅在设备已经使用匹配的暗云大分区布局时刷写本项目固件。
2. 刷写前确认设备型号、分区布局和固件类型，并保留原始分区、配置和可用恢复方式。
3. 不要混用其他固件生成的 `.ko`、`.ipk` 或 `.apk`；AX9000 NSS 模块必须与当前内核 ABI 一起生成。
4. 正式系统默认地址和认证为 `192.168.32.1`、`root/password`。initramfs 尚未执行首次启动脚本，不要用正式系统默认值推断其地址和认证状态。

## 主要目录

```text
start.py                  前后端一键启动与进程清理
requirements.txt          普通 Python/pip 后端依赖
profiles/ax9000/          AX9000 配置、预设、包目录、feeds 和源码补丁
packages/                 本地 OpenWrt 软件包
scripts/build.sh          容器内 OpenWrt 构建入口
scripts/build-docker.ps1  Windows Docker 启动脚本
web/server/               FastAPI、构建状态和软件目录同步
web/frontend/             Vue 3 桌面控制台
outputs/ax9000/           本地构建产物
```

## 上游项目与致谢

本项目建立在 OpenWrt、Qosmio NSS 分支及多个社区项目之上。下列链接对应当前构建配置实际引用的上游；各项目版权归其作者和贡献者所有。

### 核心源码与 NSS

| 项目 | 当前用途 | 分支 |
| --- | --- | --- |
| [OpenWrt](https://github.com/openwrt/openwrt) | 上游 OpenWrt 基础项目 | `openwrt-25.12` |
| [Qosmio/openwrt-ipq](https://github.com/qosmio/openwrt-ipq) | AX9000、Qualcomm IPQ807x、Linux 6.12 与 NSS 构建源码 | `25.12-nss` |
| [Qosmio/nss-packages](https://github.com/qosmio/nss-packages) | NSS、ECM、QCA SSDK 等加速组件 | `NSS-12.5-K6.x` |
| [Qosmio/sqm-scripts-nss](https://github.com/qosmio/sqm-scripts-nss) | NSS SQM 可选 feed，是否启用以当前保存配置为准 | `main` |

### OpenWrt 官方 feeds

以下 feeds 当前均使用 `openwrt-25.12` 分支：

- [openwrt/packages](https://github.com/openwrt/packages)
- [openwrt/luci](https://github.com/openwrt/luci)
- [openwrt/routing](https://github.com/openwrt/routing)
- [openwrt/telephony](https://github.com/openwrt/telephony)
- [openwrt/video](https://github.com/openwrt/video)

### 社区软件

- [kiddin9/op-packages](https://github.com/kiddin9/op-packages)：社区 LuCI 应用、主题和扩展包，使用 `main` 分支。
- [adminchenyu/LAN-Wake](https://github.com/adminchenyu/LAN-Wake)：局域网唤醒应用，构建固定到提交 `893805ee2f57b4490cc38e0abfd1aa45f362a958`。

### Linux 内核补丁

EMC2305 的 OF、thermal cooling、PWM 频率、极性和推挽输出支持来自 Linux 内核邮件列表中的上游补丁系列：

- [EMC2305 OF 与 thermal cooling 支持](https://lore.kernel.org/r/20250321143308.4008623-3-florin.leotescu@oss.nxp.com)
- [EMC2305 PWM 频率、极性与输出配置支持](https://lore.kernel.org/r/20250603113125.3175103-2-florin.leotescu@oss.nxp.com)

本项目与上述项目不存在隶属关系，也不代表其官方发布。OpenWrt、LuCI、Qosmio 源码、feeds、主题、软件包和内核补丁分别遵循各自许可证；使用、修改和分发时应同时满足对应上游许可证及其通知要求。

## 许可证

本项目采用 [PolyForm Noncommercial License 1.0.0](LICENSE)。允许个人及符合许可证定义的非商业组织查看、使用、修改和再发布本项目作者有权许可的源码；分发原版或二次开发版本时，必须同时保留 `LICENSE`、其中的 `Required Notice` 和原始项目来源：<https://github.com/nixevol/Ax9000WRTBuild>。

任何商业使用、商业集成、收费服务或预期商业应用均不在本许可证授权范围内，必须事先取得作者的单独书面许可。本许可证不会替代、扩展或限制任何第三方组件的许可证。
