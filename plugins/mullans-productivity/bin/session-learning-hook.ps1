$warnMissingPython = $false
$runtimeHost = $null
for ($index = 0; $index -lt $args.Count; $index++) {
    if ($args[$index] -eq "--warn-missing-python") {
        $warnMissingPython = $true
    }
    elseif ($args[$index] -eq "--host" -and $index + 1 -lt $args.Count) {
        $index++
        $runtimeHost = $args[$index]
    }
}

$dataDir = $env:PLUGIN_DATA
if (-not $dataDir) {
    $dataDir = $env:CLAUDE_PLUGIN_DATA
}
if (-not $dataDir -or -not $runtimeHost) {
    exit 0
}
try {
    [System.IO.Directory]::CreateDirectory($dataDir) | Out-Null
}
catch {
    exit 0
}

$payload = [Console]::In.ReadToEnd()
try {
    $hookInput = $payload | ConvertFrom-Json -ErrorAction Stop
}
catch {
    $hookInput = $null
}

function Get-ConfiguredPython([string]$configPath) {
    if (-not $configPath -or -not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        return $null
    }
    try {
        $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json -ErrorAction Stop
        $configured = $config.python_path
        if ($config.schema_version -ne 1 -or -not ($configured -is [string])) {
            return $null
        }
        if ($configured -notmatch '^(?:[A-Za-z]:[\\/]|\\\\)') {
            return $null
        }
        $resolved = [System.IO.Path]::GetFullPath($configured)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            return $null
        }
        return $resolved
    }
    catch {
        return $null
    }
}

function Find-ProjectConfig([string]$cwd) {
    if (-not $cwd -or -not (Test-Path -LiteralPath $cwd -PathType Container)) {
        return $null
    }
    try {
        $current = [System.IO.DirectoryInfo]::new([System.IO.Path]::GetFullPath($cwd))
        while ($null -ne $current) {
            $candidate = Join-Path $current.FullName ".agents\learning\config.json"
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                return $candidate
            }
            $current = $current.Parent
        }
    }
    catch {
        return $null
    }
    return $null
}

function Test-Python3([string]$command, [string[]]$prefix) {
    if (-not $command) {
        return $false
    }
    try {
        & $command @prefix -c "import sys; raise SystemExit(sys.version_info[0] != 3)" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

$configuredCandidates = [System.Collections.Generic.List[string]]::new()
$projectConfig = Find-ProjectConfig $hookInput.cwd
$projectPython = Get-ConfiguredPython $projectConfig
if ($projectPython) {
    $configuredCandidates.Add($projectPython)
}
$userHome = [Environment]::GetFolderPath("UserProfile")
if ($userHome) {
    $personalConfig = Join-Path $userHome ".agents\session-learning\config.json"
    $personalPython = Get-ConfiguredPython $personalConfig
    if ($personalPython -and -not $configuredCandidates.Contains($personalPython)) {
        $configuredCandidates.Add($personalPython)
    }
}

$selectedCommand = $null
$selectedPrefix = @()
$selectedIdentifier = $null
foreach ($configured in $configuredCandidates) {
    if (Test-Python3 $configured @()) {
        $selectedCommand = $configured
        break
    }
}

$fixedCandidates = [ordered]@{
    py = @("-3")
    python3 = @()
    python = @()
}
$cachePath = Join-Path $dataDir "python-launcher.txt"
if (-not $selectedCommand -and (Test-Path -LiteralPath $cachePath -PathType Leaf)) {
    $cachedIdentifier = (Get-Content -Raw -LiteralPath $cachePath).Trim()
    if ($fixedCandidates.Contains($cachedIdentifier)) {
        $cachedPrefix = [string[]]$fixedCandidates[$cachedIdentifier]
        if (Test-Python3 $cachedIdentifier $cachedPrefix) {
            $selectedCommand = $cachedIdentifier
            $selectedPrefix = $cachedPrefix
            $selectedIdentifier = $cachedIdentifier
        }
    }
}
if (-not $selectedCommand) {
    foreach ($identifier in $fixedCandidates.Keys) {
        $prefix = [string[]]$fixedCandidates[$identifier]
        if (Test-Python3 $identifier $prefix) {
            $selectedCommand = $identifier
            $selectedPrefix = $prefix
            $selectedIdentifier = $identifier
            break
        }
    }
}

if (-not $selectedCommand) {
    if ($warnMissingPython) {
        $warningPath = Join-Path $dataDir "python-launcher-warning"
        try {
            $warning = [System.IO.File]::Open(
                $warningPath,
                [System.IO.FileMode]::CreateNew,
                [System.IO.FileAccess]::Write,
                [System.IO.FileShare]::None
            )
            $warning.Dispose()
            [Console]::Out.WriteLine('{"systemMessage":"Session Learning automatic retrieval is unavailable because Python 3 was not found."}')
        }
        catch {
            # A previous session already emitted the warning.
        }
    }
    exit 0
}

if ($selectedIdentifier) {
    try {
        $temporaryCache = "$cachePath.$PID.tmp"
        [System.IO.File]::WriteAllText($temporaryCache, "$selectedIdentifier`n")
        Move-Item -Force -LiteralPath $temporaryCache -Destination $cachePath
    }
    catch {
        # Caching is an optimization; retrieval can still proceed.
    }
}

$pluginRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$engine = Join-Path $pluginRoot "skills\session-learning\scripts\session_learning.py"
$engineArguments = @($selectedPrefix) + @(
    $engine,
    "hook",
    "--data-dir",
    $dataDir,
    "--host",
    $runtimeHost
)
try {
    $payload | & $selectedCommand @engineArguments
    exit $LASTEXITCODE
}
catch {
    exit 0
}
