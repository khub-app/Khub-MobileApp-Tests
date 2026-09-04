# Reads data/test_data.xlsx -> RunConfig sheet (Environment + Suite toggles)
# and runs the matching tests. Mirrors khub-pos-tests' run_tests.ps1: Appium
# drives ONE device (emulator or real_device) at a time, so there's no
# Headless/Workers/multi-env toggle - just which environment to target and
# which suite(s) to run.
#
# Which test gets which suite marker is controlled by data/test_data.xlsx's
# Tags sheet (FilePath | smoke | regression columns) - conftest.py applies
# those markers automatically at collection time.
#
# The Allure HTML report is regenerated automatically after the run
# (conftest.py's pytest_sessionfinish hook) - no separate step needed here.
#
# Override the sheet for a one-off run:
#   .\run_mobile_tests.ps1 -Path tests/login -Suite ""      # run a folder, ignore markers
#   .\run_mobile_tests.ps1 -Env real_device

param(
    [string]$Path  = "tests/",
    [string]$Suite,           # omit = use the RunConfig sheet; "" = no marker filter
    [string]$Env              # omit = use the RunConfig sheet
)

$cfg = & "venv\Scripts\python.exe" scripts/read_run_config.py | ConvertFrom-Json
if ($cfg.error) {
    Write-Host "[ERROR] $($cfg.error)"
    exit 1
}

$envName = if ($PSBoundParameters.ContainsKey('Env')) { $Env } else { $cfg.environment }

if ($PSBoundParameters.ContainsKey('Suite')) {
    $markerExpr = $Suite
} else {
    $suites = @($cfg.suites)
    if ($suites.Count -eq 0) {
        Write-Host "[WARNING] No suites enabled in the RunConfig sheet. Set Smoke or Regression to Yes."
        exit 1
    }
    $markerExpr = $suites -join " or "
}

Write-Host ""
Write-Host "=== Config for this run ==="
Write-Host "  Path         : $Path"
Write-Host "  Marker(s)    : $(if ($markerExpr) { $markerExpr } else { '(none)' })"
Write-Host "  Environment  : $envName"
Write-Host "=========================="
Write-Host ""

$pyArgs = @("-m", "pytest", $Path, "-v", "--env=$envName")
if ($markerExpr) { $pyArgs += @("-m", $markerExpr) }

& "venv\Scripts\python.exe" @pyArgs
exit $LASTEXITCODE
