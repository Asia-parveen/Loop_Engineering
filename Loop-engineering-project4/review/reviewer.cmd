@echo off
setlocal EnableDelayedExpansion

rem reviewer.cmd - independent maker-checker reviewer.
rem Runs from the REVIEW worktree on branch review/fix-price.
rem Inspects the implementer's real diff, runs the tests itself,
rem and writes exactly one PASS or FAIL verdict to review\result.txt.

set PROJECT_DIR=%~dp0..
set RESULT_FILE=%PROJECT_DIR%\review\result.txt
set DIFF_FILE=%PROJECT_DIR%\review\impl_diff.txt
set TEST_OUT=%PROJECT_DIR%\review\test_output.txt

pushd "%PROJECT_DIR%"

rem --- 1. Locate the implementer's commit -------------------------------
set IMPL_SHA=
for /f %%i in ('git rev-parse impl/fix-price 2^>nul') do set IMPL_SHA=%%i
if not defined IMPL_SHA (
    echo FAIL: cannot resolve branch impl/fix-price in this worktree.
    echo FAIL: cannot resolve branch impl/fix-price in this worktree.> "%RESULT_FILE%"
    popd
    exit /b 0
)

rem --- 2. Capture the actual diff the implementer introduced -------------
git diff master...impl/fix-price > "%DIFF_FILE%" 2>&1
echo Inspected implementer commit %IMPL_SHA%, diff saved to %DIFF_FILE%.

rem --- 3. Run the test suite ourselves, capture real output + exit code --
python -m unittest discover -s tests -v > "%TEST_OUT%" 2>&1
set TEST_EXIT=%errorlevel%
type "%TEST_OUT%"
echo.
echo implementer commit: %IMPL_SHA%
echo test exit code: %TEST_EXIT%

rem --- 4. Verdict: evidence-based, never the implementer's claim ---------
if "%TEST_EXIT%"=="0" (
    echo PASS: tests pass on implementer commit %IMPL_SHA%. Reason: test suite exits 0, all assertions satisfied.> "%RESULT_FILE%"
) else (
    echo FAIL: tests fail on implementer commit %IMPL_SHA%. Reason: test suite exits %TEST_EXIT%, see %TEST_OUT%.> "%RESULT_FILE%"
)

echo.
echo Verdict:
type "%RESULT_FILE%"

popd
exit /b 0
