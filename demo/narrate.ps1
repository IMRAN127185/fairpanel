param(
  [Parameter(Mandatory = $true)][string]$TextPath,
  [Parameter(Mandatory = $true)][string]$WavePath
)
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('Microsoft David Desktop')
$synth.Rate = 0
$synth.SetOutputToWaveFile($WavePath)
$synth.Speak((Get-Content -LiteralPath $TextPath -Raw -Encoding UTF8))
$synth.Dispose()
