param(
    [string]$Key
)

# Creates a venv inside Winrate_Prediction\.venv, installs requirements,
# writes a `.env` file containing `RIOT_API_KEY`, and appends an env-var
# assignment to the venv Activate.ps1 so activating the venv sets the key.

if (-not $Key) {
    $Key = Read-Host -Prompt 'Enter Riot API Key (input will be written to .env and venv activation script)'
}

# Determine project folder as the parent of the scripts folder (robust to where script is run from)
$projectPathObj = Resolve-Path (Join-Path $PSScriptRoot '..')
if (-not $projectPathObj) {
    Write-Error "Could not resolve project path from script location: $PSScriptRoot"
    exit 1
}
$project = $projectPathObj.Path

Write-Host "Creating venv at: $project\\.venv"
python -m venv "$project\.venv"

# Activation script path inside the created venv
$activatePath = Join-Path $project '.venv\Scripts\Activate.ps1'
if (Test-Path $activatePath) {
    $marker = "# Added by scripts/setup_venv.ps1"
    $assign = "`$env:RIOT_API_KEY = '$Key'"
    # Avoid adding twice
    $content = Get-Content $activatePath -Raw
    if ($content -notmatch [regex]::Escape($marker)) {
        Add-Content -Path $activatePath -Value "`n$marker`n$assign`n"
        Write-Host "Appended API key assignment to Activate.ps1"
    } else {
        Write-Host "Activate.ps1 already modified; skipping append."
    }
} else {
    Write-Warning "Activate.ps1 not found at $activatePath; the venv may not have been created correctly."
}

# Write .env in project root (this file is in .gitignore by scaffold)
$envPath = Join-Path $project '.env'
New-Item -Path $envPath -ItemType File -Force -Value "RIOT_API_KEY=$Key" | Out-Null
Write-Host "Wrote API key to $envPath"

Write-Host "Installing requirements using the venv python (no activation required)"
$venvPython = Join-Path $project '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    $reqPath = Join-Path $project 'requirements.txt'
    if (Test-Path $reqPath) {
        & $venvPython -m pip install -r $reqPath
    } else {
        Write-Warning "requirements.txt not found at $reqPath; skipping pip install."
    }
} else {
    Write-Warning "Venv python not found at $venvPython; skipping pip install."
}

Write-Host "Done. Remember Riot keys expire every 24 hours; rotate as needed."
