param (
    [string]$RootPath = (Get-Location).Path,
    [string]$Prefix = ""
)

$items = Get-ChildItem -LiteralPath $RootPath -Force |
         Where-Object { $_.Name -notin @(".git", "__pycache__", ".venv") }

for ($i = 0; $i -lt $items.Count; $i++) {
    $item = $items[$i]
    $isLast = ($i -eq $items.Count - 1)

    $branch = if ($isLast) { "+-- " } else { "|-- " }
    Write-Output "$Prefix$branch$item"

    if ($item.PSIsContainer) {
        $newPrefix = if ($isLast) { "$Prefix    " } else { "$Prefix|   " }
        & $MyInvocation.MyCommand.Path `
            -RootPath $item.FullName `
            -Prefix $newPrefix
    }
}
