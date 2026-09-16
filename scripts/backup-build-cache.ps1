param(
    [string]$BackupDirectory = "",
    [switch]$IncludeImage
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $BackupDirectory) {
    $BackupDirectory = Join-Path $ProjectRoot "work\cache-backups"
}
New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
$BackupDirectory = (Resolve-Path -LiteralPath $BackupDirectory).Path

# 锁与构建使用同一文件，备份时不允许另一个构建修改缓存。
docker run --rm --entrypoint bash `
    -v openwrt-build-work:/work `
    -v "${BackupDirectory}:/backup" `
    openwrt-local-builder:25.12 -lc `
    'set -euo pipefail; exec 9>/work/.build-ax9000.lock; flock -n 9; tar --use-compress-program="zstd -T4 -3" -cf /backup/openwrt-build-work.tar.zst.partial -C /work .; mv /backup/openwrt-build-work.tar.zst.partial /backup/openwrt-build-work.tar.zst; cd /backup; sha256sum openwrt-build-work.tar.zst > openwrt-build-work.tar.zst.sha256'
if ($LASTEXITCODE -ne 0) { throw "Build cache backup failed" }

if ($IncludeImage) {
    $ImagePath = Join-Path $BackupDirectory "openwrt-local-builder-25.12.tar"
    docker image save --output "$ImagePath.partial" openwrt-local-builder:25.12
    if ($LASTEXITCODE -ne 0) { throw "Builder image backup failed" }
    Move-Item -LiteralPath "$ImagePath.partial" -Destination $ImagePath -Force
}
Get-ChildItem -LiteralPath $BackupDirectory | Select-Object Name, Length, LastWriteTime
