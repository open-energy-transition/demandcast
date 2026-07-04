# benchmark_retrieve_resume.ps1 — resume from step 5/6 only
# Steps 1-4 already completed; this runs temperature (ERA5) + assemble.
# Monitor: Get-Content -Wait logs\benchmark_orchestration.log

Set-Location "C:\Users\Dell\Desktop\DemandCast\demandcast\demandcast"

New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$MasterLog = "logs\benchmark_orchestration.log"

function Log([string]$msg) {
    $line = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  " + $msg
    Write-Host $line
    Add-Content -Path $MasterLog -Value $line
}

function Run-Step([string]$Desc, [string]$Config, [string]$Script = "retrieve.py") {
    Log ("--- STARTING  " + $Desc + " ---")
    $t0 = Get-Date

    uv run $Script --config $Config
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        Log ("--- FAILED    " + $Desc + "  (exit " + $exitCode + ") ---")
        Log "ABORTED -- check logs\ directory for per-step log files."
        exit 1
    }

    $mins = [int]((Get-Date) - $t0).TotalMinutes
    Log ("--- DONE      " + $Desc + "  (" + $mins + "m) ---")
}

Log "=========================================================="
Log "Benchmark retrieval RESUME (steps 5-6 only)"
Log "  Entities : DNK, AUT, PRT"
Log "  Years    : 2021-2023"
Log "  Note     : ERA5 licence accepted; resuming after step 4"
Log "=========================================================="

Run-Step "5/6  temperature 2021-2023  (ERA5 via CDS)" "config\benchmark_retrieve_temperature.yaml"
Run-Step "6/6  assemble"                              "config\benchmark_assemble.yaml" "assemble.py"

Log "=========================================================="
Log "Benchmark retrieval COMPLETE"
Log "Assembled dataset written to: data\assembled\"
Log "=========================================================="
