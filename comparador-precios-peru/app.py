def buscar_en_la_web(producto):
    script_temp = "buscador_global.py"
    
    # Preparamos la query fuera para evitar problemas de escape de caracteres
    tiendas = 'site:mercadolibre.com.pe OR site:coolbox.pe OR site:hiraoka.com.pe'
    query_final = f'{tiendas} "{producto}"'
    
    codigo_extractor = f"""
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        # Argumentos críticos para correr en AWS/Docker
        browser = await p.chromium.launch(
            headless=True, 
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        search_query = {repr(query_final)}
        url = f"https://www.google.com/search?q={{search_query.replace(' ', '+')}}"
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=60000)
            
            resultados = []
            # Selector de resultados de Google actualizado
            items = await page.query_selector_all('div.g')
            
            for item in items[:10]:
                texto = await item.inner_text()
                # Limpiamos el texto de saltos de linea para no romper el separador
                texto_limpio = " ".join(texto.split())
                
                link_elem = await item.query_selector('a')
                link = await link_elem.get_attribute('href') if link_elem else ""
                
                if link and len(texto_limpio) > 50:
                    resultados.append(f"DATOS: {{texto_limpio}} | LINK: {{link}}")
            
            if resultados:
                print("---SEPARADOR---".join(resultados))
        except Exception as e:
            print(f"ERROR_BUSQUEDA: {{e}}")
        finally:
            await browser.close()

asyncio.run(run())
"""
    with open(script_temp, "w", encoding="utf-8") as f:
        f.write(codigo_extractor)
    
    try:
        # Usamos stderr=subprocess.STDOUT para que si falla, veamos el error real en Streamlit
        resultado = subprocess.check_output(
            [sys.executable, script_temp], 
            text=True, 
            encoding="utf-8",
            stderr=subprocess.STDOUT
        )
        return resultado.split("---SEPARADOR---") if "---SEPARADOR---" in resultado else []
    except subprocess.CalledProcessError as e:
        st.error(f"Error detallado del script: {e.output}")
        return []
    finally:
        if os.path.exists(script_temp):
            os.remove(script_temp)
