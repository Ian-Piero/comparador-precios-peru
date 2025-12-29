import streamlit as st
import asyncio
from playwright.async_api import async_playwright
import json
from groq import Groq
import os

# --- CONFIGURACIÓN ---
# En EC2, pasaremos la API_KEY como variable de entorno en el comando Docker
API_KEY = os.getenv("GROQ_API_KEY")

st.set_page_config(page_title="Comparador Tech Perú", page_icon="⚙️", layout="wide")
st.title("⚙️ Comparador de productos")
st.markdown("Corriendo en AWS EC2 con Docker")

async def extraer_datos_asincrono(producto):
    resultados = []
    async with async_playwright() as p:
        # Argumentos necesarios para contenedores Linux
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        q_plus = producto.replace(' ', '+')
        q_dash = producto.replace(' ', '-')

        tiendas = [
            {"nombre": "Mercado Libre", "url": f"https://listado.mercadolibre.com.pe/{q_dash}", "selector": ".ui-search-result__wrapper"},
            {"nombre": "Coolbox", "url": f"https://www.coolbox.pe/{q_plus}?_q={q_plus}&map=ft", "selector": ".vtex-search-result-3-x-galleryItem"},
            {"nombre": "Hiraoka", "url": f"https://hiraoka.com.pe/catalogsearch/result/?q={q_plus}", "selector": ".product-item-info"}
        ]

        async def scrapear_una_tienda(tienda):
            page = await context.new_page()
            try:
                await page.goto(tienda["url"], wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(3000)
                items = await page.query_selector_all(tienda["selector"])
                for item in items[:5]:
                    texto = await item.inner_text()
                    link_elem = await item.query_selector('a')
                    link = await link_elem.get_attribute('href') if link_elem else ""
                    if link and link.startswith('/'):
                        if "coolbox" in tienda["url"]: link = "https://www.coolbox.pe" + link
                        elif "hiraoka" in tienda["url"]: link = "https://hiraoka.com.pe" + link
                    
                    if len(texto.strip()) > 30:
                        resultados.append(f"TIENDA: {tienda['nombre']} | DATOS: {texto.replace('\\n', ' ')[:400]} | LINK: {link}")
            except: pass
            finally: await page.close()

        await asyncio.gather(*(scrapear_una_tienda(t) for t in tiendas))
        await browser.close()
    return resultados

def comparar_con_ia(lista_productos, key):
    client = Groq(api_key=key)
    prompt = f"Genera un JSON con la llave 'productos' (tienda, nombre, precio, enlace). Datos: {chr(10).join(lista_productos)}"
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )
    return completion.choices[0].message.content

producto_buscado = st.text_input("¿Qué producto buscas?")

if st.button("🔍 Buscar"):
    if producto_buscado:
        if not API_KEY:
            st.error("Falta la API Key de Groq en las variables de entorno.")
        else:
            try:
                with st.spinner("Buscando ofertas..."):
                    bloques = asyncio.run(extraer_datos_asincrono(producto_buscado))
                
                if bloques:
                    with st.spinner("IA analizando precios..."):
                        respuesta_json = comparar_con_ia(bloques, API_KEY)
                        datos = json.loads(respuesta_json)
                        st.dataframe(datos.get("productos", []), hide_index=True, width="stretch")
                else:
                    st.error("No se encontraron resultados.")
            except Exception as e:
                st.error(f"Error técnico: {e}")
