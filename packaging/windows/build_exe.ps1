[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$distribution = Join-Path $projectRoot "dist\HDL-X"
$workDirectory = Join-Path $projectRoot "build\pyinstaller-work"
$pythonPrefix = (& python -c "import sys; print(sys.prefix)").Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($pythonPrefix)) {
    throw "无法确定当前 Python 安装目录"
}
$pythonLibraryBin = Join-Path $pythonPrefix "Library\bin"
$originalPath = $env:PATH

foreach ($path in @($distribution, $workDirectory)) {
    if (Test-Path -LiteralPath $path) {
        throw "为避免覆盖已有文件，构建目标必须不存在：$path"
    }
}

Push-Location $projectRoot
try {
    if (Test-Path -LiteralPath $pythonLibraryBin) {
        $env:PATH = "$pythonLibraryBin$([IO.Path]::PathSeparator)$originalPath"
    }
    python -m PyInstaller `
        --noconfirm `
        --distpath "dist" `
        --workpath "build\pyinstaller-work" `
        "packaging\windows\hdl_x_gui.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller 构建失败，退出码 $LASTEXITCODE"
    }

    foreach ($dllName in @("tcl86t.dll", "tk86t.dll")) {
        $sourceDll = Join-Path $pythonLibraryBin $dllName
        $targetDll = Join-Path $distribution "_internal\$dllName"
        if ((Test-Path -LiteralPath $sourceDll) -and (Test-Path -LiteralPath $targetDll)) {
            Copy-Item -LiteralPath $sourceDll -Destination $targetDll -Force
        }
    }

    Copy-Item `
        -LiteralPath (Join-Path $PSScriptRoot "使用说明.txt") `
        -Destination (Join-Path $distribution "使用说明.txt")
}
finally {
    $env:PATH = $originalPath
    Pop-Location
}
