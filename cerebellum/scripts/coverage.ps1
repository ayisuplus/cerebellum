# Measures per-area test coverage and enforces the >= 80% bar.
#
#   Rust workspace  : llvm-tools-preview source instrumentation (cargo test)
#   Python suites   : pytest-cov, one run per package
#
# Usage:  powershell -NoProfile -File scripts/coverage.ps1 [-FailBelow 80]
#
# Requires: rustup component add llvm-tools-preview; python -m pip install pytest pytest-cov
param(
    [double]$FailBelow = 80.0
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

$results = @()

try {
    # ---------------- Rust ----------------
    $toolchain = (rustup show active-toolchain) -split '\s+' | Select-Object -First 1
    $llvmBin = Join-Path $env:USERPROFILE ".rustup/toolchains/$toolchain/lib/rustlib/x86_64-pc-windows-msvc/bin"
    if (-not (Test-Path (Join-Path $llvmBin "llvm-cov.exe"))) {
        throw "llvm-tools-preview missing; run: rustup component add llvm-tools-preview"
    }

    $covDir = "target/cov"
    if (Test-Path $covDir) { Remove-Item -Recurse -Force $covDir }
    New-Item -ItemType Directory -Path $covDir | Out-Null

    # Drop stale test binaries so every cerebellum*.exe under deps/ afterwards
    # belongs to the instrumented build (no hash/timestamp guessing).
    Get-ChildItem target/debug/deps -Filter "cerebellum*.exe" -ErrorAction SilentlyContinue |
        Remove-Item -Force

    $env:CARGO_INCREMENTAL = "0"
    $env:RUSTFLAGS = "-C instrument-coverage"
    $env:LLVM_PROFILE_FILE = "$($repositoryRoot -replace '\\','/')/$covDir/cerebellum-%p-%m.profraw"
    cargo test --workspace --all-targets --quiet
    $testExit = $LASTEXITCODE
    Remove-Item Env:RUSTFLAGS, Env:LLVM_PROFILE_FILE, Env:CARGO_INCREMENTAL -ErrorAction SilentlyContinue
    if ($testExit -ne 0) { throw "instrumented cargo test failed" }

    $profdata = Get-ChildItem $covDir -Filter *.profraw | ForEach-Object FullName
    & (Join-Path $llvmBin "llvm-profdata.exe") merge -sparse @profdata -o "$covDir/merged.profdata" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "llvm-profdata merge failed" }

    $objects = @(Get-ChildItem target/debug/deps -Filter "cerebellum*.exe" | ForEach-Object { $_.FullName })
    if ($objects.Count -eq 0) { throw "no instrumented test binaries found" }
    $covArgs = @("report", "--instr-profile=$covDir/merged.profdata")
    foreach ($obj in $objects) { $covArgs += "--object=$obj" }
    $report = & (Join-Path $llvmBin "llvm-cov.exe") @covArgs
    if ($LASTEXITCODE -ne 0) { throw "llvm-cov report failed" }

    $rustLines = 0L; $rustMissed = 0L
    foreach ($line in $report) {
        if ($line -notmatch "cerebellum-app.src|cerebellum-core.src") { continue }
        if ($line -match "(\d+)\s+(\d+)\s+[\d.]+%\s+(\d+)\s+(\d+)\s+[\d.]+%\s+(\d+)\s+(\d+)\s+[\d.]+%") {
            $rustLines += [int64]$Matches[5]
            $rustMissed += [int64]$Matches[6]
        }
    }
    if ($rustLines -eq 0) { throw "no first-party Rust coverage rows parsed" }
    $results += [pscustomobject]@{
        Area = "rust-workspace"; Covered = ($rustLines - $rustMissed); Total = $rustLines
        Percent = [math]::Round(100.0 * ($rustLines - $rustMissed) / $rustLines, 1)
    }

    # ---------------- Python ----------------
    $suites = @(
        @{ Name = "evolver"; PyPath = "components/evolver"; Tests = "components/evolver/tests"; Source = "components/evolver/evolver" },
        @{ Name = "worker-skillopt"; PyPath = "workers/skillopt-reference/src"; Tests = "workers/skillopt-reference/tests"; Source = "workers/skillopt-reference/src" },
        @{ Name = "worker-meta-training"; PyPath = "workers/meta-training/src"; Tests = "workers/meta-training/tests"; Source = "workers/meta-training/src" },
        @{ Name = "worker-web-acquisition"; PyPath = "workers/web-acquisition/src"; Tests = "workers/web-acquisition/tests"; Source = "workers/web-acquisition/src" },
        @{ Name = "worker-social-acquisition"; PyPath = "workers/social-acquisition/src"; Tests = "workers/social-acquisition/tests"; Source = "workers/social-acquisition/src" }
    )
    foreach ($suite in $suites) {
        $env:PYTHONPATH = Join-Path $repositoryRoot $suite.PyPath
        # Per-suite datafile so the five runs never overwrite each other.
        $env:COVERAGE_FILE = Join-Path $repositoryRoot ".coverage.$($suite.Name)"
        $output = python -m pytest $suite.Tests -q --tb=no -p no:cacheprovider `
            --cov=$($suite.Source) --cov-report=term 2>&1
        if ($LASTEXITCODE -ne 0) { throw "pytest failed for $($suite.Name):`n$($output | Select-Object -Last 5)" }
        $total = $output | Where-Object { $_ -match "^TOTAL\s+(\d+)\s+(\d+)\s+" } | Select-Object -First 1
        if (-not $total) { throw "no TOTAL coverage row for $($suite.Name)" }
        $null = $total -match "^TOTAL\s+(\d+)\s+(\d+)\s+"
        $stmts = [int64]$Matches[1]; $missed = [int64]$Matches[2]
        $results += [pscustomobject]@{
            Area = $suite.Name; Covered = ($stmts - $missed); Total = $stmts
            Percent = [math]::Round(100.0 * ($stmts - $missed) / $stmts, 1)
        }
    }
}
finally {
    Pop-Location
    Remove-Item Env:COVERAGE_FILE -ErrorAction SilentlyContinue
}

$results | Format-Table Area, Covered, Total, Percent -AutoSize
$overallTotal = ($results | Measure-Object Total -Sum).Sum
$overallCovered = ($results | Measure-Object Covered -Sum).Sum
$overall = [math]::Round(100.0 * $overallCovered / $overallTotal, 1)
Write-Output ("OVERALL {0}% ({1}/{2})" -f $overall, $overallCovered, $overallTotal)

$below = $results | Where-Object { $_.Percent -lt $FailBelow }
if ($below -or $overall -lt $FailBelow) {
    $names = ($below | ForEach-Object { "$($_.Area)=$($_.Percent)%" }) -join ", "
    Write-Error "coverage below $FailBelow%: $names overall=$overall%"
    exit 1
}
Write-Output "coverage gate passed (>= $FailBelow%)"
