param(
    [string]$SummonerFile = "seeds.txt",
    [int]$Target = 2000,
    [int]$Workers = 6,
    [string]$MatchIdsOut = "match_ids.txt",
    [string]$Region = "EUW1"
)

Write-Host "Running full pipeline: collect ids -> fetch matches -> prepare features -> train"

# Step 1: collect ids (resumable)
Write-Host "Step 1: Collecting match ids (target=$Target)"
python -m Winrate_Prediction.src.collect_ids_multi --summoner-file $SummonerFile --out $MatchIdsOut --target $Target --workers $Workers --key $env:RIOT_API_KEY

Write-Host "Step 2: Fetch full match JSONs"
python -m Winrate_Prediction.src.collect_multi --match-ids-file $MatchIdsOut --workers $Workers --key $env:RIOT_API_KEY

Write-Host "Step 3: Prepare features"
python -m Winrate_Prediction.src.prepare_features

Write-Host "Step 4: Train model"
python -m Winrate_Prediction.src.train_model --features Winrate_Prediction\data\processed\features.parquet

Write-Host "Pipeline finished"
