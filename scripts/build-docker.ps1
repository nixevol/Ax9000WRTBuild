param(
    [string]$Profile = "ax9000",
    [ValidateRange(0, 64)]
    [int]$Jobs = 0,
    [switch]$Clean,
    [string]$OptionsFile = "",
    [string]$ContainerName = "openwrt-local-builder-run"
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Image = "openwrt-local-builder:25.12"
$CleanValue = if ($Clean) { "1" } else { "0" }
$BuildProxy = $env:OPENWRT_BUILD_PROXY

function Get-ProjectRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $baseFull = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\', '/') + '\'
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($baseFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "OptionsFile must be inside project root: $pathFull"
    }
    return $pathFull.Substring($baseFull.Length).Replace('\', '/')
}

if ($Profile -notmatch '^[a-z0-9][a-z0-9_-]{0,31}$') {
    throw "Invalid profile name: $Profile"
}
if ($ContainerName -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$') {
    throw "Invalid Docker container name: $ContainerName"
}

docker build -t $Image $Root
if ($LASTEXITCODE -ne 0) {
    throw "Docker image build failed with exit code $LASTEXITCODE"
}

$dockerArgs = @(
    "run", "--rm",
    "--name", $ContainerName,
    "-e", "PROFILE=$Profile",
    "-e", "JOBS=$Jobs",
    "-e", "CLEAN=$CleanValue",
    "-v", "${Root}:/workspace",
    "-v", "openwrt-build-work:/work"
)

if ($BuildProxy) {
    $proxyUri = $null
    if (-not [Uri]::TryCreate($BuildProxy, [UriKind]::Absolute, [ref]$proxyUri) -or
        $proxyUri.Scheme -notin @("http", "https") -or
        -not $proxyUri.Host -or $proxyUri.Port -le 0) {
        throw "OPENWRT_BUILD_PROXY must be an HTTP(S) proxy URL"
    }
    $containerProxy = $BuildProxy -replace '://(?:127\.0\.0\.1|localhost)(?=[:/])', '://host.docker.internal'
    $dockerArgs += @(
        "--add-host", "host.docker.internal:host-gateway",
        "-e", "HTTP_PROXY=$containerProxy",
        "-e", "HTTPS_PROXY=$containerProxy",
        "-e", "http_proxy=$containerProxy",
        "-e", "https_proxy=$containerProxy"
    )
}

if ($OptionsFile) {
    $ResolvedOptions = (Resolve-Path -LiteralPath $OptionsFile).Path
    $RelativeOptions = Get-ProjectRelativePath -BasePath $Root -Path $ResolvedOptions
    $dockerArgs += @("-e", "BUILD_OPTIONS_FILE=/workspace/$RelativeOptions")
}

$dockerArgs += $Image
docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    throw "Firmware build failed with exit code $LASTEXITCODE"
}
