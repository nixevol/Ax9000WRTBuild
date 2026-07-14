#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


DTS_RELATIVE_PATH = Path(
    "target/linux/qualcommax/files/arch/arm64/boot/dts/qcom/ipq8072-ax9000.dts"
)
PLATFORM_RELATIVE_PATH = Path(
    "target/linux/qualcommax/ipq807x/base-files/lib/upgrade/platform.sh"
)
KERNEL_BACKPORT_RELATIVE_PATH = Path("target/linux/generic/backport-6.12")
EMC2305_PATCH_DIR = Path(__file__).resolve().parents[1] / "profiles/ax9000/kernel-patches"
EMC2305_PATCH_NAMES = (
    "830-01-v6.15-hwmon-emc2305-Add-OF-support.patch",
    "830-02-v6.15-hwmon-emc2305-Use-devm_thermal_of_cooling_device_reg.patch",
    "830-03-v6.17-hwmon-emc2305-Add-support-for-PWM-frequency-polarity.patch",
    "830-04-v6.17-hwmon-emc2305-Configure-PWM-channels-based-on-DT-pro.patch",
    "830-05-v6.17-hwmon-emc2305-Enable-PWM-polarity-and-output-configu.patch",
)

UPSTREAM_PARTITIONS = '''\
\t\t\tpartition@1180000 {
\t\t\t\tlabel = "ubi_kernel";
\t\t\t\treg = <0x1180000 0x3800000>;
\t\t\t};

\t\t\tpartition@4980000 {
\t\t\t\tlabel = "rootfs";
\t\t\t\treg = <0x4980000 0xb680000>;
\t\t\t};'''

LARGE_ROOTFS_PARTITIONS = '''\
\t\t\t/* AX9000 large-partition U-Boot/MIBIB layout. */
\t\t\tpartition@1180000 {
\t\t\t\tlabel = "rootfs";
\t\t\t\treg = <0x1180000 0xe800000>;
\t\t\t};

\t\t\tpartition@f980000 {
\t\t\t\tlabel = "cfg_bak";
\t\t\t\treg = <0xf980000 0x80000>;
\t\t\t};'''

UPSTREAM_ROOTFS_BOOTARGS = '\t\tbootargs-append = " root=/dev/ubiblock0_0";'
LARGE_ROOTFS_BOOTARGS = '\t\tbootargs-append = " root=/dev/ubiblock0_1";'

UPSTREAM_I2C = '''\
&blsp1_i2c6 {
\tstatus = "okay";

\tpinctrl-0 = <&i2c_pins>;
\tpinctrl-names = "default";
};'''

FAN_CONTROLLER_I2C = '''\
&blsp1_i2c6 {
\tstatus = "okay";

\tpinctrl-0 = <&i2c_pins>;
\tpinctrl-names = "default";

\tfan_controller: fan-controller@2f {
\t\tcompatible = "microchip,emc2301", "microchip,emc2305";
\t\treg = <0x2f>;
\t\t#address-cells = <1>;
\t\t#size-cells = <0>;
\t\t#pwm-cells = <3>;

\t\tfan: fan@0 {
\t\t\treg = <0>;
\t\t\tpwms = <&fan_controller 26000 0 1>;
\t\t\t#cooling-cells = <2>;
\t\t};
\t};
};'''

UPSTREAM_PRE_UPGRADE = '''\
\tredmi,ax6|\\
\txiaomi,ax3600|\\
\txiaomi,ax9000)
\t\txiaomi_initramfs_prepare
\t\t;;'''

LARGE_ROOTFS_PRE_UPGRADE = '''\
\tredmi,ax6|\\
\txiaomi,ax3600)
\t\txiaomi_initramfs_prepare
\t\t;;
\txiaomi,ax9000)
\t\t# The custom MIBIB has one UBI partition containing kernel and rootfs.
\t\t[ "$(rootfs_type)" = "tmpfs" ] || return 0
\t\tlocal rootfs_mtdnum
\t\trootfs_mtdnum="$(find_mtd_index rootfs)"
\t\t[ -n "$rootfs_mtdnum" ] || {
\t\t\techo "unable to find mtd partition rootfs"
\t\t\treturn 1
\t\t}
\t\tubidetach -m "$rootfs_mtdnum" 2>/dev/null || true
\t\tubiformat "/dev/mtd$rootfs_mtdnum" -y
\t\t;;'''

UPSTREAM_UPGRADE = '''\
\tredmi,ax6|\\
\txiaomi,ax3600|\\
\txiaomi,ax9000)
\t\t# Make sure that UART is enabled
\t\tfw_setenv boot_wait on
\t\tfw_setenv uart_en 1

\t\t# Enforce single partition.
\t\tfw_setenv flag_boot_rootfs 0
\t\tfw_setenv flag_last_success 0
\t\tfw_setenv flag_boot_success 1
\t\tfw_setenv flag_try_sys1_failed 8
\t\tfw_setenv flag_try_sys2_failed 8

\t\t# Kernel and rootfs are placed in 2 different UBI
\t\tCI_KERN_UBIPART="ubi_kernel"
\t\tCI_ROOT_UBIPART="rootfs"
\t\tnand_do_upgrade "$1"
\t\t;;'''

LARGE_ROOTFS_UPGRADE = '''\
\tredmi,ax6|\\
\txiaomi,ax3600)
\t\t# Make sure that UART is enabled
\t\tfw_setenv boot_wait on
\t\tfw_setenv uart_en 1

\t\t# Enforce single partition.
\t\tfw_setenv flag_boot_rootfs 0
\t\tfw_setenv flag_last_success 0
\t\tfw_setenv flag_boot_success 1
\t\tfw_setenv flag_try_sys1_failed 8
\t\tfw_setenv flag_try_sys2_failed 8

\t\t# Kernel and rootfs are placed in 2 different UBI
\t\tCI_KERN_UBIPART="ubi_kernel"
\t\tCI_ROOT_UBIPART="rootfs"
\t\tnand_do_upgrade "$1"
\t\t;;
\txiaomi,ax9000)
\t\t# AX9000 custom U-Boot boots one large rootfs UBI partition.
\t\tfw_setenv boot_wait on 2>/dev/null || true
\t\tfw_setenv uart_en 1 2>/dev/null || true
\t\tfw_setenv flag_boot_rootfs 0 2>/dev/null || true
\t\tfw_setenv flag_last_success 0 2>/dev/null || true
\t\tfw_setenv flag_boot_success 1 2>/dev/null || true
\t\tfw_setenv flag_try_sys1_failed 8 2>/dev/null || true
\t\tfw_setenv flag_try_sys2_failed 8 2>/dev/null || true
\t\tCI_UBIPART="rootfs"
\t\tnand_do_upgrade "$1"
\t\t;;'''


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description} block, found {count}")
    return text.replace(old, new, 1)


def patch_dts(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if '#include "ipq8074-nss.dtsi"' not in text:
        raise RuntimeError("AX9000 DTS does not include ipq8074-nss.dtsi")

    text = replace_once(
        text,
        UPSTREAM_PARTITIONS,
        LARGE_ROOTFS_PARTITIONS,
        "AX9000 partition",
    )
    text = replace_once(
        text,
        UPSTREAM_ROOTFS_BOOTARGS,
        LARGE_ROOTFS_BOOTARGS,
        "AX9000 root volume boot argument",
    )
    text = replace_once(
        text,
        UPSTREAM_I2C,
        FAN_CONTROLLER_I2C,
        "AX9000 EMC2305 fan controller",
    )
    if UPSTREAM_ROOTFS_BOOTARGS in text or LARGE_ROOTFS_BOOTARGS not in text:
        raise RuntimeError("AX9000 DTS does not boot from the rootfs UBI volume")
    ports = {
        1: ("qsgmii", "lan4"),
        2: ("qsgmii", "lan3"),
        3: ("qsgmii", "lan2"),
        4: ("qsgmii", "lan1"),
        5: ("sgmii", "wan"),
    }
    for device, (mode, label) in ports.items():
        block_start = text.find(f"&dp{device} {{")
        block_end = text.find("};", block_start)
        block = text[block_start:block_end]
        if (
            block_start < 0
            or f'phy-mode = "{mode}";' not in block
            or f'label = "{label}";' not in block
            or 'status = "okay";' not in block
        ):
            raise RuntimeError(
                f"AX9000 dp{device} must be enabled as {label} using {mode.upper()}"
            )
    if 'label = "ubi_kernel";' in text:
        raise RuntimeError("AX9000 DTS still contains the incompatible ubi_kernel partition")
    if 'reg = <0x1180000 0xe800000>;' not in text:
        raise RuntimeError("AX9000 DTS does not contain the 232 MiB rootfs partition")
    if 'fan_controller: fan-controller@2f' not in text:
        raise RuntimeError("AX9000 DTS does not contain the EMC2305 fan controller")
    path.write_text(text, encoding="utf-8")


def patch_platform(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        UPSTREAM_PRE_UPGRADE,
        LARGE_ROOTFS_PRE_UPGRADE,
        "AX9000 pre-upgrade",
    )
    text = replace_once(
        text, UPSTREAM_UPGRADE, LARGE_ROOTFS_UPGRADE, "AX9000 upgrade"
    )
    if 'CI_UBIPART="rootfs"' not in text or "AX9000 custom U-Boot" not in text:
        raise RuntimeError("AX9000 single-rootfs upgrade path was not installed")
    path.write_text(text, encoding="utf-8")


def install_emc2305_backports(source: Path, patch_dir: Path = EMC2305_PATCH_DIR) -> None:
    destination = source / KERNEL_BACKPORT_RELATIVE_PATH
    if not destination.is_dir():
        raise RuntimeError(f"kernel backport directory not found: {destination}")
    for name in EMC2305_PATCH_NAMES:
        patch = patch_dir / name
        if not patch.is_file():
            raise RuntimeError(f"EMC2305 kernel backport not found: {patch}")
        shutil.copy2(patch, destination / name)


def patch_source(source: Path) -> None:
    dts_path = source / DTS_RELATIVE_PATH
    platform_path = source / PLATFORM_RELATIVE_PATH
    if not dts_path.is_file():
        raise RuntimeError(f"AX9000 DTS not found: {dts_path}")
    if not platform_path.is_file():
        raise RuntimeError(f"platform.sh not found: {platform_path}")
    install_emc2305_backports(source)
    patch_dts(dts_path)
    patch_platform(platform_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path.cwd())
    args = parser.parse_args()
    patch_source(args.source.resolve())


if __name__ == "__main__":
    main()
