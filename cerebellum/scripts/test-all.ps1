$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$previousPythonPath = $env:PYTHONPATH

function Invoke-PythonSuite {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonPath,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [string]$WorkingDirectory = "."
    )

    $env:PYTHONPATH = Join-Path $repositoryRoot $PythonPath
    Push-Location (Join-Path $repositoryRoot $WorkingDirectory)
    try {
        & python @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Python suite failed: python $($Arguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

Push-Location $repositoryRoot
try {
    & cargo fmt --all -- --check
    if ($LASTEXITCODE -ne 0) { throw "cargo fmt failed" }

    & cargo clippy --workspace --all-targets -- -D warnings
    if ($LASTEXITCODE -ne 0) { throw "cargo clippy failed" }

    & cargo test --workspace --all-targets
    if ($LASTEXITCODE -ne 0) { throw "cargo test failed" }

    & node --check admin/app.js
    if ($LASTEXITCODE -ne 0) { throw "admin JavaScript syntax check failed" }

    & python scripts/validate-monorepo.py
    if ($LASTEXITCODE -ne 0) { throw "monorepo validation failed" }

    Invoke-PythonSuite `
        -PythonPath "components/evolver" `
        -WorkingDirectory "components/evolver" `
        -Arguments @("-m", "pytest", "tests", "-q")
    Invoke-PythonSuite "workers/skillopt-reference/src" @(
        "-m", "unittest", "discover", "-s", "workers/skillopt-reference/tests",
        "-p", "test_*.py", "-v"
    )
    Invoke-PythonSuite "workers/web-acquisition/src" @(
        "-m", "unittest", "discover", "-s", "workers/web-acquisition/tests",
        "-p", "test_*.py", "-v"
    )
    Invoke-PythonSuite "workers/meta-training/src" @(
        "-m", "unittest", "discover", "-s", "workers/meta-training/tests",
        "-p", "test_*.py", "-v"
    )
    Invoke-PythonSuite "workers/social-acquisition/src" @(
        "-m", "pytest", "workers/social-acquisition/tests", "-q"
    )

    $env:PYTHONPATH = $previousPythonPath
    & python -m unittest discover -s benchmarks/verify -p "test_*.py" -v
    if ($LASTEXITCODE -ne 0) { throw "benchmark tests failed" }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
