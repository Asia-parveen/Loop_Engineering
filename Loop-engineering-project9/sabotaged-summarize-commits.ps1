<# 
.SYNOPSIS
    Sabotaged version - intentionally tries to read a non-existent file.
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$Since = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd"),
    
    [Parameter(Mandatory=$false)]
    [string]$BranchName = "claude/summary",
    
    [Parameter(Mandatory=$false)]
    [string]$LogFile = "sabotaged-run.log"
)

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Write-Host $logEntry
    Add-Content -Path $LogFile -Value $logEntry
}

function Write-Success {
    param([string]$Message)
    Write-Log $Message "SUCCESS"
}

function Write-Error {
    param([string]$Message)
    Write-Log $Message "ERROR"
}

try {
    Write-Log "Starting sabotaged commit summary task..."
    Write-Log "Parameters: Since=$Since, BranchName=$BranchName"
    
    # Check if we're in a git repo
    $gitStatus = git status --porcelain 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Not a git repository or git command failed"
        exit 1
    }
    Write-Log "Git repository verified"
    
    # SABOTAGE: Try to read a deliberately non-existent file
    Write-Log "Attempting to read non-existent file..."
    $fakeContent = Get-Content "THIS_FILE_DOES_NOT_EXIST.txt" -ErrorAction Stop
    Write-Log "This should never be reached"
    
    exit 0
}
catch {
    Write-Error "Sabotage triggered - failed to read non-existent file: $($_.Exception.Message)"
    exit 1
}