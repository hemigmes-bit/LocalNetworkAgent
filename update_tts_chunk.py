with open(r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue\server\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace send_tts_chunk method
old = '''    async def send_tts_chunk(self, chunk_b64: str):
        msg = {
            "type": "tts_chunk",
            "audio_base64": chunk_b64,
            "sample_rate": 24000,
            "format": "pcm",
            "is_final": False,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)'''

new = '''    async def send_tts_chunk(self, chunk_b64: str):
        # Calculate amplitude and vowel for lip-sync
        import base64
        import numpy as np
        
        # Decode base64 audio
        audio_bytes = base64.b64decode(chunk_b64)
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        # RMS amplitude (0-1)
        rms = np.sqrt(np.mean(audio_array**2))
        amplitude = min(1.0, rms * 10)  # Scale for visibility
        
        # Simple vowel estimation from spectral centroid
        vowel = 'a'  # default
        if len(audio_array) > 100:
            # Very simple heuristic: check energy in different freq bands
            fft = np.fft.rfft(audio_array)
            freqs = np.fft.rfftfreq(len(audio_array), 1/24000)
            magnitude = np.abs(fft)
            
            # F1/F2 regions for vowels (rough approximation)
            f1_energy = np.sum(magnitude[(freqs > 300) & (freqs < 1000)])
            f2_energy = np.sum(magnitude[(freqs > 1000) & (freqs < 3000)])
            
            if f1_energy > f2_energy * 2:
                vowel = 'a'  # low F1, low F2
            elif f2_energy > f1_energy * 2:
                vowel = 'i'  # high F2
            elif f1_energy > f2_energy:
                vowel = 'o'  # mid F1, low F2
            else:
                vowel = 'e'  # mid
        
        msg = {
            "type": "tts_chunk",
            "audio_base64": chunk_b64,
            "sample_rate": 24000,
            "format": "pcm",
            "is_final": False,
            "amplitude": float(amplitude),
            "vowel": vowel,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)'''

content = content.replace(old, new)

with open(r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue\server\main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated send_tts_chunk')