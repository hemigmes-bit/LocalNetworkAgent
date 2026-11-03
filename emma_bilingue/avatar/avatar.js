import * as THREE from 'three';
import { VRM, VRMUtils } from '@pixiv/three-vrm';

/**
 * Emma Avatar - VRM Controller
 * Maneja estados: idle, listening, thinking, speaking
 * Lip-sync con amplitudes de audio TTS
 */
export class EmmaAvatar {
  constructor(canvas) {
    this.canvas = canvas;
    this.vrm = null;
    this.mixer = null;
    this.clock = new THREE.Clock();
    
    // Estados del avatar
    this.currentState = 'idle';
    this.targetState = 'idle';
    this.stateTransitionTime = 0;
    
    // Lip-sync
    this.lipSyncEnabled = true;
    this.audioAmplitude = 0;
    this.targetAmplitude = 0;
    this.vowelBlendshapes = {
      'a': 'aa',  // Abierta
      'e': 'ih',  // Media
      'i': 'ih',  // Cerrada
      'o': 'oh',  // Redonda
      'u': 'ou'   // Muy redonda
    };
    this.currentVowel = 'a';
    
    // Expresiones por estado
    this.stateExpressions = {
      idle: { 
        blink: true, 
        expressions: { happy: 0.1, relaxed: 0.3 },
        lookAt: { x: 0, y: 0, z: -1 }
      },
      listening: { 
        blink: true, 
        expressions: { surprised: 0.2, relaxed: 0.2 },
        lookAt: { x: 0, y: 0, z: -1 }
      },
      thinking: { 
        blink: false, 
        expressions: { angry: 0.1, surprised: 0.1 },
        lookAt: { x: 0.3, y: 0.2, z: -1 }
      },
      speaking: { 
        blink: true, 
        expressions: { happy: 0.2 },
        lookAt: { x: 0, y: 0, z: -1 }
      }
    };
    
    this.initThree();
    this.loadVRM();
    this.animate();
  }
  
  initThree() {
    // Renderer
    this.renderer = new THREE.WebGLRenderer({ 
      canvas: this.canvas, 
      antialias: true, 
      alpha: true 
    });
    this.renderer.setSize(this.canvas.width, this.canvas.height);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.shadowMap.enabled = true;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    
    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x000000);
    
    // Camera
    this.camera = new THREE.PerspectiveCamera(
      45, 
      this.canvas.width / this.canvas.height, 
      0.1, 
      100
    );
    this.camera.position.set(0, 1.5, 3);
    this.camera.lookAt(0, 1.5, 0);
    
    // Lights
    const ambient = new THREE.AmbientLight(0xffffff, 1.0);
    this.scene.add(ambient);
    
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
    dirLight.position.set(5, 10, 7);
    dirLight.castShadow = true;
    this.scene.add(dirLight);
    
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.5);
    fillLight.position.set(-5, 5, -5);
    this.scene.add(fillLight);
    
    // Resize handler
    window.addEventListener('resize', () => this.onResize());
  }
  
  async loadVRM() {
    try {
      // Usar modelo CC0 de 100Avatars (PolygonalMind)
      // Descargar de: https://github.com/PolygonalMind/100Avatars/releases
      // Por ahora usar uno de VTubeMe CC-BY 4.0 (Nova)
      const vrmUrl = 'https://vrm.vtubeme.com/vrm/nova.vrm';
      
      const response = await fetch(vrmUrl);
      const arrayBuffer = await response.arrayBuffer();
      
      this.vrm = await VRM.from(arrayBuffer);
      this.scene.add(this.vrm.scene);
      
      // Configurar animaciones
      this.mixer = new THREE.AnimationMixer(this.vrm.scene);
      
      // Configurar blink automático
      this.setupBlink();
      
      // Configurar lookAt
      this.setupLookAt();
      
      // Configurar spring bones
      this.vrm.springBoneManager?.springBones.forEach(bone => {
        bone.stiffness = 0.5;
        bone.gravityPower = 0.3;
      });
      
      console.log('✅ VRM cargado:', this.vrm.meta?.name || 'Unknown');
      this.setState('idle');
      
    } catch (error) {
      console.error('❌ Error cargando VRM:', error);
      // Fallback: crear avatar simple
      this.createFallbackAvatar();
    }
  }
  
  createFallbackAvatar() {
    // Avatar simple con geometría básica si falla el VRM
    const geometry = new THREE.SphereGeometry(0.3, 32, 32);
    const material = new THREE.MeshStandardMaterial({ color: 0x667eea });
    this.fallbackMesh = new THREE.Mesh(geometry, material);
    this.fallbackMesh.position.y = 1.5;
    this.scene.add(this.fallbackMesh);
    console.log('⚠️ Usando avatar fallback');
  }
  
  setupBlink() {
    if (!this.vrm?.expressionManager) return;
    
    // Blink automático cada 3-5 segundos
    this.blinkInterval = setInterval(() => {
      if (this.stateExpressions[this.currentState]?.blink && this.vrm) {
        this.vrm.expressionManager.setValue('blink', 1.0);
        setTimeout(() => {
          if (this.vrm) this.vrm.expressionManager.setValue('blink', 0.0);
        }, 150);
      }
    }, 3000 + Math.random() * 2000);
  }
  
  setupLookAt() {
    if (!this.vrm?.lookAt) return;
    
    this.vrm.lookAt.target = new THREE.Vector3(0, 1.5, -1);
    this.vrm.lookAt.eyes = {
      pitchRange: { min: -0.5, max: 0.5 },
      yawRange: { min: -0.8, max: 0.8 }
    };
    this.vrm.lookAt.head = {
      pitchRange: { min: -0.3, max: 0.3 },
      yawRange: { min: -0.5, max: 0.5 }
    };
  }
  
  setState(newState) {
    if (!this.stateExpressions[newState]) return;
    
    this.targetState = newState;
    this.stateTransitionTime = this.clock.getElapsedTime();
    
    const expr = this.stateExpressions[newState];
    
    // Aplicar expresiones faciales
    if (this.vrm?.expressionManager) {
      Object.entries(expr.expressions).forEach(([name, value]) => {
        this.vrm.expressionManager.setValue(name, value);
      });
    }
    
    // Actualizar lookAt target
    if (this.vrm?.lookAt && expr.lookAt) {
      this.vrm.lookAt.target.set(expr.lookAt.x, expr.lookAt.y, expr.lookAt.z);
    }
    
    this.currentState = newState;
    console.log(`🎭 Avatar state: ${newState}`);
  }
  
  // Mapear estados del WebSocket (Sesión 7) a estados del avatar
  handleWSMessage(message) {
    switch (message.type) {
      case 'start_session':
        this.setState('idle');
        break;
      case 'transcription_start':
      case 'vad_start':
        this.setState('listening');
        break;
      case 'transcription_complete':
        this.setState('thinking');
        break;
      case 'llm_token':
      case 'llm_streaming':
        this.setState('thinking');
        break;
      case 'llm_complete':
        this.setState('speaking');
        break;
      case 'tts_chunk':
      case 'tts_start':
        this.setState('speaking');
        break;
      case 'tts_complete':
        this.setState('idle');
        break;
      case 'corrections':
      case 'vocabulary':
        // Mantener speaking o volver a idle
        break;
      case 'session_end':
        this.setState('idle');
        break;
    }
  }
  
  // Lip-sync: recibir amplitud de audio (0-1)
  setAudioAmplitude(amplitude) {
    this.targetAmplitude = Math.max(0, Math.min(1, amplitude));
  }
  
  // Lip-sync: recibir vocal actual para blendshapes precisos
  setVowel(vowel) {
    if (this.vowelBlendshapes[vowel]) {
      this.currentVowel = vowel;
    }
  }
  
  updateLipSync(delta) {
    if (!this.vrm?.expressionManager || !this.lipSyncEnabled) return;
    
    // Suavizar amplitud
    this.audioAmplitude += (this.targetAmplitude - this.audioAmplitude) * delta * 10;
    
    // Aplicar blendshapes de vocales basados en amplitud
    const vowelShape = this.vowelBlendshapes[this.currentVowel];
    const jawOpen = this.audioAmplitude * 0.8;
    
    // Jaw open
    this.vrm.expressionManager.setValue('aa', jawOpen * (this.currentVowel === 'a' ? 1 : 0.3));
    this.vrm.expressionManager.setValue('ih', jawOpen * (this.currentVowel === 'e' || this.currentVowel === 'i' ? 1 : 0.2));
    this.vrm.expressionManager.setValue('oh', jawOpen * (this.currentVowel === 'o' ? 1 : 0.2));
    this.vrm.expressionManager.setValue('ou', jawOpen * (this.currentVowel === 'u' ? 1 : 0.2));
    this.vrm.expressionManager.setValue('ee', jawOpen * (this.currentVowel === 'i' ? 0.8 : 0.1));
  }
  
  onResize() {
    this.camera.aspect = this.canvas.width / this.canvas.height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(this.canvas.width, this.canvas.height);
  }
  
  animate() {
    requestAnimationFrame(() => this.animate());
    
    const delta = this.clock.getDelta();
    
    // Update VRM
    if (this.vrm) {
      this.vrm.update(delta);
      this.updateLipSync(delta);
    }
    
    // Update mixer animations
    if (this.mixer) {
      this.mixer.update(delta);
    }
    
    // Fallback animation
    if (this.fallbackMesh) {
      this.fallbackMesh.rotation.y += delta * 0.3;
      this.fallbackMesh.position.y = 1.5 + Math.sin(this.clock.getElapsedTime() * 2) * 0.1;
      
      // Simular boca en fallback
      if (this.currentState === 'speaking') {
        this.fallbackMesh.scale.y = 1 + this.audioAmplitude * 0.3;
      } else {
        this.fallbackMesh.scale.y = 1;
      }
    }
    
    // Render
    this.renderer.render(this.scene, this.camera);
  }
  
  dispose() {
    if (this.blinkInterval) clearInterval(this.blinkInterval);
    if (this.vrm) VRMUtils.removeVRM(this.vrm.scene);
    this.renderer.dispose();
  }
}

// Exportar para uso en pywebview o página standalone
export default EmmaAvatar;