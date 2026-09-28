#requires -Version 5.1

# ============================================================
# 1. VERIFICACIÓN Y AUTO-ELEVACIÓN DE ADMINISTRADOR (NUEVO)
# ============================================================
$EsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $EsAdmin) {
    Write-Host "Solicitando privilegios de Administrador..." -ForegroundColor Yellow
    
    # Determinar ruta del script
    $RutaScript = $MyInvocation.MyCommand.Definition
    if ([string]::IsNullOrEmpty($RutaScript)) {
        $RutaScript = $PSCommandPath
    }

    try {
        Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$RutaScript`"" -Verb RunAs
    } catch {
        Write-Host "ERROR: No se pudieron obtener privilegios de Administrador." -ForegroundColor Red
        Read-Host "Presione ENTER para salir"
    }
    exit
}

# ============================================================
# 2. CONFIGURACIÓN DE CODIFICACIÓN Y ENTORNO
# ============================================================
Set-ExecutionPolicy -Scope Process Bypass -Force

[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Clear-Host

# ============================================================
# 3. CONFIGURACIÓN DE RUTAS Y PARÁMETROS
# ============================================================
$Repositorio = "C:\Repositorio-WinGet"
$CarpetaInstaladores = Join-Path $Repositorio "Instaladores"
$CarpetaListas       = Join-Path $Repositorio "Listas"
$CarpetaLogs         = Join-Path $Repositorio "Logs"

$MaxReintentos = 3

# Crear carpetas si no existen
$Carpetas = @($Repositorio, $CarpetaInstaladores, $CarpetaListas, $CarpetaLogs)
foreach ($Carpeta in $Carpetas) {
    if (-not (Test-Path -LiteralPath $Carpeta)) {
        New-Item -ItemType Directory -Path $Carpeta -Force | Out-Null
    }
}

# ============================================================
# 4. CATÁLOGO DE APLICACIONES
# ============================================================
$Aplicaciones = @(
    # Navegadores
    [PSCustomObject]@{ Categoria = "Navegadores"; Nombre = "Google Chrome"; ID = "Google.Chrome"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Navegadores"; Nombre = "Mozilla Firefox"; ID = "Mozilla.Firefox"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Navegadores"; Nombre = "Brave"; ID = "Brave.Brave"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Navegadores"; Nombre = "Microsoft Edge"; ID = "Microsoft.Edge"; Fuente = "winget" }

    # Multimedia
    [PSCustomObject]@{ Categoria = "Multimedia"; Nombre = "VLC"; ID = "VideoLAN.VLC"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Multimedia"; Nombre = "Audacity"; ID = "Audacity.Audacity"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Multimedia"; Nombre = "HandBrake"; ID = "HandBrake.HandBrake"; Fuente = "winget" }

    # Compresión
    [PSCustomObject]@{ Categoria = "Compresion"; Nombre = "7-Zip"; ID = "7zip.7zip"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Compresion"; Nombre = "WinRAR"; ID = "RARLab.WinRAR"; Fuente = "winget" }

    # Desarrollo
    [PSCustomObject]@{ Categoria = "Desarrollo"; Nombre = "Visual Studio Code"; ID = "Microsoft.VisualStudioCode"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Desarrollo"; Nombre = "Git"; ID = "Git.Git"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Desarrollo"; Nombre = "Python"; ID = "Python.Python.3.13"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Desarrollo"; Nombre = "Notepad++"; ID = "Notepad++.Notepad++"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Desarrollo"; Nombre = "VSCodium"; ID = "VSCodium.VSCodium"; Fuente = "winget" }

    # Oficina
    [PSCustomObject]@{ Categoria = "Oficina"; Nombre = "LibreOffice"; ID = "TheDocumentFoundation.LibreOffice"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Oficina"; Nombre = "SumatraPDF"; ID = "SumatraPDF.SumatraPDF"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Oficina"; Nombre = "Foxit PDF Reader"; ID = "Foxit.FoxitReader"; Fuente = "winget" }

    # Utilidades
    [PSCustomObject]@{ Categoria = "Utilidades"; Nombre = "Everything"; ID = "voidtools.Everything"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Utilidades"; Nombre = "PowerToys"; ID = "Microsoft.PowerToys"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Utilidades"; Nombre = "XnView"; ID = "XnSoft.XnView.Classic"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Utilidades"; Nombre = "CCleaner"; ID = "Piriform.CCleaner.Slim"; Fuente = "winget" }

    # Soporte Técnico (WinGet)
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "CrystalDiskInfo"; ID = "CrystalDewWorld.CrystalDiskInfo"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "HWiNFO"; ID = "REALiX.HWiNFO"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "Rufus"; ID = "Rufus.Rufus"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "Ventoy"; ID = "Ventoy.Ventoy"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "Winhance"; ID = "memstechtips.Winhance"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "Bulk Crap Uninstaller"; ID = "Klocman.BulkCrapUninstaller"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "CPUID CPU-Z"; ID = "CPUID.CPU-Z"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "CPUID HWMonitor"; ID = "CPUID.HWMonitor"; Fuente = "winget" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "CPUAlert"; ID = "Smartbooth.CPUAlert"; Fuente = "winget" }

    # Soporte Técnico (Microsoft Store)
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "CPU-Info"; ID = "9PHXQ0F4KNBL"; Fuente = "msstore" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "CPU Plus"; ID = "9P5G6W4FPNS2"; Fuente = "msstore" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "CPU Display"; ID = "9NFV3CF648KX"; Fuente = "msstore" }
    [PSCustomObject]@{ Categoria = "Soporte"; Nombre = "Wise Registry Cleaner"; ID = "XPDLS1XBTXVPP4"; Fuente = "msstore" }
)

# ============================================================
# 5. FUNCIONES MEJORADAS
# ============================================================

function Mostrar-Titulo {
    Clear-Host
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "               REPOSITORIO DE INSTALADORES WinGet" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Comprobar-WinGet {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host ""
        Write-Host "ERROR: WinGet no está disponible en este sistema." -ForegroundColor Red
        Write-Host "Instale o actualice 'App Installer' desde la Microsoft Store." -ForegroundColor Yellow
        Write-Host ""
        Read-Host "Presione ENTER para salir"
        exit
    }
}

function Seleccionar-Arquitectura {
    Mostrar-Titulo
    Write-Host "SELECCIONE LA ARQUITECTURA DE LOS INSTALADORES:" -ForegroundColor Cyan
    Write-Host "  1. x64  (64 bits - Recomendado para la mayoría de sistemas)"
    Write-Host "  2. x86  (32 bits)"
    Write-Host "  3. arm64 (Procesadores ARM / Snapdragon)"
    Write-Host ""

    $Opcion = Read-Host "Seleccione una opción [1-3] (Por defecto: 1)"

    switch ($Opcion.Trim()) {
        "2"     { return "x86" }
        "3"     { return "arm64" }
        default { return "x64" }
    }
}

function Seleccionar-AplicacionesGrid {
    # Verificar si el entorno soporta Out-GridView
    $TieneGUI = $true
    if ($env:OS -ne "Windows_NT" -or (Get-Command Out-GridView -ErrorAction SilentlyContinue) -eq $null) {
        $TieneGUI = $false
    }

    if ($TieneGUI) {
        try {
            Mostrar-Titulo
            Write-Host "Abriendo ventana de selección interactiva de aplicaciones..." -ForegroundColor Cyan
            
            $Resultado = $Aplicaciones | Out-GridView `
                -Title "Seleccione los programas a procesar (CTRL o SHIFT para múltiple)" `
                -OutputMode Multiple

            if ($Resultado) {
                return @($Resultado)
            } else {
                return $null
            }
        }
        catch {
            $TieneGUI = $false
        }
    }

    # Respaldo por Consola
    Mostrar-Titulo
    Write-Host "SELECCIÓN MÚLTIPLE POR CONSOLA`n" -ForegroundColor Cyan
    for ($i = 0; $i -lt $Aplicaciones.Count; $i++) {
        Write-Host (" [{0,2}] [{1,-11}] {2}" -f ($i + 1), $Aplicaciones[$i].Categoria, $Aplicaciones[$i].Nombre)
    }
    Write-Host ""
    Write-Host "Ingrese los números separados por coma (e.g. 1,3,5) o presione ENTER para procesar TODAS:"
    $Entrada = Read-Host "Selección"

    if ([string]::IsNullOrWhiteSpace($Entrada)) {
        return @($Aplicaciones)
    }

    $Indices = $Entrada.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -match "^\d+$" }
    $SeleccionadasConsola = @()

    foreach ($Idx in $Indices) {
        $IndexNum = [int]$Idx - 1
        if ($IndexNum -ge 0 -and $IndexNum -lt $Aplicaciones.Count) {
            $SeleccionadasConsola += $Aplicaciones[$IndexNum]
        }
    }
    return @($SeleccionadasConsola)
}

function Obtener-Instalados {
    Write-Host "`nConsultando aplicaciones instaladas en el sistema..." -ForegroundColor Cyan
    $SalidaWinget = winget list 2>$null | Out-String
    $Instalados = @{}

    foreach ($App in $Aplicaciones) {
        # Corrección Regex: Busca el ID delimitado por espacios/tabulaciones para evitar falsos positivos
        $PatronID = "(?i)(^|\s)" + [regex]::Escape($App.ID) + "(\s|$)"
        if ($SalidaWinget -match $PatronID) {
            $Instalados[$App.ID] = $true
        }
    }
    return $Instalados
}

function Obtener-VersionRemota {
    param(
        [string]$ID,
        [string]$Fuente
    )
    
    $Info = winget show --id $ID --exact --source $Fuente 2>$null | Out-String
    
    # Corrección Regex: Sombra multilenguaje para "Versión:" o "Version:"
    if ($Info -match "(?i)(Versi[oó]n|Version):\s+([^\r\n]+)") {
        return $Matches[2].Trim()
    }
    return $null
}

function Descargar-Paquete {
    param(
        [Parameter(Mandatory = $true)] $Aplicacion,
        [Parameter(Mandatory = $true)] [string]$Arquitectura
    )

    Write-Host ""
    Write-Host "------------------------------------------------------------"
    Write-Host "Procesando: $($Aplicacion.Nombre)"
    Write-Host "ID: $($Aplicacion.ID) | Fuente: $($Aplicacion.Fuente) | Arq: $Arquitectura"
    Write-Host "------------------------------------------------------------"

    $Destino = Join-Path $CarpetaInstaladores $Aplicacion.Nombre

    if (-not (Test-Path -LiteralPath $Destino)) {
        New-Item -ItemType Directory -Path $Destino -Force | Out-Null
    }

    $ArchivoVersion = Join-Path $Destino ".version"
    $VersionLocal = $null

    if (Test-Path -LiteralPath $ArchivoVersion) {
        $VersionLocal = (Get-Content -Path $ArchivoVersion -Encoding UTF8 -ErrorAction SilentlyContinue).Trim()
    }

    $ArchivosExistentes = @(Get-ChildItem -LiteralPath $Destino -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne ".version" })

    Write-Host "Consultando versión remota disponible..." -ForegroundColor Cyan
    $VersionRemota = Obtener-VersionRemota -ID $Aplicacion.ID -Fuente $Aplicacion.Fuente

    if ($ArchivosExistentes.Count -gt 0 -and $VersionLocal) {
        if ($VersionRemota -and $VersionLocal -eq $VersionRemota) {
            Write-Host "El instalador ya existe en la versión más reciente ($VersionLocal)." -ForegroundColor Green
            Write-Host "Se omite la descarga." -ForegroundColor Green
            return $true
        } elseif ($VersionRemota) {
            Write-Host "Nueva versión disponible: $VersionRemota (Versión local previa: $VersionLocal)." -ForegroundColor Yellow
            Write-Host "Limpiando archivos antiguos..." -ForegroundColor Yellow
            Get-ChildItem -LiteralPath $Destino -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
        }
    }

    $IntentoActual = 1
    $ExitoDescarga = $false

    while ($IntentoActual -le $MaxReintentos -and -not $ExitoDescarga) {
        Write-Host "`nIniciando descarga (Intento $IntentoActual de $MaxReintentos)..." -ForegroundColor Cyan

        if ($Aplicacion.Fuente -eq "msstore") {
            & winget download --id $Aplicacion.ID --exact --source msstore --architecture $Arquitectura --platform Windows.Desktop --skip-license --download-directory $Destino --accept-source-agreements --accept-package-agreements --verbose-logs
        } else {
            & winget download --id $Aplicacion.ID --exact --source winget --architecture $Arquitectura --download-directory $Destino --accept-source-agreements --accept-package-agreements --verbose-logs
        }

        $ArchivosActuales = @(Get-ChildItem -LiteralPath $Destino -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne ".version" })

        if ($ArchivosActuales.Count -gt 0) {
            $ExitoDescarga = $true
        } else {
            Write-Host "Intento $IntentoActual fallido." -ForegroundColor Red
            if ($IntentoActual -lt $MaxReintentos) {
                Write-Host "Reintentando en 3 segundos..." -ForegroundColor Yellow
                Start-Sleep -Seconds 3
            }
            $IntentoActual++
        }
    }

    if ($ExitoDescarga) {
        $VersionAGuardar = if ($VersionRemota) { $VersionRemota } else { "Descargado-$(Get-Date -Format 'yyyyMMdd')" }
        $VersionAGuardar | Set-Content -Path $ArchivoVersion -Encoding UTF8 -Force

        Write-Host "`nDESCARGA CORRECTA" -ForegroundColor Green
        Write-Host "Archivos guardados en: $Destino (Versión: $VersionAGuardar)" -ForegroundColor Green
        return $true
    } else {
        Write-Host "`nERROR EN LA DESCARGA: Se superó el número máximo de reintentos." -ForegroundColor Red
        return $false
    }
}

function Crear-Lista {
    param([Parameter(Mandatory = $true)] $AplicacionesLista)

    $Archivo = Join-Path $CarpetaListas "paquetes-seleccionados.txt"
    $AplicacionesLista.ID | Set-Content -Path $Archivo -Encoding UTF8
    Write-Host "`nLista de paquetes guardada en: $Archivo" -ForegroundColor Cyan
}

# ============================================================
# 6. EJECUCIÓN PRINCIPAL
# ============================================================

Comprobar-WinGet

# 1. Seleccionar Arquitectura
$ArquitecturaSeleccionada = Seleccionar-Arquitectura

# 2. Seleccionar Aplicaciones
$Seleccionadas = @(Seleccionar-AplicacionesGrid)

if ($null -eq $Seleccionadas -or $Seleccionadas.Count -eq 0) {
    Write-Host "`nNo se seleccionó ninguna aplicación. Saliendo..." -ForegroundColor Yellow
    exit
}

# 3. Confirmación de Selección (Corrección de sintaxis variable `${...}`)
Mostrar-Titulo
Write-Host "APLICACIONES SELECCIONADAS ($($Seleccionadas.Count)) | ARQUITECTURA: ${ArquitecturaSeleccionada}:`n" -ForegroundColor Cyan
foreach ($App in $Seleccionadas) {
    Write-Host "  * [$($App.Categoria)] $($App.Nombre) ($($App.ID))"
}

Write-Host ""
$Confirmar = Read-Host "¿Desea continuar con el análisis? [S/N]"

if ($Confirmar.Trim() -notmatch "^[Ss]$") {
    Write-Host "`nOperación cancelada por el usuario." -ForegroundColor Yellow
    exit
}

# 4. Auditoría de Instalación
$Instalados = Obtener-Instalados
$Faltantes = @()

foreach ($App in $Seleccionadas) {
    if ($Instalados.ContainsKey($App.ID)) {
        $App | Add-Member -NotePropertyName Estado -NotePropertyValue "INSTALADO" -Force
    } else {
        $App | Add-Member -NotePropertyName Estado -NotePropertyValue "FALTANTE" -Force
        $Faltantes += $App
    }
}

Mostrar-Titulo
Write-Host "AUDITORÍA DEL EQUIPO:`n" -ForegroundColor Cyan

foreach ($App in $Seleccionadas) {
    if ($App.Estado -eq "INSTALADO") {
        Write-Host "  [OK]    $($App.Nombre)" -ForegroundColor Green
    } else {
        Write-Host "  [FALTA] $($App.Nombre)" -ForegroundColor Yellow
    }
}

$CantidadInstaladas = ($Seleccionadas | Where-Object { $_.Estado -eq "INSTALADO" }).Count

Write-Host "`n------------------------------------------------------------"
Write-Host "Aplicaciones analizadas : $($Seleccionadas.Count)"
Write-Host "Ya instaladas           : $CantidadInstaladas"
Write-Host "Faltantes               : $($Faltantes.Count)"
Write-Host "Arquitectura elegida    : $ArquitecturaSeleccionada"
Write-Host "------------------------------------------------------------"

if ($Faltantes.Count -eq 0) {
    Write-Host "`nTodas las aplicaciones seleccionadas ya están instaladas." -ForegroundColor Green
    Read-Host "`nPresione ENTER para salir"
    exit
}

# 5. Generación de Lista y Confirmación
Crear-Lista -AplicacionesLista $Faltantes

Write-Host "`nPAQUETES A DESCARGAR:`n" -ForegroundColor Cyan
foreach ($App in $Faltantes) {
    Write-Host "  * $($App.Nombre)"
}

Write-Host "`nDestino final:"
Write-Host "  $CarpetaInstaladores" -ForegroundColor Cyan

Write-Host ""
$ConfirmarDescarga = Read-Host "¿Desea iniciar la descarga de instaladores? [S/N]"

if ($ConfirmarDescarga.Trim() -notmatch "^[Ss]$") {
    Write-Host "`nDescarga cancelada." -ForegroundColor Yellow
    exit
}

# 6. Proceso de Descarga
$Correctos = 0
$Errores = 0
$Inicio = Get-Date

foreach ($App in $Faltantes) {
    $Resultado = Descargar-Paquete -Aplicacion $App -Arquitectura $ArquitecturaSeleccionada
    if ($Resultado) {
        $Correctos++
    } else {
        $Errores++
    }
}

$Fin = Get-Date
$Duracion = $Fin - $Inicio

# 7. Generación de Log
$NombreLog = "descarga-" + (Get-Date -Format "yyyy-MM-dd-HHmmss") + ".txt"
$Log = Join-Path $CarpetaLogs $NombreLog

$PaquetesLog = $Faltantes | ForEach-Object { "$($_.Nombre) | $($_.ID)" }

$ContenidoLog = @"
REPOSITORIO WinGet
==================

Fecha:        $(Get-Date)
Equipo:       $env:COMPUTERNAME
Usuario:      $env:USERNAME
Arquitectura: $ArquitecturaSeleccionada

Aplicaciones analizadas: $($Seleccionadas.Count)
Ya instaladas:            $CantidadInstaladas
Faltantes:                $($Faltantes.Count)

Descargas procesadas:     $Correctos
Errores:                  $Errores

Duración:                 $($Duracion.ToString())
Destino:                  $CarpetaInstaladores

PAQUETES FALTANTES:
------------------
$($PaquetesLog -join "`r`n")
"@

$ContenidoLog | Set-Content -Path $Log -Encoding UTF8

# 8. Resumen Final
Mostrar-Titulo
Write-Host "RESULTADO DEL PROCESO:`n" -ForegroundColor Cyan
Write-Host "  Aplicaciones analizadas : $($Seleccionadas.Count)"
Write-Host "  Ya instaladas           : $CantidadInstaladas"
Write-Host "  Faltantes               : $($Faltantes.Count)"
Write-Host ""
Write-Host "  Descargas procesadas    : $Correctos" -ForegroundColor Green

if ($Errores -gt 0) {
    Write-Host "  Errores                 : $Errores" -ForegroundColor Red
} else {
    Write-Host "  Errores                 : $Errores" -ForegroundColor Green
}

Write-Host "`n------------------------------------------------------------"
Write-Host "Ubicación del Registro:"
Write-Host "  $Log" -ForegroundColor Cyan
Write-Host "============================================================`n"

Read-Host "Presione ENTER para finalizar"