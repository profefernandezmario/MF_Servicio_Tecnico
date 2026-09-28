import json
import os
import shutil
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

import requests


# ============================================================
# CONFIGURACIÓN
# ============================================================

TIMEOUT = 12

# Códigos HTTP que consideraremos como enlace probablemente muerto.
CODIGOS_MUERTOS = {
    404,
    410,
}

# Chrome puede devolver estos códigos aunque la página exista.
# Por eso NO los consideramos automáticamente muertos.
CODIGOS_AMBIGUOS = {
    401,
    403,
    405,
    407,
    408,
    429,
    451,
    500,
    502,
    503,
    504,
}


# ============================================================
# COLORES PARA WINDOWS
# ============================================================

ROJO = "\033[91m"
VERDE = "\033[92m"
AMARILLO = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BLANCO = "\033[97m"
RESET = "\033[0m"


# ============================================================
# LOCALIZAR MARCADORES DE CHROME
# ============================================================

def obtener_archivo_marcadores():

    local_app_data = os.environ.get("LOCALAPPDATA")

    if not local_app_data:
        print("No se pudo localizar LOCALAPPDATA.")
        sys.exit(1)

    base = os.path.join(
        local_app_data,
        "Google",
        "Chrome",
        "User Data"
    )

    posibles = []

    # Perfil principal y perfiles adicionales
    if os.path.exists(base):

        for nombre in os.listdir(base):

            ruta = os.path.join(base, nombre)

            if os.path.isdir(ruta):

                archivo = os.path.join(ruta, "Bookmarks")

                if os.path.isfile(archivo):
                    posibles.append((nombre, archivo))

    if not posibles:
        print(
            f"{ROJO}No se encontró el archivo de marcadores de Chrome.{RESET}"
        )
        print()
        print("Ruta esperada:")
        print(base)
        sys.exit(1)

    if len(posibles) == 1:
        return posibles[0]

    print()
    print(f"{CYAN}Se encontraron varios perfiles de Chrome:{RESET}")
    print()

    for i, (nombre, archivo) in enumerate(posibles, 1):
        print(f"{i}. {nombre}")
        print(f"   {archivo}")

    print()

    while True:
        try:
            opcion = int(input("Selecciona el perfil que quieres analizar: "))

            if 1 <= opcion <= len(posibles):
                return posibles[opcion - 1]

        except ValueError:
            pass

        print("Opción inválida.")


# ============================================================
# LEER MARCADORES
# ============================================================

def leer_marcadores(archivo):

    try:
        with open(archivo, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"{ROJO}Error leyendo marcadores: {e}{RESET}")
        sys.exit(1)


# ============================================================
# RECORRER TODOS LOS MARCADORES
# ============================================================

def obtener_marcadores(nodo, ruta=""):

    resultados = []

    tipo = nodo.get("type")

    if tipo == "url":

        resultados.append({
            "nombre": nodo.get("name", "(sin nombre)"),
            "url": nodo.get("url", ""),
            "ruta": ruta,
            "nodo": nodo
        })

    elif tipo == "folder":

        nombre_carpeta = nodo.get("name", "")

        nueva_ruta = (
            f"{ruta} / {nombre_carpeta}"
            if ruta
            else nombre_carpeta
        )

        for hijo in nodo.get("children", []):
            resultados.extend(
                obtener_marcadores(hijo, nueva_ruta)
            )

    return resultados


def obtener_todos_marcadores(datos):

    todos = []

    roots = datos.get("roots", {})

    for nombre_root, root in roots.items():

        if isinstance(root, dict):

            ruta = root.get("name", nombre_root)

            for hijo in root.get("children", []):

                todos.extend(
                    obtener_marcadores(hijo, ruta)
                )

    return todos


# ============================================================
# COMPROBAR URL
# ============================================================

def comprobar_url(url):

    if not url:
        return "ERROR", "URL vacía"

    # No intentamos comprobar protocolos que no sean HTTP/HTTPS.
    if not url.lower().startswith(("http://", "https://")):
        return "IGNORADO", "No es HTTP/HTTPS"

    try:

        # Primero HEAD, que normalmente es más liviano.
        try:

            respuesta = requests.head(
                url,
                timeout=TIMEOUT,
                allow_redirects=True,
                headers={
                    "User-Agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/154 Safari/537.36"
                }
            )

            codigo = respuesta.status_code

            # Algunos servidores no soportan HEAD.
            if codigo == 405:
                raise Exception("HEAD no permitido")

        except Exception:

            respuesta = requests.get(
                url,
                timeout=TIMEOUT,
                allow_redirects=True,
                stream=True,
                headers={
                    "User-Agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/154 Safari/537.36"
                }
            )

            codigo = respuesta.status_code

        if codigo in CODIGOS_MUERTOS:

            return "MUERTO", f"HTTP {codigo}"

        if codigo in CODIGOS_AMBIGUOS:

            return "REVISAR", f"HTTP {codigo}"

        if 200 <= codigo < 400:

            return "OK", f"HTTP {codigo}"

        if codigo >= 400:

            return "REVISAR", f"HTTP {codigo}"

        return "OK", f"HTTP {codigo}"

    except requests.exceptions.SSLError:

        return "REVISAR", "Error SSL/certificado"

    except requests.exceptions.ConnectionError:

        return "MUERTO", "No se pudo conectar"

    except requests.exceptions.Timeout:

        return "REVISAR", "Timeout"

    except requests.exceptions.RequestException as e:

        return "REVISAR", type(e).__name__

    except Exception as e:

        return "REVISAR", str(e)


# ============================================================
# COPIA DE SEGURIDAD
# ============================================================

def crear_backup(archivo):

    carpeta = os.path.dirname(archivo)

    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup = os.path.join(
        carpeta,
        f"Bookmarks_BACKUP_{fecha}"
    )

    try:

        shutil.copy2(archivo, backup)

        print()
        print(f"{VERDE}Copia de seguridad creada:{RESET}")
        print(backup)
        print()

        return backup

    except Exception as e:

        print(f"{ROJO}No se pudo crear el backup: {e}{RESET}")
        return None


# ============================================================
# ELIMINAR MARCADORES
# ============================================================

def eliminar_nodos(nodo, urls_a_eliminar):

    if not isinstance(nodo, dict):
        return

    if nodo.get("type") == "folder":

        hijos = nodo.get("children", [])

        nuevos_hijos = []

        for hijo in hijos:

            if (
                hijo.get("type") == "url"
                and hijo.get("url") in urls_a_eliminar
            ):
                continue

            eliminar_nodos(hijo, urls_a_eliminar)

            nuevos_hijos.append(hijo)

        nodo["children"] = nuevos_hijos


def eliminar_marcadores(datos, marcadores):

    urls = {
        m["url"]
        for m in marcadores
    }

    roots = datos.get("roots", {})

    for root in roots.values():

        if isinstance(root, dict):
            eliminar_nodos(root, urls)


def guardar_marcadores(archivo, datos):

    temporal = archivo + ".tmp"

    try:

        with open(
            temporal,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                datos,
                f,
                ensure_ascii=False,
                indent=2
            )

        shutil.move(temporal, archivo)

        return True

    except Exception as e:

        print(f"{ROJO}Error guardando marcadores: {e}{RESET}")

        if os.path.exists(temporal):
            os.remove(temporal)

        return False


# ============================================================
# INFORME
# ============================================================

def guardar_informe(resultados, carpeta):

    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")

    archivo = os.path.join(
        carpeta,
        f"informe_marcadores_{fecha}.txt"
    )

    try:

        with open(
            archivo,
            "w",
            encoding="utf-8"
        ) as f:

            f.write("INFORME DE MARCADORES DE CHROME\n")
            f.write("=" * 80 + "\n\n")

            for i, r in enumerate(resultados, 1):

                f.write(
                    f"{i}. {r['nombre']}\n"
                )

                f.write(
                    f"   Carpeta: {r['ruta']}\n"
                )

                f.write(
                    f"   URL: {r['url']}\n"
                )

                f.write(
                    f"   Estado: {r['estado']}\n"
                )

                f.write(
                    f"   Detalle: {r['detalle']}\n\n"
                )

        return archivo

    except Exception as e:

        print(f"{ROJO}No se pudo guardar el informe: {e}{RESET}")
        return None


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    print()
    print(f"{CYAN}=============================================={RESET}")
    print(f"{CYAN}     LIMPIADOR DE MARCADORES DE CHROME{RESET}")
    print(f"{CYAN}=============================================={RESET}")
    print()

    # --------------------------------------------------------
    # Buscar perfil
    # --------------------------------------------------------

    perfil, archivo = obtener_archivo_marcadores()

    print(f"Perfil: {perfil}")
    print(f"Archivo: {archivo}")
    print()

    # --------------------------------------------------------
    # Advertencia sobre Chrome
    # --------------------------------------------------------

    print(
        f"{AMARILLO}IMPORTANTE:{RESET}"
    )

    print(
        "Cierra completamente Google Chrome antes de continuar."
    )

    print(
        "Esto evita que Chrome sobrescriba los cambios."
    )

    print()

    input("Presiona ENTER cuando Chrome esté cerrado...")

    # --------------------------------------------------------
    # Leer
    # --------------------------------------------------------

    datos = leer_marcadores(archivo)

    marcadores = obtener_todos_marcadores(datos)

    print()
    print(
        f"Se encontraron {MAGENTA}{len(marcadores)}"
        f"{RESET} marcadores."
    )
    print()

    if not marcadores:

        print("No hay marcadores para analizar.")
        input("\nPresiona ENTER para salir...")
        return

    # --------------------------------------------------------
    # Backup
    # --------------------------------------------------------

    backup = crear_backup(archivo)

    if not backup:

        print(
            f"{ROJO}No se continuará sin copia de seguridad.{RESET}"
        )

        input("Presiona ENTER para salir...")
        return

    # --------------------------------------------------------
    # Analizar
    # --------------------------------------------------------

    resultados = []

    print(f"{CYAN}Comenzando análisis...{RESET}")
    print()

    for numero, marcador in enumerate(marcadores, 1):

        nombre = marcador["nombre"]
        url = marcador["url"]

        print(
            f"[{numero}/{len(marcadores)}] "
            f"{nombre}"
        )

        print(
            f"    {url}"
        )

        estado, detalle = comprobar_url(url)

        resultado = marcador.copy()

        resultado["estado"] = estado
        resultado["detalle"] = detalle

        resultados.append(resultado)

        if estado == "OK":

            print(
                f"    {VERDE}OK - {detalle}{RESET}"
            )

        elif estado == "MUERTO":

            print(
                f"    {ROJO}MUERTO - {detalle}{RESET}"
            )

        elif estado == "REVISAR":

            print(
                f"    {AMARILLO}REVISAR - {detalle}{RESET}"
            )

        else:

            print(
                f"    {AMARILLO}IGNORADO - {detalle}{RESET}"
            )

        print()

        # Pequeña pausa para no bombardear servidores.
        time.sleep(0.15)

    # --------------------------------------------------------
    # Estadísticas
    # --------------------------------------------------------

    muertos = [
        r for r in resultados
        if r["estado"] == "MUERTO"
    ]

    revisar = [
        r for r in resultados
        if r["estado"] == "REVISAR"
    ]

    correctos = [
        r for r in resultados
        if r["estado"] == "OK"
    ]

    ignorados = [
        r for r in resultados
        if r["estado"] == "IGNORADO"
    ]

    print()
    print(f"{CYAN}=============================================={RESET}")
    print(f"{CYAN}                 RESULTADO{RESET}")
    print(f"{CYAN}=============================================={RESET}")
    print()

    print(f"{VERDE}Activos:{RESET}       {len(correctos)}")
    print(f"{ROJO}Muertos:{RESET}       {len(muertos)}")
    print(f"{AMARILLO}Revisar:{RESET}      {len(revisar)}")
    print(f"{AMARILLO}Ignorados:{RESET}    {len(ignorados)}")
    print()

    # --------------------------------------------------------
    # Mostrar muertos
    # --------------------------------------------------------

    if muertos:

        print(
            f"{ROJO}MARCADORES QUE SE CONSIDERAN MUERTOS:{RESET}"
        )

        print()

        for i, r in enumerate(muertos, 1):

            print(
                f"{i}. {r['nombre']}"
            )

            print(
                f"   {r['url']}"
            )

            print(
                f"   {r['detalle']}"
            )

            print(
                f"   Carpeta: {r['ruta']}"
            )

            print()

    else:

        print(
            f"{VERDE}No se encontraron marcadores claramente muertos.{RESET}"
        )

    # --------------------------------------------------------
    # Informe
    # --------------------------------------------------------

    informe = guardar_informe(
        resultados,
        os.path.dirname(archivo)
    )

    if informe:

        print()
        print(
            f"{CYAN}Informe guardado en:{RESET}"
        )

        print(informe)

    # --------------------------------------------------------
    # Preguntar si eliminar
    # --------------------------------------------------------

    if not muertos:

        print()
        input("Presiona ENTER para salir...")
        return

    print()
    print(
        f"{AMARILLO}ATENCIÓN:{RESET}"
    )

    print(
        "Los siguientes marcadores fueron clasificados "
        "como muertos."
    )

    print(
        "Ya existe una copia de seguridad."
    )

    print()

    respuesta = input(
        "¿Quieres eliminarlos? [S/N]: "
    ).strip().lower()

    if respuesta not in ("s", "si", "sí", "y", "yes"):

        print()
        print(
            f"{VERDE}No se eliminó ningún marcador.{RESET}"
        )

        input("\nPresiona ENTER para salir...")
        return

    # --------------------------------------------------------
    # Eliminar
    # --------------------------------------------------------

    urls_eliminar = {
        r["url"]
        for r in muertos
    }

    eliminar_marcadores(
        datos,
        muertos
    )

    if guardar_marcadores(
        archivo,
        datos
    ):

        print()
        print(
            f"{VERDE}=============================================={RESET}"
        )

        print(
            f"{VERDE}Marcadores eliminados correctamente: "
            f"{len(muertos)}{RESET}"
        )

        print(
            f"{VERDE}=============================================={RESET}"
        )

        print()
        print(
            "Copia de seguridad:"
        )

        print(backup)

    else:

        print()
        print(
            f"{ROJO}No se pudieron guardar los cambios.{RESET}"
        )

        print(
            "La copia de seguridad original permanece intacta."
        )

    print()

    input("Presiona ENTER para salir...")


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":
    main()