#!/bin/sh
# 在路由器上运行；目录中需包含已核验的三个模块及配套服务文件。
set -eu
umask 077
source_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
[ "$(uname -r)" = "6.12.91" ] || { echo 'Kernel mismatch' >&2; exit 1; }
[ "$(cat /tmp/sysinfo/board_name)" = "xiaomi,ax9000" ] || exit 1
kernel_package="$(apk info 2>/dev/null | grep '^kernel$')"
[ "$kernel_package" = kernel ] || exit 1
apk info -a kernel 2>/dev/null | grep -q '^kernel-6\.12\.91~3ca07581b60107336a14a0678bbe242b-r1 ' || {
	echo 'Kernel build fingerprint mismatch' >&2
	exit 1
}
(cd "$source_dir" && sha256sum -c modules.sha256) || exit 1
for module in reed_solomon pstore ramoops; do
	if [ -f "/lib/modules/6.12.91/$module.ko" ]; then
		cmp -s "$source_dir/$module.ko" "/lib/modules/6.12.91/$module.ko" || {
			echo "Different existing module: $module" >&2
			exit 1
		}
	fi
done
for module in reed_solomon pstore ramoops; do
	cp "$source_dir/$module.ko" "/lib/modules/6.12.91/$module.ko"
	chmod 644 "/lib/modules/6.12.91/$module.ko"
done
cp "$source_dir/ax9000-crash-capture.init" /etc/init.d/ax9000-crash-capture
cp "$source_dir/ax9000-crash-archive.sh" /usr/sbin/ax9000-crash-archive
chmod 755 /etc/init.d/ax9000-crash-capture /usr/sbin/ax9000-crash-archive
/etc/init.d/ax9000-crash-capture enable
/etc/init.d/ax9000-crash-capture start
sync
