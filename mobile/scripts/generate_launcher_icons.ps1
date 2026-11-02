$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$appRoot = Split-Path $PSScriptRoot -Parent
$source = [Drawing.Image]::FromFile((Join-Path $appRoot 'assets/images/branding/roadie_logo.png'))
$sizes = @{ mdpi = 48; hdpi = 72; xhdpi = 96; xxhdpi = 144; xxxhdpi = 192 }

try {
    foreach ($density in $sizes.Keys) {
        $size = $sizes[$density]
        $bitmap = New-Object Drawing.Bitmap($size, $size)
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        try {
            # An opaque cream background keeps the supplied transparent logo
            # readable on every launcher background.
            $graphics.Clear([Drawing.Color]::FromArgb(255, 255, 247, 226))
            $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.DrawImage($source, 0, 0, $size, $size)
            $target = Join-Path $appRoot "android/app/src/main/res/mipmap-$density/ic_launcher.png"
            $bitmap.Save($target, [Drawing.Imaging.ImageFormat]::Png)
        }
        finally {
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }
}
finally {
    $source.Dispose()
}
