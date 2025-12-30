def buscar_y_extraer(producto):
    script_temp = "buscador_tech.py"
    
    # Hemos limpiado los reemplazos de texto para evitar el error de sintaxis en el f-string
    codigo_extractor = f"""
import asyncio
from playwright.async_api import async_playwright

async def extraer_tienda(context, url, tienda_nombre, selector_items):
    page = await context.new_page()
    resultados = []
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        items = await page.query_selector_all(selector_items)
        for item in items[:7]:
            texto = await item.inner_text()
            # PRE-PROCESAMIENTO: Limpiamos el texto aquí para no usar backslashes en el f-string
            texto_limpio = texto.replace('\\n', ' ').replace('\\r', ' ').strip()[:400]
            
            link_elem = await item.query_selector('a')
            link = await link_elem.get_attribute('href') if link_elem else ""
            
            if link and link.startswith('/'):
                if "coolbox" in url: link = "https://www.coolbox.pe" + link
                elif "hiraoka" in url: link = "https://hiraoka.com.pe" + link
            
            if len(texto_limpio) > 30:
                # Usamos la variable ya limpia sin expresiones complejas dentro de las llaves
                resultados.append(f"TIENDA: {{tienda_nombre}} | DATOS: {{texto_limpio}} | LINK: {{link}}")
    except Exception as e:
        print(f"Error en {{tienda_nombre}}: {{e}}")
    finally:
        await page.close()
    return resultados

async def run():
    async with async_playwright() as p:
        # Args necesarios para Docker en AWS
        browser = await p.chromium.launch(
            headless=True, 
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        q = "{producto.replace(' ', '+')}"
        
        tareas = [
            extraer_tienda(context, f"https://listado.mercadolibre.com.pe/{{q.replace('+', '-')}}", "Mercado Libre", ".ui-search-result__wrapper"),
            extraer_tienda(context, f"https://www.coolbox.pe/{{q}}?_q={{q}}&map=ft", "Coolbox", ".vtex-search-result-3-x-galleryItem"),
            extraer_tienda(context, f"https://hiraoka.com.pe/catalogsearch/result/?q={{q}}", "Hiraoka", ".product-item-info")
        ]
        
        listas = await asyncio.gather(*tareas)
        total = [item for sublist in listas for item in sublist]
        
        if total:
            print("---SEPARADOR---".join(total))
        await browser.close()

asyncio.run(run())
"""
    with open(script_temp, "w", encoding="utf-8") as f:
        f.write(codigo_extractor)
    
    try:
        # Capturamos la salida para ver errores detallados en los logs de Docker
        resultado = subprocess.check_output(
            [sys.executable, script_temp], 
            text=True, 
            encoding="utf-8", 
            stderr=subprocess.STDOUT
        )
        return resultado.split("---SEPARADOR---") if resultado.strip() else []
    except subprocess.CalledProcessError as e:
        st.error(f"Error interno del buscador: {e.output}")
        return []
    finally:
        if os.path.exists(script_temp):
            os.remove(script_temp)
