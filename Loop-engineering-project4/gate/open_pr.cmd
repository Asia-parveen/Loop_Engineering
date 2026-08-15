@echo off
setlocal EnableDelayedExpansion

rem open_pr.cmd - the PASS/FAIL gate that controls the PR step.
rem PASS -> verify reviewer result, push the implementer branch, and print
rem         the exact GitHub compare URL to open the PR manually.
rem FAIL (or missing result) -> block the PR completely, exit code 1.
rem
rem Automatic PR creation needs the gh CLI, which is currently unavailable.
rem This gate therefore stops at the compare/PR URL. It never fakes a PR.

set PROJECT_DIR=%~dp0..
set RESULT_FILE=%PROJECT_DIR%\review\result.txt

if not exist "%RESULT_FILE%" (
    echo FAIL: no review result found at %RESULT_FILE%. Run the reviewer first.
    exit /b 1
)

set VERDICT=
for /f "tokens=1" %%v in (%RESULT_FILE%) do set VERDICT=%%v

if /i not "%VERDICT%"=="PASS" (
    echo.
    echo PR BLOCKED: reviewer did not return PASS.
    type "%RESULT_FILE%"
    echo exit code 1
    exit /b 1
)

echo.
echo PR ALLOWED: reviewer returned PASS.
git push origin impl/fix-price

echo.
echo Open the PR manually at this compare URL:
echo https://github.com/Asia-parveen/Loop_Engineering/compare/master...impl/fix-price
echo (Automatic `gh pr create` requires the gh CLI, which is not installed.)
exit /b 0
