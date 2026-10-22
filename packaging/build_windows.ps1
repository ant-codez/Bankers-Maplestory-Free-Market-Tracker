# Build the single-file Windows app "Free Market Tracker.exe" (Python, Tk, Pillow
# and Tesseract OCR all inside). Needs, on the build machine only:
#   Python 3.10+ (python.org or winget) and Tesseract (UB Mannheim build).
# "Build Windows App.bat" next to this file installs both with winget and runs it.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$Root = (Get-Location).Path
$Name = "Free Market Tracker"
$Work = Join-Path $Root "build\windows"

# --- Python for building (a private venv; nothing is installed system-wide)
$Py = if ($env:PYTHON) { $env:PYTHON } else { "py" }
$PyArgs = if ($Py -eq "py") { @("-3") } else { @() }
if (Test-Path $Work) { Remove-Item -Recurse -Force $Work }
New-Item -ItemType Directory -Force -Path $Work | Out-Null
& $Py @PyArgs -m venv (Join-Path $Work "venv")
$VPy = Join-Path $Work "venv\Scripts\python.exe"
& $VPy -m pip install --upgrade pip
& $VPy -m pip install pyinstaller pillow pytesseract mss pyspellchecker certifi pynput

# --- Tesseract: tesseract.exe, its DLLs and English data only
$TessDir = $env:TESSERACT_DIR
if (-not $TessDir) {
  foreach ($c in @("$env:ProgramFiles\Tesseract-OCR", "${env:ProgramFiles(x86)}\Tesseract-OCR",
                   "$env:LOCALAPPDATA\Programs\Tesseract-OCR")) {
    if (Test-Path (Join-Path $c "tesseract.exe")) { $TessDir = $c; break }
  }
}
if (-not $TessDir) { throw "Tesseract not found. Install it (winget install UB-Mannheim.TesseractOCR) or set TESSERACT_DIR." }
$Tess = Join-Path $Work "tesseract"
New-Item -ItemType Directory -Force -Path (Join-Path $Tess "tessdata") | Out-Null
Copy-Item (Join-Path $TessDir "tesseract.exe") $Tess
Copy-Item (Join-Path $TessDir "*.dll") $Tess
Copy-Item (Join-Path $TessDir "tessdata\eng.traineddata") (Join-Path $Tess "tessdata")
# the app's own OCR model, trained on the game's chat and shops (used as "mfm+eng")
if (Test-Path (Join-Path $Root "ocr\mfm.traineddata")) {
  Copy-Item (Join-Path $Root "ocr\mfm.traineddata") (Join-Path $Tess "tessdata")
}
if (Test-Path (Join-Path $TessDir "tessdata\configs")) {
  Copy-Item -Recurse (Join-Path $TessDir "tessdata\configs") (Join-Path $Tess "tessdata")
}
& (Join-Path $Tess "tesseract.exe") --version

# --- the app
& $VPy -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name $Name `
  --icon (Join-Path $Root "packaging\icon.ico") `
  --paths $Root `
  --hidden-import mfm --hidden-import mfm_gui --hidden-import mfm_shared `
  --hidden-import PIL._tkinter_finder --hidden-import PIL.ImageTk `
  --collect-data spellchecker --collect-data certifi --hidden-import certifi `
  --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 `
  --add-data "$Tess;tesseract" `
  --add-data "$(Join-Path $Root 'ocr\glyphs.json');ocr" `
  --add-data "$(Join-Path $Root 'ocr\name_glyphs.json');ocr" `
  --add-data "$(Join-Path $Root 'packaging\icon.png');." `
  --add-data "$(Join-Path $Root 'packaging\fonts');fonts" `
  --workpath (Join-Path $Work "pyi") --specpath $Work --distpath (Join-Path $Root "dist") `
  (Join-Path $Root "packaging\launcher.py")
Write-Host ""
Write-Host "Done: $(Join-Path $Root "dist\$Name.exe")"
