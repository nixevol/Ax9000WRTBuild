#!/bin/sh
# 将上一轮运行保留在 RAM 中的日志复制到闪存，最多保留最近 8 份归档。
set -eu
umask 077
root=/root/router-logs/crashes
boot_id="$(cat /proc/sys/kernel/random/boot_id)"
mkdir -p "$root"
[ ! -f "$root/.archived-$boot_id" ] || exit 0
count=0
for source in /sys/fs/pstore/*-ramoops-*; do
	[ -f "$source" ] || continue
	count=$((count + 1))
done
[ "$count" -gt 0 ] || exit 0

# 使用单调序号，避免启动时尚未 NTP 校时造成目录排序错误。
sequence="$(cat "$root/.sequence" 2>/dev/null || echo 0)"
case "$sequence" in ''|*[!0-9]*) exit 1;; esac
sequence=$((sequence + 1))
directory="$root/$(printf '%08d' "$sequence")-$boot_id"
mkdir -p "$directory"
for source in /sys/fs/pstore/*-ramoops-*; do
	[ -f "$source" ] || continue
	name="${source##*/}"
	cp "$source" "$directory/$name"
	cmp -s "$source" "$directory/$name" || exit 1
done
{
	printf 'Archive boot ID: %s\nWall clock (may precede NTP sync): %s\n' "$boot_id" "$(date -Iseconds)"
	printf 'Uptime: '; cat /proc/uptime
	uname -a
	printf '\nKernel panic settings:\n'
	cat /proc/sys/kernel/panic /proc/sys/kernel/panic_on_oops
	printf '\nLoaded modules on archive boot (not crash boot):\n'
	cat /proc/modules
} > "$directory/archive-context.txt"
(cd "$directory" && sha256sum ./*-ramoops-* archive-context.txt > SHA256SUMS)
printf '%s\n' "$sequence" > "$root/.sequence"
touch "$root/.archived-$boot_id"
sync

index=0
printf '%s\n' "$root"/????????-????????-????-????-????-???????????? | sort -r | while IFS= read -r candidate; do
	name="${candidate##*/}"
	case "$name" in ????????-????????-????-????-????-????????????) ;; *) continue;; esac
	[ -d "$root/$name" ] || continue
	index=$((index + 1))
	[ "$index" -le 8 ] || rm -rf "${root:?}/${name:?}"
done
# 仅保留当前启动的幂等标记，历史记录由上述归档目录保存。
for marker in "$root"/.archived-*; do
	[ "$marker" = "$root/.archived-$boot_id" ] || rm -f "$marker"
done
logger -t ax9000-crash-capture "Archived $count records to $directory"
