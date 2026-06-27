<#
.SYNOPSIS
  imgpush用のCloudflareクイックトンネルを起動し、発行された公開URLを
  docker/.env の IMGPUSH_PUBLIC_BASE_URL へ自動反映して pipelines を再起動する。

.DESCRIPTION
  Cloudflareクイックトンネルは起動のたびにランダムなURLを発行するため、
  逆画像検索（reverse_image_search）を実行する前に、毎回
  「新URL取得 → docker/.env 書き換え → pipelines 再起動」という手作業が必要になる。
  本スクリプトはその一連の手順を自動化する。

  実行するとトンネルが起動し、公開URLが docker/.env に反映され、pipelines が再起動される。
  トンネルはこのウィンドウが開いている間だけ有効。終了するには Ctrl+C を押す。

  使い方:
    pwsh ./scripts/start-imgpush-tunnel.ps1

.PARAMETER Port
  imgpushのホスト公開ポート（既定: 5100 = docker/.env の IMGPUSH_PORT）。

.PARAMETER EnvFile
  書き換え対象の .env ファイルパス（既定: リポジトリの docker/.env）。

.PARAMETER CloudflaredPath
  cloudflared.exe のパス。未指定時はPATHと既定インストール先を自動探索する。

.NOTES
  本格的に常時運用する場合は、URLが固定される「名前付きトンネル」への移行を検討すること
  （docs/reverse-image-search-setup.md の手順1-2を参照）。
#>
[CmdletBinding()]
param(
    [int]$Port = 5100,
    [string]$EnvFile = (Join-Path $PSScriptRoot '..\docker\.env'),
    [string]$CloudflaredPath
)

$ErrorActionPreference = 'Stop'

# --- cloudflared.exe の場所を解決 ---
function Resolve-Cloudflared {
    param([string]$Explicit)
    if ($Explicit) {
        if (Test-Path $Explicit) { return $Explicit }
        throw "指定された cloudflared が見つかりません: $Explicit"
    }
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $default = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
    if (Test-Path $default) { return $default }
    throw "cloudflared が見つかりません。'winget install --id Cloudflare.cloudflared' でインストールするか、-CloudflaredPath で実行ファイルを指定してください。"
}

$cloudflared = Resolve-Cloudflared -Explicit $CloudflaredPath

if (-not (Test-Path $EnvFile)) {
    throw "envファイルが見つかりません: $EnvFile"
}
$EnvFile = (Resolve-Path $EnvFile).Path
$dockerDir = Split-Path $EnvFile -Parent

Write-Host "cloudflared : $cloudflared"
Write-Host "env file    : $EnvFile"
Write-Host "tunnel to   : http://localhost:$Port"
Write-Host ""

# --- cloudflared の出力を受け取る一時ログファイル ---
$logOut = Join-Path ([System.IO.Path]::GetTempPath()) "cloudflared-imgpush-$PID.out.log"
$logErr = Join-Path ([System.IO.Path]::GetTempPath()) "cloudflared-imgpush-$PID.err.log"
foreach ($f in @($logOut, $logErr)) { if (Test-Path $f) { Remove-Item $f -Force } }

# --- cloudflared をバックグラウンド起動（出力はログファイルへリダイレクト） ---
$proc = Start-Process -FilePath $cloudflared `
    -ArgumentList @('tunnel', '--url', "http://localhost:$Port") `
    -RedirectStandardOutput $logOut `
    -RedirectStandardError $logErr `
    -NoNewWindow -PassThru

Write-Host "cloudflared を起動しました (PID: $($proc.Id))。公開URLの発行を待機中..." -ForegroundColor Cyan

# --- ログから trycloudflare.com のURLを抽出（最大60秒待機） ---
$pattern = 'https://[a-z0-9-]+\.trycloudflare\.com'
$publicUrl = $null
$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    if ($proc.HasExited) {
        throw "cloudflared が予期せず終了しました (ExitCode: $($proc.ExitCode))。ログを確認してください: $logErr"
    }
    foreach ($f in @($logErr, $logOut)) {
        if (Test-Path $f) {
            $match = Select-String -Path $f -Pattern $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($match) { $publicUrl = $match.Matches[0].Value; break }
        }
    }
    if ($publicUrl) { break }
    Start-Sleep -Milliseconds 500
}

if (-not $publicUrl) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    throw "60秒以内に公開URLを取得できませんでした。ログを確認してください: $logErr"
}

Write-Host "公開URLを取得: $publicUrl" -ForegroundColor Green

# --- docker/.env の IMGPUSH_PUBLIC_BASE_URL を書き換え ---
$content = [System.IO.File]::ReadAllText($EnvFile)
$current = [regex]::Match($content, '(?m)^IMGPUSH_PUBLIC_BASE_URL=(.*)$')
if (-not $current.Success) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    throw "$EnvFile に IMGPUSH_PUBLIC_BASE_URL= の行が見つかりません。"
}

if ($current.Groups[1].Value.Trim() -eq $publicUrl) {
    Write-Host "IMGPUSH_PUBLIC_BASE_URL は既に最新です。.envの更新と pipelines 再起動をスキップします。" -ForegroundColor Yellow
} else {
    $updated = [regex]::Replace($content, '(?m)^IMGPUSH_PUBLIC_BASE_URL=.*$', "IMGPUSH_PUBLIC_BASE_URL=$publicUrl")
    # 既存のUTF-8（BOMなし・日本語コメント含む）を保持して書き戻す
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($EnvFile, $updated, $utf8NoBom)
    Write-Host "docker/.env の IMGPUSH_PUBLIC_BASE_URL を更新しました。" -ForegroundColor Green

    # --- pipelines コンテナを再起動して .env を反映 ---
    Write-Host "pipelines コンテナを再起動中..." -ForegroundColor Cyan
    Push-Location $dockerDir
    try {
        docker compose restart pipelines
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "pipelines の再起動に失敗しました (exit $LASTEXITCODE)。Docker起動後に 'docker compose restart pipelines' を手動実行してください。"
        }
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host " 準備完了。Open WebUI で逆画像検索を実行できます。" -ForegroundColor Green
Write-Host " 公開URL: $publicUrl" -ForegroundColor Green
Write-Host " このウィンドウを閉じる / Ctrl+C でトンネルが切れます。" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""

# --- cloudflared を前面で生かし続ける（終了時にプロセスとログを後始末） ---
try {
    Wait-Process -Id $proc.Id
} finally {
    if (-not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $logOut, $logErr -Force -ErrorAction SilentlyContinue
    Write-Host "トンネルを終了しました。" -ForegroundColor Yellow
}
