import streamlit as st
import subprocess
import sys
import os
import json
from groq import Groq

# --- CONFIGURACIÓN ESTATICA ---
API_KEY_DIRECTA = "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"

st.set_page_config(page_title="Comparador Tech Perú", page_icon="⚙️", layout="wide")
st.title("⚙️ Comparador de productos")
st.markdown("Buscando en tiendas locales con IA.")

def buscar_y_extraer(producto):
    script_temp = "buscador_tech.py"
    
    codigo_extractor = f"""
import asyncio
from playwright.async_api import async_playwright

async def extraer_tienda(context, url, tienda_nombre, selector_items):
    page = await context.new_page()
    # Simular comportamiento humano moviendo el mouse o scroll
    resultados = []
    try:
        await page.goto(url, wait_until='networkidle', timeout=45000)
        await page.wait_for_timeout(4000) 
        
        items = await page.query_selector_all(selector_items)
        print(f"DEBUG: {{tienda_nombre}} encontro {{len(items)}} items")
        
        for item in items[:10]:
            try:
                texto = await item.inner_text()
                # Limpieza agresiva de saltos de linea
                texto_limpio = " ".join(texto.split())[:500]
                
                link_elem = await item.query_selector('a')
                link = await link_elem.get_attribute('href') if link_elem else ""
                
                if link and link.startswith('/'):
                    if "coolbox" in url: link = "https://www.coolbox.pe" + link
                    elif "hiraoka" in url: link = "https://hiraoka.com.pe" + link
                
                if len(texto_limpio) > 50:
                    resultados.append(f"TIENDA: {{tienda_nombre}} | DATOS: {{texto_limpio}} | LINK: {{link}}")
            except:
                continue
    except Exception as e:
        print(f"Error en {{tienda_nombre}}: {{e}}")
    finally:
        await page.close()
    return resultados

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, 
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        # User agent actualizado y headers de lenguaje para evitar bloqueos
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            extra_http_headers={{"Accept-Language": "es-PE,es;q=0.9"}}
        )
        
        q = "{producto.replace(' ', '+')}"
        
        tareas = [
            # Mercado Libre: Selector mas robusto para la nueva version
            extraer_tienda(context, f"https://listado.mercadolibre.com.pe/{{q.replace('+', '-')}}", "Mercado Libre", "li.ui-search-layout__item"),
            
            # Coolbox: Selector actualizado a su contenedor de productos principal
            extraer_tienda(context, f"https://www.coolbox.pe/{{q}}?_q={{q}}&map=ft", "Coolbox", "div.vtex-search-result-3-x-galleryItem"),
            
            # Hiraoka
            extraer_tienda(context, f"https://hiraoka.com.pe/catalogsearch/result/?q={{q}}", "Hiraoka", ".product-item-info")
        ]
        
        listas = await asyncio.gather(*tareas)
        total = [item for sublist in listas for item in sublist]
        
        if total:
            # Imprimimos para que subprocess lo capture
            print("---SEPARADOR---".join(total))
        await browser.close()

asyncio.run(run())
"""
    with open(script_temp, "w", encoding="utf-8") as f:
        f.write(codigo_extractor)
    
    try:
        resultado = subprocess.check_output([sys.executable, script_temp], text=True, encoding="utf-8", errors="replace")
        return resultado.split("---SEPARADOR---") if resultado.strip() else []
    except Exception as e:
        print(f"Error en subprocess: {e}")
        return []
    finally:
        if os.path.exists(script_temp):
            os.remove(script_temp)

def comparar_con_ia(lista_productos, key):
    client = Groq(api_key=key)
    # Prompt optimizado para que no ignore ninguna tienda
    prompt = f"""
    Analiza estos datos de tiendas en Perú. Crea un JSON con la llave "productos".
    CADA producto debe tener: "tienda", "nombre", "precio" (solo numero), "enlace".
    No inventes datos. Si no hay precio, pon null.
    
    DATOS:
    {chr(10).join(lista_productos)}
    """
    
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )
    return completion.choices[0].message.content

producto_buscado = st.text_input("¿Qué producto buscas?", placeholder="Ej: Laptop, Smartwatch...")

if st.button("🔍 Buscar"):
    if producto_buscado:
        try:
            with st.spinner("Extrayendo datos en tiempo real..."):
                bloques = buscar_y_extraer(producto_buscado)
            
            if bloques:
                with st.spinner("IA comparando precios..."):
                    respuesta_json = comparar_con_ia(bloques, API_KEY_DIRECTA)
                    datos = json.loads(respuesta_json)
                    lista = datos.get("productos", [])
                    
                    if lista:
                        st.subheader(f"📊 Resultados encontrados")
                        st.dataframe(
                            lista,
                            column_config={
                                "enlace": st.column_config.LinkColumn("Ver Oferta"),
                                "precio": st.column_config.NumberColumn("Soles", format="S/. %d"),
                                "nombre": st.column_config.TextColumn("Producto", width="large")
                            },
                            hide_index=True,
                            width="stretch"
                        )
                    else:
                        st.warning("La IA no pudo procesar los datos. Intenta nuevamente.")
            else:
                st.error("Las tiendas (ML y Coolbox) bloquearon la conexión o no hay resultados.")
        except Exception as e:
            st.error(f"Error general: {e}")
