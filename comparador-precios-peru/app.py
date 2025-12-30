import streamlit as st
import subprocess
import sys
import os
import json
from groq import Groq

# --- CONFIGURACIÓN ---
API_KEY_DIRECTA = "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"

st.set_page_config(page_title="Comparador Global Perú", page_icon="🌐", layout="wide")
st.title("🌐 Comparador Inteligente (Búsqueda Global)")
st.markdown("Buscando en la web y procesando con IA.")

def buscar_en_la_web(producto):
    script_temp = "buscador_global.py"
    
    # Este script busca en Google los resultados de las tiendas peruanas
    codigo_extractor = f"""
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")
        page = await context.new_page()
        
        # Construimos una busqueda que abarque tus tiendas favoritas en Peru
        query = 'site:mercadolibre.com.pe OR site:coolbox.pe OR site:hiraoka.com.pe "{producto}"'
        search_url = f"https://www.google.com/search?q={{query.replace(' ', '+')}}"
        
        await page.goto(search_url, wait_until='networkidle')
        
        # Extraemos los bloques de resultados de Google (título, link y descripción)
        resultados = []
        items = await page.query_selector_all('div.g')
        for item in items[:15]:
            texto = await item.inner_text()
            link_elem = await item.query_selector('a')
            link = await link_elem.get_attribute('href') if link_elem else ""
            if link:
                resultados.append(f"INFO: {{texto.replace('\\n', ' ')}} | LINK: {{link}}")
        
        if resultados:
            print("---SEPARADOR---".join(resultados))
        await browser.close()

asyncio.run(run())
"""
    with open(script_temp, "w", encoding="utf-8") as f:
        f.write(codigo_extractor)
    
    try:
        resultado = subprocess.check_output([sys.executable, script_temp], text=True, encoding="utf-8")
        return resultado.split("---SEPARADOR---") if resultado.strip() else []
    finally:
        if os.path.exists(script_temp): os.remove(script_temp)

def procesar_con_ia(datos_web, key):
    client = Groq(api_key=key)
    prompt = f"De estos resultados de Google, extrae un JSON con la llave 'productos'. Identifica: tienda, nombre del producto, precio en soles y enlace. Datos: {chr(10).join(datos_web)}"
    
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )
    return completion.choices[0].message.content

# --- INTERFAZ ---
producto = st.text_input("¿Qué producto quieres comparar?")

if st.button("🔍 Buscar en todo el internet"):
    if producto:
        with st.spinner("Rastreando la web..."):
            bloques = buscar_en_la_web(producto)
        
        if bloques:
            with st.spinner("IA analizando ofertas..."):
                res_json = procesar_con_ia(bloques, API_KEY_DIRECTA)
                datos = json.loads(res_json)
                st.dataframe(datos.get("productos", []), hide_index=True, width="stretch")
        else:
            st.error("No se encontraron resultados en el buscador.")
