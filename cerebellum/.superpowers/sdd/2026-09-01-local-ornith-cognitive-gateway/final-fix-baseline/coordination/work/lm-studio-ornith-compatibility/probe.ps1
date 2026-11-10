param(
    [Parameter(Mandatory = $true)][string]$Endpoint,
    [Parameter(Mandatory = $true)][string]$Model,
    [Parameter(Mandatory = $true)][string]$Backend,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ArtifactSha256,
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$RuntimeName,
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$RuntimeVersion,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [int]$Runs = 2
)

$ErrorActionPreference = 'Stop'
$inputsPath = Join-Path $PSScriptRoot 'probe-inputs.json'
$inputBytes = [System.IO.File]::ReadAllBytes($inputsPath)
$sha256 = [System.Security.Cryptography.SHA256]::Create()
try {
    $inputHash = ([BitConverter]::ToString($sha256.ComputeHash($inputBytes))).Replace('-', '').ToLowerInvariant()
} finally {
    $sha256.Dispose()
}
$inputs = Get-Content -Raw -Encoding UTF8 -LiteralPath $inputsPath | ConvertFrom-Json
$candidateIds = @($inputs.candidates | ForEach-Object { $_.workflow_id })
$results = [System.Collections.Generic.List[object]]::new()
$schema = [ordered]@{
    type = 'object'
    additionalProperties = $false
    required = @('workflow_id', 'confidence', 'reasons')
    properties = [ordered]@{
        workflow_id = @{ type = 'string'; enum = $candidateIds }
        confidence = @{ type = 'number'; minimum = 0; maximum = 1 }
        reasons = @{ type = 'array'; maxItems = 8; items = @{ type = 'string'; maxLength = 240 } }
    }
}

function Get-GpuSnapshot {
    $rows = & nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits
    if ($LASTEXITCODE -ne 0) { throw "nvidia-smi failed with exit code $LASTEXITCODE" }
    @($rows | ForEach-Object {
        $fields = $_ -split ',\s*'
        [ordered]@{
            index = [int]$fields[0]
            name = $fields[1]
            memoryUsedMiB = [int]$fields[2]
            memoryTotalMiB = [int]$fields[3]
            utilizationPercent = [int]$fields[4]
        }
    })
}

$gpuBefore = Get-GpuSnapshot

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
            response_format = @{
                type = 'json_schema'
                json_schema = @{ name = 'cerebellum_router'; strict = $true; schema = $schema }
            }
            messages = @(
                @{ role = 'system'; content = 'Select exactly one supplied workflow. Never invent IDs. Return only the required JSON object.' },
                @{ role = 'user'; content = ($prompt | ConvertTo-Json -Depth 12 -Compress) }
            )
        }
        $started = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $response = Invoke-RestMethod -Method Post -Uri $Endpoint -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 12 -Compress) -TimeoutSec 45
            $started.Stop()
            $content = [string]$response.choices[0].message.content
            $selected = $content | ConvertFrom-Json
            $propertyNames = @($selected.PSObject.Properties.Name)
            $exactProperties = $propertyNames.Count -eq 3 -and
                @($propertyNames | Where-Object { $_ -notin @('workflow_id', 'confidence', 'reasons') }).Count -eq 0
            $workflowIdIsString = $selected.workflow_id -is [string]
            $legalId = $workflowIdIsString -and $candidateIds -contains $selected.workflow_id
            $confidenceIsNumber = $selected.confidence -is [byte] -or
                $selected.confidence -is [sbyte] -or
                $selected.confidence -is [int16] -or
                $selected.confidence -is [uint16] -or
                $selected.confidence -is [int32] -or
                $selected.confidence -is [uint32] -or
                $selected.confidence -is [int64] -or
                $selected.confidence -is [uint64] -or
                $selected.confidence -is [single] -or
                $selected.confidence -is [double] -or
                $selected.confidence -is [decimal]
            $confidence = if ($confidenceIsNumber) { [double]$selected.confidence } else { $null }
            $validConfidence = $confidenceIsNumber -and $confidence -ge 0 -and $confidence -le 1
            $reasonsIsArray = $selected.reasons -is [array]
            $validReasons = $reasonsIsArray -and @($selected.reasons).Count -le 8 -and
                @($selected.reasons | Where-Object { $_ -isnot [string] -or $_.Length -gt 240 }).Count -eq 0
            $schemaValid = $exactProperties -and $workflowIdIsString -and $legalId -and
                $validConfidence -and $validReasons
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
                schemaValid = $schemaValid
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
                schemaValid = $false
                exact = $false
                accepted = $false
                reasoningFieldPresent = $false
                error = $_.Exception.Message
            })
        }
    }
}

$gpuAfter = Get-GpuSnapshot
$latencies = @($results | Where-Object accepted | ForEach-Object elapsedMs | Sort-Object)
$summary = [ordered]@{
    schemaVersion = 2
    backend = $Backend
    endpoint = $Endpoint
    model = $Model
    artifactSha256 = $ArtifactSha256.ToLowerInvariant()
    runtimeName = $RuntimeName
    runtimeVersion = $RuntimeVersion
    inputSha256 = $inputHash
    gpuBefore = $gpuBefore
    gpuAfter = $gpuAfter
    runs = $Runs
    casesPerRun = @($inputs.cases).Count
    total = $results.Count
    accepted = @($results | Where-Object accepted).Count
    schemaValid = @($results | Where-Object schemaValid).Count
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
if ($summary.accepted -ne $summary.total -or $summary.schemaValid -ne $summary.total) { exit 1 }
