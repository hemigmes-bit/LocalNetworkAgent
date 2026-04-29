# Solución de Problemas - WoL no funciona

## El LED del adaptador no permanece encendido tras apagar

Esto indica que el adaptador de red no está recibiendo energía en estado de apagado. Sigue estos pasos:

### 1. Verificar en BIOS/UEFI

**CRUCIAL**: WoL debe estar habilitado en la BIOS/UEFI.

- Reinicia CORE0 y entra en BIOS/UEFI (generalmente pulsando Del, F2, o F10 durante el arranque)
- Busca opciones como:
  - **Wake-on-LAN** → Enable
  - **Power On By PCI-E/PCI** → Enable
  - **ERP Ready** → Disable (esto puede deshabilitar WoL)
  - **Deep Sleep** → Disable
  - **EuP 2013** → Disable

### 2. Verificar configuración de energía en Windows

Ejecuta estos comandos en CORE0 como Administrador:

```powershell
# Verificar estado de hibernación
powercfg /a

# Si la hibernación no está deshabilitada, deshabilitarla:
powercfg /h /off

# Verificar configuración de energía del adaptador
Get-NetAdapter | Where-Object Status -eq 'Up' | Get-NetAdapterPowerManagement | Format-Table
```

### 3. Verificar configuración del adaptador de red

En CORE0, ejecuta como Administrador:

```powershell
# Verificar configuración WoL en registro
$regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\*"
Get-ChildItem $regPath | ForEach-Object {
    $props = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
    if ($props.DriverDesc) {
        Write-Host "Adaptador: $($props.DriverDesc)"
        Write-Host "  *WakeOnMagicPacket: $($props.'*WakeOnMagicPacket')"
        Write-Host "  *EnablePowerManagement: $($props.'*EnablePowerManagement')"
        Write-Host "  *WakeOnPattern: $($props.'*WakeOnPattern')"
        Write-Host "  PnPCapabilities: $($props.PnPCapabilities)"
    }
}
```

### 4. Configuración manual en Administrador de Dispositivos

En CORE0:

1. Abre **Administrador de Dispositivos** (devmgmt.msc)
2. Expande **Adaptadores de red**
3. Haz clic derecho en tu adaptador Ethernet → **Propiedades**
4. Pestaña **Administración de energía**:
   - ✅ "Permitir que este dispositivo reactive el equipo"
   - ✅ "Solo permitir que un Magic Packet reactive el equipo" (si está disponible)
5. Pestaña **Opciones avanzadas**:
   - Busca **Wake on Magic Packet** → **Enabled**
   - Busca **Wake on Pattern Match** → **Enabled** (opcional)
   - Busca **Energy Efficient Ethernet** → **Disabled** (puede interferir)

### 5. Verificar fuente de alimentación

- Algunas fuentes de alimentación antiguas no proporcionan suficiente energía en estado de apagado
- Prueba con otra fuente si es posible

### 6. Verificar cable de red y router

- El cable Ethernet debe estar conectado tanto en CORE0 como en el router/switch
- Algunos routers/switches pueden no proporcionar energía suficiente al cable

### 7. Comprobar si es un problema de hardware

- Algunos adaptadores de red (especialmente USB) no soportan WoL correctamente
- Los adaptadores Ethernet integrados suelen funcionar mejor

### 8. Alternativa: Usar estado S3 (Suspender a RAM)

Si WoL no funciona en estado S4/S5 (apagado completo), prueba con suspensión:

```powershell
# Suspender en lugar de apagar
shutdown /h
```

El LED debería permanecer encendido en estado de suspensión.

### 9. Verificar con Diagnose-WoL.ps1

Ejecuta en CORE0 como Administrador:

```powershell
.\Diagnose-WoL.ps1
```

Este script mostrará un diagnóstico completo del estado WoL.

## Comandos útiles para verificar

```powershell
# Verificar si WoL está habilitado en BIOS (requiere WMI)
Get-WmiObject -Namespace root/WMI -Class MSPower_DeviceWakeEnable | Select-Object InstanceName, Enable

# Verificar adaptadores que soportan WoL
Get-WmiObject Win32_NetworkAdapter | Where-Object { $_.NetEnabled -eq $true } | Select-Object Name, MACAddress
```

## Si nada funciona

Si después de todos estos pasos el LED sigue sin encenderse:

1. **Actualiza la BIOS/UEFI** a la última versión
2. **Actualiza los drivers del adaptador de red**
3. **Prueba con otro adaptador de red** (algunos no soportan WoL correctamente)
4. **Considera usar una Raspberry Pi u otro dispositivo** como "WOL proxy" que siempre esté encendido