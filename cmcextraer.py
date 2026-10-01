import json
import os
import re
import sys
import urllib.request

# ==============================================================================
# REGLAS Y MAPEOS ESPECÍFICOS
# ==============================================================================
# - AI: Artificial Inu, blockchain Robinhood -> asignar contrato
# - LIT: blockchain Ethereum -> asignar nombre Lighter
# - RAY: blockchain Solana -> asignar nombre Raydium
# - UNI: blockchain Ethereum -> asignar nombre Uniswap
# ==============================================================================

REGLAS_ESPECIALES = {
    "AI": {
        "nombre": "Artificial Inu",
        "blockchain": "Robinhood",
        "fallback_contrato": "0x2E8c31162b855A2ffa90F6F8634643Ad6F111e18",
        # Asignar contrato
        "valor_en_lista": "0x2E8c31162b855A2ffa90F6F8634643Ad6F111e18",
    },
    "LIT": {
        "nombre": "Lighter",
        "blockchain": "Ethereum",
        "fallback_contrato": "0x232ce3bd40fcd6f80f3d55a522d03f25df784ee2",
        # Asignar nombre Lighter
        "valor_en_lista": "LIGHTER",
    },
    "RAY": {
        "nombre": "Raydium",
        "blockchain": "Solana",
        "fallback_contrato": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        # Asignar nombre Raydium
        "valor_en_lista": "RAYDIUM",
    },
    "UNI": {
        "nombre": "Uniswap",
        "blockchain": "Ethereum",
        "fallback_contrato": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
        # Asignar nombre Uniswap
        "valor_en_lista": "UNISWAP",
    },
}


def obtener_contrato_cmc(crypto_id: int, blockchain_objetivo: str) -> str | None:
    """Extrae el contrato de la criptomoneda desde la API de detalle de CoinMarketCap según su blockchain."""
    try:
        url = f"https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail?id={crypto_id}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            platforms = data.get("data", {}).get("platforms", [])
            for p in platforms:
                platform_name = p.get("contractPlatform", "").lower()
                if blockchain_objetivo.lower() in platform_name:
                    return p.get("contractAddress")
            if platforms:
                return platforms[0].get("contractAddress")
    except Exception as e:
        print(f"  [Advertencia] No se pudo obtener contrato online para id={crypto_id}: {e}")
    return None


def obtener_datos_watchlist(watchlist_url: str) -> list[dict]:
    """Extrae las criptomonedas de una lista (watchlist) de CoinMarketCap."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    req = urllib.request.Request(watchlist_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8")

    match = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
    if not match:
        raise ValueError(
            f"No se pudo encontrar el bloque __NEXT_DATA__ en {watchlist_url}"
        )

    data = json.loads(match.group(1))
    page_props = data.get("props", {}).get("pageProps", {})
    watchlist = page_props.get("fetchedWatchlist", {})
    crypto_list = watchlist.get("cryptoCurrencies", [])

    return crypto_list


def procesar_activo(crypto: dict) -> str:
    """Procesa el activo aplicando las reglas especiales para:
    AI (Artificial Inu - Robinhood), LIT (Lighter - Ethereum),
    RAY (Raydium - Solana), UNI (Uniswap - Ethereum).
    Para las reglas especiales extrae el contrato como variable valor_en_lista.
    Demás activos: coloca su símbolo estándar.
    """
    symbol = crypto.get("symbol", "").strip()
    name = crypto.get("name", "").strip()
    crypto_id = crypto.get("id")

    # Identificar si coincide con alguna regla especial
    regla_key = None
    if symbol == "AI" or "artificial inu" in name.lower():
        regla_key = "AI"
    elif symbol == "LIT" or "lighter" in name.lower():
        regla_key = "LIT"
    elif symbol == "RAY" or "raydium" in name.lower():
        regla_key = "RAY"
    elif symbol == "UNI" or "uniswap" in name.lower():
        regla_key = "UNI"

    if regla_key:
        regla = REGLAS_ESPECIALES[regla_key]
        contrato = None
        if crypto_id:
            contrato = obtener_contrato_cmc(crypto_id, regla["blockchain"])

        if not contrato:
            contrato = regla["fallback_contrato"]

        regla["contrato_extraido"] = contrato
        valor_en_lista = regla["valor_en_lista"]
        print(f"  -> Regla especial [{regla_key}] ({regla['nombre']} en {regla['blockchain']}): contrato extraído = {contrato} | valor_en_lista = {valor_en_lista}")
        return valor_en_lista

    return symbol


def extraer_lista_activos(watchlist_url: str) -> list[str]:
    """Obtiene la lista procesada para los archivos activos.js."""
    cryptos = obtener_datos_watchlist(watchlist_url)
    items = []
    for crypto in cryptos:
        item = procesar_activo(crypto)
        if item:
            items.append(item)
    return items


def actualizar_archivo_js(
    archivo_js: str, items: list[str], encabezado_lineas: list[str]
) -> None:
    """Actualiza el archivo .js respetando el formato original y su estructura const SYMBOLS_LIST = `...`;"""
    if os.path.exists(archivo_js):
        with open(archivo_js, "r", encoding="utf-8") as f:
            contenido_actual = f.read()

        match_const = re.search(r"const\s+SYMBOLS_LIST\s*=\s*`", contenido_actual)
        if match_const:
            encabezado = contenido_actual[: match_const.end()]
        else:
            encabezado = "\n".join(encabezado_lineas) + "\nconst SYMBOLS_LIST = `"
    else:
        encabezado = "\n".join(encabezado_lineas) + "\nconst SYMBOLS_LIST = `"

    cuerpo = "\n".join(items)
    contenido_final = f"{encabezado}\n{cuerpo}\n`;\n"

    with open(archivo_js, "w", encoding="utf-8") as f:
        f.write(contenido_final)

    print(f"[OK] Archivo {archivo_js} actualizado con {len(items)} registros.")


def main():
    tareas = [
        {
            "url": "https://coinmarketcap.com/watchlist/665296ac3a9fc91e643242c9/",
            "archivo": "activos1.js",
            "encabezado": [
                "// Lista de símbolos o contratos para activos1.html",
                "// Puedes agregar símbolos (ej: BTC, ETH) o direcciones de contrato (0x...):",
            ],
        },
        {
            "url": "https://coinmarketcap.com/watchlist/6a9f0fd1c70da40254917d7d/",
            "archivo": "activos2.js",
            "encabezado": [
                "// Lista de símbolos para activos1.html",
                "// Puedes agregar, quitar o reordenar los símbolos aquí:",
            ],
        },
    ]

    base_dir = os.path.dirname(os.path.abspath(__file__))

    print("==============================================================")
    print(" EXTRACCIÓN DE CRIPTOMONEDAS DE COINMARKETCAP")
    print("  - AI: Artificial Inu (Blockchain Robinhood)")
    print("  - LIT: Lighter (Blockchain Ethereum)")
    print("  - RAY: Raydium (Blockchain Solana)")
    print("  - UNI: Uniswap (Blockchain Ethereum)")
    print("==============================================================")

    for tarea in tareas:
        url = tarea["url"]
        archivo_path = os.path.join(base_dir, tarea["archivo"])
        print(f"\nProcesando watchlist:\n{url}")

        try:
            items = extraer_lista_activos(url)
            print(f"Total procesados ({len(items)}):")
            print(", ".join(items))
            actualizar_archivo_js(archivo_path, items, tarea["encabezado"])
        except Exception as e:
            print(f"Error procesando {url}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
