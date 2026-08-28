<# 
.SYNOPSIS
    Tests for the summarize-commits script - both success and intentional failure cases.
#>

param(
    [string]$ScriptPath = ".\summarize-commits.ps1"
)

function Run-Test {
    param(
        [string]$TestName,
        [scriptblock]$TestScript,
        [bool]$ShouldPass
    )
    Write-Host "`n========== $TestName ==========" -ForegroundColor Cyan
    try {
        & $TestScript
        $passed = $true
    }
    catch {
        $passed = $false
        $errorMsg = $_.Exception.Message
    }
    
    if ($passed -eq $ShouldPass) {
        Write-Host "PASS: $TestName" -ForegroundColor Green
        return $true
    }
    else {
        Write-Host "FAIL: $TestName (Expected pass: $ShouldPass, Got pass: $passed)" -ForegroundColor Red
        if (-not $passed) { Write-Host "Error: $errorMsg" -ForegroundColor Red }
        return $false
    }
}

$results = @()

# Test 1: Successful run
$results += Run-Test "Test 1: Successful run" {
    & $ScriptPath -Since (Get-Date).AddDays(-7).ToString("yyyy-MM-dd") -BranchName "claude/summary-test" -LogFile "test-success.log"
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "Script exited with code $exitCode" }
    
    # Verify branch was created
    $branchExists = git ls-remote --heads origin claude/summary-test | Select-String "claude/summary-test"
    if (-not $branchExists) { throw "Branch claude/summary-test was not created on remote" }
    
    # Verify log contains success markers
    $logContent = Get-Content "test-success.log" -Raw
    if (-not $logContent.Contains("SUCCESS")) { throw "Log does not contain SUCCESS marker" }
    if (-not $logContent.Contains("Task completed successfully")) { throw "Log does not contain completion message" }
    
    Write-Host "Verified: Branch created, log contains success markers"
} -ShouldPass $true

# Test 2: Intentional failure - non-existent file read
$results += Run-Test "Test 2: Intentional failure (non-existent file)" {
    # Create a sabotaged version of the script that tries to read a non-existent file
    $sabotagedScript = @'
param([string]$Since = "2020-01-01", [string]$BranchName = "claude/summary-fail", [string]$LogFile = "test-fail.log")

function Write-Log { param([string]$Message, [string]$Level = "INFO"); $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"; $logEntry = "[$timestamp] [$Level] $Message"; Write-Host $logEntry; Add-Content -Path $LogFile -Value $logEntry }
function Write-Success { param([string]$Message); Write-Log $Message "SUCCESS" }
function Write-Error { param([string]$Message); Write-Log $Message "ERROR" }

try {
    Write-Log "Starting sabotaged commit summary task..."
    # SABOTAGE: Try to read a deliberately non-existent file
    $fakeContent = Get-Content "C:\This\Path\Does\Not\Exist\fake-file.txt" -ErrorAction Stop
    Write-Log "This should never be reached"
    exit 0
}
catch {
    Write-Error "Sabotage triggered - failed to read non-existent file: $($_.Exception.Message)"
    exit 1
}
'@
    
    $sabotagedPath = "sabotaged-script.ps1"
    Set-Content -Path $sabotagedPath -Value $sabotagedScript -Encoding UTF8
    
    & powershell -File $sabotagedPath -Since "2020-01-01" -BranchName "claude/summary-fail" -LogFile "test-fail.log"
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) { throw "Script should have failed but exited with code 0" }
    
    # Verify log contains error markers
    $logContent = Get-Content "test-fail.log" -Raw
    if (-not $logContent.Contains("ERROR")) { throw "Log does not contain ERROR marker" }
    if (-not $logContent.Contains("Sabotage triggered") -and -not $logContent.Contains("non-existent")) { 
        throw "Log does not contain sabotage failure message" 
    }
    
    Write-Host "Verified: Script failed non-silently, log contains error markers"
    Remove-Item $sabotagedPath -Force
} -ShouldPass $true

# Summary
Write-Host "`n========== TEST SUMMARY ==========" -ForegroundColor Cyan
$passed = ($results | Where-Object { $_ -eq $true }).Count
$failed = ($results | Where-Object { $_ -eq $false }).Count
Write-Host "Passed: $passed"
Write-Host "Failed: $failed"

if ($failed -gt 0) {
    exit 1
}
exit 0