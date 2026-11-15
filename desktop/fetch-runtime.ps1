# Downloads MySQL, embeddable Python, and the VC++ runtime, then copies the Django
# project into desktop/runtime. The NSIS setup file contains the result. Nothing
# is downloaded again when a shop installs Popy.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Desktop = $PSScriptRoot
$Root = Split-Path $Desktop -Parent
$Runtime = Join-Path $Desktop 'runtime'
$Cache = Join-Path $Desktop 'cache'
$PythonVersion = '3.12.10'
$MysqlZipName = 'mysql-8.4.13-winx64.zip'
$MysqlUrl = "https://cdn.mysql.com/Downloads/MySQL-8.4/$MysqlZipName"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$VcUrl = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'

New-Item -ItemType Directory -Force -Path $Runtime, $Cache | Out-Null

function Get-File($Url, $Destination) {
  if (Test-Path $Destination) {
    return
  }
  Write-Host "Downloading $Url"
  Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
}

function Expand-Mysql($ZipPath, $Destination) {
  if (Test-Path (Join-Path $Destination 'bin\mysqld.exe')) {
    Write-Host 'MySQL runtime already present.'
    return
  }
  $temp = Join-Path $env:TEMP ("popy-mysql-" + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force -Path $temp | Out-Null
  try {
    Expand-Archive -Path $ZipPath -DestinationPath $temp -Force
    $mysqld = Get-ChildItem -Path $temp -Recurse -Filter mysqld.exe | Select-Object -First 1
    if (-not $mysqld) {
      throw 'mysqld.exe was not found in the MySQL zip.'
    }
    $mysqlRoot = $mysqld.Directory.Parent.FullName
    if (Test-Path $Destination) {
      Remove-Item -Recurse -Force $Destination
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -Path (Join-Path $mysqlRoot '*') -Destination $Destination -Recurse
  } finally {
    Remove-Item -Recurse -Force $temp -ErrorAction SilentlyContinue
  }
}

function Enable-EmbeddablePython($PythonDir) {
  $pth = Get-ChildItem -Path $PythonDir -Filter 'python*._pth' | Select-Object -First 1
  if (-not $pth) {
    throw 'python._pth was not found in the embeddable Python zip.'
  }
  $zipName = (Get-ChildItem -Path $PythonDir -Filter 'python*.zip' | Select-Object -First 1).Name
  @(
    $zipName
    '.'
    'Lib\site-packages'
    'import site'
  ) | Set-Content -Path $pth.FullName -Encoding ascii
}

$mysqlZip = Join-Path $Cache $MysqlZipName
Get-File $MysqlUrl $mysqlZip
Expand-Mysql $mysqlZip (Join-Path $Runtime 'mysql')

$pythonDir = Join-Path $Runtime 'python'
$pythonZip = Join-Path $Cache "python-$PythonVersion-embed-amd64.zip"
if (-not (Test-Path (Join-Path $pythonDir 'python.exe'))) {
  Get-File $PythonUrl $pythonZip
  if (Test-Path $pythonDir) {
    Remove-Item -Recurse -Force $pythonDir
  }
  Expand-Archive -Path $pythonZip -DestinationPath $pythonDir -Force
  Enable-EmbeddablePython $pythonDir
}

Enable-EmbeddablePython $pythonDir
$pythonExe = Join-Path $pythonDir 'python.exe'
$requirements = Join-Path $Desktop 'requirements-desktop.txt'
$stamp = Join-Path $pythonDir '.requirements.stamp'
$hash = (Get-FileHash $requirements -Algorithm SHA256).Hash
$installed = ''
if (Test-Path $stamp) {
  $installed = (Get-Content $stamp -Raw).Trim()
}
if ($installed -ne $hash) {
  $getPip = Join-Path $Cache 'get-pip.py'
  Get-File 'https://bootstrap.pypa.io/get-pip.py' $getPip
  Write-Host 'Installing Python packages for the desktop server...'
  & $pythonExe $getPip
  if ($LASTEXITCODE -ne 0) { throw 'get-pip.py failed' }
  & $pythonExe -m pip install --upgrade pip
  & $pythonExe -m pip install -r $requirements
  if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
  Set-Content -Path $stamp -Value $hash -Encoding ascii
}

$vcDest = Join-Path $Runtime 'vc_redist.x64.exe'
Get-File $VcUrl $vcDest

$backendDest = Join-Path $Runtime 'backend'
if (Test-Path $backendDest) {
  Remove-Item -Recurse -Force $backendDest
}
New-Item -ItemType Directory -Force -Path $backendDest | Out-Null
$backendSrc = Join-Path $Root 'popy-be'
& robocopy $backendSrc $backendDest /E /NFL /NDL /NJH /NJS /nc /ns /np `
  /XD venv __pycache__ media staticfiles seed-data .git .pytest_cache .mypy_cache .ruff_cache `
  /XF .env *.sqlite3 *.pyc
if ($LASTEXITCODE -ge 8) {
  throw "robocopy failed with exit code $LASTEXITCODE"
}
if (-not (Test-Path (Join-Path $backendDest 'desktop_entry.py'))) {
  throw 'desktop_entry.py was not copied into the backend runtime.'
}

Write-Host "Desktop runtime is ready at $Runtime"
