# Acceso al motor Analysis Services local de Power BI Desktop vía ADOMD.NET.
# Uso: powershell -NoProfile -File engine.ps1 -Dll <ruta AdomdClient.dll> -Mode <catalogs|refresh|query> [-Port n] [-Catalog c] [-Dax "..."]
# Salida: JSON en stdout. Errores: JSON {"error": "..."} y código de salida 1.
param(
    [Parameter(Mandatory = $true)][string]$Dll,
    [Parameter(Mandatory = $true)][ValidateSet("catalogs", "refresh", "query")][string]$Mode,
    [int]$Port = 0,
    [string]$Catalog = "",
    [string]$Dax = ""
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
try {
    Add-Type -Path $Dll
    if ($Port -eq 0) {
        $procs = Get-Process msmdsrv -ErrorAction SilentlyContinue
        if (-not $procs) { throw "no hay ningún msmdsrv.exe en ejecución: abre el PBIP en Power BI Desktop" }
        $ports = @()
        foreach ($p in $procs) {
            $ports += Get-NetTCPConnection -OwningProcess $p.Id -State Listen -ErrorAction SilentlyContinue |
                Where-Object LocalAddress -eq "127.0.0.1" | Select-Object -ExpandProperty LocalPort
        }
        if ($ports.Count -ne 1) { throw "se esperaba un motor local y hay $($ports.Count): indica -Port (puertos: $($ports -join ', '))" }
        $Port = $ports[0]
    }
    $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$Port")
    $conn.Open()
    $cats = @($conn.GetSchemaDataSet("DBSCHEMA_CATALOGS", $null).Tables[0].Rows | ForEach-Object { $_.CATALOG_NAME })
    $conn.Close()
    if ($Mode -eq "catalogs") {
        @{ port = $Port; catalogs = $cats } | ConvertTo-Json -Compress
        exit 0
    }
    if (-not $Catalog) {
        if ($cats.Count -ne 1) { throw "hay $($cats.Count) catálogos; indica -Catalog" }
        $Catalog = $cats[0]
    }
    $c = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$Port;Initial Catalog=$Catalog")
    $c.Open()
    $cmd = $c.CreateCommand()
    if ($Mode -eq "refresh") {
        $cmd.CommandText = '{"refresh":{"type":"full","objects":[{"database":"' + $Catalog + '"}]}}'
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        [void]$cmd.ExecuteNonQuery()
        $c.Close()
        @{ port = $Port; catalog = $Catalog; refreshed = $true; ms = $sw.ElapsedMilliseconds } | ConvertTo-Json -Compress
        exit 0
    }
    $cmd.CommandText = $Dax
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $r = $cmd.ExecuteReader()
    $rows = @()
    while ($r.Read()) {
        $row = [ordered]@{}
        for ($i = 0; $i -lt $r.FieldCount; $i++) {
            $name = $r.GetName($i) -replace '^\[|\]$', ''
            $row[$name] = $r[$i]
        }
        $rows += $row
    }
    $r.Close()
    $c.Close()
    @{ port = $Port; catalog = $Catalog; ms = $sw.ElapsedMilliseconds; rows = $rows } | ConvertTo-Json -Compress -Depth 4
    exit 0
}
catch {
    @{ error = $_.Exception.Message } | ConvertTo-Json -Compress
    exit 1
}
