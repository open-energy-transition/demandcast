# benchmark_retrieve.ps1 — fail-fast retrieval for DNK/AUT/PRT 2021-2023
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
Log "Benchmark retrieval START"
Log "  Entities : DNK, AUT, PRT"
Log "  Years    : 2021-2023"
Log "  Steps    : electricity / annual-elec / population / gdp / temperature / assemble"
Log "=========================================================="

Run-Step "1/6  electricity demand (ENTSO-E)"         "config\benchmark_retrieve_electricity.yaml"
Run-Step "2/6  annual electricity demand per capita" "config\benchmark_retrieve_annual_elec.yaml"
Run-Step "3/6  population"                           "config\benchmark_retrieve_population.yaml"
Run-Step "4/6  GDP PPP per capita"                   "config\benchmark_retrieve_gdp.yaml"

Log "--- NOTE  Steps 1-4 complete. Step 5 issues up to 15 CDS API requests ---"
Log "---       (ERA5 for years 2020-2024, 3 entities). Expect 4-8 h.       ---"

Run-Step "5/6  temperature 2021-2023  (ERA5 via CDS)" "config\benchmark_retrieve_temperature.yaml"
Run-Step "6/6  assemble"                              "config\benchmark_assemble.yaml" "assemble.py"

Log "=========================================================="
Log "Benchmark retrieval COMPLETE"
Log "Assembled dataset written to: data\assembled\"
Log "=========================================================="
