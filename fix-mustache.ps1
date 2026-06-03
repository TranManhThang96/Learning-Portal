$knownHtmlTags = @(
    'details', '/details', 'summary', '/summary',
    'code', '/code', 'pre', '/pre',
    'span', '/span', 'div', '/div',
    'table', '/table', 'tr', '/tr', 'td', '/td', 'th', '/th',
    'thead', '/thead', 'tbody', '/tbody',
    'a', '/a', 'img', 'br', 'hr',
    'input', 'button', '/button',
    'h1', '/h1', 'h2', '/h2', 'h3', '/h3', 'h4', '/h4', 'h5', '/h5', 'h6', '/h6',
    'p', '/p', 'ul', '/ul', 'ol', '/ol', 'li', '/li',
    'label', '/label', 'form', '/form',
    'section', '/section', 'article', '/article',
    'header', '/header', 'footer', '/footer',
    'nav', '/nav', 'main', '/main', 'aside', '/aside',
    'mark', '/mark', 'small', '/small',
    'strong', '/strong', 'em', '/em', 'b', '/b', 'i', '/i',
    'u', '/u', 's', '/s', 'sub', '/sub', 'sup', '/sup',
    'blockquote', '/blockquote',
    'dl', '/dl', 'dt', '/dt', 'dd', '/dd'
)

$knownPattern = $knownHtmlTags -join '|'

$files = Get-ChildItem -Path "docs/devops" -Recurse -Filter "*.md" | Where-Object { $_.Name -ne 'index.md' }

foreach ($file in $files) {
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
    $original = $content
    $inFence = $false
    $result = [System.Text.StringBuilder]::new()
    $lines = $content -split "`n"

    foreach ($line in $lines) {
        $trimmed = $line.TrimStart()
        if ($trimmed -match '^```') {
            $inFence = -not $inFence
            $null = $result.AppendLine($line)
            continue
        }

        if (-not $inFence) {
            # Split line into inline-code and non-inline-code segments
            # Backtick-delimited inline code: `code`
            $segments = [regex]::Split($line, '(?<=`)(.*?)(?=`)')
            # Actually, let's use a simpler approach:
            # Split on backtick boundaries
            $parts = $line -split '(`[^`]*`)'
            $processedParts = @()

            foreach ($part in $parts) {
                if ($part -match '^`[^`]*`$') {
                    # This is inline code - leave it unchanged
                    $processedParts += $part
                } else {
                    # This is regular text - escape {{ }} and HTML-like tags
                    $p = $part
                    $p = $p -replace '\{\{', '&#123;&#123;' -replace '\}\}', '&#125;&#125;'
                    $p = [regex]::Replace($p, '<(/?)(\w+)([^>]*)>', {
                        param($m)
                        $sl = $m.Groups[1].Value
                        $tn = $m.Groups[2].Value.ToLower()
                        $rs = $m.Groups[3].Value
                        $ft = "$sl$tn$rs"
                        if ($ft -match "^(/)?$knownPattern`$") {
                            return $m.Value
                        }
                        return "&lt;$ft&gt;"
                    })
                    $processedParts += $p
                }
            }

            $newLine = $processedParts -join ''
            $null = $result.AppendLine($newLine)
        } else {
            $null = $result.AppendLine($line)
        }
    }

    $newContent = $result.ToString().TrimEnd("`r`n") + "`n"
    if ($newContent -ne $original) {
        Set-Content -Path $file.FullName -Value $newContent -Encoding UTF8
        Write-Host "Fixed: $($file.FullName)"
    }
}

Write-Host "Done!"
