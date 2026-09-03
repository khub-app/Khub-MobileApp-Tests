# Convenience runner. Usage:
#   .\run_tests.ps1                 # all tests, emulator
#   .\run_tests.ps1 -Suite smoke   # only @pytest.mark.smoke
#   .\run_tests.ps1 -Env real_device
param(
    [string]$Suite = "",
    [string]$Env = "emulator",
    [string]$Path = "tests/"
)

$py = "venv\Scripts\python.exe"
$args = @("-m", "pytest", $Path, "-v", "--env=$Env")
if ($Suite) { $args += @("-m", $Suite) }

Write-Host "=== pytest $($args -join ' ') ===" -ForegroundColor Cyan
& $py @args
exit $LASTEXITCODE
