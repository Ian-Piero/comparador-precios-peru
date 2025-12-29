import streamlit as st
import subprocess
import sys
import os
import json
from groq import Groq

# --- CONFIGURACIÓN ESTATICA ---
API_KEY = st.secrets["GROQ_API_KEY"]

st.set_page_config(page_title="Comparador Tech Perú", page_icon="⚙️", layout="wide")

st.title("⚙️ Comparador de productos")
st.markdown("Buscando en tiendas con carga de datos directa.")

# --- MOTOR DE BÚSQUEDA Y EXTRACCIÓN ---
def buscar_y_extraer(producto):
    script_temp = "buscador_tech.py"
    
    codigo_extractor = f"""
import asyncio
from playwright.async_api import async_playwright

async def extraer_tienda(context, url, tienda_nombre, selector_items):
    page = await context.new_page()
    resultados = []
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000) # Tiempo para carga de precios
        
        items = await page.query_selector_all(selector_items)
        for item in items[:7]:
            texto = await item.inner_text()
            link_elem = await item.query_selector('a')
            link = await link_elem.get_attribute('href') if link_elem else ""
            
            # Normalización de enlaces
            if link and link.startswith('/'):
                if "coolbox" in url: link = "https://www.coolbox.pe" + link
                elif "hiraoka" in url: link = "https://hiraoka.com.pe" + link
            
            if len(texto.strip()) > 30:
                resultados.append(f"TIENDA: {{tienda_nombre}} | DATOS: {{texto.replace('\\n', ' ')[:400]}} | LINK: {{link}}")
    except:
        pass
    finally:
        await page.close()
    return resultados

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
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
        resultado = subprocess.check_output([sys.executable, script_temp], text=True, encoding="utf-8", errors="replace")
        return resultado.split("---SEPARADOR---") if resultado.strip() else []
    finally:
        if os.path.exists(script_temp):
            os.remove(script_temp)

# --- PROCESADOR IA ---
def comparar_con_ia(lista_productos, key):
    client = Groq(api_key=key)
    prompt = f"""
    Eres un experto en compras. Genera un JSON con la llave "productos".
    Extrae: "tienda", "nombre", "precio", "enlace".
    
    IMPORTANTE: 
    1. No omitas Coolbox ni Hiraoka.
    2. Si el precio no es visible, intenta deducirlo del texto o ignora el item.
    3. Los precios son en soles.
    
    Datos:
    {chr(10).join(lista_productos)}
    """
    
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )
    return completion.choices[0].message.content

# --- INTERFAZ ---
producto_buscado = st.text_input("¿Qué producto buscas?", placeholder="Ej: Audífonos Sony, Laptop...")

if st.button("🔍 Buscar"):
    if producto_buscado:
        try:
            with st.spinner("Buscando en tiendas locales..."):
                bloques = buscar_y_extraer(producto_buscado)
            
            if bloques:
                with st.spinner("Organizando resultados..."):
                    respuesta_json = comparar_con_ia(bloques, API_KEY_DIRECTA)
                    datos = json.loads(respuesta_json)
                    lista = datos.get("productos", [])
                    
                    st.subheader(f"📊 Resultados")
                    st.dataframe(
                        lista,
                        column_config={
                            "enlace": st.column_config.LinkColumn("Link"),
                            "nombre": st.column_config.TextColumn("Producto", width="large")
                        },
                        hide_index=True,
                        width="stretch"
                    )
            else:
                st.error("No se encontraron resultados.")
        except Exception as e:
            st.error(f"Error: {e}")