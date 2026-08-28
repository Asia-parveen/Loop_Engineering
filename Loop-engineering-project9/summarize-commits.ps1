<# 
.SYNOPSIS
    Summarizes yesterday's commits and creates a claude/summary branch.

.DESCRIPTION
    This script performs a one-off checkable task: it fetches yesterday's commits,
    creates a summary, and pushes it to a claude/summary branch.
    Designed for manual "Run now" execution with clear success/failure logging.
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$Since = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd"),
    
    [Parameter(Mandatory=$false)]
    [string]$BranchName = "claude/summary",
    
    [Parameter(Mandatory=$false)]
    [string]$LogFile = "summarize-commits.log"
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
    Write-Log "Starting commit summary task..."
    Write-Log "Parameters: Since=$Since, BranchName=$BranchName"
    
    # Check if we're in a git repo
    $gitStatus = git status --porcelain 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Not a git repository or git command failed"
        exit 1
    }
    Write-Log "Git repository verified"
    
    # Get yesterday's commits
    $commits = git log --since="$Since" --pretty=format:"%h %an: %s" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to retrieve commits: $commits"
        exit 1
    }
    
    if (-not $commits) {
        Write-Log "No commits found since $Since"
        $summary = "No commits found since $Since"
    } else {
        $commitCount = ($commits -split "`n").Count
        Write-Log "Found $commitCount commit(s) since $Since"
        $summary = "Commit Summary for $Since`n========================`n$commits"
    }
    
    # Create or update the summary branch
    Write-Log "Creating/updating branch: $BranchName"
    
    # Stash any local changes
    git stash push -m "summarize-commits stash" 2>&1 | Out-Null
    
    # Delete branch if exists (local and remote)
    git branch -D $BranchName 2>&1 | Out-Null
    git push origin --delete $BranchName 2>&1 | Out-Null
    
    # Create new orphan branch for summary
    git checkout --orphan $BranchName 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create orphan branch"
        exit 1
    }
    
    # Remove all files from the branch
    git rm -rf . 2>&1 | Out-Null
    
    # Create summary file
    $summaryPath = "COMMIT_SUMMARY.md"
    Set-Content -Path $summaryPath -Value $summary -Encoding UTF8
    Write-Log "Created summary file: $summaryPath"
    
    # Commit and push
    git add $summaryPath
    git commit -m "Commit summary for $Since" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to commit summary"
        exit 1
    }
    
    git push origin $BranchName --force 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to push branch $BranchName"
        exit 1
    }
    
    Write-Success "Successfully created/updated $BranchName with commit summary"
    Write-Log "Summary content:`n$summary"
    
    # Return to master
    git checkout master 2>&1 | Out-Null
    git stash pop 2>&1 | Out-Null
    
    Write-Success "Task completed successfully"
    exit 0
}
catch {
    Write-Error "Unexpected error: $($_.Exception.Message)"
    exit 1
}