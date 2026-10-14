$ErrorActionPreference = 'Stop'
$pbiBin = 'C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop_2.158.1304.0_x64__8wekyb3d8bbwe\bin'
[System.Reflection.Assembly]::LoadFrom((Join-Path $pbiBin 'Microsoft.AnalysisServices.Server.Core.dll')) | Out-Null
[System.Reflection.Assembly]::LoadFrom((Join-Path $pbiBin 'Microsoft.AnalysisServices.Server.Tabular.dll')) | Out-Null
[System.Reflection.Assembly]::LoadFrom((Join-Path $pbiBin 'Microsoft.AnalysisServices.Server.Tabular.Json.dll')) | Out-Null
$modelJson = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'CommerceLens.SemanticModel\model.bim')
$database = [Microsoft.AnalysisServices.Tabular.JsonSerializer]::DeserializeDatabase($modelJson)
Write-Output ('TOM parse PASS: {0} tables, {1} relationships' -f $database.Model.Tables.Count, $database.Model.Relationships.Count)
@{result='PASS'; scope='Microsoft TOM deserialization only; M refresh and DAX execution pending'; tables=$database.Model.Tables.Count; relationships=$database.Model.Relationships.Count} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'validation\tom_result.json')
