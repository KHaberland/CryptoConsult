# PLAN04 end-to-end smoke test via API.
#  1. New session_id, portfolio import (BTC + USDT).
#  2. Contribute-by-units 0.005 BTC at 65000.
#  3. Swap USDT -> BTC with manual correction (~95% of expected).
#  4. Reverse swap BTC -> USDT (no correction).
# Logs key portfolio numbers after each step.

$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8000/api'
$sid  = [guid]::NewGuid().ToString()
$headers = @{ 'X-Session-ID' = $sid; 'Content-Type' = 'application/json; charset=utf-8' }

function Show-Portfolio($title, $value) {
    Write-Host ("----- " + $title + " -----") -ForegroundColor Cyan
    $tv  = [double]$value.total_value
    $inv = [double]$value.initial_value
    $pl  = [double]$value.profit_loss
    $plp = [double]$value.profit_loss_percent
    Write-Host ("invested = {0:N2}, value = {1:N2}, P/L = {2:N2} ({3:N2}%)" -f $inv, $tv, $pl, $plp)
    Write-Host "Assets:"
    foreach ($a in $value.assets) {
        Write-Host ("  {0,-6} units={1,-14} price={2,-10} value={3,-10} pct={4}%" -f `
            $a.symbol, $a.units, $a.current_price, $a.current_value, $a.percentage)
    }
}

function Get-Value() {
    return Invoke-RestMethod -Uri "$base/portfolio/value/" -Headers $headers -Method GET
}

Write-Host "=== Session: $sid ===" -ForegroundColor Yellow

# 1. Import portfolio --------------------------------------------------------
$importBody = @{
    name = 'Smoke PLAN04'
    target_years = 5
    assets = @(
        @{ symbol = 'BTC';  units = 0.05;  purchase_price = 60000 },
        @{ symbol = 'USDT'; units = 1000;  purchase_price = 1 }
    )
} | ConvertTo-Json -Depth 6

$import = Invoke-RestMethod -Uri "$base/portfolio/import/" -Headers $headers -Method POST -Body $importBody
Write-Host ("[1] Portfolio created: id=" + $import.portfolio.id + ", name=" + $import.portfolio.name) -ForegroundColor Green
Show-Portfolio 'After import' (Get-Value)

# 2. Contribute by units: 0.005 BTC at 65000 --------------------------------
$contribBody = @{
    items = @(
        @{ symbol = 'BTC'; units = 0.005; purchase_price = 65000 }
    )
} | ConvertTo-Json -Depth 6

$contrib = Invoke-RestMethod -Uri "$base/portfolio/contribute/" -Headers $headers -Method POST -Body $contribBody
Write-Host ("[2] Contribute-by-units OK. initial_amount=" + $contrib.initial_amount) -ForegroundColor Green
Show-Portfolio 'After contribute-by-units 0.005 BTC' (Get-Value)

# 3. Swap USDT -> BTC with manual correction --------------------------------
$quoteParams = @{ from_symbol = 'USDT'; to_symbol = 'BTC'; from_units = 100 }
$quote = Invoke-RestMethod -Uri "$base/portfolio/swap/quote/" -Headers $headers -Method GET -Body $quoteParams
Write-Host ("[3a] Quote USDT->BTC: from_price=" + $quote.from_price + ", to_price=" + $quote.to_price + ", to_units_expected=" + $quote.to_units_expected) -ForegroundColor Green

$expected = [double]$quote.to_units_expected
$adjusted = [math]::Round($expected * 0.95, 8)
Write-Host ("[3b] Manual correction: expected=" + $expected + ", confirmed=" + $adjusted) -ForegroundColor Yellow

$swapBody = @{
    from_symbol = 'USDT'
    from_units  = 100
    to_symbol   = 'BTC'
    to_units    = $adjusted
    note        = 'smoke fee 5%'
} | ConvertTo-Json -Depth 6

$swap1 = Invoke-RestMethod -Uri "$base/portfolio/swap/" -Headers $headers -Method POST -Body $swapBody
Write-Host ("[3c] Swap done. swap.id=" + $swap1.swap.id + ", fee_usd=" + $swap1.swap.fee_usd) -ForegroundColor Green
Show-Portfolio 'After swap USDT -> BTC' (Get-Value)

# 4. Reverse swap BTC -> USDT -----------------------------------------------
$active = Invoke-RestMethod -Uri "$base/portfolio/active/" -Headers $headers -Method GET
$btcAsset = $active.assets | Where-Object { $_.symbol -eq 'BTC' } | Select-Object -First 1
$btcUnits = [double]$btcAsset.units
$swapBack = [math]::Round($btcUnits * 0.1, 8)
Write-Host ("[4a] Current BTC=" + $btcUnits + ", swapping " + $swapBack + " BTC -> USDT") -ForegroundColor Yellow

$quoteParams2 = @{ from_symbol = 'BTC'; to_symbol = 'USDT'; from_units = $swapBack }
$quote2 = Invoke-RestMethod -Uri "$base/portfolio/swap/quote/" -Headers $headers -Method GET -Body $quoteParams2
Write-Host ("[4b] Quote BTC->USDT: to_units_expected=" + $quote2.to_units_expected) -ForegroundColor Green

$swapBackBody = @{
    from_symbol = 'BTC'
    from_units  = $swapBack
    to_symbol   = 'USDT'
    to_units    = [double]$quote2.to_units_expected
    note        = 'reverse swap'
} | ConvertTo-Json -Depth 6

$swap2 = Invoke-RestMethod -Uri "$base/portfolio/swap/" -Headers $headers -Method POST -Body $swapBackBody
Write-Host ("[4c] Reverse swap done. swap.id=" + $swap2.swap.id + ", fee_usd=" + $swap2.swap.fee_usd) -ForegroundColor Green
Show-Portfolio 'After reverse swap BTC -> USDT' (Get-Value)

Write-Host "=== Smoke test finished ===" -ForegroundColor Yellow
