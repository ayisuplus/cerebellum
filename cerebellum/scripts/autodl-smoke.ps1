param(
    [Parameter(Mandatory = $true)][string]$ServerUrl,
    [Parameter(Mandatory = $true)][string]$SnapshotId,
    [Parameter(Mandatory = $true)][string]$BaseModelId,
    [Parameter(Mandatory = $true)][string]$BaseModelRevision,
    [Parameter(Mandatory = $true)][string]$BaseModelSha256,
    [Parameter(Mandatory = $true)][string]$GpuSpec,
    [Parameter(Mandatory = $true)][double]$MaxHourlyCny,
    [Parameter(Mandatory = $true)][double]$MaxTotalCny,
    [int]$MaxWallSeconds = 600,
    [switch]$AcknowledgeCost
)

$ErrorActionPreference = "Stop"
if (-not $AcknowledgeCost -or $env:CEREBELLUM_REAL_AUTODL_SMOKE -ne "I_UNDERSTAND_THIS_CREATES_A_BILLABLE_INSTANCE") {
    throw "Real smoke test requires -AcknowledgeCost and CEREBELLUM_REAL_AUTODL_SMOKE=I_UNDERSTAND_THIS_CREATES_A_BILLABLE_INSTANCE"
}
if ([string]::IsNullOrWhiteSpace($env:CEREBELLUM_AUTH_TOKEN)) {
    throw "CEREBELLUM_AUTH_TOKEN is required in the process environment"
}
if ($MaxWallSeconds -lt 60 -or $MaxWallSeconds -gt 21600 -or $MaxHourlyCny -le 0 -or $MaxTotalCny -le 0) {
    throw "Budgets must be positive and MaxWallSeconds must be 60..21600"
}

$headers = @{ Authorization = "Bearer $($env:CEREBELLUM_AUTH_TOKEN)" }
$createBody = @{
    snapshot_id = $SnapshotId
    base_model = @{
        model_id = $BaseModelId
        revision = $BaseModelRevision
        sha256 = $BaseModelSha256
    }
    qlora = @{
        epochs = 1
        max_sequence_length = 256
        lora_rank = 4
        lora_alpha = 8
        lora_dropout = 0.05
        learning_rate = 0.0002
        gradient_accumulation_steps = 1
    }
    gpu_spec = $GpuSpec
    administrator = "autodl-smoke"
    reason = "explicit real AutoDL smoke test"
    budget = @{
        max_hourly_cny = $MaxHourlyCny
        max_total_cny = $MaxTotalCny
        max_wall_seconds = $MaxWallSeconds
    }
} | ConvertTo-Json -Depth 8

$run = Invoke-RestMethod -Method Post -Uri "$($ServerUrl.TrimEnd('/'))/v1/training-runs" -Headers $headers -ContentType "application/json" -Body $createBody
Write-Host "Created non-billable TrainingRun $($run.run_id). Starting the confirmed AutoDL allocation."
$startBody = @{
    administrator = "autodl-smoke"
    reason = "explicit cost confirmation"
    confirm_gpu_spec = $GpuSpec
    confirm_max_hourly_cny = $MaxHourlyCny
    confirm_max_total_cny = $MaxTotalCny
    confirm_max_wall_seconds = $MaxWallSeconds
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "$($ServerUrl.TrimEnd('/'))/v1/training-runs/$($run.run_id):start" -Headers $headers -ContentType "application/json" -Body $startBody
