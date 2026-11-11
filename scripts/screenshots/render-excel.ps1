# Renders the Summary and Endpoint Test Plan sheets of a workbook to PNG using desktop Excel (Windows only).
# Usage: powershell -File render-excel.ps1 <report.xlsx> <outDir>
# Note: Excel's "copy as picture" uses the clipboard, so whatever was on the clipboard is replaced.
param([string]$Xlsx, [string]$OutDir)
$ErrorActionPreference = "Stop"
$x = $null
try {
  $x = New-Object -ComObject Excel.Application
  $x.Visible = $true
  $x.DisplayAlerts = $false
  $wb = $x.Workbooks.Open($Xlsx, 0, $true)
  $x.CalculateFull()

  function Snap($sheetName, $addr, $file) {
    $ws = $wb.Worksheets.Item($sheetName)
    $ws.Activate()
    $rng = $ws.Range($addr)
    $rng.CopyPicture(1, 2) | Out-Null
    $co = $ws.ChartObjects().Add(5, 5, $rng.Width, $rng.Height)
    $co.Activate()
    $co.Chart.Paste() | Out-Null
    $co.Chart.Export((Join-Path $OutDir $file)) | Out-Null
    $co.Delete() | Out-Null
  }

  # Summary: from the title down to the end of the OWASP table (so both charts are complete)
  $sum = $wb.Worksheets.Item("Summary")
  $stop = 0
  for ($r = 6; $r -le 200; $r++) { if ([string]$sum.Cells.Item($r, 2).Text -like "Test cases by OWASP*") { $stop = $r + 11; break } }  # through the OWASP table: both charts end inside it
  if ($stop -lt 10) { $stop = 75 }
  Snap "Summary" "A1:I$stop" "excel-summary.png"
  Snap "Endpoint Test Plan" "A1:O14" "excel-plan.png"
  $wb.Close($false)
} finally {
  if ($x) { $x.Quit(); [void][System.Runtime.Interopservices.Marshal]::ReleaseComObject($x) }
}
"ok"
