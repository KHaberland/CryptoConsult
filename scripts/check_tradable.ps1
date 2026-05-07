# Diagnostics: imitate dashboard flow.
$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8000/api'
$sid  = [guid]::NewGuid().ToString()
$h = @{ 'X-Session-ID' = $sid; 'Content-Type' = 'application/json; charset=utf-8' }

Write-Host "=== Session: $sid ===" -ForegroundColor Yellow

# 1. Default portfolio (BTC/ETH/BNB/SOL/USDT)
$pBody = @{ name = 'Diag'; initial_amount = 10000; target_years = 5; use_default_assets = $true } | ConvertTo-Json
$p = Invoke-RestMethod -Uri "$base/portfolio/" -Headers $h -Method POST -Body $pBody
Write-Host "[1] Portfolio id=$($p.id), assets:"
$p.assets | Format-Table symbol,name,percentage -AutoSize

# 2. tradable-assets
$ta = Invoke-RestMethod -Uri "$base/portfolio/tradable-assets/" -Headers $h -Method GET
Write-Host "[2] tradable count = $($ta.count)"
$ta.assets | Format-Table symbol,name,current_price,is_recommended,in_portfolio,is_stable -AutoSize

# 3. simulate frontend filters
Write-Host "[3] Filter 'TOP-10' (!in_portfolio && is_recommended):"
$top = $ta.assets | Where-Object { -not $_.in_portfolio -and $_.is_recommended }
$top | Format-Table symbol,name,current_price -AutoSize

Write-Host "[4] Filter 'In Portfolio' (in_portfolio):"
$inP = $ta.assets | Where-Object { $_.in_portfolio }
$inP | Format-Table symbol,name,current_price -AutoSize

Write-Host "[5] Filter 'Stables' (!in_portfolio && !is_recommended && is_stable):"
$st = $ta.assets | Where-Object { -not $_.in_portfolio -and -not $_.is_recommended -and $_.is_stable }
$st | Format-Table symbol,name,current_price -AutoSize
