param(
    [Parameter(Mandatory = $true)] [string] $OpenPencilSource,
    [Parameter(Mandatory = $true)] [string] $ComfyUiSource,
    [Parameter(Mandatory = $true)] [string] $ComfyPythonSource,
    [Parameter(Mandatory = $true)] [string] $CheckpointSource
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$thirdPartyRoot = Join-Path $repoRoot 'third_party'

function Resolve-Source([string] $Path) {
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
        throw "Source directory does not exist: $Path"
    }
    return $resolved
}

function Resolve-Target([string] $RelativePath) {
    $target = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $RelativePath))
    $allowed = [System.IO.Path]::GetFullPath($thirdPartyRoot) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $target.StartsWith($allowed, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Target escapes third_party: $target"
    }
    return $target
}

function Copy-Tree(
    [string] $Source,
    [string] $Target,
    [string[]] $ExcludeDirectories = @(),
    [string[]] $ExcludeFiles = @()
) {
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    $arguments = @($Source, $Target, '/E', '/COPY:DAT', '/DCOPY:DAT', '/R:2', '/W:1', '/XJ', '/NP', '/NFL', '/NDL')
    if ($ExcludeDirectories.Count -gt 0) {
        $arguments += '/XD'
        $arguments += $ExcludeDirectories
    }
    if ($ExcludeFiles.Count -gt 0) {
        $arguments += '/XF'
        $arguments += $ExcludeFiles
    }
    & robocopy @arguments
    $code = $LASTEXITCODE
    if ($code -ge 8) {
        throw "robocopy failed with exit code ${code}: $Source -> $Target"
    }
}

function Copy-RequiredFile([string] $Source, [string] $Target) {
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Required file does not exist: $Source"
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $Target) -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Force
}

$openPencil = Resolve-Source $OpenPencilSource
$comfyUi = Resolve-Source $ComfyUiSource
$comfyPython = Resolve-Source $ComfyPythonSource
$checkpoints = Resolve-Source $CheckpointSource

$openPencilTarget = Resolve-Target 'third_party/open-pencil'
$comfyUiTarget = Resolve-Target 'third_party/comfyui'
$comfyPythonTarget = Resolve-Target 'third_party/.runtimes/comfyui-python'
$bunTarget = Resolve-Target 'third_party/.runtimes/bun/bun.exe'

Write-Host 'Copying OpenPencil...'
$openPencilExcluded = @('node_modules') | ForEach-Object { Join-Path $openPencil $_ }
Copy-Tree $openPencil $openPencilTarget $openPencilExcluded

$bunCommand = Get-Command bun -ErrorAction SilentlyContinue
if ($null -eq $bunCommand) {
    throw 'Bun is required to restore and build the project-local OpenPencil copy: https://bun.sh/'
}
$bunExecutable = $bunCommand.Source
if ([System.IO.Path]::GetExtension($bunExecutable) -ne '.exe') {
    $bunExecutable = Join-Path (Split-Path -Parent $bunExecutable) 'node_modules/bun/bin/bun.exe'
}
if (-not (Test-Path -LiteralPath $bunExecutable -PathType Leaf)) {
    throw "Unable to resolve the Bun executable behind: $($bunCommand.Source)"
}
Write-Host 'Copying Bun runtime...'
Copy-RequiredFile $bunExecutable $bunTarget
Write-Host 'Restoring and building project-local OpenPencil...'
Push-Location $openPencilTarget
try {
    & $bunTarget install --frozen-lockfile --force
    if ($LASTEXITCODE -ne 0) { throw "OpenPencil dependency install failed with exit code $LASTEXITCODE" }
    & $bunTarget run build:packages
    if ($LASTEXITCODE -ne 0) { throw "OpenPencil build failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

Write-Host 'Copying ComfyUI core without local inputs, outputs, users, caches, models, or unrelated nodes...'
$excluded = @('models', 'custom_nodes', 'input', 'output', 'user', 'temp', '__pycache__') | ForEach-Object { Join-Path $comfyUi $_ }
$excludedFiles = @('extra_model_paths.yaml', 'comfy_stdout.log', 'comfy_stderr.log') | ForEach-Object { Join-Path $comfyUi $_ }
Copy-Tree $comfyUi $comfyUiTarget $excluded $excludedFiles

$nodes = @(
    'comfyui_controlnet_aux',
    'ComfyUI_IPAdapter_plus',
    'ComfyUI-layerdiffuse',
    'ComfyUI-segment-anything-2',
    'comfyui-lama-remover',
    'ComfyUI_UltimateSDUpscale',
    'ComfyUI-Impact-Pack',
    'ComfyUI_LayerStyle',
    'rgthree-comfy',
    'ComfyUI-Manager'
)
foreach ($node in $nodes) {
    Write-Host "Copying ComfyUI node: $node"
    $nodeSource = Join-Path $comfyUi "custom_nodes/$node"
    $nodeExcludedFiles = @()
    if ($node -eq 'ComfyUI-Impact-Pack') {
        $nodeExcludedFiles = @((Join-Path $nodeSource 'impact-pack.ini'))
    }
    Copy-Tree $nodeSource (Join-Path $comfyUiTarget "custom_nodes/$node") @() $nodeExcludedFiles
}

Write-Host 'Copying portable ComfyUI Python runtime...'
Copy-Tree $comfyPython $comfyPythonTarget

$modelCopies = @(
    @{ Source = Join-Path $checkpoints 'gameIconInstitute_v4XL.safetensors'; Target = Join-Path $comfyUiTarget 'models/checkpoints/gameIconInstitute_v4XL.safetensors' },
    @{ Source = Join-Path $checkpoints 'animagine-xl-4.0-opt.safetensors'; Target = Join-Path $comfyUiTarget 'models/checkpoints/animagine-xl-4.0-opt.safetensors' },
    @{ Source = Join-Path $comfyUi 'models/controlnet/control-lora-canny-rank128.safetensors'; Target = Join-Path $comfyUiTarget 'models/controlnet/control-lora-canny-rank128.safetensors' },
    @{ Source = Join-Path $comfyUi 'models/ipadapter/ip-adapter_sdxl_vit-h.safetensors'; Target = Join-Path $comfyUiTarget 'models/ipadapter/ip-adapter_sdxl_vit-h.safetensors' },
    @{ Source = Join-Path $comfyUi 'models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors'; Target = Join-Path $comfyUiTarget 'models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors' },
    @{ Source = Join-Path $comfyUi 'models/sam2/sam2.1_hiera_large-fp16.safetensors'; Target = Join-Path $comfyUiTarget 'models/sam2/sam2.1_hiera_large-fp16.safetensors' }
)
foreach ($model in $modelCopies) {
    Write-Host "Copying model: $([System.IO.Path]::GetFileName($model.Source))"
    Copy-RequiredFile $model.Source $model.Target
}

Write-Host "Local toolchain imported into: $thirdPartyRoot"
