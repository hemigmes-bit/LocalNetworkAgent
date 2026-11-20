Add-Type -AssemblyName System.Speech
$speech = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speech.Rate = 0
$speech.Volume = 100
$speech.SelectVoice("Microsoft Helena Desktop")
$speech.Speak("Víctor, vete a Dormir ya!")