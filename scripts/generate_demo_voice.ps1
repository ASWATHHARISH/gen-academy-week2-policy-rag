param(
    [string]$Voice = 'Microsoft Zira Desktop',
    [ValidateRange(-10, 10)][int]$Rate = -1,
    [string]$OutputName = 'synthetic_narration_3min.wav'
)

# Run with Windows PowerShell 5.1. Uses only an installed local Windows voice.
# This is synthetic narration, never a recording or imitation of the student.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$projectDirectory = Split-Path -Parent $PSScriptRoot
$narrationPath = Join-Path $projectDirectory 'docs\demo_narration.md'
$outputDirectory = Join-Path $projectDirectory 'artifacts\demo'
if ([IO.Path]::GetFileName($OutputName) -ne $OutputName) {
    throw 'OutputName must be a filename, not a path.'
}
$outputPath = Join-Path $outputDirectory $OutputName
if (Test-Path -LiteralPath $outputPath) {
    throw 'Output already exists; choose a new filename to preserve the prior recording.'
}

$started = $false
$spokenLines = New-Object 'System.Collections.Generic.List[string]'
foreach ($line in [IO.File]::ReadAllLines($narrationPath)) {
    $trimmed = $line.Trim()
    if ($trimmed.StartsWith('[')) { $started = $true; continue }
    if ($started -and $trimmed -and -not $trimmed.StartsWith('#')) {
        $spokenLines.Add($trimmed)
    }
}
$spokenText = $spokenLines -join "`n`n"
$wordCount = [regex]::Matches($spokenText, '\S+').Count
if ($wordCount -lt 350 -or $wordCount -gt 375) {
    throw "Expected 350-375 spoken words, found $wordCount. Inspect the script before rendering."
}

$null = New-Item -ItemType Directory -Path $outputDirectory -Force
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synth.SelectVoice($Voice)
    $synth.Rate = $Rate
    $synth.Volume = 100
    $format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
        22050,
        [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono
    )
    $synth.SetOutputToWaveFile($outputPath, $format)
    $prompt = New-Object System.Speech.Synthesis.PromptBuilder
    foreach ($paragraph in $spokenLines) {
        $prompt.AppendText($paragraph)
        $prompt.AppendBreak([TimeSpan]::FromMilliseconds(450))
    }
    $synth.Speak($prompt)
}
finally {
    $synth.Dispose()
}

$metadata = [ordered]@{
    synthetic_voice = $true
    disclosure = 'Local Windows synthetic narration; not a recording of the student.'
    voice = $Voice
    rate = $Rate
    spoken_words = $wordCount
    source = 'docs/demo_narration.md (preparation note and bracketed stage cues excluded)'
    audio = $OutputName
    sample_rate_hz = 22050
    channels = 1
    bits_per_sample = 16
    network_or_api_calls = 0
    created_utc = [DateTime]::UtcNow.ToString('o')
}
$metadataPath = [IO.Path]::ChangeExtension($outputPath, '.json')
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding UTF8
$metadata | ConvertTo-Json
