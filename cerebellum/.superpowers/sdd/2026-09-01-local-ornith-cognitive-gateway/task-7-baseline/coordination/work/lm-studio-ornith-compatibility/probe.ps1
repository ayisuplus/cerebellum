param(
    [Parameter(Mandatory = $true)][string]$Endpoint,
    [Parameter(Mandatory = $true)][string]$Model,
    [Parameter(Mandatory = $true)][string]$Backend,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [int]$Runs = 2
)

$ErrorActionPreference = 'Stop'
$inputsPath = Join-Path $PSScriptRoot 'probe-inputs.json'
$inputBytes = [System.IO.File]::ReadAllBytes($inputsPath)
$inputHash = [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData($inputBytes)).ToLowerInvariant()
$inputs = Get-Content -Raw -LiteralPath $inputsPath | ConvertFrom-Json
$candidateIds = @($inputs.candidates | ForEach-Object { $_.workflow_id })
$results = [System.Collections.Generic.List[object]]::new()

foreach ($run in 1..$Runs) {
    foreach ($case in $inputs.cases) {
        $prompt = [ordered]@{
            task = $case.task
            context = $case.context
            capabilities = $case.capabilities
            candidates = $inputs.candidates
            required_output = [ordered]@{
                workflow_id = 'candidate id'
                confidence = 'number 0..1'
                reasons = @('short reason')
            }
        }
        $body = [ordered]@{
            model = $Model
            temperature = 0
            response_format = @{ type = 'json_object' }
            messages = @(
                @{ role = 'system'; content = 'Select exactly one supplied workflow. Never invent IDs. Return only the required JSON object.' },
                @{ role = 'user'; content = ($prompt | ConvertTo-Json -Depth 12 -Compress) }
            )
        }
        $started = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $response = Invoke-RestMethod -Method Post -Uri $Endpoint -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 12 -Compress) -TimeoutSec 10
            $started.Stop()
            $content = [string]$response.choices[0].message.content
            $selected = $content | ConvertFrom-Json
            $legalId = $candidateIds -contains [string]$selected.workflow_id
            $confidence = [double]$selected.confidence
            $validConfidence = $confidence -ge 0.25 -and $confidence -le 1.0
            $exact = [string]$selected.workflow_id -eq [string]$case.expected
            $results.Add([ordered]@{
                run = $run
                case = $case.id
                expected = $case.expected
                selected = $selected.workflow_id
                confidence = $confidence
                elapsedMs = $started.ElapsedMilliseconds
                validJson = $true
                legalId = $legalId
                validConfidence = $validConfidence
                exact = $exact
                accepted = $legalId -and $validConfidence
                reasoningFieldPresent = $null -ne $response.choices[0].message.reasoning_content
                error = $null
            })
        } catch {
            $started.Stop()
            $results.Add([ordered]@{
                run = $run
                case = $case.id
                expected = $case.expected
                selected = $null
                confidence = $null
                elapsedMs = $started.ElapsedMilliseconds
                validJson = $false
                legalId = $false
                validConfidence = $false
                exact = $false
                accepted = $false
                reasoningFieldPresent = $false
                error = $_.Exception.Message
            })
        }
    }
}

$latencies = @($results | Where-Object accepted | ForEach-Object elapsedMs | Sort-Object)
$summary = [ordered]@{
    schemaVersion = 1
    backend = $Backend
    endpoint = $Endpoint
    model = $Model
    inputSha256 = $inputHash
    runs = $Runs
    casesPerRun = @($inputs.cases).Count
    total = $results.Count
    accepted = @($results | Where-Object accepted).Count
    exact = @($results | Where-Object exact).Count
    validJson = @($results | Where-Object validJson).Count
    reasoningFieldPresent = @($results | Where-Object reasoningFieldPresent).Count
    meanLatencyMs = if ($latencies.Count) { [math]::Round(($latencies | Measure-Object -Average).Average) } else { $null }
    medianLatencyMs = if ($latencies.Count) { $latencies[[math]::Floor($latencies.Count / 2)] } else { $null }
    maxLatencyMs = if ($latencies.Count) { $latencies[-1] } else { $null }
    results = $results
}

$summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutputPath -Encoding utf8
$summary | ConvertTo-Json -Depth 4
if ($summary.accepted -ne $summary.total -or $summary.exact -ne $summary.total) { exit 1 }
