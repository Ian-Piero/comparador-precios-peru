import streamlit as st
import asyncio
from playwright.async_api import async_playwright
import json
from groq import Groq
import os  # <--- Asegúrate de que este import esté aquí

# ==========================================
# AQUÍ VA EL PASO 3:
# ==========================================
if "browser_installed" not in st.session_state:
    os.system("playwright install chromium")
    st.session_state["browser_installed"] = True
# ==========================================
browser = await p.chromium.launch(
    headless=True,
    args=[
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',  # <--- Agregado
        '--disable-software-rasterizer' # <--- Agregado
    ]
)
# --- CONFIGURACIÓN ESTATICA ---
# Cargamos la API Key desde los Secrets de Streamlit
API_KEY = st.secrets["GROQ_API_KEY"]
st.set_page_config(page_title="Comparador Tech Perú", page_icon="⚙️", layout="wide")

st.title("⚙️ Comparador de productos")
st.markdown("Versión optimizada para ejecución en la nube (Streamlit Cloud).")

# --- MOTOR DE EXTRACCIÓN DIRECTO (SIN SUBPROCESS) ---
async def extraer_datos_asincrono(producto):
    resultados = []
    async with async_playwright() as p:
        # Lanzamos el navegador con argumentos necesarios para Linux/Nube
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        q_plus = producto.replace(' ', '+')
        q_dash = producto.replace(' ', '-')

        # Definimos las tiendas a buscar
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
            except Exception as e:
                pass
            finally:
                await page.close()

        # Ejecutamos las búsquedas en paralelo
        await asyncio.gather(*(scrapear_una_tienda(t) for t in tiendas))
        await browser.close()
    return resultados

# --- PROCESADOR IA ---
def comparar_con_ia(lista_productos, key):
    client = Groq(api_key=key)
    prompt = f"""
    Eres un experto en compras. Genera un JSON con la llave "productos".
    Extrae: "tienda", "nombre", "precio", "enlace".
    Importante: Los precios son en soles (S/). Si no hay precio, ignora el item.
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
                # Ejecución del loop asíncrono dentro de Streamlit
                bloques = asyncio.run(extraer_datos_asincrono(producto_buscado))
            
            if bloques:
                with st.spinner("IA analizando precios..."):
                    respuesta_json = comparar_con_ia(bloques, API_KEY)
                    datos = json.loads(respuesta_json)
                    lista = datos.get("productos", [])
                    
                    st.subheader(f"📊 Resultados para: {producto_buscado}")
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
                st.error("No se encontraron resultados válidos.")
        except Exception as e:
            st.error(f"Hubo un problema técnico: {e}")


